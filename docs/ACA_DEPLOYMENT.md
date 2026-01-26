# Azure Container Apps Deployment Guide

This guide provides step-by-step instructions for deploying the Product Service to **Azure Container Apps** with built-in Dapr support.

---

## Prerequisites

- **Azure CLI** installed - [Install Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
- **Azure Subscription** with appropriate permissions
- **Docker** installed for building container images
- **Azure Container Registry** (or Docker Hub account)

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
# Set variables (shared across all xshopai services)
RESOURCE_GROUP="rg-xshopai-aca"
LOCATION="swedencentral"

# Create resource group (idempotent - safe to run if already exists)
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION
```

### Step 3: Create Azure Container Registry

```bash
# Set ACR name (ACA-specific, must be globally unique)
ACR_NAME="acrxshopaiaca"

# Create container registry (skip if already created by another service)
# This command is NOT idempotent - it will fail if ACR already exists
# You can safely ignore "already exists" errors
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled true

# Get ACR login server
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer --output tsv)
echo "ACR Login Server: $ACR_LOGIN_SERVER"
```

### Step 4: Build and Push Container Image

```bash
# Login to ACR
az acr login --name $ACR_NAME

# Build Docker image
docker build -t product-service:latest .

# Tag image for ACR
docker tag product-service:latest $ACR_LOGIN_SERVER/product-service:latest

# Push to ACR
docker push $ACR_LOGIN_SERVER/product-service:latest

# Verify image was pushed
az acr repository list --name $ACR_NAME --output table
```

### Step 5: Register Resource Providers

```bash
# Register required resource providers (one-time per subscription)
az provider register --namespace microsoft.operationalinsights --wait
az provider register --namespace microsoft.insights --wait
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.ServiceBus --wait

# Verify registration status
az provider show --namespace microsoft.operationalinsights --query "registrationState" --output tsv
az provider show --namespace microsoft.insights --query "registrationState" --output tsv
```

> **Note**: Provider registration can take 1-2 minutes. The `--wait` flag ensures the command waits for registration to complete.

### Step 6: Create Application Insights

```bash
# Create Application Insights (ACA-specific)
AI_NAME="ai-xshopai-aca"

az monitor app-insights component create \
  --app $AI_NAME \
  --location $LOCATION \
  --resource-group $RESOURCE_GROUP

# Get instrumentation key (needed for Container Apps Environment)
AI_KEY=$(az monitor app-insights component show \
  --app $AI_NAME \
  --resource-group $RESOURCE_GROUP \
  --query instrumentationKey \
  --output tsv)

echo "App Insights Key: $AI_KEY"
```

### Step 7: Create Log Analytics Workspace

```bash
# Set Log Analytics workspace name (shared across all xshopai services)
LOG_ANALYTICS_WORKSPACE="law-xshopai-aca"

# Create Log Analytics workspace (skip if already exists)
az monitor log-analytics workspace create \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $LOG_ANALYTICS_WORKSPACE \
  --location $LOCATION

# Get workspace ID and key (needed for Container Apps Environment)
LOG_ANALYTICS_WORKSPACE_ID=$(az monitor log-analytics workspace show \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $LOG_ANALYTICS_WORKSPACE \
  --query customerId \
  --output tsv)

LOG_ANALYTICS_KEY=$(az monitor log-analytics workspace get-shared-keys \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $LOG_ANALYTICS_WORKSPACE \
  --query primarySharedKey \
  --output tsv)

echo "Log Analytics Workspace ID: $LOG_ANALYTICS_WORKSPACE_ID"
```

### Step 8: Create Container Apps Environment

```bash
# Set environment name (ACA-specific)
ENVIRONMENT_NAME="cae-xshopai-aca"

# Create Container Apps environment with Dapr enabled
# Skip if already created by another service - will fail with "already exists" error
az containerapp env create \
  --name $ENVIRONMENT_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --dapr-instrumentation-key $AI_KEY \
  --logs-workspace-id $LOG_ANALYTICS_WORKSPACE_ID \
  --logs-workspace-key $LOG_ANALYTICS_KEY \
  --enable-workload-profiles false
```

### Step 9: Create Azure Service Bus (for messaging)

```bash
# Set Service Bus namespace (ACA-specific)
SB_NAMESPACE="sb-xshopai-aca"

# Create Service Bus namespace (skip if already exists)
az servicebus namespace create \
  --name $SB_NAMESPACE \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard

# Create topic for product events
az servicebus topic create \
  --name product-events \
  --namespace-name $SB_NAMESPACE \
  --resource-group $RESOURCE_GROUP

# Get connection string
SB_CONNECTION=$(az servicebus namespace authorization-rule keys list \
  --namespace-name $SB_NAMESPACE \
  --resource-group $RESOURCE_GROUP \
  --name RootManageSharedAccessKey \
  --query primaryConnectionString \
  --output tsv)
