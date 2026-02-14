"""
Message Consumers for Product Service

This module provides message consumption infrastructure.
- For Dapr: Uses HTTP endpoints in app/api/events.py
- For RabbitMQ: Uses RabbitMQConsumer in this module (dev without Dapr)
"""
from .rabbitmq_consumer import (
    RabbitMQConsumer,
    start_rabbitmq_consumer,
    stop_rabbitmq_consumer
)

__all__ = [
    "RabbitMQConsumer",
    "start_rabbitmq_consumer",
    "stop_rabbitmq_consumer"
]
