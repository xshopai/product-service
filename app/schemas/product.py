"""
API schemas for Product endpoints following FastAPI best practices
"""

from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

from app.models.product import ProductBase, ProductTaxonomy


class VariantInput(BaseModel):
    """Schema for variant input during product creation"""
    color: Optional[str] = Field(None, description="Variant color")
    size: Optional[str] = Field(None, description="Variant size")
    initial_stock: int = Field(default=0, ge=0, description="Initial inventory stock")
    # SKU will be auto-generated, no input needed


class ProductCreate(BaseModel):
    """Schema for creating a new product with variants and initial stock"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    price: float = Field(..., ge=0)
    brand: Optional[str] = Field(None, max_length=100)
    status: str = Field(default="active")
    
    # Hierarchical category taxonomy (nested object per PRD)
    taxonomy: ProductTaxonomy = Field(default_factory=ProductTaxonomy)
    
    # Media and metadata
    images: List[str] = []
    tags: List[str] = []
    
    # Product variants with initial stock (SKUs auto-generated)
    variants: List[VariantInput] = Field(
        default_factory=list,
        description="Product variants - SKUs will be auto-generated based on name/color/size"
    )
    
    # Product specifications
    specifications: dict = {}


class ProductUpdate(BaseModel):
    """Schema for updating an existing product"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    price: Optional[float] = Field(None, ge=0)
    brand: Optional[str] = Field(None, max_length=100)
    sku: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = None
    
    # Hierarchical category taxonomy (nested object per PRD)
    taxonomy: Optional[ProductTaxonomy] = None
    
    # Media and metadata
    images: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    
    # Product variations
    colors: Optional[List[str]] = None
    sizes: Optional[List[str]] = None
    variants: Optional[List] = None  # Allow updating variants array
    
    # Product specifications
    specifications: Optional[dict] = None


class ProductResponse(ProductBase):
    """Schema for product responses including all fields"""
    id: str
    
    class Config:
        from_attributes = True


class ProductStatsResponse(BaseModel):
    """Response schema for admin product statistics"""
    total: int
    active: int


# ============================================
# Badge Management Schemas
# ============================================

class BadgeAssign(BaseModel):
    """Schema for assigning a badge to a product"""
    type: str = Field(..., description="Badge type: new-arrival, best-seller, on-sale, featured, limited-edition")
    label: str = Field(..., description="Display label for the badge")
    priority: int = Field(default=0, ge=0, le=100, description="Display priority (higher = more prominent)")
    expires_at: Optional[datetime] = Field(None, description="Badge expiration date (null = never expires)")


class BadgeResponse(BaseModel):
    """Response schema for a badge"""
    type: str
    label: str
    priority: int
    expires_at: Optional[datetime]
    assigned_at: datetime
    assigned_by: str


# ============================================
# Product Variations Schemas
# ============================================

class VariationCreate(BaseModel):
    """Schema for a single variation when creating parent with variations"""
    name: str = Field(..., min_length=1, max_length=255)
    sku: str = Field(..., min_length=1, max_length=50)
    price: float = Field(..., ge=0)
    variation_attributes: Dict[str, str] = Field(..., description="Attributes like {color: 'Red', size: 'M'}")
    images: List[str] = []
    description: Optional[str] = None


class ProductWithVariationsCreate(BaseModel):
    """Schema for creating a parent product with variations"""
    # Parent product fields
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    price: float = Field(..., ge=0, description="Base price for parent product")
    brand: Optional[str] = Field(None, max_length=100)
    sku: str = Field(..., min_length=1, max_length=50, description="Parent SKU")
    status: str = Field(default="active")
    
    # Taxonomy
    taxonomy: ProductTaxonomy = Field(default_factory=ProductTaxonomy)
    
    # Media and metadata
    images: List[str] = []
    tags: List[str] = []
    
    # Variation attributes (defines which attributes vary)
    variation_attributes_schema: List[str] = Field(..., description="List of attributes that vary, e.g., ['color', 'size']")
    
    # Child variations
    variations: List[VariationCreate] = Field(..., min_length=1, description="At least one variation required")


