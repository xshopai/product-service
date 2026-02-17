"""
RabbitMQ Consumer for Product Service
Provides direct RabbitMQ message consumption for development environments without Dapr.

This consumer:
1. Connects to RabbitMQ directly
2. Subscribes to the same topics as Dapr subscriptions
3. Routes messages to the same event handlers (review_consumer, inventory_consumer)

Usage:
- Set MESSAGING_PROVIDER=rabbitmq in environment
- Call start_rabbitmq_consumer() during app startup
"""
import asyncio
import json
import logging
import threading
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    """
    Background consumer for RabbitMQ messages.
    Runs in a separate thread to avoid blocking the FastAPI app.
    Handles async event handlers by running them in an asyncio event loop.
    """
    
    # Topic to handler mapping - mirrors the SUBSCRIPTIONS in api/events.py
    # Format: topic -> (consumer_module, handler_method)
    TOPIC_HANDLERS: Dict[str, tuple] = {
        "review.created": ("review", "handle_review_created"),
        "review.updated": ("review", "handle_review_updated"),
        "review.deleted": ("review", "handle_review_deleted"),
        "inventory.stock.updated": ("inventory", "handle_inventory_updated"),
        "inventory.low.stock": ("inventory", "handle_inventory_low_stock"),
        "inventory.out.of.stock": ("inventory", "handle_inventory_out_of_stock"),
    }
    
    def __init__(self, rabbitmq_url: str, exchange: str = "xshopai.events"):
        """
        Initialize RabbitMQ consumer.
        
        Args:
            rabbitmq_url: RabbitMQ connection URL
            exchange: Exchange name to bind queues to
        """
        self.rabbitmq_url = rabbitmq_url
        self.exchange = exchange
        self.connection = None
        self.channel = None
        self._consumer_thread: Optional[threading.Thread] = None
        self._running = False
        self._review_consumer = None
        self._inventory_consumer = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        logger.info(f"RabbitMQConsumer initialized with exchange: {exchange}")
    
    def _get_review_consumer(self):
        """Lazy load review consumer to avoid circular imports."""
        if self._review_consumer is None:
            from app.events.consumers.review_consumer import review_event_consumer
            self._review_consumer = review_event_consumer
        return self._review_consumer
    
    def _get_inventory_consumer(self):
        """Lazy load inventory consumer to avoid circular imports."""
        if self._inventory_consumer is None:
            from app.events.consumers.inventory_consumer import inventory_event_consumer
            self._inventory_consumer = inventory_event_consumer
        return self._inventory_consumer
    
    def _setup_connection(self):
        """Set up RabbitMQ connection, exchange, and queue bindings."""
        try:
            import pika
            
            # Parse connection URL and create connection
            parameters = pika.URLParameters(self.rabbitmq_url)
            # Set heartbeat to keep connection alive
            parameters.heartbeat = 30
            parameters.blocked_connection_timeout = 300
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare exchange (topic type for routing by event type)
            self.channel.exchange_declare(
                exchange=self.exchange,
                exchange_type='topic',
                durable=True
            )
            
            # Create a unique queue for this service instance
            result = self.channel.queue_declare(
                queue='product-service-events',
                durable=True,
                exclusive=False,
                auto_delete=False
            )
            queue_name = result.method.queue
            
            # Bind queue to all topics we're interested in
            for topic in self.TOPIC_HANDLERS.keys():
                self.channel.queue_bind(
                    exchange=self.exchange,
                    queue=queue_name,
                    routing_key=topic
                )
                logger.info(f"Bound queue to topic: {topic}")
            
            # Set prefetch count for fair dispatch
            self.channel.basic_qos(prefetch_count=1)
            
            logger.info(f"RabbitMQ connection established. Queue: {queue_name}")
            return queue_name
            
        except ImportError:
            logger.error("pika package not installed. Install with: pip install pika")
            raise
        except Exception as e:
            logger.error(f"Failed to set up RabbitMQ connection: {e}")
            raise
    
    def _run_async_handler(self, coro):
        """Run an async coroutine from the sync consumer thread."""
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop.run_until_complete(coro)
    
    def _process_message(self, ch, method, properties, body):
        """
        Process incoming message from RabbitMQ.
        Routes to appropriate handler based on routing key (topic).
        """
        topic = method.routing_key
        correlation_id = properties.correlation_id or "unknown"
        
        try:
            # Parse message body as JSON
            event_data = json.loads(body)
            
            logger.info(
                f"📨 Received message on topic: {topic}",
                extra={"topic": topic, "correlationId": correlation_id}
            )
            
            # Find handler for this topic
            handler_info = self.TOPIC_HANDLERS.get(topic)
            if not handler_info:
                logger.warning(f"No handler found for topic: {topic}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            
            consumer_type, handler_name = handler_info
            
            # Get the appropriate consumer instance
            if consumer_type == "review":
                consumer = self._get_review_consumer()
            elif consumer_type == "inventory":
                consumer = self._get_inventory_consumer()
            else:
                logger.error(f"Unknown consumer type: {consumer_type}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            
            # Get handler method from consumer
            handler = getattr(consumer, handler_name, None)
            
            if not handler:
                logger.error(f"Handler method not found: {handler_name}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            
            # Execute async handler (product-service uses FastAPI/async)
            result = self._run_async_handler(handler(event_data))
            
            if result.get('status') == 'error':
                logger.error(
                    f"Handler returned error: {result.get('message')}",
                    extra={"topic": topic, "correlationId": correlation_id}
                )
                # Don't requeue on business logic errors
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                logger.info(
                    f"✅ Successfully processed message: {topic}",
                    extra={"topic": topic, "correlationId": correlation_id}
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
                    
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message body as JSON: {e}")
            # Don't requeue invalid messages
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(
                f"Error processing message: {e}",
                extra={"topic": topic, "correlationId": correlation_id, "error": str(e)}
            )
            # Requeue for retry on unexpected errors
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def _consume_messages(self, queue_name: str):
        """
        Start consuming messages from the queue.
        This runs in a separate thread.
        """
        logger.info(f"Starting message consumption from queue: {queue_name}")
        
        try:
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=self._process_message,
                auto_ack=False
            )
            
            while self._running:
                # Process one message at a time with timeout
                # This allows checking _running flag periodically
                self.connection.process_data_events(time_limit=1)
                
        except Exception as e:
            if self._running:
                logger.error(f"Error in message consumption: {e}")
            else:
                logger.info("Message consumption stopped")
        finally:
            # Clean up event loop
            if self._loop:
                self._loop.close()
                self._loop = None
    
    def start(self):
        """Start the consumer in a background thread."""
        if self._running:
            logger.warning("Consumer is already running")
            return
        
        try:
            queue_name = self._setup_connection()
            self._running = True
            
            self._consumer_thread = threading.Thread(
                target=self._consume_messages,
                args=(queue_name,),
                daemon=True,
                name="rabbitmq-consumer"
            )
            self._consumer_thread.start()
            
            logger.info("🐰 RabbitMQ consumer started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start RabbitMQ consumer: {e}")
            self._running = False
            raise
    
    def stop(self):
        """Stop the consumer gracefully."""
        logger.info("Stopping RabbitMQ consumer...")
        self._running = False
        
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5.0)
        
        try:
            if self.channel:
                self.channel.close()
            if self.connection:
                self.connection.close()
        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {e}")
        
        logger.info("RabbitMQ consumer stopped")
    
    def is_running(self) -> bool:
        """Check if consumer is currently running."""
        return self._running and self._consumer_thread and self._consumer_thread.is_alive()


# Global consumer instance
_consumer: Optional[RabbitMQConsumer] = None


def start_rabbitmq_consumer() -> Optional[RabbitMQConsumer]:
    """
    Start RabbitMQ consumer.
    Only starts if MESSAGING_PROVIDER is set to 'rabbitmq'.
    
    Returns:
        RabbitMQConsumer instance if started, None otherwise
    """
    global _consumer
    
    messaging_provider = os.environ.get('MESSAGING_PROVIDER', 'dapr').lower()
    
    if messaging_provider != 'rabbitmq':
        logger.info(
            f"RabbitMQ consumer not started (MESSAGING_PROVIDER={messaging_provider}). "
            "Using Dapr for event consumption."
        )
        return None
    
    # Use RABBITMQ_URL directly (consistent with Node.js services)
    rabbitmq_url = os.environ.get('RABBITMQ_URL', 'amqp://localhost:5672')
    rabbitmq_exchange = os.environ.get('RABBITMQ_EXCHANGE', 'xshopai.events')
    
    try:
        _consumer = RabbitMQConsumer(rabbitmq_url, rabbitmq_exchange)
        _consumer.start()
        return _consumer
    except Exception as e:
        logger.error(f"Failed to start RabbitMQ consumer: {e}")
        return None


def stop_rabbitmq_consumer():
    """Stop the global RabbitMQ consumer if running."""
    global _consumer
    if _consumer:
        _consumer.stop()
        _consumer = None
