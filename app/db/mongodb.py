"""
MongoDB database connection and configuration following FastAPI best practices
"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional

from app.core.config import config
from app.core.errors import ErrorResponse
from app.core.logger import logger
from app.core.secret_manager import get_database_config


class Database:
    """Database connection manager"""
    
    client: Optional[AsyncIOMotorClient] = None
    database = None


db = Database()


async def connect_to_mongo():
    """Create database connection"""
    logger.info("Connecting to MongoDB...")
    
    try:
        # Get database configuration from Dapr Secret Manager (not async)
        db_config = get_database_config()
        
        # Build MongoDB URL
        username = db_config.get('username', '')
        password = db_config.get('password', '')
        host = db_config.get('host', 'localhost')
        port = db_config.get('port', '27019')
        database = db_config.get('database', 'product_service_db')
        
        # Check if this is Azure Cosmos DB (port 10255 or host contains cosmos)
        # Use str() conversion to handle both string and number port values
        is_cosmos_db = str(port) == '10255' or 'cosmos.azure.com' in host
        
        # Cosmos DB requires ssl=true, replicaSet=globaldb, retryWrites=false, maxIdleTimeMS=120000
        cosmos_params = 'ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000'
        
        logger.info(f"Database config - Host: {host}, Port: {port} (type: {type(port).__name__}), IsCosmosDB: {is_cosmos_db}", 
                    metadata={"event": "db_config_debug"})
        
        if is_cosmos_db:
            logger.info("Detected Azure Cosmos DB, using TLS connection with replicaSet=globaldb", 
                       metadata={"event": "cosmos_db_detected"})
        
        if username and password:
            if is_cosmos_db:
                mongodb_url = f"mongodb://{username}:{password}@{host}:{port}/{database}?authSource=admin&{cosmos_params}"
                sanitized_url = f"mongodb://{username}:***@{host}:{port}/{database}?authSource=admin&{cosmos_params}"
            else:
                mongodb_url = f"mongodb://{username}:{password}@{host}:{port}/{database}?authSource=admin"
                sanitized_url = f"mongodb://{username}:***@{host}:{port}/{database}?authSource=admin"
            logger.info(f"MongoDB URL: {sanitized_url}", metadata={"event": "mongodb_url_debug"})
        else:
            if is_cosmos_db:
                mongodb_url = f"mongodb://{host}:{port}/{database}?{cosmos_params}"
            else:
                mongodb_url = f"mongodb://{host}:{port}/{database}"
            logger.info(f"MongoDB URL: {mongodb_url}", metadata={"event": "mongodb_url_debug"})
        
        # Connection options
        connection_options = {
            "serverSelectionTimeoutMS": 30000,  # 30 seconds for cloud connections
            "socketTimeoutMS": 45000,
        }
        
        if is_cosmos_db:
            connection_options["tls"] = True
            connection_options["retryWrites"] = False
        
        db.client = AsyncIOMotorClient(mongodb_url, **connection_options)
        db.database = db.client[database]
        
        logger.info(
            f"Database object set to: {database}",
            metadata={"event": "db_object_debug", "database_name": database, "db_database_name": db.database.name}
        )
        
        # Test connection
        await db.client.admin.command('ping')
        
        logger.info(
            f"Successfully connected to MongoDB database '{database}'",
            metadata={
                "event": "mongodb_connected", 
                "database": database,
                "host": host,
                "port": port
            }
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