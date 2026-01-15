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
        self.secret_store_name = 'secret-store'
        
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
    
    Note: Secret names use hyphens (not underscores) for Azure Key Vault compatibility.
    Both local secrets.json and Azure Key Vault use the same naming convention.
    
    Returns:
        Dictionary with database connection parameters
    """
    username = secret_manager.get_secret('mongo-initdb-root-username')
    password = secret_manager.get_secret('mongo-initdb-root-password')
    
    # Filter out empty strings - treat them as None
    username = username if username and username.strip() else None
    password = password if password and password.strip() else None
    
    config = {
        'host': secret_manager.get_secret('mongodb-host') or 'localhost',
        'port': int(secret_manager.get_secret('mongodb-port') or '27019'),
        'username': username,
        'password': password,
        'database': secret_manager.get_secret('mongo-initdb-database') or 'productdb',
    }
    
    logger.info(
        f"Database config retrieved",
        metadata={
            "event": "db_config_retrieved",
            "host": config['host'],
            "port": config['port'],
            "database": config['database'],
            "has_credentials": bool(username and password)
        }
    )
    
    return config


def get_jwt_config() -> Dict[str, Any]:
    """
    Get JWT configuration from secrets or environment variables.
    Only jwt-secret is truly secret - algorithm and expiration are just config.
    
    Note: Secret names use hyphens (not underscores) for Azure Key Vault compatibility.
    
    Returns:
        Dictionary with JWT configuration parameters
    """
    # Only the secret key is actually secret - get it securely
    jwt_secret = secret_manager.get_secret('jwt-secret')
    if not jwt_secret:
        # Fallback to environment variable (for local dev)
        jwt_secret = os.environ.get('JWT_SECRET', 'your_jwt_secret_key')
        logger.warning(
            "JWT_SECRET not found in secret store, using environment variable or default",
            metadata={
                "event": "jwt_secret_fallback",
                "source": "environment" if os.environ.get('JWT_SECRET') else "default"
            }
        )
    
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
