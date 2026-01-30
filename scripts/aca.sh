#!/bin/bash

# ============================================================================
# Azure Container Apps Deployment Script for Product Service
# ============================================================================
# This script deploys the Product Service to Azure Container Apps.
# 
# PREREQUISITE: Run the infrastructure deployment script first:
#   cd infrastructure/azure/aca/scripts
#   ./deploy-infra.sh
#
# The infrastructure script creates all shared resources:
#   - Resource Group, ACR, Container Apps Environment
#   - Service Bus, Redis, Cosmos DB, MySQL, Key Vault
#   - Dapr components (pubsub, statestore, secretstore)
# ============================================================================

set -e

# -----------------------------------------------------------------------------
# Colors for output
# -----------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo -e "\n${BLUE}==============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}==============================================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

# ============================================================================
# Prerequisites Check
# ============================================================================
print_header "Checking Prerequisites"

# Check Azure CLI
if ! command -v az &> /dev/null; then
    print_error "Azure CLI is not installed. Please install it from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi
print_success "Azure CLI is installed"

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi
print_success "Docker is installed"

# Check if logged into Azure
if ! az account show &> /dev/null; then
    print_warning "Not logged into Azure. Initiating login..."
    az login
fi
print_success "Logged into Azure"

# ============================================================================
# Configuration
# ============================================================================
print_header "Configuration"

# Service-specific configuration
SERVICE_NAME="product-service"
APP_PORT=8001
PROJECT_NAME="xshopai"

# Dapr configuration for Azure Container Apps
# In ACA, Dapr sidecar ALWAYS runs on port 3500 (HTTP) and 50001 (gRPC)
# (different from local dev where each service has unique ports per PORT_CONFIGURATION.md)
DAPR_HTTP_PORT=3500
DAPR_GRPC_PORT=50001
DAPR_PUBSUB_NAME="pubsub"

# Get script directory and service directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(dirname "$SCRIPT_DIR")"

# ============================================================================
# Environment Selection
# ============================================================================
echo -e "${CYAN}Available Environments:${NC}"
echo "   dev     - Development environment"
echo "   prod    - Production environment"
echo ""

read -p "Enter environment (dev/prod) [dev]: " ENVIRONMENT
ENVIRONMENT="${ENVIRONMENT:-dev}"

if [[ ! "$ENVIRONMENT" =~ ^(dev|prod)$ ]]; then
    print_error "Invalid environment: $ENVIRONMENT"
    echo "   Valid values: dev, prod"
    exit 1
fi
print_success "Environment: $ENVIRONMENT"

# ============================================================================
# Suffix Configuration
# ============================================================================
print_header "Infrastructure Configuration"

echo -e "${CYAN}The suffix was set during infrastructure deployment.${NC}"
echo "You can find it by running:"
echo -e "   ${BLUE}az group list --query \"[?starts_with(name, 'rg-xshopai-$ENVIRONMENT')].{Name:name, Suffix:tags.suffix}\" -o table${NC}"
echo ""

read -p "Enter the infrastructure suffix: " SUFFIX

if [ -z "$SUFFIX" ]; then
    print_error "Suffix is required. Please run the infrastructure deployment first."
    exit 1
fi

# Validate suffix format
if [[ ! "$SUFFIX" =~ ^[a-z0-9]{3,6}$ ]]; then
    print_error "Invalid suffix format: $SUFFIX"
    echo "   Suffix must be 3-6 lowercase alphanumeric characters."
    exit 1
fi
print_success "Using suffix: $SUFFIX"

# ============================================================================
# Derive Resource Names from Infrastructure
# ============================================================================
# These names must match what was created by deploy-infra.sh
RESOURCE_GROUP="rg-${PROJECT_NAME}-${ENVIRONMENT}-${SUFFIX}"
ACR_NAME="${PROJECT_NAME}${ENVIRONMENT}${SUFFIX}"
CONTAINER_ENV="cae-${PROJECT_NAME}-${ENVIRONMENT}-${SUFFIX}"
COSMOS_ACCOUNT="cosmos-${PROJECT_NAME}-${ENVIRONMENT}-${SUFFIX}"
KEY_VAULT="kv-${PROJECT_NAME}-${ENVIRONMENT}-${SUFFIX}"
MANAGED_IDENTITY="id-${PROJECT_NAME}-${ENVIRONMENT}-${SUFFIX}"

# Container App name follows convention: ca-{service}-{env}-{suffix}
CONTAINER_APP_NAME="ca-${SERVICE_NAME}-${ENVIRONMENT}-${SUFFIX}"

print_info "Derived resource names:"
echo "   Resource Group:      $RESOURCE_GROUP"
echo "   Container Registry:  $ACR_NAME"
echo "   Container Env:       $CONTAINER_ENV"
echo "   Container App:       $CONTAINER_APP_NAME"
echo "   Cosmos DB Account:   $COSMOS_ACCOUNT"
echo "   Key Vault:           $KEY_VAULT"
echo ""

