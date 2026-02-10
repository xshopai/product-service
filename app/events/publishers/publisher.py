"""
Event Publisher for Product Service
Uses messaging abstraction layer for deployment flexibility.
"""

import json
import os
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.core.config import config
from app.core.logger import logger
from app.middleware.trace_context import get_trace_id
from app.messaging import create_messaging_provider, MessagingProvider


class EventPublisher:
    """
    Publisher for sending events via messaging abstraction layer.
    Handles product lifecycle events for event-driven architecture.
    
    Uses MESSAGING_PROVIDER env var to select provider:
    - 'dapr': Dapr pub/sub (default)
    - 'servicebus': Azure Service Bus direct
    - 'rabbitmq': RabbitMQ direct
    """
    
    def __init__(self):
        self.service_name = config.service_name
        self._provider: Optional[MessagingProvider] = None
        
    @property
    def provider(self) -> MessagingProvider:
        """Lazy initialization of messaging provider."""
        if self._provider is None:
            self._provider = create_messaging_provider()
        return self._provider
        
    async def publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Publish an event via messaging provider.
        
        Args:
            event_type: Type of event (e.g., 'product.created', 'product.updated')
            data: Event data payload
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            True if successful, False otherwise
        """
        # Get trace ID from context if not provided
        if not correlation_id:
            correlation_id = get_trace_id()
        
        # Construct CloudEvents-compliant payload
        event_payload = {
            "specversion": "1.0",
            "type": event_type,
            "source": self.service_name,
            "id": correlation_id or f"{event_type}-{datetime.now(timezone.utc).timestamp()}",
            "time": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "datacontenttype": "application/json",
            "data": data,
            "correlationId": correlation_id
        }
        
        # Publish via messaging provider (Dapr, Service Bus, or RabbitMQ)
        return await self.provider.publish_event(
            topic=event_type,
            event_data=event_payload,
            correlation_id=correlation_id
        )
    
    async def publish_product_created(
        self,
        product_id: str,
        product_data: Dict[str, Any],
        created_by: str,
        correlation_id: Optional[str] = None
    ) -> bool:
        """Publish product.created event"""
        data = {
            "productId": product_id,
            "product": product_data,
            "createdBy": created_by,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        return await self.publish_event("product.created", data, correlation_id)
    
    async def publish_product_updated(
        self,
        product_id: str,
        product_data: Dict[str, Any],
        updated_by: str,
        correlation_id: Optional[str] = None
    ) -> bool:
        """Publish product.updated event"""
        data = {
            "productId": product_id,
            "product": product_data,
            "updatedBy": updated_by,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        return await self.publish_event("product.updated", data, correlation_id)
    
    async def publish_product_deleted(
        self,
        product_id: str,
        deleted_by: str,
        correlation_id: Optional[str] = None,
        variants: Optional[List] = None
    ) -> bool:
        """Publish product.deleted event with optional variants (for variant removal)"""
        data = {
            "productId": product_id,
            "deletedBy": deleted_by,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        if variants is not None:
            data["variants"] = variants
        return await self.publish_event("product.deleted", data, correlation_id)

    async def publish_product_price_changed(
        self,
        product_id: str,
        old_price: float,
        new_price: float,
        updated_by: str,
        correlation_id: Optional[str] = None
    ) -> bool:
        """Publish product.price.changed event"""
        data = {
            "productId": product_id,
            "oldPrice": old_price,
            "newPrice": new_price,
            "updatedBy": updated_by,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        return await self.publish_event("product.price.changed", data, correlation_id)

    async def publish_badge_assigned(
        self,
        product_id: str,
        badge_type: str,
        badge_label: str,
        assigned_by: str,
        expires_at: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> bool:
        """Publish product.badge.assigned event"""
        data = {
            "productId": product_id,
            "badgeType": badge_type,
            "badgeLabel": badge_label,
            "assignedBy": assigned_by,
            "expiresAt": expires_at,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        return await self.publish_event("product.badge.assigned", data, correlation_id)

    async def publish_badge_removed(
        self,
        product_id: str,
        badge_type: str,
        removed_by: str,
        correlation_id: Optional[str] = None
    ) -> bool:
        """Publish product.badge.removed event"""
        data = {
            "productId": product_id,
            "badgeType": badge_type,
            "removedBy": removed_by,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        return await self.publish_event("product.badge.removed", data, correlation_id)


# Global publisher instance
event_publisher = EventPublisher()

# Backwards compatibility alias
DaprEventPublisher = EventPublisher