```

### Step 10: Create Azure Cosmos DB (MongoDB API)

```bash
# Set Cosmos DB account name (ACA-specific)
COSMOS_ACCOUNT="cosmos-xshopai-aca"
DB_NAME="product_service_db"

# Create Cosmos DB account with MongoDB API
# Note: Local auth must be enabled for connection string authentication
az cosmosdb create \
  --resource-group $RESOURCE_GROUP \
  --name $COSMOS_ACCOUNT \
  --kind MongoDB \
  --server-version 4.2 \
  --default-consistency-level Session \
  --locations regionName=$LOCATION failoverPriority=0 isZoneRedundant=false

# Enable local (key-based) authentication for connection string access
# This is required for seeding and local development tools
az resource update \
  --resource-group $RESOURCE_GROUP \
  --name $COSMOS_ACCOUNT \
  --resource-type "Microsoft.DocumentDB/databaseAccounts" \
  --set properties.disableLocalAuth=false

# Configure Cosmos DB firewall:
# - Enable public network access
# - Add your current IP for local development/seeding
# - Add 0.0.0.0 to allow Azure services (Container Apps, etc.)
# Note: Cosmos DB updates can take 5-15 minutes to complete

# Get your current public IP
MY_IP=$(curl -s ifconfig.me)
echo "Your public IP: $MY_IP"

# Enable public access with your IP and Azure services
az cosmosdb update \
  --name $COSMOS_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --public-network-access ENABLED \
  --ip-range-filter "$MY_IP,0.0.0.0"

# Wait for the update to complete (check status)
echo "Waiting for Cosmos DB update to complete..."
while [ "$(az cosmosdb show --name $COSMOS_ACCOUNT --resource-group $RESOURCE_GROUP --query provisioningState -o tsv)" = "Updating" ]; do
  echo "Still updating..."
  sleep 30
done
echo "Cosmos DB update complete!"

# Create database
az cosmosdb mongodb database create \
  --resource-group $RESOURCE_GROUP \
  --account-name $COSMOS_ACCOUNT \
  --name $DB_NAME

# Get connection string and format with database name in path
# Cosmos DB raw connection: mongodb://user:pass@host:10255/?ssl=true&...
# We need: mongodb://user:pass@host:10255/DATABASE?ssl=true&...
COSMOS_CONNECTION_RAW=$(az cosmosdb keys list \
  --resource-group $RESOURCE_GROUP \
  --name $COSMOS_ACCOUNT \
  --type connection-strings \
  --query connectionStrings[0].connectionString \
  --output tsv)

# Insert database name before the query string (replace /? with /DATABASE?)
COSMOS_CONNECTION=$(echo "$COSMOS_CONNECTION_RAW" | sed "s|/\?|/${DB_NAME}?|")

echo "Cosmos DB connection string formatted with database: $DB_NAME"
echo "Connection (sanitized): $(echo "$COSMOS_CONNECTION" | sed 's|://[^:]*:[^@]*@|://***:***@|')"
```

> **Important**:
>
> - The `sed` command inserts the database name (`product_service_db`) into the URI path. The product-service extracts the database name from the URI automatically - no separate `MONGODB_DATABASE` variable needed.
> - **Firewall changes can take 5-15 minutes** to propagate. The script includes a wait loop.
> - `0.0.0.0` allows Azure services (like Container Apps) to access Cosmos DB.

### Step 11: Create Dapr Component for Azure Service Bus

The local `.dapr/components/pubsub.yaml` is configured for RabbitMQ. For Azure Container Apps, create an Azure Service Bus component in the same folder:

```bash
# Create Azure Service Bus component file in .dapr/components folder
cat > .dapr/components/dapr-servicebus-component.yaml << EOF
componentType: pubsub.azure.servicebus.topics
version: v1
metadata:
  - name: connectionString
    value: '$SB_CONNECTION'
  - name: consumerID
    value: product-service
scopes:
  - product-service
EOF

# Verify the file
cat .dapr/components/dapr-servicebus-component.yaml
```

> **Note**:
>
> - Local development uses RabbitMQ (`.dapr/components/pubsub.yaml`)
> - Azure Container Apps uses Azure Service Bus (`.dapr/components/dapr-servicebus-component.yaml`)
> - The `$SB_CONNECTION` variable was set in Step 9

### Step 12: Deploy Container App

```bash
# Set app name
APP_NAME="product-service"

# Get ACR credentials
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value --output tsv)

# Create container app
az containerapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $ENVIRONMENT_NAME \
  --image $ACR_LOGIN_SERVER/product-service:latest \
  --registry-server $ACR_LOGIN_SERVER \
  --registry-username $ACR_NAME \
  --registry-password $ACR_PASSWORD \
  --target-port 8001 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 5 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --enable-dapr \
  --dapr-app-id product-service \
  --dapr-app-port 8001 \
  --env-vars \
    "ENVIRONMENT=production" \
    "PORT=8001" \
    "MONGODB_URI=$COSMOS_CONNECTION" \
    "DAPR_PUBSUB_NAME=xshopai-pubsub" \
    "DAPR_HTTP_PORT=3500" \
    "LOG_LEVEL=INFO"
