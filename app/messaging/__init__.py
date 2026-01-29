"""
Messaging Abstraction Layer for Product Service
Implements message broker abstraction for deployment flexibility.

Supports:
- Dapr pub/sub (Azure Container Apps, AKS, local with Dapr)
- Azure Service Bus (Azure App Service without Dapr)
- RabbitMQ (local development without Dapr)
"""
from .provider import MessagingProvider
from .factory import create_messaging_provider

__all__ = ['MessagingProvider', 'create_messaging_provider']
