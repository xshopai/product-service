"""
Azure Service Bus Provider Implementation

For deployment to:
- Azure App Service (no Dapr sidecar available)
"""
import json
from typing import Dict, Any, Optional

from app.core.logger import logger
from .provider import MessagingProvider


class ServiceBusProvider(MessagingProvider):
    """
    Azure Service Bus provider for App Service deployments.
    Uses Azure Service Bus SDK directly (no Dapr sidecar).
    
    Note: Requires azure-servicebus package to be installed.
    """
    
    def __init__(self, connection_string: str, topic_name: str):
        """
        Initialize Service Bus provider.
        
        Args:
            connection_string: Azure Service Bus connection string
            topic_name: Service Bus topic name
        """
        self.connection_string = connection_string
        self.topic_name = topic_name
        self.client = None
        
        logger.info(
            f"Initialized ServiceBusProvider",
            metadata={"topic": topic_name}
        )
        
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Service Bus client."""
        try:
            from azure.servicebus import ServiceBusClient
            self.client = ServiceBusClient.from_connection_string(
                self.connection_string
            )
            logger.info("Service Bus client initialized")
        except ImportError:
            logger.warning(
                "azure-servicebus package not installed. "
                "Install with: pip install azure-servicebus"
            )
        except Exception as e:
            logger.error(
                f"Failed to initialize Service Bus client: {e}",
                metadata={"error": str(e)}
            )
    
    async def publish_event(self, topic: str, event_data: Dict[str, Any],
                           correlation_id: Optional[str] = None) -> bool:
        """
        Publish event to Azure Service Bus.
        
        Args:
            topic: Event topic (used as message subject)
            event_data: CloudEvents payload
            correlation_id: Correlation ID for tracing
            
        Returns:
            bool: True if published successfully
        """
        try:
            if not self.client:
                logger.error("Service Bus client not initialized")
                return False
            
            from azure.servicebus import ServiceBusMessage
            
            message = ServiceBusMessage(
                body=json.dumps(event_data),
                content_type="application/json",
                subject=topic,
                correlation_id=correlation_id
            )
            
            with self.client.get_topic_sender(self.topic_name) as sender:
                sender.send_messages(message)
            
            logger.info(
                f"Published event via Service Bus: {topic}",
                metadata={
                    "provider": "servicebus",
                    "topic": topic,
                    "serviceBusTopic": self.topic_name,
                    "correlationId": correlation_id
                }
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to publish event via Service Bus: {topic}",
                metadata={
                    "provider": "servicebus",
                    "topic": topic,
                    "error": str(e)
                }
            )
            return False
    
    def close(self):
        """Close Service Bus client."""
        try:
            if self.client:
                self.client.close()
                logger.info("Service Bus client closed")
        except Exception as e:
            logger.error(f"Error closing Service Bus client: {e}")