```

> **Note**: The `MONGODB_URI` must include the database name in the path (e.g., `mongodb://...host/product_service_db?params`). The product-service extracts the database name from the URI automatically.

### Step 13: Configure Dapr Component in Container Apps

```bash
# Create Dapr pub/sub component (using the file created in Step 11)
az containerapp env dapr-component set \
  --name $ENVIRONMENT_NAME \
  --resource-group $RESOURCE_GROUP \
  --dapr-component-name xshopai-pubsub \
  --yaml .dapr/components/dapr-servicebus-component.yaml
```

### Step 14: Verify Deployment

```bash
# Check app status
az containerapp show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query properties.runningStatus

# Get application URL
APP_URL=$(az containerapp show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn \
  --output tsv)

echo "Application URL: https://$APP_URL"

# Test health endpoint
curl https://$APP_URL/health
```

---

## Configure Secrets (Production)

### Using Azure Key Vault

```bash
# Create Key Vault (ACA-specific)
KV_NAME="kv-xshopai-aca"

az keyvault create \
  --name $KV_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Store secrets
az keyvault secret set --vault-name $KV_NAME --name "mongodb-uri" --value "$COSMOS_CONNECTION"
az keyvault secret set --vault-name $KV_NAME --name "jwt-public-key" --value "<jwt-public-key>"

# Grant Container App access to Key Vault
# Enable managed identity first
az containerapp identity assign \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --system-assigned

# Get principal ID
PRINCIPAL_ID=$(az containerapp identity show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId \
  --output tsv)

# Grant Key Vault access
az keyvault set-policy \
  --name $KV_NAME \
  --object-id $PRINCIPAL_ID \
  --secret-permissions get list
```

---

## Monitoring and Observability

### View Application Logs

```bash
# Stream logs
az containerapp logs show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --follow

# View Dapr sidecar logs
az containerapp logs show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --container daprd \
  --follow
```

### Application Insights Integration

Application Insights was created in Step 6. To add it to the container app's environment variables:

```bash
# Update container app with App Insights connection string
az containerapp update \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars "APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=$AI_KEY"
```

---

## Troubleshooting

### CosmosDB MongoDB API Limitations

**Issue:** Queries that use MongoDB aggregation pipelines with `$sort` on computed fields or non-indexed fields will fail with:

```
The index path corresponding to the specified order-by item is excluded
```

**Root Cause:** CosmosDB MongoDB API has limited support for aggregation pipeline operations. Unlike native MongoDB, CosmosDB requires explicit indexes for sorted fields and doesn't support sorting on computed fields in aggregation pipelines.

**Solution:** For endpoints that need sorting (e.g., `/api/products/trending`), avoid using aggregation pipelines with `$sort`. Instead:

1. Use simple `find()` queries with indexed field sorting
2. Perform complex sorting/computation in application code (Python/Node.js)

**Example - Before (fails in CosmosDB):**

```python
# DON'T: $addFields + $sort on computed field
pipeline = [
    {"$addFields": {"trendingScore": {"$add": ["$salesCount", "$viewCount"]}}},
    {"$sort": {"trendingScore": -1}}  # Fails!
]
```

**Example - After (works in CosmosDB):**

```python
# DO: Simple find() + sort in Python
products = list(collection.find({"status": "active"}).limit(100))
products.sort(key=lambda p: p.get("salesCount", 0) + p.get("viewCount", 0), reverse=True)
```

### Missing Python Dependencies

**Issue:** FastAPI returns 500 error with `No module named 'python_multipart'`

**Solution:** Ensure `requirements.txt` includes:

```
python-multipart>=0.0.6
```

Then rebuild and push the Docker image:

```bash
docker build -t $ACR_LOGIN_SERVER/product-service:latest .
docker push $ACR_LOGIN_SERVER/product-service:latest
az containerapp update --name $APP_NAME --resource-group $RESOURCE_GROUP --image $ACR_LOGIN_SERVER/product-service:latest
```

### Database Connection Errors

**Issue:** Application fails to connect to CosmosDB

**Check:**

1. Verify `MONGODB_URI` environment variable is set correctly
2. Ensure CosmosDB firewall allows Azure Container Apps (or has "Allow access from Azure services" enabled)
3. Check connection string format: `mongodb://<account>:<key>@<account>.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&...`

```bash
# View current environment variables
az containerapp show --name $APP_NAME --resource-group $RESOURCE_GROUP \
    --query "properties.template.containers[0].env"
```

---

## Cleanup Resources

```bash
# Delete container app (safe - only removes product-service)
az containerapp delete \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --yes

# Delete entire ACA deployment (all xshopai services in ACA)
# az group delete --name $RESOURCE_GROUP --yes
```