# ============================================================================
# Verify Infrastructure Exists
# ============================================================================
print_header "Verifying Infrastructure"

# Check Resource Group
if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
    print_error "Resource group '$RESOURCE_GROUP' does not exist."
    echo ""
    echo "Please run the infrastructure deployment first:"
    echo -e "   ${BLUE}cd infrastructure/azure/aca/scripts${NC}"
    echo -e "   ${BLUE}./deploy-infra.sh${NC}"
    exit 1
fi
print_success "Resource Group exists: $RESOURCE_GROUP"

# Check ACR
if ! az acr show --name "$ACR_NAME" &> /dev/null; then
    print_error "Container Registry '$ACR_NAME' does not exist."
    exit 1
fi
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
print_success "Container Registry exists: $ACR_LOGIN_SERVER"

# Check Container Apps Environment
if ! az containerapp env show --name "$CONTAINER_ENV" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    print_error "Container Apps Environment '$CONTAINER_ENV' does not exist."
    exit 1
fi
print_success "Container Apps Environment exists: $CONTAINER_ENV"

# Check Cosmos DB Account
if ! az cosmosdb show --name "$COSMOS_ACCOUNT" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    print_error "Cosmos DB Account '$COSMOS_ACCOUNT' does not exist."
    exit 1
fi
print_success "Cosmos DB Account exists: $COSMOS_ACCOUNT"

# Get Managed Identity ID
# Note: MSYS_NO_PATHCONV=1 prevents Git Bash from converting /subscriptions/... paths on Windows
IDENTITY_ID=$(MSYS_NO_PATHCONV=1 az identity show --name "$MANAGED_IDENTITY" --resource-group "$RESOURCE_GROUP" --query id -o tsv 2>/dev/null || echo "")
if [ -z "$IDENTITY_ID" ]; then
    print_warning "Managed Identity not found, will deploy without it"
else
    print_success "Managed Identity exists: $MANAGED_IDENTITY"
fi

# ============================================================================
# Database Configuration
# ============================================================================
print_header "Database Configuration"

DB_NAME="product_service_db"
print_info "Database name: $DB_NAME"

# Check if MongoDB database exists, create if not
print_info "Checking if database exists..."
if az cosmosdb mongodb database show --account-name "$COSMOS_ACCOUNT" --resource-group "$RESOURCE_GROUP" --name "$DB_NAME" &> /dev/null; then
    print_success "Database '$DB_NAME' already exists"
else
    print_info "Creating database '$DB_NAME'..."
    az cosmosdb mongodb database create \
        --account-name "$COSMOS_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --name "$DB_NAME" \
        --output none
    print_success "Database '$DB_NAME' created"
fi