class ProductWithVariationsResponse(BaseModel):
    """Response schema for parent product with variations"""
    parent: ProductResponse
    variations: List[ProductResponse]


# ============================================
# Bulk Import Schemas
# ============================================

class BulkImportJobResponse(BaseModel):
    """Response schema for bulk import job creation"""
    job_id: str
    status: str = Field(default="pending", description="pending, processing, completed, failed")
    total_rows: int = 0
    processed_rows: int = 0
    success_count: int = 0
    error_count: int = 0
    created_at: datetime
    message: Optional[str] = None


class BulkImportStatusResponse(BaseModel):
    """Response schema for bulk import job status"""
    job_id: str
    status: str
    total_rows: int
    processed_rows: int
    success_count: int
    error_count: int
    errors: List[Dict[str, str]] = []
    created_at: datetime
    completed_at: Optional[datetime] = None


# ============================================
# Autocomplete Schema
# ============================================

class AutocompleteResponse(BaseModel):
    """Response schema for search autocomplete"""
    suggestions: List[str] = Field(default_factory=list, description="List of autocomplete suggestions")


# ============================================
# Cursor Pagination Schemas
# ============================================

class CursorPaginationMeta(BaseModel):
    """Metadata for cursor-based pagination"""
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")
    prev_cursor: Optional[str] = Field(None, description="Cursor for previous page")
    has_more: bool = Field(default=False, description="Whether more results exist")
    limit: int = Field(default=20, description="Number of items per page")


class CursorPaginatedResponse(BaseModel):
    """Response schema for cursor-paginated results"""
    products: List[ProductResponse]
    pagination: CursorPaginationMeta


# ============================================
# Batch Lookup Schemas
# ============================================

class BatchProductLookupRequest(BaseModel):
    """Request schema for batch product lookup"""
    product_ids: List[str] = Field(..., min_length=1, max_length=100, description="List of product IDs to lookup")


class BatchProductLookupResponse(BaseModel):
    """Response schema for batch product lookup"""
    products: List[ProductResponse]
    not_found: List[str] = Field(default_factory=list, description="IDs that were not found")


# ============================================
# SEO Update Schema
# ============================================

class SEOMetadataUpdate(BaseModel):
    """Schema for updating SEO metadata"""
    meta_title: Optional[str] = Field(None, max_length=70, description="SEO title tag")
    meta_description: Optional[str] = Field(None, max_length=160, description="SEO meta description")
    meta_keywords: Optional[List[str]] = Field(None, description="SEO keywords")
    canonical_url: Optional[str] = Field(None, description="Canonical URL")
    og_title: Optional[str] = Field(None, max_length=70, description="Open Graph title")
    og_description: Optional[str] = Field(None, max_length=200, description="Open Graph description")
    og_image: Optional[str] = Field(None, description="Open Graph image URL")


class SEOMetadataResponse(BaseModel):
    """Response schema for SEO metadata"""
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[List[str]] = None
    canonical_url: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    updated_at: datetime


# ============================================
# Bulk Badge Assignment Schema
# ============================================

class BulkBadgeAssignRequest(BaseModel):
    """Request schema for bulk badge assignment"""
    product_ids: List[str] = Field(..., min_length=1, max_length=100, description="Product IDs to assign badge")
    badge: BadgeAssign


class BulkBadgeAssignResponse(BaseModel):
    """Response schema for bulk badge assignment"""
    success_count: int
    failure_count: int
    failed_ids: List[str] = Field(default_factory=list)


# ============================================
# Add Variation to Existing Parent Schema
# ============================================

class AddVariationRequest(BaseModel):
    """Request schema for adding a variation to an existing parent product"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Variation name (inherits from parent if not provided)")
    sku: str = Field(..., min_length=1, max_length=50, description="Unique SKU for this variation")
    price: float = Field(..., ge=0, description="Variation price")
    variation_attributes: Dict[str, str] = Field(..., description="Variation attributes, e.g., {'color': 'Blue', 'size': 'L'}")
    images: List[str] = Field(default_factory=list)
    description: Optional[str] = Field(None, max_length=2000)