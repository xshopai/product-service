// Product Service Infrastructure
// Creates: Container App + MongoDB database in Cosmos DB + Key Vault secrets
// Dependencies: Platform infrastructure (cae-xshopai-{env}, cosmos-xshopai-{env}, kv-xshopai-{env}, id-xshopai-{env})

@description('Environment name')
param environment string = 'dev'

@description('Location for resources')
param location string = resourceGroup().location

@description('Cosmos DB account name')
param cosmosAccountName string = 'cosmos-xshopai-${environment}'

@description('Key Vault name')
param keyVaultName string = 'kv-xshopai-${environment}2'

@description('Database name')
param databaseName string = 'productdb'

@description('Container Apps Environment name')
param containerAppEnvName string = 'cae-xshopai-${environment}'

@description('Managed Identity name')
param managedIdentityName string = 'id-xshopai-${environment}'

@description('Service name')
param serviceName string = 'product-service'

@description('Container port')
param containerPort int = 8001

@description('Minimum replicas')
param minReplicas int = 1

@description('Maximum replicas')
param maxReplicas int = 3

@description('ACR name')
param acrName string = environment == 'prod' ? 'xshopaimodulesprod' : 'xshopaimodulesdev'

@description('Initial container image tag (will be updated by app deployment)')
param initialImageTag string = 'latest'

@description('Skip role assignments (default false - deployment script handles idempotency)')
param skipRoleAssignments bool = false

// Reference existing Cosmos DB account (deployed by platform)
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
}

// Create MongoDB database for product-service
resource mongoDatabase 'Microsoft.DocumentDB/databaseAccounts/mongodbDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// Create products collection with indexes
// Note: Cosmos DB MongoDB API doesn't support nested paths in compound indexes
// Keep indexes simple for serverless tier - complex indexes can be added via app code
resource productsCollection 'Microsoft.DocumentDB/databaseAccounts/mongodbDatabases/collections@2024-05-15' = {
  parent: mongoDatabase
  name: 'products'
  properties: {
    resource: {
      id: 'products'
      indexes: [
        {
          key: { keys: ['_id'] }
        }
        {
          key: { keys: ['sku'] }
          options: { unique: true }
        }
        {
          key: { keys: ['status'] }
        }
        {
          key: { keys: ['is_active'] }
        }
        {
          key: { keys: ['parentId'] }
        }
        {
          key: { keys: ['price'] }
        }
      ]
    }
  }
}

// Reference existing Key Vault (deployed by platform)
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// Reference existing Container Apps Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: containerAppEnvName
}

// Reference existing Managed Identity
resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: managedIdentityName
}

// Reference existing ACR
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

// Role definition IDs
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d' // AcrPull
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6' // Key Vault Secrets User

// ========================================
// ROLE ASSIGNMENTS - Idempotent using Azure CLI deployment script
// Azure ARM role assignments are NOT idempotent - they fail if already exist
// Solution: Use deployment script with Azure CLI to check existence before creating
// This ensures deployments are repeatable without manual intervention
// ========================================

