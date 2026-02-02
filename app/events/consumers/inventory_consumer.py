"""
Dapr Event Consumer for Inventory Events
Handles inventory-related events from inventory service via Dapr pub/sub
"""

from typing import Dict, Any

from app.core.logger import logger
from app.repositories.product import ProductRepository


class InventoryEventConsumer:
    """
    Consumer for handling inventory-related events.
    Updates product availability and stock status based on inventory changes.
    """
    
    def __init__(self):
        self.db = None
        self.product_repo = None
    
    async def initialize(self):
        """Initialize database connection and repository"""
        if self.db is None:
            # Lazy import to avoid circular dependency
            from app.db.mongodb import get_database
            self.db = await get_database()
            self.product_repo = ProductRepository(self.db)
    
    async def handle_inventory_updated(self, event_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Handle inventory.updated event.
        Updates product stock status when inventory changes.
        
        Args:
            event_data: CloudEvents formatted event data (may be double-wrapped by Dapr)
            
        Returns:
            Response dict with status
        """
        try:
            await self.initialize()
            
            # Dapr delivers CloudEvents envelope. The publisher may also wrap in CloudEvents.
            # Structure: Dapr envelope -> Publisher CloudEvents envelope -> Actual data
            # Need to unwrap potentially nested CloudEvents structure
            
            inner_data = event_data.get("data", {})
            
            # Check if inner_data is another CloudEvents envelope (has specversion)
            if isinstance(inner_data, dict) and "specversion" in inner_data:
                # Double-wrapped: Dapr envelope contains publisher's CloudEvents envelope
                correlation_id = inner_data.get("correlationId", inner_data.get("correlationid", "no-correlation"))
                payload = inner_data.get("data", {})
            else:
                # Single-wrapped: Dapr envelope contains raw payload
                correlation_id = event_data.get("correlationId", event_data.get("correlationid", "no-correlation"))
                payload = inner_data
            
            # Extract actual inventory data
            sku = payload.get("sku")
            stock_level = payload.get("quantity")
            
            if not sku or stock_level is None:
                logger.warning(
                    "Invalid inventory.updated event - missing required fields",
                    metadata={
                        "correlationId": correlation_id,
                        "payloadKeys": list(payload.keys()) if isinstance(payload, dict) else "not-a-dict"
                    }
                )
                return {"status": "error", "message": "Missing required fields"}
            
            logger.info(
                f"Processing inventory.updated event for SKU {sku}",
                metadata={
                    "correlationId": correlation_id,
                    "sku": sku,
                    "stockLevel": stock_level
                }
            )
            
            # TODO: Add logic to update product stock status
            # Find product by variant SKU and update availabilityStatus
            
            return {"status": "success"}
            
        except Exception as e:
            logger.error(
                f"Error processing inventory.updated event: {str(e)}",
                metadata={
                    "correlationId": event_data.get("correlationId", "no-correlation"),
                    "error": str(e)
                }
            )
            return {"status": "error", "message": str(e)}
    
    async def handle_inventory_low_stock(self, event_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Handle inventory.low_stock event.
        Marks product when inventory is running low.
        
        Args:
            event_data: CloudEvents formatted event data
            
        Returns:
            Response dict with status
        """
        try:
            await self.initialize()
            
            correlation_id = event_data.get("correlationId", "no-correlation")
            data = event_data.get("data", {})
            
            sku = data.get("sku")
            
            logger.info(
                f"Processing inventory.low_stock event for SKU {sku}",
                metadata={
                    "correlationId": correlation_id,
                    "sku": sku
                }
            )
            
            # TODO: Add logic to handle low stock notification
            # Find product by variant SKU and set low_stock flag
            
            return {"status": "success"}
            
        except Exception as e:
            logger.error(
                f"Error processing inventory.low_stock event: {str(e)}",
                metadata={
                    "correlationId": event_data.get("correlationId", "no-correlation"),
                    "error": str(e)
                }
            )
            return {"status": "error", "message": str(e)}
    
    async def handle_inventory_out_of_stock(self, event_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Handle inventory.out.of.stock event.
        Marks product as out of stock when inventory is depleted.
        
        Args:
            event_data: CloudEvents formatted event data
            
        Returns:
            Response dict with status
        """
        try:
            await self.initialize()
            
            correlation_id = event_data.get("correlationId", "no-correlation")
            data = event_data.get("data", {})
            
            sku = data.get("sku")
            
            logger.info(
                f"Processing inventory.out.of.stock event for SKU {sku}",
                metadata={
                    "correlationId": correlation_id,
                    "sku": sku
                }
            )
            
            # TODO: Add logic to mark product as out of stock
            # Find product by variant SKU and set availabilityStatus
            
            return {"status": "success"}
            
        except Exception as e:
            logger.error(
                f"Error processing inventory.out.of.stock event: {str(e)}",
                metadata={
                    "correlationId": event_data.get("correlationId", "no-correlation"),
                    "error": str(e)
                }
            )
            return {"status": "error", "message": str(e)}


# Global consumer instance
inventory_event_consumer = InventoryEventConsumer()