# Get Cosmos DB connection string
print_info "Retrieving Cosmos DB connection string..."
COSMOS_CONNECTION_STRING=$(az cosmosdb keys list \
    --name "$COSMOS_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --type connection-strings \
    --query "connectionStrings[0].connectionString" \
    --output tsv)

if [ -z "$COSMOS_CONNECTION_STRING" ]; then
    print_error "Could not retrieve Cosmos DB connection string"
    exit 1
fi
print_success "Database connection configured"

# ============================================================================
# Confirmation
# ============================================================================
print_header "Deployment Configuration Summary"

echo -e "${CYAN}Environment:${NC}          $ENVIRONMENT"
echo -e "${CYAN}Suffix:${NC}               $SUFFIX"
echo -e "${CYAN}Resource Group:${NC}       $RESOURCE_GROUP"
echo -e "${CYAN}Container Registry:${NC}   $ACR_LOGIN_SERVER"
echo -e "${CYAN}Container Env:${NC}        $CONTAINER_ENV"
echo -e "${CYAN}Cosmos DB Account:${NC}    $COSMOS_ACCOUNT"
echo -e "${CYAN}Database:${NC}             $DB_NAME"
echo -e "${CYAN}Service:${NC}              $SERVICE_NAME"
echo -e "${CYAN}Port:${NC}                 $APP_PORT"
echo ""

read -p "Do you want to proceed with deployment? (Y/n): " CONFIRM
CONFIRM=${CONFIRM:-Y}
if [[ "$CONFIRM" =~ ^[Nn]$ ]]; then
    print_warning "Deployment cancelled by user"
    exit 0
fi

# ============================================================================
# Step 1: Build and Push Container Image
# ============================================================================
print_header "Step 1: Building and Pushing Container Image"

# Login to ACR
print_info "Logging into ACR..."
az acr login --name "$ACR_NAME"
print_success "Logged into ACR"

# Navigate to service directory
cd "$SERVICE_DIR"

# Build Docker image (production target)
print_info "Building Docker image..."
docker build --target production -t "$SERVICE_NAME:latest" .
print_success "Docker image built"

# Tag and push
IMAGE_TAG="$ACR_LOGIN_SERVER/$SERVICE_NAME:latest"
docker tag "$SERVICE_NAME:latest" "$IMAGE_TAG"
print_info "Pushing image to ACR..."
docker push "$IMAGE_TAG"
print_success "Image pushed: $IMAGE_TAG"

# ============================================================================
# Step 2: Deploy Container App
# ============================================================================
print_header "Step 2: Deploying Container App"

# Get ACR credentials
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

# Build environment variables for FastAPI/uvicorn
ENV_VARS=("ENVIRONMENT=production")
ENV_VARS+=("PORT=$APP_PORT")
ENV_VARS+=("MONGODB_URI=$COSMOS_CONNECTION_STRING")
ENV_VARS+=("MONGODB_DB_NAME=$DB_NAME")
ENV_VARS+=("DAPR_HTTP_PORT=$DAPR_HTTP_PORT")
ENV_VARS+=("DAPR_GRPC_PORT=$DAPR_GRPC_PORT")
ENV_VARS+=("DAPR_PUBSUB_NAME=$DAPR_PUBSUB_NAME")
ENV_VARS+=("LOG_LEVEL=info")

# Check if container app exists
if az containerapp show --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    print_info "Container app '$CONTAINER_APP_NAME' exists, updating..."
    az containerapp update \
        --name "$CONTAINER_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --image "$IMAGE_TAG" \
        --set-env-vars "${ENV_VARS[@]}" \
        --output none
    print_success "Container app updated"
else
    print_info "Creating container app '$CONTAINER_APP_NAME'..."
    
    # Build the create command
    # Note: MSYS_NO_PATHCONV=1 prevents Git Bash from converting /subscriptions/... paths on Windows
    MSYS_NO_PATHCONV=1 az containerapp create \
        --name "$CONTAINER_APP_NAME" \
        --container-name "$SERVICE_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --environment "$CONTAINER_ENV" \
        --image "$IMAGE_TAG" \
        --registry-server "$ACR_LOGIN_SERVER" \
        --registry-username "$ACR_NAME" \
        --registry-password "$ACR_PASSWORD" \
        --target-port $APP_PORT \
        --ingress external \
        --min-replicas 1 \
        --max-replicas 5 \
        --cpu 0.5 \
        --memory 1.0Gi \
        --enable-dapr \
        --dapr-app-id "$SERVICE_NAME" \
        --dapr-app-port $APP_PORT \
        --env-vars "${ENV_VARS[@]}" \
        ${IDENTITY_ID:+--user-assigned "$IDENTITY_ID"} \
        --output none
    
    print_success "Container app created"
fi

# ============================================================================
# Step 3: Verify Deployment
# ============================================================================
print_header "Step 3: Verifying Deployment"

APP_URL=$(az containerapp show \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn \
    -o tsv)

print_success "Deployment completed!"
echo ""
print_info "Application URL: https://$APP_URL"
print_info "Health Check:    https://$APP_URL/health"
echo ""

# Test health endpoint
print_info "Waiting for app to start (30s)..."
sleep 30

print_info "Testing health endpoint..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 "https://$APP_URL/health" 2>/dev/null || echo "000")

if [ "$HTTP_STATUS" = "200" ]; then
    print_success "Health check passed! (HTTP $HTTP_STATUS)"
else
    print_warning "Health check returned HTTP $HTTP_STATUS. The app may still be starting."
fi

# ============================================================================
# Summary
# ============================================================================
print_header "Deployment Summary"

echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}   ✅ $SERVICE_NAME DEPLOYED SUCCESSFULLY${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo ""
echo -e "${CYAN}Application:${NC}"
echo "   URL:              https://$APP_URL"
echo "   Health:           https://$APP_URL/health"
echo "   Readiness:        https://$APP_URL/readiness"
echo ""
echo -e "${CYAN}Infrastructure:${NC}"
echo "   Resource Group:   $RESOURCE_GROUP"
echo "   Environment:      $CONTAINER_ENV"
echo "   Registry:         $ACR_LOGIN_SERVER"
echo ""
echo -e "${CYAN}Database:${NC}"
echo "   Cosmos DB:        $COSMOS_ACCOUNT"
echo "   Database:         $DB_NAME"
echo ""
echo -e "${CYAN}API Endpoints:${NC}"
echo "   Products:         https://$APP_URL/api/products"
echo "   Search:           https://$APP_URL/api/products/search"
echo "   Admin:            https://$APP_URL/api/admin/products"
echo ""
echo -e "${CYAN}Useful Commands:${NC}"
echo -e "   View logs:        ${BLUE}az containerapp logs show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --follow${NC}"
echo -e "   View Dapr logs:   ${BLUE}az containerapp logs show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --container daprd --follow${NC}"
echo -e "   Delete app:       ${BLUE}az containerapp delete --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --yes${NC}"
echo ""
echo -e "${CYAN}Note:${NC} Product Service uses MongoDB (Cosmos DB) - no migrations needed."
echo ""
