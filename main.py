"""
FastAPI Application - Product Service
Following FastAPI best practices with proper separation of concerns
"""

# Load environment variables from .env file FIRST before any other imports
from dotenv import load_dotenv
load_dotenv()

import os
import logging

# Configure basic logging early
logging.basicConfig(
    level=logging.DEBUG if os.environ.get('DEBUG') == 'true' else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
_logger = logging.getLogger(__name__)

# Suppress verbose Azure SDK logging (Live Metrics pings, HTTP requests)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure.monitor.opentelemetry.exporter').setLevel(logging.WARNING)
logging.getLogger('opentelemetry').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# ============================================================================
# CRITICAL: Instrument PyMongo BEFORE any motor/pymongo imports happen!
# The instrumentation must happen before the MongoDB client is created.
# ============================================================================
try:
    from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
    if not PymongoInstrumentor().is_instrumented_by_opentelemetry:
        PymongoInstrumentor().instrument()
        _logger.info("PyMongo instrumentation initialized EARLY (before motor import)")
except ImportError as e:
    _logger.warning(f"PyMongo instrumentation package not available: {e}")
except Exception as e:
    _logger.warning(f"Failed to initialize early PyMongo instrumentation: {e}")


# Configure tracing using unified module
from app.core.tracing import setup_tracing, is_tracing_enabled

tracing_enabled = setup_tracing('product-service')
_logger.info(f"Tracing setup complete: enabled={tracing_enabled}")

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import config
from app.core.errors import error_response_handler, http_exception_handler, ErrorResponse
from app.core.logger import logger
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.api import products, operational, admin, home, events
from app.middleware import TraceContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Product Service...")
    await connect_to_mongo()
    
    logger.info(
        "Product Service started successfully",
        metadata={
            "service_name": config.service_name,
            "version": config.service_version,
            "environment": config.environment,
            "port": config.port
        }
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down Product Service...")
    await close_mongo_connection()


# Create FastAPI application with lifespan management
app = FastAPI(
    title="Product Service",
    description="Microservice for product management with clean architecture",
    version=config.service_version,
    lifespan=lifespan,
    redirect_slashes=False  # Prevent 307 redirects that break Dapr invoke with query params
)

# Configure error handlers
app.add_exception_handler(ErrorResponse, error_response_handler)
app.add_exception_handler(RequestValidationError, lambda request, exc: JSONResponse(
    status_code=422,
    content={"error": "Validation error", "details": exc.errors()}
))

# Add W3C Trace Context middleware
app.add_middleware(TraceContextMiddleware)

# Include API routers
app.include_router(home.router, tags=["home"])
app.include_router(operational.router, tags=["operational"])  # No /api prefix for health/metrics
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(events.router)  # Dapr pub/sub event subscriptions


if __name__ == "__main__":
    import uvicorn
    
    logger.info(
        f"Starting {config.service_name} on port {config.port}",
        metadata={
            "service_name": config.service_name,
            "version": config.service_version,
            "environment": config.environment,
            "port": config.port
        }
    )
    
    # Disable reload to prevent Flask/Uvicorn from spawning a child process
    # This ensures VS Code debugger breakpoints work correctly
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=False  # Always False for VS Code debugging
    )