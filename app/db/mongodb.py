"""
MongoDB database connection and configuration following FastAPI best practices
"""

import os
import re
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
from urllib.parse import urlparse

from app.core.config import config
from app.core.errors import ErrorResponse
from app.core.logger import logger


class Database:
    """Database connection manager"""
    
    client: Optional[AsyncIOMotorClient] = None
    database = None


db = Database()


async def connect_to_mongo():
    """Create database connection"""
    logger.info("Connecting to MongoDB...")
    
    try:
        # Get database configuration from environment variables
        mongodb_url = os.environ.get('MONGODB_URI')
        
        if not mongodb_url:
            raise RuntimeError(
                "MongoDB connection string not found. "
                "Set MONGODB_URI as environment variable."
            )
        
        # Extract database name from URI or env var
        parsed = urlparse(mongodb_url)
        database = parsed.path.lstrip('/') if parsed.path and parsed.path != '/' else None
        
        if not database:
            database = os.environ.get('MONGODB_DB_NAME', 'product_service_db')
        
        # Sanitize URL for logging (hide password)
        sanitized_url = re.sub(r'://[^:]+:[^@]+@', '://***:***@', mongodb_url)
        
        # Detect if this is Cosmos DB (for connection options)
        is_cosmos_db = 'cosmos.azure.com' in mongodb_url or ':10255' in mongodb_url
        
        logger.info(
            f"MongoDB URL: {sanitized_url}",
            metadata={"event": "mongodb_url_debug", "is_cosmos_db": is_cosmos_db}
        )
        
        # Connection options
        connection_options = {
            "serverSelectionTimeoutMS": 30000,
            "socketTimeoutMS": 45000,
        }
        
        if is_cosmos_db:
            connection_options["tls"] = True
            connection_options["retryWrites"] = False
            logger.info(
                "Detected Azure Cosmos DB, using TLS connection",
                metadata={"event": "cosmos_db_detected"}
            )
        
        db.client = AsyncIOMotorClient(mongodb_url, **connection_options)
        db.database = db.client[database]
        
        # Test connection
        await db.client.admin.command('ping')
        
        logger.info(
            f"Successfully connected to MongoDB database '{database}'",
            metadata={"event": "mongodb_connected", "database": database}
        )
    except Exception as e:
        logger.error(
            f"Could not connect to MongoDB: {e}",
            metadata={"event": "mongodb_connection_error", "error": str(e)}
        )
        raise ErrorResponse(
            f"Could not connect to MongoDB: {e}",
            status_code=503
        )


async def close_mongo_connection():
    """Close database connection"""
    logger.info("Closing connection to MongoDB...")
    if db.client is not None:
        db.client.close()


async def get_database():
    """Get database instance"""
    if db.database is None:
        await connect_to_mongo()
    return db.database


async def get_product_collection():
    """Get products collection"""
    database = await get_database()
    return database["products"]