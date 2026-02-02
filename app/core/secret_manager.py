"""
Secret Manager Utility
Manages secrets retrieval using Dapr Secret Store building block

Naming Convention:
- Application code uses UPPER_SNAKE_CASE environment variables
- Local dev (.env, .dapr/secrets.json) uses UPPER_SNAKE_CASE
- Azure Key Vault uses lower-kebab-case (aca.sh translates at deployment time)

Product Service Required Secrets:
- COSMOS_ACCOUNT_CONNECTION : Cosmos DB (MongoDB API) connection string
- JWT_SECRET                : JWT signing secret
- APPINSIGHTS_CONNECTION    : Application Insights connection string
- SERVICE_PRODUCT_TOKEN     : Product service auth token
- SERVICE_ORDER_TOKEN       : Order service auth token
- SERVICE_CART_TOKEN        : Cart service auth token
- SERVICE_WEBBFF_TOKEN      : Web BFF auth token
"""

import os
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from app.core.logger import logger
from app.core.config import config


# Secrets required by product-service (UPPER_SNAKE_CASE everywhere)
REQUIRED_SECRETS = [
    'COSMOS_ACCOUNT_CONNECTION',
    'JWT_SECRET',
    'APPINSIGHTS_CONNECTION',
    'SERVICE_PRODUCT_TOKEN',
    'SERVICE_ORDER_TOKEN',
    'SERVICE_CART_TOKEN',
    'SERVICE_WEBBFF_TOKEN',
]


class SecretManager:
    """
    Unified secret manager - same key names everywhere.
    Tries Dapr first, falls back to env vars.
    """
    
    def __init__(self):
        self.secret_store_name = 'secretstore'
        self._dapr_client = None
        self._cache: Dict[str, str] = {}
        
        logger.info(
            f"Secret manager initialized",
            metadata={
                "event": "secret_manager_init",
                "environment": config.environment,
                "secret_store": self.secret_store_name
            }
        )
    
    @property
    def dapr_client(self):
        """Lazy load Dapr client"""
        if self._dapr_client is None:
            try:
                from dapr.clients import DaprClient
                self._dapr_client = DaprClient()
            except Exception as e:
                logger.debug(f"Dapr client not available: {e}")
                self._dapr_client = False
        return self._dapr_client if self._dapr_client else None
    
    def get_secret(self, key: str) -> Optional[str]:
        """
        Get secret by key name (UPPER_SNAKE_CASE).
        
        Args:
            key: Secret key (e.g., 'JWT_SECRET')
        
        Returns:
            Secret value or None if not found
        """
        # Check cache
        if key in self._cache:
            return self._cache[key]
        
        value = None
        
        # Try Dapr Secret Store first
        if self.dapr_client:
            try:
                response = self.dapr_client.get_secret(
                    store_name=self.secret_store_name,
                    key=key
                )
                if response and response.secret:
                    value = response.secret.get(key)
                    if value:
                        logger.debug(f"Secret '{key}' loaded from Dapr")
            except Exception as e:
                logger.debug(f"Dapr lookup failed for '{key}': {e}")
        
        # Fallback to environment variable (same key name)
        if not value:
            value = os.environ.get(key)
            if value:
                logger.debug(f"Secret '{key}' loaded from env")
        
        if value:
            self._cache[key] = value
            return value
        
        return None
    
    def get_database_config(self) -> Dict[str, Any]:
        """
        Get MongoDB database configuration.
        
        Returns:
            Dictionary with 'connection_string' and 'database' keys
        """
        # Try MONGODB_URI first (set by aca.sh)
        uri = os.environ.get('MONGODB_URI')
        
        # Fall back to COSMOS_ACCOUNT_CONNECTION via Dapr
        if not uri:
            uri = self.get_secret('COSMOS_ACCOUNT_CONNECTION')
        
        if not uri:
            raise RuntimeError(
                "MongoDB connection string not found. "
                "Set MONGODB_URI env var or COSMOS_ACCOUNT_CONNECTION in Dapr secret store."
            )
        
        # Extract database name from URI or env var
        parsed = urlparse(uri)
        database = parsed.path.lstrip('/') if parsed.path and parsed.path != '/' else None
        
        if not database:
            database = os.environ.get('MONGODB_DB_NAME', 'product_service_db')
        
        return {
            'connection_string': uri,
            'database': database,
        }
    
    def get_jwt_config(self) -> Dict[str, Any]:
        """Get JWT configuration."""
        jwt_secret = os.environ.get('JWT_SECRET') or self.get_secret('JWT_SECRET')
        
        if not jwt_secret:
            logger.warning("JWT secret not found, using default (NOT SECURE)")
            jwt_secret = 'your_jwt_secret_key'
        
        return {
            'secret': jwt_secret,
            'algorithm': os.environ.get('JWT_ALGORITHM', 'HS256'),
            'expiration': int(os.environ.get('JWT_EXPIRATION', '3600')),
            'issuer': os.environ.get('JWT_ISSUER', 'auth-service'),
            'audience': os.environ.get('JWT_AUDIENCE', 'xshopai-platform')
        }
    
    def get_service_tokens(self) -> Dict[str, str]:
        """Get service tokens for service-to-service auth."""
        token_keys = {
            'product-service': 'SERVICE_PRODUCT_TOKEN',
            'order-service': 'SERVICE_ORDER_TOKEN',
            'cart-service': 'SERVICE_CART_TOKEN',
            'web-bff': 'SERVICE_WEBBFF_TOKEN',
        }
        
        tokens = {}
        for service, key in token_keys.items():
            value = os.environ.get(key) or self.get_secret(key)
            if value:
                tokens[service] = value
            else:
                logger.warning(f"Token for '{service}' not configured (key: {key})")
        
        return tokens
    
    def get_appinsights_connection_string(self) -> Optional[str]:
        """Get Application Insights connection string."""
        # Check standard Azure SDK env var first
        conn_string = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
        if conn_string:
            return conn_string
        
        # Fall back to Dapr secretstore / env var
        return self.get_secret('APPINSIGHTS_CONNECTION')


# Singleton
_manager: Optional[SecretManager] = None

def get_secret_manager() -> SecretManager:
    global _manager
    if _manager is None:
        _manager = SecretManager()
    return _manager


# Convenience functions
def get_database_config() -> Dict[str, Any]:
    return get_secret_manager().get_database_config()

def get_jwt_config() -> Dict[str, Any]:
    return get_secret_manager().get_jwt_config()

def get_appinsights_connection_string() -> Optional[str]:
    return get_secret_manager().get_appinsights_connection_string()

def get_service_tokens() -> Dict[str, str]:
    return get_secret_manager().get_service_tokens()
