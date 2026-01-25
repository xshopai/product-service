"""
Admin API endpoints
Administrative operations and dashboard statistics
All endpoints require admin authentication
"""

from fastapi import APIRouter, Depends, HTTPException, Header, status, UploadFile, File

from app.core.logger import logger
from app.core.errors import ErrorResponseModel
from app.dependencies.product import get_product_service
from app.dependencies.auth import get_current_user, require_admin
from app.models.user import User
from app.schemas.product import (
    ProductCreate, 
    ProductUpdate, 
    ProductResponse,
    ProductStatsResponse,
    BadgeAssign,
    BadgeResponse,
    ProductWithVariationsCreate,
    ProductWithVariationsResponse,
    BulkImportJobResponse,
    BulkImportStatusResponse,
    AddVariationRequest,
    BulkBadgeAssignRequest,
    BulkBadgeAssignResponse,
    SEOMetadataUpdate,
    SEOMetadataResponse
)
from app.services.product import ProductService
from typing import List

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


# ============================================
# Product Variations (PRD 4.9)
# ============================================

@router.post(
    "/products/variations",
    response_model=ProductWithVariationsResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponseModel},
        401: {"model": ErrorResponseModel},
        403: {"model": ErrorResponseModel}
    },
    summary="Create Product with Variations",
    description="Create a parent product with its variations (e.g., sizes, colors). Requires admin role."
)
async def create_product_with_variations(
    data: ProductWithVariationsCreate,
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)
):
    """
    Create a parent product with multiple variations.
    Each variation will have its own SKU, price, and attributes.
    Requires admin authentication.
    """
    logger.info(
        "Admin creating product with variations",
        metadata={
            "event": "admin_create_variations",
            "user_id": user.id,
            "parent_sku": data.parent.sku,
            "variation_count": len(data.variations)
        }
    )
    return await service.create_product_with_variations(data, created_by=user.id)


# ============================================
# Badge Management (PRD 4.11)
# ============================================

@router.post(
    "/products/{product_id}/badges",
    response_model=BadgeResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponseModel},
        401: {"model": ErrorResponseModel},
        403: {"model": ErrorResponseModel},
        404: {"model": ErrorResponseModel},
        409: {"model": ErrorResponseModel}
    },
    summary="Assign Badge to Product",
    description="Assign a badge (New Arrival, Best Seller, etc.) to a product. Requires admin role."
)
async def assign_badge(
    product_id: str,
    badge_data: BadgeAssign,
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)
):
    """
    Assign a badge to a product.
    Badge types: new-arrival, best-seller, featured, sale, limited-edition
    Requires admin authentication.
    """
    logger.info(
        "Admin assigning badge to product",
        metadata={
            "event": "admin_assign_badge",
            "user_id": user.id,
            "product_id": product_id,
            "badge_type": badge_data.type
        }
    )
    return await service.assign_badge(product_id, badge_data, assigned_by=user.id)


@router.delete(
    "/products/{product_id}/badges/{badge_type}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponseModel},
        403: {"model": ErrorResponseModel},
        404: {"model": ErrorResponseModel}
    },
    summary="Remove Badge from Product",
    description="Remove a badge from a product. Requires admin role."
)
async def remove_badge(
    product_id: str,
    badge_type: str,
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)
):
    """
    Remove a badge from a product.
    Requires admin authentication.
    """
    logger.info(
        "Admin removing badge from product",
        metadata={
            "event": "admin_remove_badge",
            "user_id": user.id,
            "product_id": product_id,
            "badge_type": badge_type
        }
    )
    await service.remove_badge(product_id, badge_type, removed_by=user.id)


@router.get(
    "/products/{product_id}/badges",
    response_model=List[BadgeResponse],
    responses={
        401: {"model": ErrorResponseModel},
        403: {"model": ErrorResponseModel},
        404: {"model": ErrorResponseModel}
    },
    summary="Get Product Badges",
    description="Get all badges assigned to a product. Requires admin role."
)
async def get_product_badges(
    product_id: str,
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)
):
    """
    Get all badges for a product.
    Requires admin authentication.
    """
    return await service.get_product_badges(product_id)


# ============================================
# Bulk Import Operations (PRD 4.10)
# ============================================

@router.post(
    "/products/bulk/import",
    response_model=BulkImportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponseModel},
        401: {"model": ErrorResponseModel},
        403: {"model": ErrorResponseModel},
        413: {"model": ErrorResponseModel}
    },
    summary="Bulk Import Products",
    description="Upload CSV/Excel file for bulk product import. Processing is asynchronous."
)
async def bulk_import_products(
    file: UploadFile = File(...),
    mode: str = "partial-import",
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)
):
    """
    Start a bulk product import job.
    
    - **file**: CSV or Excel file with product data
    - **mode**: 'partial-import' (continue on errors) or 'all-or-nothing' (rollback on any error)
    
    Returns a job ID for tracking import progress.
    Requires admin authentication.
    """
    # Validate file type
    allowed_extensions = ['.csv', '.xlsx', '.xls']
    file_ext = '.' + file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Validate file size (max 10MB)
    max_size = 10 * 1024 * 1024  # 10 MB
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {max_size // (1024*1024)}MB"
        )
    
    logger.info(
        "Admin starting bulk import",
        metadata={
            "event": "admin_bulk_import_start",
            "user_id": user.id,
            "filename": file.filename,
            "file_size": len(content),
            "mode": mode
        }
    )
    
    return await service.start_bulk_import(
        file_content=content,
        filename=file.filename,
        mode=mode,
        created_by=user.id
    )


