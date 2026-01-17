// Product Service Container App
// Creates: Container App in existing Container Apps Environment
// Dependencies: Platform infrastructure (cae-xshopai-{env}, id-xshopai-{env}, kv-xshopai-{env})

@description('Environment name')
param environment string = 'dev'

@description('Location for resources')
param location string = resourceGroup().location

@description('Container image to deploy')
param containerImage string

@description('Container Apps Environment name')
param containerAppEnvName string = 'cae-xshopai-${environment}'

@description('Key Vault name')
param keyVaultName string = 'kv-xshopai-${environment}2'

@description('Managed Identity name')
param managedIdentityName string = 'id-xshopai-${environment}'

@description('Service name')
param serviceName string = 'product-service'

@description('Container port')
param containerPort int = 8001

@description('Minimum replicas (set to 1 for dev to avoid cold starts)')
param minReplicas int = environment == 'dev' ? 1 : 0

@description('Maximum replicas')
param maxReplicas int = 3

// Reference existing Container Apps Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: containerAppEnvName
}

// Reference existing Managed Identity
resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: managedIdentityName
}

// Reference existing Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// Container App for product-service
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
          image: containerImage
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
                path: '/health/ready'
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
}

// Outputs
output containerAppName string = containerApp.name
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output containerAppId string = containerApp.id
