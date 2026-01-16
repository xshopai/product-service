// Product Service Infrastructure
// Creates: MongoDB database in Cosmos DB + Key Vault secrets
// Dependencies: Platform infrastructure (cosmos-xshopai-{env}, kv-xshopai-{env})

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
          key: { keys: ['status', 'taxonomy.category', 'price'] }
        }
        {
          key: { keys: ['is_active', 'status', 'taxonomy.category'] }
        }
        {
          key: { keys: ['parentId'] }
        }
      ]
    }
  }
}

// Reference existing Key Vault (deployed by platform)
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
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

// JWT Secret for authentication
// Note: Pass via parameter during deployment: --parameters jwtSecret='your-secret-here'
@secure()
param jwtSecret string = ''

resource jwtSecretResource 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(jwtSecret)) {
  parent: keyVault
  name: 'product-service-jwt-secret'
  properties: {
    value: jwtSecret
  }
}

// Outputs
output cosmosAccountName string = cosmosAccount.name
output databaseName string = mongoDatabase.name
output keyVaultName string = keyVault.name