@router.get(
    "/products/bulk/import/{job_id}",
    response_model=BulkImportStatusResponse,
    responses={
        401: {"model": ErrorResponseModel},
        403: {"model": ErrorResponseModel},
        404: {"model": ErrorResponseModel}
    },
    summary="Get Bulk Import Status",
    description="Get the status of a bulk import job."
)
async def get_bulk_import_status(
    job_id: str,
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)
):
    """
    Get the status and progress of a bulk import job.
    Requires admin authentication.
    """
    logger.info(
        "Admin checking bulk import status",
        metadata={
            "event": "admin_bulk_import_status",
            "user_id": user.id,
            "job_id": job_id
        }
    )
    return await service.get_bulk_import_status(job_id)


@router.get(
    "/products/bulk/import/{job_id}/errors",
    responses={
        401: {"model": ErrorResponseModel},
        403: {"model": ErrorResponseModel},
        404: {"model": ErrorResponseModel}
    },
    summary="Get Bulk Import Errors",
    description="Get all errors from a bulk import job."
)
async def get_bulk_import_errors(
    job_id: str,
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)
):
    """
    Get all errors from a bulk import job.
    Requires admin authentication.
    """
    logger.info(
        "Admin checking bulk import errors",
        metadata={
            "event": "admin_bulk_import_errors",
            "user_id": user.id,
            "job_id": job_id
        }
    )
    errors = await service.get_bulk_import_errors(job_id)
    return {"job_id": job_id, "errors": errors, "total_errors": len(errors)}


@router.get(
    "/products/bulk/template",
    summary="Download Bulk Import Template",
    description="Download a CSV template for bulk product import."
)
async def download_bulk_template():
    """
    Download a CSV template file for bulk product import.
    """
    from fastapi.responses import Response
    
    # CSV template header
    template = """name,description,sku,price,original_price,department,category,subcategory,tags
"Example Product","Product description here","SKU-001",29.99,39.99,"Electronics","Accessories","Cables","usb,cable,charger"
"Another Product","Another description","SKU-002",19.99,,"Clothing","Shirts","T-Shirts","cotton,summer"
"""
    
    return Response(
        content=template,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=product_import_template.csv"}
    )


# ============================================
# Add Variation to Existing Parent (ARCH 4.1)
# ============================================

@router.post(
    "/products/{product_id}/variations",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponseModel},
        401: {"model": ErrorResponseModel},
        403: {"model": ErrorResponseModel},
        404: {"model": ErrorResponseModel},
        409: {"model": ErrorResponseModel}
    },
    summary="Add Variation to Parent Product",
    description="Add a new variation to an existing parent product. Requires admin role."
)
async def add_variation_to_parent(
    product_id: str,
    variation: AddVariationRequest,
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)
):
    """
    Add a new variation (child product) to an existing parent product.
    The parent product must have variation_type = "parent".
    Requires admin authentication.
    """
    logger.info(
        "Admin adding variation to parent product",
        metadata={
            "event": "admin_add_variation",
            "user_id": user.id,
            "parent_id": product_id,
            "sku": variation.sku
        }
    )
    return await service.add_variation_to_parent(product_id, variation, created_by=user.id)


# ============================================
# Bulk Badge Assignment (ARCH 4.1)
# ============================================

@router.post(
    "/products/badges/bulk",
    response_model=BulkBadgeAssignResponse,
    responses={
        400: {"model": ErrorResponseModel},
        401: {"model": ErrorResponseModel},
        403: {"model": ErrorResponseModel}
    },
    summary="Bulk Assign Badge to Products",
    description="Assign a badge to multiple products at once. Requires admin role."
)
async def bulk_assign_badges(
    request: BulkBadgeAssignRequest,
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)
):
    """
    Assign a badge to multiple products in a single request.
    Returns success/failure counts.
    Requires admin authentication.
    """
    logger.info(
        "Admin bulk assigning badges",
        metadata={
            "event": "admin_bulk_badge_assign",
            "user_id": user.id,
            "badge_type": request.badge.type,
            "product_count": len(request.product_ids)
        }
    )
    result = await service.bulk_assign_badges(
        request.product_ids, 
        request.badge, 
        assigned_by=user.id
    )
    return BulkBadgeAssignResponse(**result)


# ============================================
# SEO Metadata Update (ARCH 4.1)
# ============================================

@router.put(
    "/products/{product_id}/seo",
    response_model=SEOMetadataResponse,
    responses={
        400: {"model": ErrorResponseModel},
        401: {"model": ErrorResponseModel},
        403: {"model": ErrorResponseModel},
        404: {"model": ErrorResponseModel}
    },
    summary="Update Product SEO Metadata",
    description="Update SEO metadata for a product. Requires admin role."
)
async def update_seo_metadata(
    product_id: str,
    seo_data: SEOMetadataUpdate,
    service: ProductService = Depends(get_product_service),
    user: User = Depends(require_admin)
):
    """
    Update SEO metadata (meta title, description, keywords, Open Graph, etc.)
    for a product.
    Requires admin authentication.
    """
    logger.info(
        "Admin updating SEO metadata",
        metadata={
            "event": "admin_update_seo",
            "user_id": user.id,
            "product_id": product_id
        }
    )
    seo_dict = seo_data.model_dump(exclude_unset=True)
    result = await service.update_seo_metadata(product_id, seo_dict, updated_by=user.id)
    return SEOMetadataResponse(**result)
