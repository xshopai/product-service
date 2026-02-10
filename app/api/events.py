"""
Dapr Pub/Sub Subscription Endpoints
Handles incoming events from Dapr pub/sub
"""

from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any, List

from app.events.consumers.review_consumer import review_event_consumer
from app.events.consumers.inventory_consumer import inventory_event_consumer
from app.core.logger import logger

router = APIRouter(prefix="/events", tags=["events"])

# Programmatic subscription definitions for Azure Container Apps.
# ACA doesn't support declarative YAML subscriptions - only this endpoint.
# For local development, Dapr CLI uses .dapr/components/subscriptions.yaml instead.
# IMPORTANT: Keep both in sync when adding/removing subscriptions.
SUBSCRIPTIONS: List[Dict[str, str]] = [
    {"pubsubname": "pubsub", "topic": "inventory.stock.updated", "route": "/events/inventory.stock.updated"},
    {"pubsubname": "pubsub", "topic": "inventory.low.stock", "route": "/events/inventory.low.stock"},
    {"pubsubname": "pubsub", "topic": "inventory.out.of.stock", "route": "/events/inventory.out.of.stock"},
    {"pubsubname": "pubsub", "topic": "review.created", "route": "/events/review.created"},
    {"pubsubname": "pubsub", "topic": "review.updated", "route": "/events/review.updated"},
    {"pubsubname": "pubsub", "topic": "review.deleted", "route": "/events/review.deleted"},
]


@router.get("/dapr/subscribe")
async def get_subscriptions() -> List[Dict[str, str]]:
    """
    Dapr subscription endpoint (programmatic).
    Returns the list of pub/sub subscriptions for this service.
    Dapr sidecar calls this endpoint at startup to register subscriptions.
    
    Note: This is required for Azure Container Apps where declarative
    subscriptions (YAML) are not supported. For local development,
    the .dapr/components/subscriptions.yaml is used instead.
    """
    logger.info("Dapr requested subscription list", metadata={"count": len(SUBSCRIPTIONS)})
    return SUBSCRIPTIONS


@router.get("/config")
async def get_dapr_config():
    """
    Dapr configuration endpoint.
    Returns app-level configuration for Dapr runtime.
    """
    return {
        "entities": [],
        "actorIdleTimeout": "1h",
        "actorScanInterval": "30s",
        "drainOngoingCallTimeout": "1m",
        "drainRebalancedActors": True
    }


@router.post("/review.created")
async def handle_review_created(request: Request):
    """
    Handle review.created event from Dapr pub/sub.
    Called by Dapr when a review is created.
    """
    try:
        event_data = await request.json()
        
        logger.info(
            "Received review.created event",
            metadata={
                "correlationId": event_data.get("correlationId", "no-correlation"),
                "eventId": event_data.get("id"),
                "source": event_data.get("source")
            }
        )
        
        result = await review_event_consumer.handle_review_created(event_data)
        
        # Return success response for Dapr
        return {"status": "SUCCESS"}
        
    except Exception as e:
        logger.error(
            f"Error handling review.created event: {str(e)}",
            metadata={"error": str(e)}
        )
        # Still return success to avoid retries
        return {"status": "SUCCESS"}


@router.post("/review.updated")
async def handle_review_updated(request: Request):
    """
    Handle review.updated event from Dapr pub/sub.
    Called by Dapr when a review is updated.
    """
    try:
        event_data = await request.json()
        
        logger.info(
            "Received review.updated event",
            metadata={
                "correlationId": event_data.get("correlationId", "no-correlation"),
                "eventId": event_data.get("id")
            }
        )
        
        result = await review_event_consumer.handle_review_updated(event_data)
        
        return {"status": "SUCCESS"}
        
    except Exception as e:
        logger.error(
            f"Error handling review.updated event: {str(e)}",
            metadata={"error": str(e)}
        )
        return {"status": "SUCCESS"}


@router.post("/review.deleted")
async def handle_review_deleted(request: Request):
    """
    Handle review.deleted event from Dapr pub/sub.
    Called by Dapr when a review is deleted.
    """
    try:
        event_data = await request.json()
        
        logger.info(
            "Received review.deleted event",
            metadata={
                "correlationId": event_data.get("correlationId", "no-correlation"),
                "eventId": event_data.get("id")
            }
        )
        
        result = await review_event_consumer.handle_review_deleted(event_data)
        
        return {"status": "SUCCESS"}
        
    except Exception as e:
        logger.error(
            f"Error handling review.deleted event: {str(e)}",
            metadata={"error": str(e)}
        )
        return {"status": "SUCCESS"}


@router.post("/inventory.stock.updated")
async def handle_inventory_stock_updated(request: Request):
    """
    Handle inventory.stock.updated event from Dapr pub/sub.
    Called by Dapr when inventory stock is updated.
    """
    try:
        event_data = await request.json()
        
        logger.info(
            "Received inventory.stock.updated event",
            metadata={
                "correlationId": event_data.get("correlationId", "no-correlation"),
                "eventId": event_data.get("id")
            }
        )
        
        result = await inventory_event_consumer.handle_inventory_updated(event_data)
        
        return {"status": "SUCCESS"}
        
    except Exception as e:
        logger.error(
            f"Error handling inventory.stock.updated event: {str(e)}",
            metadata={"error": str(e)}
        )
        return {"status": "SUCCESS"}


@router.post("/inventory.low.stock")
async def handle_inventory_low_stock(request: Request):
    """
    Handle inventory.low.stock event from Dapr pub/sub.
    Called by Dapr when inventory is running low.
    """
    try:
        event_data = await request.json()
        
        logger.info(
            "Received inventory.low.stock event",
            metadata={
                "correlationId": event_data.get("correlationId", "no-correlation"),
                "eventId": event_data.get("id")
            }
        )
        
        result = await inventory_event_consumer.handle_inventory_low_stock(event_data)
        
        return {"status": "SUCCESS"}
        
    except Exception as e:
        logger.error(
            f"Error handling inventory.low.stock event: {str(e)}",
            metadata={"error": str(e)}
        )
        return {"status": "SUCCESS"}


@router.post("/inventory.out.of.stock")
async def handle_inventory_out_of_stock(request: Request):
    """
    Handle inventory.out.of.stock event from Dapr pub/sub.
    Called by Dapr when inventory is completely out of stock.
    """
    try:
        event_data = await request.json()
        
        logger.info(
            "Received inventory.out.of.stock event",
            metadata={
                "correlationId": event_data.get("correlationId", "no-correlation"),
                "eventId": event_data.get("id")
            }
        )
        
        result = await inventory_event_consumer.handle_inventory_out_of_stock(event_data)
        
        return {"status": "SUCCESS"}
        
    except Exception as e:
        logger.error(
            f"Error handling inventory.out.of.stock event: {str(e)}",
            metadata={"error": str(e)}
        )
        return {"status": "SUCCESS"}
