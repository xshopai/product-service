# Azure Kubernetes Service (AKS) Deployment Guide

This guide provides step-by-step instructions for deploying the Product Service to **Azure Kubernetes Service (AKS)** with Dapr integration.

---

## Prerequisites

- **Azure CLI** installed - [Install Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
- **kubectl** installed - [Install kubectl](https://kubernetes.io/docs/tasks/tools/)
- **Helm** installed - [Install Helm](https://helm.sh/docs/intro/install/)
- **Azure Subscription** with appropriate permissions
- **Docker** installed for building container images

---

## Step-by-Step Deployment

### Step 1: Login to Azure

```bash
# Login to Azure
az login

# Set subscription (if you have multiple)
az account set --subscription "<subscription-id>"

# Verify current subscription
az account show
```

### Step 2: Create Resource Group

```bash
# Set variables (AKS-specific to avoid conflicts with ACA resources)
RESOURCE_GROUP="rg-xshopai-aks"
LOCATION="swedencentral"

# Create resource group
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION
```

### Step 3: Create Azure Container Registry

```bash
# Set ACR name (AKS-specific, must be globally unique)
ACR_NAME="acrxshopaiaks"

# Create container registry (skip if already created by another service)
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled true

# Get ACR login server
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer --output tsv)
echo "ACR Login Server: $ACR_LOGIN_SERVER"
```

### Step 4: Create AKS Cluster

```bash
# Set cluster name
AKS_CLUSTER="aks-xshopai"

# Create AKS cluster (skip if already created by another service)
az aks create \
  --resource-group $RESOURCE_GROUP \
  --name $AKS_CLUSTER \
  --node-count 2 \
  --node-vm-size Standard_B2s \
  --enable-managed-identity \
  --attach-acr $ACR_NAME \
  --generate-ssh-keys

# Get credentials for kubectl
az aks get-credentials \
  --resource-group $RESOURCE_GROUP \
  --name $AKS_CLUSTER \
  --overwrite-existing

# Verify connection
kubectl get nodes
```

### Step 5: Install Dapr on AKS

```bash
# Add Dapr Helm repository
helm repo add dapr https://dapr.github.io/helm-charts
helm repo update

# Create dapr-system namespace
kubectl create namespace dapr-system --dry-run=client -o yaml | kubectl apply -f -

# Install Dapr with high availability
helm upgrade --install dapr dapr/dapr \
  --namespace dapr-system \
  --set global.ha.enabled=true \
  --wait

# Verify Dapr installation
kubectl get pods -n dapr-system
dapr status -k
```

### Step 6: Build and Push Docker Image

```bash
# Login to ACR
az acr login --name $ACR_NAME

# Build Docker image
docker build -t product-service:latest .

# Tag image for ACR
docker tag product-service:latest $ACR_LOGIN_SERVER/product-service:latest

# Push to ACR
docker push $ACR_LOGIN_SERVER/product-service:latest

# Verify image
az acr repository list --name $ACR_NAME --output table
```

### Step 7: Create Kubernetes Namespace

```bash
# Create namespace for xshopai services
kubectl create namespace xshopai --dry-run=client -o yaml | kubectl apply -f -

# Set as default namespace for current context
kubectl config set-context --current --namespace=xshopai
```

### Step 8: Create Kubernetes Secrets

```bash
# MongoDB connection string (replace with your actual connection string)
# For production, use Azure Cosmos DB MongoDB API
MONGODB_URI="mongodb://localhost:27019/product_service_db"

# Create secrets
kubectl create secret generic product-service-secrets \
  --namespace xshopai \
  --from-literal=mongodb-uri="$MONGODB_URI" \
  --from-literal=jwt-public-key="<your-jwt-public-key>" \
  --dry-run=client -o yaml | kubectl apply -f -

# Verify secrets
kubectl get secrets -n xshopai
```

### Step 9: Create Dapr Components

Create `k8s/dapr-components.yaml`:

```yaml
# k8s/dapr-components.yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: xshopai-pubsub
  namespace: xshopai
spec:
  type: pubsub.azure.servicebus.topics
  version: v1
  metadata:
    - name: connectionString
      secretKeyRef:
        name: servicebus-secret
        key: connectionString
    - name: consumerID
      value: 'product-service'
auth:
  secretStore: kubernetes
---
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: product-statestore
  namespace: xshopai
spec:
  type: state.mongodb
  version: v1
  metadata:
    - name: host
      secretKeyRef:
        name: product-service-secrets
        key: mongodb-uri
    - name: databaseName
      value: 'product_service_db'
    - name: collectionName
      value: 'product_state'
auth:
  secretStore: kubernetes
```

```bash
# Apply Dapr components
kubectl apply -f k8s/dapr-components.yaml

# Verify components
kubectl get components -n xshopai
```

### Step 10: Create Kubernetes Deployment

Create `k8s/deployment.yaml`:

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: product-service
  namespace: xshopai
  labels:
    app: product-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: product-service
  template:
    metadata:
      labels:
        app: product-service
      annotations:
        dapr.io/enabled: 'true'
        dapr.io/app-id: 'product-service'
        dapr.io/app-port: '8001'
        dapr.io/enable-api-logging: 'true'
    spec:
      containers:
        - name: product-service
          image: acrxshopaiaks.azurecr.io/product-service:latest
          ports:
            - containerPort: 8001
          env:
            - name: ENVIRONMENT
              value: 'production'
            - name: PORT
              value: '8001'
            - name: DAPR_HTTP_PORT
              value: '3500'
            - name: DAPR_PUBSUB_NAME
              value: 'xshopai-pubsub'
            - name: LOG_LEVEL
              value: 'INFO'
            - name: MONGODB_URI
              valueFrom:
                secretKeyRef:
                  name: product-service-secrets
                  key: mongodb-uri
            - name: MONGODB_DATABASE
              value: 'product_service_db'
          resources:
            requests:
              memory: '256Mi'
              cpu: '250m'
            limits:
              memory: '512Mi'
              cpu: '500m'
          livenessProbe:
            httpGet:
              path: /health
              port: 8001
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8001
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: product-service
  namespace: xshopai
spec:
  selector:
    app: product-service
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8001
  type: ClusterIP
```

```bash
# Apply deployment
kubectl apply -f k8s/deployment.yaml

# Verify deployment
kubectl get deployments -n xshopai
kubectl get pods -n xshopai
kubectl get services -n xshopai
```

### Step 11: Verify Deployment

```bash
# Check pod status
kubectl get pods -n xshopai -l app=product-service

# Check pod logs
kubectl logs -n xshopai -l app=product-service -c product-service

# Check Dapr sidecar logs
kubectl logs -n xshopai -l app=product-service -c daprd

# Port forward for testing
kubectl port-forward -n xshopai svc/product-service 8001:80

# Test health endpoint (in another terminal)
curl http://localhost:8001/health
```

---

## Optional: Expose via Ingress

### Install NGINX Ingress Controller

```bash
# Add ingress-nginx repository
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# Install NGINX ingress controller
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.replicaCount=2
```

### Create Ingress Resource

Create `k8s/ingress.yaml`:

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: product-service-ingress
  namespace: xshopai
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - host: product-service.xshopai.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: product-service
                port:
                  number: 80
```

```bash
# Apply ingress
kubectl apply -f k8s/ingress.yaml

# Get ingress external IP
kubectl get ingress -n xshopai
```

---

## Scaling

### Horizontal Pod Autoscaler (HPA)

```bash
# Create HPA
kubectl autoscale deployment product-service \
  --namespace xshopai \
  --cpu-percent=70 \
  --min=2 \
  --max=10

# Check HPA status
kubectl get hpa -n xshopai
```

### Manual Scaling

```bash
# Scale deployment
kubectl scale deployment product-service \
  --namespace xshopai \
  --replicas=3

# Verify
kubectl get pods -n xshopai -l app=product-service
```

---

## Rolling Updates

```bash
# Update image
kubectl set image deployment/product-service \
  --namespace xshopai \
  product-service=$ACR_LOGIN_SERVER/product-service:v2

# Watch rollout status
kubectl rollout status deployment/product-service -n xshopai

# Rollback if needed
kubectl rollout undo deployment/product-service -n xshopai
```

---

## Cleanup Resources

```bash
# Delete product-service resources
kubectl delete -f k8s/deployment.yaml
kubectl delete -f k8s/dapr-components.yaml

# Delete namespace (removes all resources in it)
kubectl delete namespace xshopai

# Delete AKS cluster (removes entire cluster)
az aks delete \
  --resource-group $RESOURCE_GROUP \
  --name $AKS_CLUSTER \
  --yes

# Delete resource group (removes all AKS resources)
# az group delete --name $RESOURCE_GROUP --yes
```
