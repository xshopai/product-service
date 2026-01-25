"""
Base Product model with validation and common fields
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


def utc_now():
    """Helper function for Pydantic default_factory to get current UTC time"""
    return datetime.now(timezone.utc)


class ProductHistoryEntry(BaseModel):
    """Model for tracking product change history"""
    updated_by: str
    updated_at: datetime
    changes: Dict[str, str]  # field: new_value


class RatingDistribution(BaseModel):
    """Model for rating distribution breakdown"""
    five_star: int = Field(default=0, alias="5")
    four_star: int = Field(default=0, alias="4")
    three_star: int = Field(default=0, alias="3")
    two_star: int = Field(default=0, alias="2")
    one_star: int = Field(default=0, alias="1")
    
    class Config:
        populate_by_name = True


class ReviewAggregates(BaseModel):
    """Model for aggregated review statistics"""
    average_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    total_review_count: int = Field(default=0, ge=0)
    verified_review_count: int = Field(default=0, ge=0)
    rating_distribution: RatingDistribution = Field(default_factory=RatingDistribution)
    recent_reviews: List[str] = Field(default_factory=list, max_length=5)
    last_review_date: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=utc_now)


class AvailabilityStatus(BaseModel):
    """Model for inventory availability status (denormalized from Inventory Service)"""
    status: str = Field(default="unknown")  # in-stock, out-of-stock, low-stock, unknown
    available_quantity: int = Field(default=0, ge=0)
    last_updated: datetime = Field(default_factory=utc_now)


class ProductVariant(BaseModel):
    """Model for product variants (specific color/size combinations with unique SKU)"""
    sku: str = Field(..., description="Unique SKU for this variant")
    color: Optional[str] = Field(None, description="Color of this variant")
    size: Optional[str] = Field(None, description="Size of this variant")


class ProductBadge(BaseModel):
    """Model for product badges (New Arrival, Best Seller, etc.)"""
    type: str = Field(..., description="Badge type: new-arrival, best-seller, on-sale, featured, limited-edition")
    label: str = Field(..., description="Display label for the badge")
    priority: int = Field(default=0, description="Display priority (higher = more prominent)")
    expires_at: Optional[datetime] = Field(None, description="Badge expiration date (null = never expires)")
    assigned_at: datetime = Field(default_factory=utc_now, description="When the badge was assigned")
    assigned_by: str = Field(default="system", description="Who assigned the badge")


class VariationType(str):
    """Variation type enum"""
    STANDALONE = "standalone"
    PARENT = "parent"
    CHILD = "child"


class ProductTaxonomy(BaseModel):
    """Hierarchical category taxonomy"""
    department: Optional[str] = None      # Level 1: Women, Men, Kids, Electronics
    category: Optional[str] = None        # Level 2: Clothing, Accessories, Computers
    subcategory: Optional[str] = None     # Level 3: Tops, Laptops, Headphones
    productType: Optional[str] = Field(None, alias="product_type")  # Level 4: T-Shirts, Gaming Laptops
    
    class Config:
        populate_by_name = True


class ProductBase(BaseModel):
    """Base Product model with all common fields"""
    
    # Basic information
    name: str
    description: Optional[str] = None
    price: float
    brand: Optional[str] = None
    sku: Optional[str] = None
    status: str = Field(default="active")  # active, inactive, draft
    
    # Hierarchical category taxonomy (nested object per PRD)
    taxonomy: ProductTaxonomy = Field(default_factory=ProductTaxonomy)
    
    # Media and metadata
    images: List[str] = []
    tags: List[str] = []
    
    # Product variations
    colors: List[str] = []
    sizes: List[str] = []
    variants: List[ProductVariant] = Field(default_factory=list, description="SKU variants for each color/size combination")
    
    # Product specifications
    specifications: Dict[str, str] = {}
    
    # Product badges
    badges: List[ProductBadge] = Field(default_factory=list, description="Product badges (New Arrival, Best Seller, etc.)")
    
    # Product variation hierarchy
    variation_type: str = Field(default="standalone", description="standalone, parent, or child")
    parent_product_id: Optional[str] = Field(None, description="Parent product ID for child variations")
    variation_attributes: Dict[str, str] = Field(default_factory=dict, description="Attributes that define this variation (color, size)")
    
    # Denormalized data from other services
    availabilityStatus: Optional[AvailabilityStatus] = Field(None, alias="availability_status")
    reviewAggregates: Optional[ReviewAggregates] = Field(None, alias="review_aggregates")
    
    # Audit trail
    is_active: bool = True
    created_by: str = "system"
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    history: List[ProductHistoryEntry] = []
    
    class Config:
        populate_by_name = True


class Product(ProductBase):
    """Product model with ID for database operations"""
    id: Optional[str] = None