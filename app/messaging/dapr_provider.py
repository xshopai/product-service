"""
Dapr Provider Implementation

For deployment to:
- Azure Container Apps (built-in Dapr)
- Azure Kubernetes Service (Dapr via Helm)
- Local development (Docker Compose with Dapr sidecar)
"""
import json
from typing import Dict, Any, Optional

from app.core.logger import logger
from .provider import MessagingProvider

try:
    from dapr.clients import DaprClient
    DAPR_AVAILABLE = True
except ImportError:
    DAPR_AVAILABLE = False


class DaprProvider(MessagingProvider):
    """
    Dapr-based messaging provider.
    Uses Dapr sidecar for pub/sub messaging.
    """
    
    def __init__(self, pubsub_name: str = "pubsub", 
                 dapr_http_port: Optional[int] = None):
        """
        Initialize Dapr provider.
        
        Args:
            pubsub_name: Name of Dapr pub/sub component (default: pubsub)
            dapr_http_port: Dapr sidecar HTTP port (optional, auto-detected if not set)
        """
        self.pubsub_name = pubsub_name
        self.dapr_http_port = dapr_http_port
        logger.info(
            f"Initialized DaprProvider",
            metadata={"pubsub_name": pubsub_name, "dapr_available": DAPR_AVAILABLE}
        )
    
    async def publish_event(self, topic: str, event_data: Dict[str, Any],
                           correlation_id: Optional[str] = None) -> bool:
        """
        Publish event via Dapr pub/sub.
        
        Args:
            topic: Event topic name (e.g., 'product.created')
            event_data: CloudEvents-compliant payload
            correlation_id: Correlation ID for distributed tracing
            
        Returns:
            bool: True if published successfully, False on error
        """
        if not DAPR_AVAILABLE:
            logger.warning(
                "Dapr SDK not available. Event publishing disabled.",
                metadata={"topic": topic}
            )
            return False
            
        try:
            # Create Dapr client with optional port override
            client_kwargs = {}
            if self.dapr_http_port:
                client_kwargs['http_port'] = self.dapr_http_port
            
            with DaprClient(**client_kwargs) as client:
                # Let Dapr handle CloudEvents wrapping/unwrapping natively
                # Do NOT use rawPayload - it causes deserialization issues with Azure Service Bus
                client.publish_event(
                    pubsub_name=self.pubsub_name,
                    topic_name=topic,
                    data=json.dumps(event_data),
                    data_content_type="application/json"
                )
            
            logger.info(
                f"Published event via Dapr: {topic}",
                metadata={
                    "provider": "dapr",
                    "topic": topic,
                    "correlationId": correlation_id
                }
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to publish event via Dapr: {topic}",
                metadata={
                    "provider": "dapr",
                    "topic": topic,
                    "error": str(e)
                }
            )
            return False
    
    def close(self):
        """Dapr client is context-managed, no cleanup needed."""
        pass
