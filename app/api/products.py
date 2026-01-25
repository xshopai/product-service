"""
Product API endpoints following FastAPI best practices
Clean API layer with dependency injection

NOTE: This router contains PUBLIC/read-only endpoints only.
Admin CRUD operations (create, update, delete, reactivate) are in admin.py
and served at /api/admin/products endpoints.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response, status

from app.dependencies.product import get_product_service
from app.services.product import ProductService
from app.schemas.product import (
    ProductResponse,
    AutocompleteResponse,
    CursorPaginatedResponse,
    BatchProductLookupRequest,
    BatchProductLookupResponse,
)
from app.core.errors import ErrorResponseModel
from app.core.logger import logger

router = APIRouter()


# ============================================
# Autocomplete Endpoint (PRD Section 4.3)
# ============================================

@router.get(
    "/autocomplete",
    response_model=AutocompleteResponse,
    tags=["search"],
    summary="Autocomplete Suggestions",
    description="Get autocomplete suggestions for search queries."
)
async def autocomplete(
    q: str = Query(..., min_length=2, description="Search query (min 2 characters)"),
    limit: int = Query(10, ge=1, le=20, description="Max suggestions to return"),
    service: ProductService = Depends(get_product_service),
):
    """
    Get autocomplete suggestions for product search.
    
    Returns:
    - suggestions: Combined list of product names, categories, and tags
    - products: Matching product names with IDs
    - categories: Matching category names
    """
    return await service.get_autocomplete_suggestions(q, limit)


# ============================================
# Batch Product Lookup (ARCH 4.1)
# ============================================

@router.post(
    "/batch",
    response_model=BatchProductLookupResponse,
    tags=["products"],
    summary="Batch Product Lookup",
    description="Get multiple products by IDs in a single request."
)
async def batch_product_lookup(
    request: BatchProductLookupRequest,
    service: ProductService = Depends(get_product_service),
):
    """
    Look up multiple products by their IDs in a single request.
    Useful for cart validation and order processing.
    
    Returns:
    - products: List of found products
    - not_found: List of IDs that were not found
    """
    result = await service.batch_get_products(request.product_ids)
    return BatchProductLookupResponse(**result)


# ============================================
# Cursor-based Search (ARCH 4.1)
# ============================================

@router.get(
    "/search/cursor",
    response_model=CursorPaginatedResponse,
    tags=["search"],
    summary="Search Products (Cursor Pagination)",
    description="Search products with cursor-based pagination for large datasets and infinite scroll."
)
async def search_products_cursor(
    q: Optional[str] = Query(None, description="Search text"),
    department: Optional[str] = Query(None, description="Filter by department"),
    category: Optional[str] = Query(None, description="Filter by category"),
    subcategory: Optional[str] = Query(None, description="Filter by subcategory"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    cursor: Optional[str] = Query(None, description="Cursor for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort: str = Query("created_at", description="Sort field: created_at, price, name"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    service: ProductService = Depends(get_product_service),
):
    """
    Search products with cursor-based pagination.
    
    Better for:
    - Large datasets (millions of products)
    - Infinite scroll UIs
    - Real-time updates (no missed/duplicate items)
    
    Returns:
    - products: List of products
    - pagination: Contains next_cursor, has_more, limit
    """
    result = await service.search_products_cursor(
        search_text=q,
        department=department,
        category=category,
        subcategory=subcategory,
        min_price=min_price,
        max_price=max_price,
        tags=tags,
        cursor=cursor,
        limit=limit,
        sort=sort,
        sort_order=sort_order
    )
    return CursorPaginatedResponse(
        products=result["products"],
        pagination=result["pagination"]
    )


# ============================================
# Category Path Endpoint (ARCH 4.1)
# ============================================

@router.get(
    "/category/{category_path:path}",
    responses={404: {"model": ErrorResponseModel}},
    tags=["categories"],
    summary="Get Products by Category Path",
    description="Get products by hierarchical category path (e.g., men/clothing/t-shirts)."
)
async def get_products_by_category_path(
    category_path: str,
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max items to return"),
    service: ProductService = Depends(get_product_service),
):
    """
    Get products by category path.
    
    Path format: department/category/subcategory
    Examples:
    - men
    - men/clothing
    - men/clothing/t-shirts
    """
    return await service.get_products_by_category_path(category_path, skip=skip, limit=limit)


# Categories endpoint
@router.get(
    "/categories",
    response_model=List[str],
    tags=["categories"],
    summary="Get Product Categories",
    description="Get all distinct product categories from active products."
)
async def get_categories(
    service: ProductService = Depends(get_product_service),
):
    """
    Get all distinct product categories.
    Returns a sorted list of category names from active products.
    """
    return await service.get_all_categories()


# Internal endpoints (for inter-service communication)
@router.get(
    "/internal/{product_id}/exists",
    response_model=dict,
    tags=["internal"],
    summary="Check Product Exists",
    description="Internal endpoint to check if a product exists (for other services)."
)
async def check_product_exists(
    product_id: str,
    service: ProductService = Depends(get_product_service),
):
    """
    Check if a product exists (internal endpoint for other services).
    
    Returns:
    - exists: Boolean indicating if the product exists and is active
    """
    return await service.check_product_exists(product_id)


# Product discovery endpoints
@router.get(
    "/trending",
    response_model=dict,
    responses={503: {"model": ErrorResponseModel}},
    tags=["storefront"],
    summary="Get Trending Products",
    description="Get trending products and categories for storefront display."
)
async def get_trending(
    products_limit: int = Query(4, ge=1, le=20, description="Max trending products to return"),
    categories_limit: int = Query(5, ge=1, le=20, description="Max trending categories to return"),
    service: ProductService = Depends(get_product_service),
):
    """
    Get trending products and categories in a single optimized call.
    
    Returns:
    - trending_products: Products with review_aggregates and trending scores
    - trending_categories: Categories with product counts and ratings
    
    This endpoint fetches both trending products and categories in one request,
    reducing round trips and improving storefront performance.
    
    Supports both Dapr and direct HTTP calls.
    """
    return await service.get_trending_products_and_categories(products_limit, categories_limit)


# Product search and listing
@router.get(
    "/search",
    responses={404: {"model": ErrorResponseModel}},
    summary="Search Products",
    description="Search products by text with optional filters and pagination."
)
async def search_products(
    response: Response,
    q: str = Query(
        ...,
        description="Search text to find in product name or description",
        min_length=1,
    ),
    department: str = Query(None, description="Filter by department (e.g., Women, Men, Electronics)"),
    category: str = Query(None, description="Filter by category (e.g., Clothing, Accessories)"),
    subcategory: str = Query(None, description="Filter by subcategory (e.g., Tops, Laptops)"),
    min_price: float = Query(None, ge=0, description="Minimum price"),
    max_price: float = Query(None, ge=0, description="Maximum price"),
    tags: list[str] = Query(None, description="Filter by tags"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(None, ge=1, le=1000, description="Max items to return (omit for all products)"),
    service: ProductService = Depends(get_product_service),
):
    """
    Search products by text in name and description with optional filters.
    Supports hierarchical filtering by department/category/subcategory.
    Returns paginated results with metadata.
    If limit is not provided, returns all products matching the search.
    """
    # Add no-cache headers to prevent client-side caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return await service.get_products(
        search_text=q, department=department, category=category, subcategory=subcategory, 
        min_price=min_price, max_price=max_price, tags=tags, skip=skip, limit=limit
    )


@router.get(
    "",
    responses={404: {"model": ErrorResponseModel}},
    summary="List Products",
    description="List products with optional filters and pagination."
)
async def list_products(
    department: str = Query(None, description="Filter by department (e.g., Women, Men, Electronics)"),
    category: str = Query(None, description="Filter by category (e.g., Clothing, Accessories)"),
    subcategory: str = Query(None, description="Filter by subcategory (e.g., Tops, Laptops)"),
    min_price: float = Query(None, ge=0, description="Minimum price"),
    max_price: float = Query(None, ge=0, description="Maximum price"),
    tags: List[str] = Query(None, description="Filter by tags"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(None, ge=1, le=1000, description="Max items to return (omit for all products)"),
    service: ProductService = Depends(get_product_service),
):
    """
    List products with optional filters and pagination.
    Supports hierarchical filtering by department/category/subcategory.
    If limit is not provided, returns all products matching the filters.
    """
    return await service.get_products(
        search_text=None, department=department, category=category, subcategory=subcategory,
        min_price=min_price, max_price=max_price, tags=tags, skip=skip, limit=limit
    )


# ============================================
# Product Variations (PRD 4.8)
# ============================================

@router.get(
    "/{product_id}/variations",
    response_model=List[ProductResponse],
    responses={404: {"model": ErrorResponseModel}},
    tags=["variations"],
    summary="Get Product Variations",
    description="Get all variations (sizes, colors, etc.) for a parent product."
)
async def get_product_variations(
    product_id: str,
    service: ProductService = Depends(get_product_service),
):
    """
    Get all child variations for a parent product.
    
    Returns an empty list if the product has no variations.
    Returns 404 if the product is not found.
    Returns 400 if the product is not a parent variation type.
    """
    return await service.get_variations(product_id)


# Get single product by ID (public endpoint)
@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    responses={404: {"model": ErrorResponseModel}},
    summary="Get Product by ID",
    description="Get a single product by its ID."
)
async def get_product(
    product_id: str, 
    service: ProductService = Depends(get_product_service)
):
    """
    Get a product by its ID.
    """
    return await service.get_product(product_id)