// Deployment script to create role assignments idempotently
// Uses Azure CLI to check if role assignment exists before creating
resource roleAssignmentsScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = if (!skipRoleAssignments) {
  name: 'script-role-assignments-${serviceName}'
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    azCliVersion: '2.52.0'
    timeout: 'PT10M'
    retentionInterval: 'PT1H'
    cleanupPreference: 'OnSuccess'
    environmentVariables: [
      {
        name: 'PRINCIPAL_ID'
        value: managedIdentity.properties.principalId
      }
      {
        name: 'ACR_RESOURCE_ID'
        value: acr.id
      }
      {
        name: 'KEY_VAULT_RESOURCE_ID'
        value: keyVault.id
      }
      {
        name: 'ACR_PULL_ROLE_ID'
        value: acrPullRoleId
      }
      {
        name: 'KEY_VAULT_SECRETS_USER_ROLE_ID'
        value: keyVaultSecretsUserRoleId
      }
    ]
    scriptContent: '''
      #!/bin/bash
      set -e

      echo "=== Idempotent Role Assignment Script ==="
      
      # Function to assign role if not exists
      assign_role_if_not_exists() {
        local SCOPE=$1
        local ROLE_ID=$2
        local ROLE_NAME=$3
        
        echo "Checking if $ROLE_NAME role assignment exists..."
        
        # Check if assignment already exists
        EXISTING=$(az role assignment list --assignee "$PRINCIPAL_ID" --scope "$SCOPE" --role "$ROLE_ID" --query "[0].id" -o tsv 2>/dev/null || true)
        
        if [ -n "$EXISTING" ]; then
          echo "✓ $ROLE_NAME role assignment already exists, skipping."
        else
          echo "Creating $ROLE_NAME role assignment..."
          az role assignment create \
            --assignee-object-id "$PRINCIPAL_ID" \
            --assignee-principal-type ServicePrincipal \
            --scope "$SCOPE" \
            --role "$ROLE_ID"
          echo "✓ $ROLE_NAME role assignment created."
        fi
      }

      # Assign AcrPull role on ACR
      assign_role_if_not_exists "$ACR_RESOURCE_ID" "$ACR_PULL_ROLE_ID" "AcrPull"
      
      # Assign Key Vault Secrets User role on Key Vault
      assign_role_if_not_exists "$KEY_VAULT_RESOURCE_ID" "$KEY_VAULT_SECRETS_USER_ROLE_ID" "Key Vault Secrets User"
      
      echo "=== Role assignments complete ==="
    '''
  }
}

// Store MongoDB connection string in Key Vault
resource mongodbUriSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'product-service-mongodb-uri'
  properties: {
    value: cosmosAccount.listConnectionStrings().connectionStrings[0].connectionString
  }
}

// Store database name in Key Vault
resource mongodbDatabaseSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'product-service-mongodb-database'
  properties: {
    value: databaseName
  }
}

// Note: jwt-secret is created by Platform Infrastructure deployment (shared across all services)
// Product-service app will reference the existing jwt-secret from Key Vault

// Container App for product-service (infrastructure)
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${serviceName}-${environment}'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: containerPort
        transport: 'http'
        allowInsecure: false
      }
      dapr: {
        enabled: true
        appId: serviceName
        appPort: containerPort
        appProtocol: 'http'
      }
      registries: [
        {
          server: '${acrName}.azurecr.io'
          identity: managedIdentity.id
        }
      ]
      secrets: [
        {
          name: 'mongodb-uri'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/product-service-mongodb-uri'
          identity: managedIdentity.id
        }
        {
          name: 'mongodb-database'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/product-service-mongodb-database'
          identity: managedIdentity.id
        }
        {
          name: 'jwt-secret'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/jwt-secret'
          identity: managedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: serviceName
          image: '${acrName}.azurecr.io/${serviceName}:${initialImageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'ENVIRONMENT'
              value: environment
            }
            {
              name: 'SERVICE_PORT'
              value: string(containerPort)
            }
            {
              name: 'MONGODB_URI'
              secretRef: 'mongodb-uri'
            }
            {
              name: 'MONGODB_DATABASE'
              secretRef: 'mongodb-database'
            }
            {
              name: 'JWT_SECRET'
              secretRef: 'jwt-secret'
            }
            {
              name: 'LOG_LEVEL'
              value: environment == 'prod' ? 'info' : 'debug'
            }
            {
              name: 'DAPR_HTTP_PORT'
              value: '3500'
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: containerPort
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/readiness'
                port: containerPort
              }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '100'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [
    mongodbUriSecret
    mongodbDatabaseSecret
    // Note: Role assignments are conditionally deployed and may be skipped
    // Platform infrastructure should have already created these
  ]
}

// Outputs
output cosmosAccountName string = cosmosAccount.name
output databaseName string = mongoDatabase.name
output keyVaultName string = keyVault.name
output containerAppName string = containerApp.name
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
