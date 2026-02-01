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


def setup_azure_monitor() -> bool:
    """
    Configure Azure Monitor / Application Insights for distributed tracing.
    Must be called BEFORE importing FastAPI app for proper auto-instrumentation.
    
    Connection string is retrieved from:
    1. APPLICATIONINSIGHTS_CONNECTION_STRING env var (set in aca.sh)
    2. Dapr secretstore (xshopai-appinsights-connection)
    """
    try:
        # Try environment variable first (set during ACA deployment)
        connection_string = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
        
        # Fall back to Dapr secretstore
        if not connection_string:
            try:
                from app.core.secret_manager import secret_manager
                connection_string = secret_manager.get_secret('APPINSIGHTS_CONNECTION')
            except Exception as e:
                _logger.debug(f"Could not get App Insights connection from Dapr: {e}")
        
        if not connection_string:
            _logger.warning("Application Insights not configured - connection string not found")
            return False
        
        # Get service name from environment (set in aca.sh)
        service_name = os.environ.get('OTEL_SERVICE_NAME', os.environ.get('NAME', 'product-service'))
        _logger.info(f"Configuring Azure Monitor with service name: {service_name}")
        
        from azure.monitor.opentelemetry import configure_azure_monitor
        
        configure_azure_monitor(
            connection_string=connection_string,
            enable_live_metrics=True,
            logger_name="product-service",
            instrumentation_options={
                "azure_sdk": {"enabled": True},
                "fastapi": {"enabled": True},
                "requests": {"enabled": True},
                "logging": {"enabled": True},
            },
        )
        
        # Create a test span to verify tracing is working
        from opentelemetry import trace
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("azure-monitor-init-verification") as span:
            span.set_attribute("service.name", service_name)
            span.set_attribute("test", "initialization")
            _logger.info("Created test span to verify tracing")
        
        _logger.info(f"Azure Monitor configured successfully - cloud_RoleName: {service_name}")
        return True
        
    except ImportError as e:
        _logger.error(f"Azure Monitor SDK not installed: {e}")
        return False
    except Exception as e:
        _logger.error(f"Failed to configure Application Insights: {e}", exc_info=True)
        return False


# Configure Azure Monitor BEFORE importing FastAPI app
# This ensures auto-instrumentation hooks are installed
azure_monitor_enabled = setup_azure_monitor()
_logger.info(f"Azure Monitor setup complete: enabled={azure_monitor_enabled}")

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
    
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.environment == "development"
    )