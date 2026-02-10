"""
Product service containing business logic layer
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from app.core.errors import ErrorResponse
from app.core.logger import logger
from app.repositories.product import ProductRepository
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductResponse, ProductStatsResponse,
    BadgeAssign, BadgeResponse, ProductWithVariationsCreate, ProductWithVariationsResponse,
    VariationCreate, BulkImportJobResponse, BulkImportStatusResponse, AutocompleteResponse
)
from app.models.product import ProductBadge, ProductVariant
from app.events import event_publisher
from app.middleware.trace_context import get_trace_id
from app.utils.sku_generator import generate_sku


# In-memory job storage (for demo - use Redis or DB in production)
_bulk_import_jobs: Dict[str, Dict[str, Any]] = {}


class ProductService:
    """Service layer for product business logic"""
    
    def __init__(self, repository: ProductRepository):
        self.repository = repository
    
    async def create_product(self, product_data: ProductCreate, created_by: str = "system") -> ProductResponse:
        """
        Create a new product with variants and auto-generated SKUs.
        Each variant gets a unique SKU and initial stock tracking.
        """
        # Validate business rules
        if product_data.price < 0:
            raise ErrorResponse("Price must be non-negative", status_code=400)
        
        # Auto-generate SKUs for all variants
        generated_variants = []
        for variant_input in product_data.variants:
            # Generate unique SKU based on product name + variant attributes
            sku = generate_sku(
                product_name=product_data.name,
                color=variant_input.color,
                size=variant_input.size
            )
            
            # Check for duplicate SKU
            if await self.repository.check_sku_exists(sku):
                raise ErrorResponse(
                    f"Generated SKU '{sku}' already exists. Please modify product name or variant attributes.",
                    status_code=400
                )
            
            # Create ProductVariant with generated SKU and initial stock
            variant = ProductVariant(
                sku=sku,
                color=variant_input.color,
                size=variant_input.size,
                initial_stock=variant_input.initial_stock
            )
            generated_variants.append(variant)
        
        # Add generated variants to product data
        product_dict = product_data.model_dump()
        product_dict['variants'] = [v.model_dump() for v in generated_variants]
        
        # Extract unique colors and sizes for product-level attributes
        colors = list(set(v.color for v in generated_variants if v.color))
        sizes = list(set(v.size for v in generated_variants if v.size))
        product_dict['colors'] = colors
        product_dict['sizes'] = sizes
        
        # Create the product
        product = await self.repository.create(ProductCreate(**product_dict), created_by)
        
        logger.info(
            f"Created product {product.id} with {len(generated_variants)} variants",
            metadata={
                "event": "create_product",
                "product_id": product.id,
                "variant_count": len(generated_variants),
                "skus": [v.sku for v in generated_variants]
            }
        )
        
        # Publish product.created event with variants (for inventory-service)
        await event_publisher.publish_product_created(
            product_id=product.id,
            product_data={
                **product.model_dump(),
                "variants": [v.model_dump() for v in generated_variants]  # Include full variant info with initial_stock
            },
            created_by=created_by,
            correlation_id=get_trace_id()
        )
        
        return product
    
    async def get_product(self, product_id: str) -> ProductResponse:
        """Get product by ID"""
        product = await self.repository.get_by_id(product_id)
        if not product:
            raise ErrorResponse("Product not found", status_code=404)
        
        logger.info(
            f"Fetched product {product_id}",
            metadata={"event": "get_product", "product_id": product_id}
        )
        
        return product
    
    async def update_product(self, product_id: str, product_data: ProductUpdate, updated_by: str = None) -> ProductResponse:
        """Update product with business validation"""
        # Validate business rules
        if product_data.price is not None and product_data.price < 0:
            raise ErrorResponse("Price must be non-negative", status_code=400)
        
        # Check for duplicate SKU
        if product_data.sku:
            if await self.repository.check_sku_exists(product_data.sku, exclude_id=product_id):
                raise ErrorResponse("A product with this SKU already exists", status_code=400)
        
        # Get current product to detect price changes
        current_product = await self.repository.get_by_id(product_id)
        if not current_product:
            raise ErrorResponse("Product not found", status_code=404)
        
        old_price = current_product.price
        
        # Update the product
        product = await self.repository.update(product_id, product_data, updated_by)
        if not product:
            raise ErrorResponse("Product not found", status_code=404)
        
        logger.info(
            f"Updated product {product_id}",
            metadata={"event": "update_product", "product_id": product_id}
        )
        
        # Publish product.updated event via Dapr
        await event_publisher.publish_product_updated(
            product_id=product_id,
            product_data=product.model_dump(),
            updated_by=updated_by or "system",
            correlation_id=get_trace_id()
        )
        
        # Publish product.price.changed event if price was updated (PRD Section 2.3.2)
        if product_data.price is not None and product_data.price != old_price:
            await event_publisher.publish_product_price_changed(
                product_id=product_id,
                old_price=old_price,
                new_price=product_data.price,
                updated_by=updated_by or "system",
                correlation_id=get_trace_id()
            )
            
            logger.info(
                f"Price changed for product {product_id}: {old_price} -> {product_data.price}",
                metadata={
                    "event": "price_changed",
                    "product_id": product_id,
                    "old_price": old_price,
                    "new_price": product_data.price
                }
            )
        
        return product
    
    async def delete_product(self, product_id: str, deleted_by: str = "system") -> None:
        """Soft delete a product"""
        # Get the product first to retrieve variants for inventory cleanup
        product = await self.repository.get_by_id(product_id)
        if not product:
            raise ErrorResponse("Product not found", status_code=404)
        
        # Soft delete the product
        success = await self.repository.delete(product_id)
        if not success:
            raise ErrorResponse("Product not found", status_code=404)
        
        logger.info(
            f"Soft deleted product {product_id}",
            metadata={"event": "soft_delete_product", "product_id": product_id}
        )
        
        # Publish product.deleted event via Dapr with variants for inventory cleanup
        variants_data = None
        if product.variants:
            variants_data = [v.model_dump() for v in product.variants]
        
        await event_publisher.publish_product_deleted(
            product_id=product_id,
            deleted_by=deleted_by,
            correlation_id=get_trace_id(),
            variants=variants_data
        )
    
    async def reactivate_product(self, product_id: str, updated_by: str = None) -> ProductResponse:
        """Reactivate a soft-deleted product"""
        # Get the product first to check SKU conflicts
        current_product = await self.repository.get_by_id(product_id)
        if not current_product:
            raise ErrorResponse("Product not found", status_code=404)
        
        if current_product.is_active:
            raise ErrorResponse("Product is already active", status_code=400)
        
        # Check for SKU conflicts if product has SKU
        if current_product.sku:
            if await self.repository.check_sku_exists(current_product.sku, exclude_id=product_id):
                raise ErrorResponse(
                    f"Cannot reactivate: Another active product already uses SKU '{current_product.sku}'",
                    status_code=400
                )
        
        # Reactivate the product
        product = await self.repository.reactivate(product_id, updated_by)
        
        logger.info(
            f"Reactivated product {product_id}",
            metadata={
                "event": "reactivate_product",
                "product_id": product_id,
                "reactivated_by": updated_by
            }
        )
        
        return product
    
    async def get_products(self,
                          search_text: str = None,
                          department: str = None,
                          category: str = None,
                          subcategory: str = None,
                          min_price: float = None,
                          max_price: float = None,
                          tags: List[str] = None,
                          skip: int = 0,
                          limit: int = None) -> Dict[str, Any]:
        """Get products with optional search and filters"""
        # If search_text is provided, perform search; otherwise, list products
        if search_text and search_text.strip():
            products, total_count = await self.repository.search(
                search_text, department, category, subcategory,
                min_price, max_price, tags, skip, limit
            )
            event_name = "search_products"
        else:
            products, total_count = await self.repository.list_products(
                department, category, subcategory,
                min_price, max_price, tags, skip, limit
            )
            event_name = "list_products"
        
        # Calculate pagination metadata
        if limit is not None and limit > 0:
            current_page = (skip // limit) + 1
            total_pages = (total_count + limit - 1) // limit
        else:
            current_page = 1
            total_pages = 1
        
        logger.info(
            f"Fetched {len(products)} products",
            metadata={
                "event": event_name,
                "count": len(products),
                "total": total_count,
                "search_text": search_text,
                "filters": {
                    "department": department,
                    "category": category,
                    "subcategory": subcategory,
                    "min_price": min_price,
                    "max_price": max_price,
                    "tags": tags,
                }
            }
        )
        
        # Convert ProductResponse objects to dicts for JSON serialization
        products_dict = [p.model_dump(mode='json') for p in products]
        
        return {
            "products": products_dict,
            "total_count": total_count,
            "current_page": current_page,
            "total_pages": total_pages
        }
    
    async def get_admin_stats(self) -> ProductStatsResponse:
        """Get product statistics for admin dashboard"""
        stats = await self.repository.get_stats()
        
        logger.info(
            "Product statistics fetched successfully",
            metadata={
                "event": "admin_stats_fetched",
                "stats": stats
            }
        )
        
        return ProductStatsResponse(**stats)
    
    async def get_trending_products_and_categories(
        self, 
        products_limit: int = 4, 
        categories_limit: int = 5
    ) -> Dict[str, Any]:
        """
        Get trending products and categories in a single call.
        Optimized for homepage display.
        
        Products include:
        - Full product details with review_aggregates
        - Trending score (pre-calculated)
        - Recency indicator
        
        Categories include:
        - Name, product count, ratings
        - Trending score
        """
        try:
            logger.info(
                "Fetching trending products and categories",
                metadata={
                    "event": "get_trending_products_and_categories",
                    "products_limit": products_limit,
                    "categories_limit": categories_limit
                }
            )
            
            # Fetch both in parallel
            products, categories = await asyncio.gather(
                self.repository.get_trending_products_with_scores(products_limit),
                self.repository.get_trending_categories(categories_limit)
            )
            
            logger.info(
                "Trending products and categories fetched successfully",
                metadata={
                    "event": "trending_data_fetched",
                    "products_count": len(products) if products else 0,
                    "categories_count": len(categories) if categories else 0
                }
            )
            
            return {
                "trending_products": products or [],
                "trending_categories": categories or []
            }
        except Exception as e:
            logger.error(
                f"Error fetching trending data: {str(e)}",
                metadata={
                    "event": "get_trending_data_error",
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise ErrorResponse(
                f"Failed to fetch trending products and categories: {str(e)}", 
                status_code=500
            )
    
    async def get_all_categories(self) -> List[str]:
        """Get all distinct categories from active products"""
        logger.info("Fetching all categories", metadata={"event": "get_all_categories"})
        
        try:
            categories = await self.repository.get_all_categories()
            
            logger.info(
                f"Fetched {len(categories)} categories",
                metadata={"event": "categories_fetched", "count": len(categories)}
            )
            
            return categories
        except Exception as e:
            logger.error(
                f"Error fetching categories: {str(e)}",
                metadata={"event": "get_categories_error", "error": str(e)}
            )
            raise
    
    async def check_product_exists(self, product_id: str) -> Dict[str, bool]:
        """Check if product exists (for inter-service communication)"""
        exists = await self.repository.exists(product_id)
        return {"exists": exists}

    # ==================== VARIATION METHODS ====================

    async def get_variations(self, product_id: str) -> List[ProductResponse]:
        """
        Get all variations (child products) for a parent product.
        Implements PRD 4.8.
        """
        logger.info(
            f"Fetching variations for product {product_id}",
            metadata={"event": "get_variations", "product_id": product_id}
        )
        
        # Verify parent product exists
        parent = await self.repository.get_by_id(product_id)
        if not parent:
            raise ErrorResponse("Parent product not found", status_code=404)
        
        # Check if it's a parent product
        if parent.variation_type != "parent":
            raise ErrorResponse(
                "Product is not a parent variation type", 
                status_code=400
            )
        
        # Fetch child variations
        variations = await self.repository.get_variations_by_parent_id(product_id)
        
        logger.info(
            f"Fetched {len(variations)} variations for product {product_id}",
            metadata={
                "event": "variations_fetched",
                "product_id": product_id,
                "count": len(variations)
            }
        )
        
        return variations

    async def create_product_with_variations(
        self, 
        data: ProductWithVariationsCreate, 
        created_by: str = "system"
    ) -> ProductWithVariationsResponse:
        """
        Create a parent product with its variations (child products).
        Implements PRD 4.9.
        """
        logger.info(
            "Creating product with variations",
            metadata={
                "event": "create_product_with_variations",
                "variation_count": len(data.variations),
                "created_by": created_by
            }
        )
        
        # Check for duplicate SKU on parent
        if data.parent.sku:
            if await self.repository.check_sku_exists(data.parent.sku):
                raise ErrorResponse("Parent product SKU already exists", status_code=400)
        
        # Check for duplicate SKUs on variations
        for i, variation in enumerate(data.variations):
            if variation.sku:
                if await self.repository.check_sku_exists(variation.sku):
                    raise ErrorResponse(
                        f"Variation {i + 1} SKU '{variation.sku}' already exists", 
                        status_code=400
                    )
        
        # Create parent product with variation_type = "parent"
        parent_data = data.parent.model_dump()
        parent_data["variation_type"] = "parent"
        parent_create = ProductCreate(**parent_data)
        
        parent_product = await self.repository.create(parent_create, created_by)
        
        # Create child variations
        created_variations = []
        for variation in data.variations:
            variation_data = variation.model_dump()
            
            # Inherit taxonomy from parent
            variation_data["department"] = parent_product.taxonomy.department if parent_product.taxonomy else None
            variation_data["category"] = parent_product.taxonomy.category if parent_product.taxonomy else None
            variation_data["subcategory"] = parent_product.taxonomy.subcategory if parent_product.taxonomy else None
            
            # Set variation fields
            variation_data["variation_type"] = "child"
            variation_data["parent_product_id"] = parent_product.id
            
            # Use parent name with variation suffix if not specified
            if not variation_data.get("name"):
                attrs = variation_data.get("variation_attributes", {})
                suffix = " - " + ", ".join(f"{k}: {v}" for k, v in attrs.items()) if attrs else ""
                variation_data["name"] = f"{parent_product.name}{suffix}"
            
            # Use parent description if not specified
            if not variation_data.get("description"):
                variation_data["description"] = parent_product.description
            
            variation_create = ProductCreate(**variation_data)
            variation_product = await self.repository.create(variation_create, created_by)
            created_variations.append(variation_product)
            
            # Publish event for each variation
            await event_publisher.publish_product_created(
                product_id=variation_product.id,
                product_data=variation_product.model_dump(),
                created_by=created_by,
                correlation_id=get_trace_id()
            )
        
        # Publish event for parent
        await event_publisher.publish_product_created(
            product_id=parent_product.id,
            product_data=parent_product.model_dump(),
            created_by=created_by,
            correlation_id=get_trace_id()
        )
        
        logger.info(
            f"Created parent product {parent_product.id} with {len(created_variations)} variations",
            metadata={
                "event": "product_with_variations_created",
                "parent_id": parent_product.id,
                "variation_ids": [v.id for v in created_variations]
            }
        )
        
        return ProductWithVariationsResponse(
            parent=parent_product,
            variations=created_variations
        )
    
    async def add_variant(
        self, 
        product_id: str, 
        variant_data: VariationCreate,
        updated_by: str = "system"
    ) -> ProductResponse:
        """
        Add a new variant to an existing product.
        Auto-generates SKU based on product name and variant attributes.
        """
        # Get the product
        product = await self.repository.get_by_id(product_id)
        if not product:
            raise ErrorResponse("Product not found", status_code=404)
        
        # Auto-generate SKU for the new variant
        from app.utils.sku_generator import generate_sku
        sku = generate_sku(
            product_name=product.name,
            color=variant_data.color,
            size=variant_data.size
        )
        
        # Check for duplicate SKU
        if await self.repository.check_sku_exists(sku):
            raise ErrorResponse(
                f"Generated SKU '{sku}' already exists. Please modify variant attributes.",
                status_code=400
            )
        
        # Create the new variant
        from app.models.product import ProductVariant
        variant = ProductVariant(
            sku=sku,
            color=variant_data.color,
            size=variant_data.size,
            initial_stock=variant_data.initial_stock or 0
        )
        
        # Add to product's variants array
        updated_variants = list(product.variants) if product.variants else []
        updated_variants.append(variant)
        
        # Update colors and sizes
        colors = list(set([v.color for v in updated_variants if v.color]))
        sizes = list(set([v.size for v in updated_variants if v.size]))
        
        # Update product with new variant
        from app.schemas.product import ProductUpdate
        update_data = ProductUpdate(
            variants=updated_variants,
            colors=colors,
            sizes=sizes
        )
        updated_product = await self.repository.update(product_id, update_data, updated_by)
        
        logger.info(
            f"Added variant {sku} to product {product_id}",
            metadata={
                "event": "variant_added",
                "product_id": product_id,
                "sku": sku,
                "color": variant_data.color,
                "size": variant_data.size
            }
        )
        
        # Publish product.created event for the new variant (so inventory service creates inventory)
        await event_publisher.publish_product_created(
            product_id=product_id,
            product_data={
                "productId": product_id,
                "name": product.name,
                "variants": [variant.model_dump()]  # Single variant
            },
            created_by=updated_by,
            correlation_id=get_trace_id()
        )
        
        return updated_product
    
    async def remove_variant(
        self, 
        product_id: str, 
        sku: str,
        updated_by: str = "system"
    ) -> None:
        """
        Remove a variant from a product by SKU.
        Also triggers inventory archival for the SKU.
        """
        # Get the product
        product = await self.repository.get_by_id(product_id)
        if not product:
            raise ErrorResponse("Product not found", status_code=404)
        
        # Find and remove the variant
        if not product.variants:
            raise ErrorResponse("Product has no variants", status_code=400)
        
        # Filter out the variant with matching SKU
        updated_variants = [v for v in product.variants if v.sku != sku]
        
        if len(updated_variants) == len(product.variants):
            raise ErrorResponse(f"Variant with SKU '{sku}' not found", status_code=404)
        
        # Update colors and sizes (regenerate from remaining variants)
        colors = list(set([v.color for v in updated_variants if v.color]))
        sizes = list(set([v.size for v in updated_variants if v.size]))
        
        # Update product without the removed variant
        from app.schemas.product import ProductUpdate
        update_data = ProductUpdate(
            variants=updated_variants,
            colors=colors,
            sizes=sizes
        )
        await self.repository.update(product_id, update_data, updated_by)
        
        logger.info(
            f"Removed variant {sku} from product {product_id}",
            metadata={
                "event": "variant_removed",
                "product_id": product_id,
                "sku": sku
            }
        )
        
        # Publish event to archive inventory for this SKU
        # Use product.deleted event with single variant to trigger inventory archival
        await event_publisher.publish_product_deleted(
            product_id=product_id,
            deleted_by=updated_by,
            correlation_id=get_trace_id(),
            variants=[{"sku": sku}]  # Just the removed variant
        )

    # ==================== BADGE METHODS ====================

    async def assign_badge(
        self, 
        product_id: str, 
        badge_data: BadgeAssign, 
        assigned_by: str = "system"
    ) -> BadgeResponse:
        """
        Assign a badge to a product.
        Implements PRD 4.11.
        """
        logger.info(
            f"Assigning badge to product {product_id}",
            metadata={
                "event": "assign_badge",
                "product_id": product_id,
                "badge_type": badge_data.type,
                "assigned_by": assigned_by
            }
        )
        
        # Verify product exists
        product = await self.repository.get_by_id(product_id)
        if not product:
            raise ErrorResponse("Product not found", status_code=404)
        
        # Check if badge type already exists
        existing_badges = product.badges or []
        for badge in existing_badges:
            if badge.type == badge_data.type:
                raise ErrorResponse(
                    f"Badge type '{badge_data.type}' already assigned to this product",
                    status_code=409
                )
        
        # Create the badge
        badge = ProductBadge(
            type=badge_data.type,
            label=badge_data.label,
            priority=badge_data.priority,
            expires_at=badge_data.expires_at,
            assigned_at=datetime.now(timezone.utc),
            assigned_by=assigned_by
        )
        
        # Add badge to product
        updated_product = await self.repository.add_badge(product_id, badge)
        
        # Publish badge assigned event
        await event_publisher.publish_badge_assigned(
            product_id=product_id,
            badge_type=badge_data.type,
            badge_label=badge_data.label,
            assigned_by=assigned_by,
            expires_at=badge_data.expires_at.isoformat() if badge_data.expires_at else None,
            correlation_id=get_trace_id()
        )
        
        logger.info(
            f"Badge '{badge_data.type}' assigned to product {product_id}",
            metadata={
                "event": "badge_assigned",
                "product_id": product_id,
                "badge_type": badge_data.type
            }
        )
        
        return BadgeResponse(
            type=badge.type,
            label=badge.label,
            priority=badge.priority,
            expires_at=badge.expires_at,
            assigned_at=badge.assigned_at,
            assigned_by=badge.assigned_by
        )

    async def remove_badge(
        self, 
        product_id: str, 
        badge_type: str, 
        removed_by: str = "system"
    ) -> bool:
        """Remove a badge from a product"""
        logger.info(
            f"Removing badge from product {product_id}",
            metadata={
                "event": "remove_badge",
                "product_id": product_id,
                "badge_type": badge_type,
                "removed_by": removed_by
            }
        )
        
        # Verify product exists
        product = await self.repository.get_by_id(product_id)
        if not product:
            raise ErrorResponse("Product not found", status_code=404)
        
        # Check if badge exists
        existing_badges = product.badges or []
        badge_exists = any(b.type == badge_type for b in existing_badges)
        if not badge_exists:
            raise ErrorResponse(
                f"Badge type '{badge_type}' not found on this product",
                status_code=404
            )
        
        # Remove the badge
        await self.repository.remove_badge(product_id, badge_type)
        
        # Publish badge removed event
        await event_publisher.publish_badge_removed(
            product_id=product_id,
            badge_type=badge_type,
            removed_by=removed_by,
            correlation_id=get_trace_id()
        )
        
        logger.info(
            f"Badge '{badge_type}' removed from product {product_id}",
            metadata={
                "event": "badge_removed",
                "product_id": product_id,
                "badge_type": badge_type
            }
        )
        
        return True

    async def get_product_badges(self, product_id: str) -> List[BadgeResponse]:
        """Get all badges for a product"""
        product = await self.repository.get_by_id(product_id)
        if not product:
            raise ErrorResponse("Product not found", status_code=404)
        
        badges = product.badges or []
        return [
            BadgeResponse(
                type=b.type,
                label=b.label,
                priority=b.priority,
                expires_at=b.expires_at,
                assigned_at=b.assigned_at,
                assigned_by=b.assigned_by
            ) for b in badges
        ]

    # ==================== BULK IMPORT METHODS ====================

    async def start_bulk_import(
        self, 
        file_content: bytes, 
        filename: str,
        mode: str = "partial-import",
        created_by: str = "system"
    ) -> BulkImportJobResponse:
        """
        Start a bulk import job. Returns job ID for status tracking.
        Implements PRD 4.10.
        """
        job_id = str(uuid.uuid4())
        
        logger.info(
            f"Starting bulk import job {job_id}",
            metadata={
                "event": "bulk_import_started",
                "job_id": job_id,
                "filename": filename,
                "mode": mode,
                "created_by": created_by
            }
        )
        
        # Initialize job status
        _bulk_import_jobs[job_id] = {
            "status": "pending",
            "total_rows": 0,
            "processed_rows": 0,
            "success_count": 0,
            "failure_count": 0,
            "errors": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": created_by,
            "mode": mode,
            "filename": filename
        }
        
        # Start async processing (fire and forget)
        asyncio.create_task(
            self._process_bulk_import(job_id, file_content, filename, mode, created_by)
        )
        
        return BulkImportJobResponse(
            job_id=job_id,
            status="pending",
            message=f"Bulk import job created. Use GET /api/admin/products/bulk/import/{job_id} to check status."
        )

    async def _process_bulk_import(
        self, 
        job_id: str, 
        file_content: bytes, 
        filename: str,
        mode: str,
        created_by: str
    ):
        """Background task to process bulk import"""
        try:
            # Update status to processing
            _bulk_import_jobs[job_id]["status"] = "processing"
            
            # Parse file (CSV or Excel)
            import csv
            import io
            
            if filename.endswith('.csv'):
                content = file_content.decode('utf-8')
                reader = csv.DictReader(io.StringIO(content))
                rows = list(reader)
            else:
                # For Excel, we'd need openpyxl - simplified for now
                raise ValueError("Only CSV files are currently supported")
            
            total_rows = len(rows)
            _bulk_import_jobs[job_id]["total_rows"] = total_rows
            
            success_count = 0
            failure_count = 0
            errors = []
            
            for i, row in enumerate(rows):
                try:
                    # Map CSV columns to ProductCreate
                    product_data = ProductCreate(
                        name=row.get("name", ""),
                        description=row.get("description", ""),
                        sku=row.get("sku"),
                        price=float(row.get("price", 0)),
                        original_price=float(row.get("original_price", 0)) if row.get("original_price") else None,
                        department=row.get("department"),
                        category=row.get("category"),
                        subcategory=row.get("subcategory"),
                        tags=row.get("tags", "").split(",") if row.get("tags") else [],
                    )
                    
                    # Create product
                    await self.create_product(product_data, created_by)
                    success_count += 1
                    
                except Exception as e:
                    failure_count += 1
                    errors.append({
                        "row": i + 2,  # +2 for header row and 0-indexing
                        "error": str(e),
                        "data": row
                    })
                    
                    # If all-or-nothing mode, rollback on first error
                    if mode == "all-or-nothing" and failure_count > 0:
                        # In production, implement rollback logic here
                        _bulk_import_jobs[job_id]["status"] = "failed"
                        _bulk_import_jobs[job_id]["errors"] = errors
                        return
                
                # Update progress
                _bulk_import_jobs[job_id]["processed_rows"] = i + 1
                _bulk_import_jobs[job_id]["success_count"] = success_count
                _bulk_import_jobs[job_id]["failure_count"] = failure_count
            
            # Complete
            _bulk_import_jobs[job_id]["status"] = "completed"
            _bulk_import_jobs[job_id]["errors"] = errors
            _bulk_import_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
            
            logger.info(
                f"Bulk import job {job_id} completed",
                metadata={
                    "event": "bulk_import_completed",
                    "job_id": job_id,
                    "success_count": success_count,
                    "failure_count": failure_count
                }
            )
            
        except Exception as e:
            _bulk_import_jobs[job_id]["status"] = "failed"
            _bulk_import_jobs[job_id]["errors"] = [{"error": str(e)}]
            
            logger.error(
                f"Bulk import job {job_id} failed: {str(e)}",
                metadata={
                    "event": "bulk_import_failed",
                    "job_id": job_id,
                    "error": str(e)
                }
            )

    async def get_bulk_import_status(self, job_id: str) -> BulkImportStatusResponse:
        """Get status of a bulk import job"""
        if job_id not in _bulk_import_jobs:
            raise ErrorResponse("Import job not found", status_code=404)
        
        job = _bulk_import_jobs[job_id]
        
        return BulkImportStatusResponse(
            job_id=job_id,
            status=job["status"],
            total_rows=job["total_rows"],
            processed_rows=job["processed_rows"],
            success_count=job["success_count"],
            failure_count=job["failure_count"],
            errors=job["errors"][:100] if job["errors"] else [],  # Limit errors returned
            created_at=job.get("created_at"),
            completed_at=job.get("completed_at")
        )

    # ==================== AUTOCOMPLETE METHODS ====================

    async def get_autocomplete_suggestions(
        self, 
        query: str, 
        limit: int = 10
    ) -> AutocompleteResponse:
        """
        Get autocomplete suggestions for search.
        Returns product names, categories, and tags matching the query.
        """
        logger.info(
            f"Getting autocomplete suggestions for query: {query}",
            metadata={"event": "autocomplete", "query": query, "limit": limit}
        )
        
        if not query or len(query) < 2:
            return AutocompleteResponse(
                suggestions=[],
                products=[],
                categories=[]
            )
        
        suggestions = await self.repository.get_autocomplete_suggestions(query, limit)
        
        logger.info(
            f"Found {len(suggestions.get('suggestions', []))} autocomplete suggestions",
            metadata={
                "event": "autocomplete_results",
                "query": query,
                "suggestion_count": len(suggestions.get("suggestions", []))
            }
        )
        
        return AutocompleteResponse(
            suggestions=suggestions.get("suggestions", []),
            products=suggestions.get("products", []),
            categories=suggestions.get("categories", [])
        )

    # ==================== CURSOR PAGINATION METHODS ====================

    async def search_products_cursor(
        self,
        search_text: Optional[str] = None,
        department: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        tags: Optional[List[str]] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
        sort: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """
        Search products with cursor-based pagination.
        Suitable for large datasets and infinite scroll.
        """
        logger.info(
            "Searching products with cursor pagination",
            metadata={
                "event": "search_cursor",
                "search_text": search_text,
                "cursor": cursor,
                "limit": limit
            }
        )
        
        result = await self.repository.search_with_cursor(
            search_text=search_text,
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
        
        return result

    # ==================== BATCH LOOKUP METHODS ====================

    async def batch_get_products(self, product_ids: List[str]) -> Dict[str, Any]:
        """
        Get multiple products by IDs in a single request.
        Returns found products and list of not found IDs.
        """
        logger.info(
            f"Batch looking up {len(product_ids)} products",
            metadata={"event": "batch_lookup", "count": len(product_ids)}
        )
        
        products = []
        not_found = []
        
        for product_id in product_ids:
            product = await self.repository.get_by_id(product_id)
            if product:
                products.append(product)
            else:
                not_found.append(product_id)
        
        logger.info(
            f"Batch lookup complete: {len(products)} found, {len(not_found)} not found",
            metadata={
                "event": "batch_lookup_complete",
                "found": len(products),
                "not_found": len(not_found)
            }
        )
        
        return {
            "products": products,
            "not_found": not_found
        }

    # ==================== CATEGORY PATH METHODS ====================

    async def get_products_by_category_path(
        self,
        category_path: str,
        skip: int = 0,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get products by category path (e.g., 'men/clothing/t-shirts').
        Parses the path and applies hierarchical filtering.
        """
        # Parse category path
        path_parts = [p.strip() for p in category_path.split("/") if p.strip()]
        
        department = path_parts[0] if len(path_parts) > 0 else None
        category = path_parts[1] if len(path_parts) > 1 else None
        subcategory = path_parts[2] if len(path_parts) > 2 else None
        
        logger.info(
            f"Getting products by category path: {category_path}",
            metadata={
                "event": "category_path_lookup",
                "department": department,
                "category": category,
                "subcategory": subcategory
            }
        )
        
        return await self.get_products(
            search_text=None,
            department=department,
            category=category,
            subcategory=subcategory,
            skip=skip,
            limit=limit
        )

    # ==================== SEO METADATA METHODS ====================

    async def update_seo_metadata(
        self,
        product_id: str,
        seo_data: Dict[str, Any],
        updated_by: str = "system"
    ) -> Dict[str, Any]:
        """
        Update SEO metadata for a product.
        """
        logger.info(
            f"Updating SEO metadata for product {product_id}",
            metadata={
                "event": "update_seo",
                "product_id": product_id,
                "updated_by": updated_by
            }
        )
        
        # Verify product exists
        product = await self.repository.get_by_id(product_id)
        if not product:
            raise ErrorResponse("Product not found", status_code=404)
        
        # Update SEO metadata
        seo_metadata = {
            **seo_data,
            "updated_at": datetime.now(timezone.utc)
        }
        
        await self.repository.update_seo(product_id, seo_metadata)
        
        # Publish update event
        await event_publisher.publish_product_updated(
            product_id=product_id,
            product_data={"seo": seo_metadata},
            updated_by=updated_by,
            correlation_id=get_trace_id()
        )
        
        logger.info(
            f"SEO metadata updated for product {product_id}",
            metadata={
                "event": "seo_updated",
                "product_id": product_id
            }
        )
        
        return seo_metadata

    # ==================== BULK BADGE ASSIGNMENT ====================

    async def bulk_assign_badges(
        self,
        product_ids: List[str],
        badge_data: Any,
        assigned_by: str = "system"
    ) -> Dict[str, Any]:
        """
        Assign a badge to multiple products at once.
        """
        logger.info(
            f"Bulk assigning badge to {len(product_ids)} products",
            metadata={
                "event": "bulk_badge_assign",
                "badge_type": badge_data.type,
                "product_count": len(product_ids),
                "assigned_by": assigned_by
            }
        )
        
        success_count = 0
        failure_count = 0
        failed_ids = []
        
        for product_id in product_ids:
            try:
                await self.assign_badge(product_id, badge_data, assigned_by)
                success_count += 1
            except Exception as e:
                failure_count += 1
                failed_ids.append(product_id)
                logger.warning(
                    f"Failed to assign badge to product {product_id}: {str(e)}",
                    metadata={
                        "event": "bulk_badge_assign_error",
                        "product_id": product_id,
                        "error": str(e)
                    }
                )
        
        logger.info(
            f"Bulk badge assignment complete: {success_count} success, {failure_count} failed",
            metadata={
                "event": "bulk_badge_assign_complete",
                "success_count": success_count,
                "failure_count": failure_count
            }
        )
        
        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "failed_ids": failed_ids
        }

    # ==================== ADD VARIATION TO EXISTING PARENT ====================

    async def add_variation_to_parent(
        self,
        parent_id: str,
        variation_data: Any,
        created_by: str = "system"
    ) -> ProductResponse:
        """
        Add a variation to an existing parent product.
        """
        logger.info(
            f"Adding variation to parent product {parent_id}",
            metadata={
                "event": "add_variation",
                "parent_id": parent_id,
                "sku": variation_data.sku,
                "created_by": created_by
            }
        )
        
        # Verify parent exists and is a parent type
        parent = await self.repository.get_by_id(parent_id)
        if not parent:
            raise ErrorResponse("Parent product not found", status_code=404)
        
        if parent.variation_type != "parent":
            raise ErrorResponse(
                "Product is not a parent variation type. Cannot add variations.",
                status_code=400
            )
        
        # Check for duplicate SKU
        if await self.repository.check_sku_exists(variation_data.sku):
            raise ErrorResponse(
                f"SKU '{variation_data.sku}' already exists",
                status_code=409
            )
        
        # Create variation product
        variation_dict = variation_data.model_dump() if hasattr(variation_data, 'model_dump') else dict(variation_data)
        
        # Inherit from parent
        variation_dict["department"] = parent.taxonomy.department if parent.taxonomy else None
        variation_dict["category"] = parent.taxonomy.category if parent.taxonomy else None
        variation_dict["subcategory"] = parent.taxonomy.subcategory if parent.taxonomy else None
        variation_dict["variation_type"] = "child"
        variation_dict["parent_product_id"] = parent_id
        
        # Use parent name with variation suffix if not specified
        if not variation_dict.get("name"):
            attrs = variation_dict.get("variation_attributes", {})
            suffix = " - " + ", ".join(f"{k}: {v}" for k, v in attrs.items()) if attrs else ""
            variation_dict["name"] = f"{parent.name}{suffix}"
        
        # Use parent description if not specified
        if not variation_dict.get("description"):
            variation_dict["description"] = parent.description
        
        variation_create = ProductCreate(**variation_dict)
        variation = await self.repository.create(variation_create, created_by)
        
        # Publish event
        await event_publisher.publish_product_created(
            product_id=variation.id,
            product_data=variation.model_dump(),
            created_by=created_by,
            correlation_id=get_trace_id()
        )
        
        logger.info(
            f"Variation {variation.id} added to parent {parent_id}",
            metadata={
                "event": "variation_added",
                "parent_id": parent_id,
                "variation_id": variation.id
            }
        )
        
        return variation

    # ==================== BULK IMPORT ERRORS ====================

    async def get_bulk_import_errors(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all errors from a bulk import job"""
        if job_id not in _bulk_import_jobs:
            raise ErrorResponse("Import job not found", status_code=404)
        
        job = _bulk_import_jobs[job_id]
        return job.get("errors", [])