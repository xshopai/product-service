"""
Admin API endpoints
Administrative operations and dashboard statistics
All endpoints require admin authentication
"""

from fastapi import APIRouter, Depends, HTTPException, Header, status

from app.core.logger import logger
from app.core.errors import ErrorResponseModel
from app.dependencies.product import get_product_service
from app.dependencies.auth import get_current_user, require_admin
from app.models.user import User
from app.schemas.product import (
    ProductCreate, 
    ProductUpdate, 
    ProductResponse,
    ProductStatsResponse
)
from app.services.product import ProductService

router = APIRouter()


# ============================================
# Admin Product CRUD Operations
# ============================================

@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponseModel}, 401: {"model": ErrorResponseModel}, 403: {"model": ErrorResponseModel}},
    summary="Create Product",
    description="Create a new product in the catalog. Requires admin role."
)
async def create_product(
    product: ProductCreate, 
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)
):
    """
    Create a new product. Prevents duplicate SKUs and negative values.
    Requires admin authentication.
    """
    logger.info(
        "Admin creating product",
        metadata={
            "event": "admin_product_create",
            "user_id": user.id,
            "sku": product.sku
        }
    )
    return await service.create_product(product, created_by=user.id)


@router.put(
    "/products/{product_id}",
    response_model=ProductResponse,
    responses={
        400: {"model": ErrorResponseModel},
        401: {"model": ErrorResponseModel},
        403: {"model": ErrorResponseModel},
        404: {"model": ErrorResponseModel},
    },
    summary="Update Product",
    description="Update an existing product. Requires admin role."
)
async def update_product(
    product_id: str,
    product: ProductUpdate,
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)
):
    """
    Update a product. Prevents duplicate SKUs and negative values.
    Requires admin authentication.
    """
    logger.info(
        "Admin updating product",
        metadata={
            "event": "admin_product_update",
            "user_id": user.id,
            "product_id": product_id
        }
    )
    return await service.update_product(product_id, product, updated_by=user.id)


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponseModel},
        403: {"model": ErrorResponseModel},
        404: {"model": ErrorResponseModel}
    },
    summary="Delete Product",
    description="Soft delete a product. Requires admin role."
)
async def delete_product(
    product_id: str,
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)
):
    """
    Soft delete a product.
    Requires admin authentication.
    """
    logger.info(
        "Admin deleting product",
        metadata={
            "event": "admin_product_delete",
            "user_id": user.id,
            "product_id": product_id
        }
    )
    await service.delete_product(product_id, deleted_by=user.email)


@router.patch(
    "/products/{product_id}/reactivate",
    response_model=ProductResponse,
    responses={
        401: {"model": ErrorResponseModel},
        403: {"model": ErrorResponseModel},
        404: {"model": ErrorResponseModel}
    },
    summary="Reactivate Product",
    description="Reactivate a soft-deleted product. Requires admin role."
)
async def reactivate_product(
    product_id: str,
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)
):
    """
    Reactivate a soft-deleted product.
    Requires admin authentication.
    """
    logger.info(
        "Admin reactivating product",
        metadata={
            "event": "admin_product_reactivate",
            "user_id": user.id,
            "product_id": product_id
        }
    )
    return await service.reactivate_product(product_id, updated_by=user.id)


# ============================================
# Admin Statistics & Dashboard
# ============================================

@router.get(
    "/products/stats",
    response_model=ProductStatsResponse,
    summary="Get Product Statistics",
    description="Get comprehensive product statistics for admin dashboard"
)
async def get_stats(
    service: ProductService = Depends(get_product_service),
    authorization: str = Header(None)
):
    """
    Get product statistics for admin dashboard.
    Requires admin role.
    
    Returns:
    - total: Total number of products in catalog
    - active: Number of active products
    
    Note: Stock information (lowStock, outOfStock) is provided by inventory service
    """
    # Manual auth check to avoid Python 3.13 dependency issue
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        from app.dependencies.auth import decode_jwt
        token = authorization.replace("Bearer ", "")
        payload = await decode_jwt(token)
        
        roles = payload.get("roles", [])
        is_admin = "admin" in roles or "Admin" in roles
        
        if not is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
            
        user_id = payload.get("id") or payload.get("user_id") or payload.get("sub")
        
        logger.info("Getting product statistics from service", metadata={"user_id": user_id})
        stats = await service.get_admin_stats()
        
        logger.info(
            "Product statistics retrieved",
            metadata={
                "event": "admin_stats_retrieved",
                "total_products": stats.total,
                "active_products": stats.active
            }
        )
        
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication")


@router.get(
    "/dashboard/summary",
    summary="Get Dashboard Summary",
    description="Get comprehensive dashboard summary for administrators"
)
async def get_dashboard_summary(
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)  # Admin only
):
    """
    Get comprehensive dashboard summary.
    Requires admin role.
    
    Includes:
    - Product statistics
    - System health status
    - Recent activity
    """
    logger.info(
        "Admin requesting dashboard summary",
        metadata={
            "event": "admin_dashboard_request",
            "user_id": user.id,
            "user_email": user.email
        }
    )
    
    # Get product stats
    product_stats = await service.get_admin_stats()
    
    return {
        "products": product_stats.model_dump(),
        "user": {
            "id": user.id,
            "email": user.email,
            "roles": user.roles
        },
        "timestamp": logger._get_timestamp()
    }
