"""
Dapr Secret Management Service
Provides secret management using Dapr's secret store building block.
Falls back to environment variables if Dapr is not available.
"""

import os
from typing import Dict, Any, Optional

from dapr.clients import DaprClient
from app.core.logger import logger
from app.core.config import config


class SecretManager:
    """
    Secret manager that uses Dapr secret store building block.
    """
    
    def __init__(self):
        self.environment = config.environment
        self.secret_store_name = 'secretstore'
        
        logger.info(
            f"Secret manager initialized",
            metadata={
                "event": "secret_manager_init",
                "environment": self.environment,
                "secret_store": self.secret_store_name
            }
        )
    
    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Get a secret value from Dapr secret store.
        
        Args:
            secret_name: Name of the secret to retrieve
            
        Returns:
            Secret value as string, or None if not found
        """
        try:
            with DaprClient() as client:
                response = client.get_secret(
                    store_name=self.secret_store_name,
                    key=secret_name
                )
                
                # Dapr returns a dictionary with the secret key
                if response.secret and secret_name in response.secret:
                    value = response.secret[secret_name]
                    logger.debug(
                        f"Retrieved secret from Dapr",
                        metadata={
                            "event": "secret_retrieved",
                            "secret_name": secret_name,
                            "source": "dapr",
                            "store": self.secret_store_name
                        }
                    )
                    return str(value)
                
                logger.warning(
                    f"Secret not found in Dapr store",
                    metadata={
                        "event": "secret_not_found",
                        "secret_name": secret_name,
                        "store": self.secret_store_name
                    }
                )
                return None
                
        except Exception as e:
            logger.error(
                f"Failed to get secret from Dapr: {str(e)}",
                metadata={
                    "event": "secret_retrieval_error",
                    "secret_name": secret_name,
                    "error": str(e),
                    "store": self.secret_store_name
                }
            )
            raise


# Global instance
secret_manager = SecretManager()


def get_database_config() -> Dict[str, Any]:
    """
    Get database configuration from secrets or environment variables.
    
    Priority order:
    1. MONGODB_URI environment variable (Azure Container Apps)
    2. mongodb-uri secret from Dapr secret store (local development)
    
    Database name is extracted from the URI path (e.g., mongodb://host/dbname?params)
    
    Returns:
        Dictionary with 'connection_string' and 'database' keys
    """
    from urllib.parse import urlparse
    
    # Try environment variable first (Azure Container Apps)
    mongodb_uri = os.environ.get('MONGODB_URI')
    
    # Fall back to Dapr secret store (local development)
    if not mongodb_uri:
        mongodb_uri = secret_manager.get_secret('MONGODB_URI')
    
    if not mongodb_uri:
        raise ValueError(
            "MongoDB connection string not found. "
            "Set MONGODB_URI env var or MONGODB_URI in Dapr secret store."
        )
    
    # Extract database name from URI path or environment variable
    # URI format: mongodb://user:pass@host:port/database?params
    # or: mongodb+srv://user:pass@host/database?params
    parsed = urlparse(mongodb_uri)
    database = parsed.path.lstrip('/') if parsed.path and parsed.path != '/' else None
    
    # Check for MONGODB_DB_NAME environment variable (used by Azure Container Apps)
    if not database:
        database = os.environ.get('MONGODB_DB_NAME')
    
    if not database:
        database = 'product_service_db'  # Default fallback
        logger.warning(
            f"No database name in URI or MONGODB_DB_NAME env var, using default: {database}",
            metadata={"event": "db_name_fallback", "database": database}
        )
    
    # Determine source for logging
    source = 'env' if os.environ.get('MONGODB_URI') else 'dapr'
    
    logger.info(
        f"Database config retrieved",
        metadata={
            "event": "db_config_retrieved",
            "source": source,
            "database": database,
            "has_connection_string": True
        }
    )
    
    return {
        'connection_string': mongodb_uri,
        'database': database,
    }


def get_jwt_config() -> Dict[str, Any]:
    """
    Get JWT configuration from secrets or environment variables.
    
    Priority order for JWT secret:
    1. JWT_SECRET environment variable (Azure Container Apps)
    2. jwt-secret from Dapr secret store (local development)
    
    Note: jwt-secret is a shared secret across all services, created by Platform
    Infrastructure deployment. Secret names use hyphens (not underscores) for
    Azure Key Vault compatibility.
    
    Returns:
        Dictionary with JWT configuration parameters
    """
    # Try environment variable first (Azure Container Apps)
    jwt_secret = os.environ.get('JWT_SECRET')
    
    # Fall back to Dapr secret store (local development)
    if not jwt_secret:
        jwt_secret = secret_manager.get_secret('JWT_SECRET')
    
    if not jwt_secret:
        logger.warning(
            "JWT secret not found, using default (NOT SECURE FOR PRODUCTION)",
            metadata={
                "event": "jwt_secret_fallback",
                "source": "default"
            }
        )
        jwt_secret = 'your_jwt_secret_key'
    
    # Algorithm and expiration are just configuration, not secrets
    # Get from environment variables directly - no need for secret store
    jwt_algorithm = os.environ.get('JWT_ALGORITHM', 'HS256')
    jwt_expiration = int(os.environ.get('JWT_EXPIRATION', '3600'))
    jwt_issuer = os.environ.get('JWT_ISSUER', 'auth-service')
    jwt_audience = os.environ.get('JWT_AUDIENCE', 'xshopai-platform')
    
    return {
        'secret': jwt_secret,
        'algorithm': jwt_algorithm,
        'expiration': jwt_expiration,
        'issuer': jwt_issuer,
        'audience': jwt_audience
    }
