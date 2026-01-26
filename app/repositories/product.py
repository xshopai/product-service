"""
Product repository for data access layer following Repository pattern
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from bson import ObjectId

from pymongo.errors import PyMongoError
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.errors import ErrorResponse
from app.core.logger import logger
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse


class ProductRepository:
    """Repository for product data access operations"""
    
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection
    
    def _doc_to_response(self, doc: dict) -> ProductResponse:
        """Convert MongoDB document to ProductResponse schema"""
        if not doc:
            return None
            
        # Convert ObjectId to string
        doc["id"] = str(doc.pop("_id"))
        
        # Handle datetime fields
        for field in ["created_at", "updated_at"]:
            if field in doc and not isinstance(doc[field], datetime):
                doc[field] = datetime.now(timezone.utc)
        
        # Handle history datetime conversion
        if "history" in doc:
            for entry in doc.get("history", []):
                if "updated_at" in entry and not isinstance(entry["updated_at"], datetime):
                    entry["updated_at"] = datetime.now(timezone.utc)
        
        # Ensure review_aggregates is not None - create default if missing
        if doc.get("review_aggregates") is None:
            from app.models.product import ReviewAggregates
            doc["review_aggregates"] = ReviewAggregates().model_dump()
        
        return ProductResponse(**doc)
    
    async def create(self, product_data: ProductCreate, created_by: str = "system") -> ProductResponse:
        """Create a new product"""
        try:
            # Prepare document for insertion
            doc = product_data.model_dump()
            doc.update({
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "created_by": created_by,
                "is_active": True,
                "history": []
            })
            
            # Insert document
            result = await self.collection.insert_one(doc)
            
            # Retrieve and return created product
            created_doc = await self.collection.find_one({"_id": result.inserted_id})
            return self._doc_to_response(created_doc)
            
        except PyMongoError as e:
            logger.error(f"MongoDB error creating product: {e}")
            raise ErrorResponse("Database error during product creation", status_code=503)
    
    async def get_by_id(self, product_id: str) -> Optional[ProductResponse]:
        """Get product by ID"""
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(product_id):
                return None
                
            doc = await self.collection.find_one({"_id": ObjectId(product_id)})
            return self._doc_to_response(doc) if doc else None
            
        except PyMongoError as e:
            logger.error(f"MongoDB error getting product: {e}")
            raise ErrorResponse("Database error during product retrieval", status_code=503)
    
    async def update(self, product_id: str, product_data: ProductUpdate, updated_by: str = None) -> Optional[ProductResponse]:
        """Update an existing product"""
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(product_id):
                return None
            
            obj_id = ObjectId(product_id)
            
            # Get current product for change tracking
            current_doc = await self.collection.find_one({"_id": obj_id})
            if not current_doc:
                return None
            
            # Extract only fields that were set
            update_data = {k: v for k, v in product_data.model_dump(exclude_unset=True).items()}
            if not update_data:
                return self._doc_to_response(current_doc)
            
            # Track changes
            changes = {k: v for k, v in update_data.items() if k in current_doc and current_doc[k] != v}
            if changes and updated_by:
                history_entry = {
                    "updated_by": updated_by,
                    "updated_at": datetime.now(timezone.utc),
                    "changes": changes,
                }
                update_data.setdefault("history", current_doc.get("history", [])).append(history_entry)
            
            # Add update timestamp
            update_data["updated_at"] = datetime.now(timezone.utc)
            
            # Perform update
            result = await self.collection.update_one(
                {"_id": obj_id}, 
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                return None
            
            # Return updated document
            updated_doc = await self.collection.find_one({"_id": obj_id})
            return self._doc_to_response(updated_doc)
            
        except PyMongoError as e:
            logger.error(f"MongoDB error updating product: {e}")
            raise ErrorResponse("Database error during product update", status_code=503)
    
    async def delete(self, product_id: str) -> bool:
        """Soft delete a product"""
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(product_id):
                return False
            
            result = await self.collection.update_one(
                {"_id": ObjectId(product_id)},
                {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
            )
            
            return result.matched_count > 0
            
        except PyMongoError as e:
            logger.error(f"MongoDB error deleting product: {e}")
            raise ErrorResponse("Database error during product deletion", status_code=503)
    
    async def reactivate(self, product_id: str, updated_by: str = None) -> Optional[ProductResponse]:
        """Reactivate a soft-deleted product"""
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(product_id):
                return None
            
            obj_id = ObjectId(product_id)
            
            # Get current product
            current_doc = await self.collection.find_one({"_id": obj_id})
            if not current_doc:
                return None
            
            # Check if already active
            if current_doc.get("is_active", True):
                return self._doc_to_response(current_doc)
            
            # Prepare update data
            update_data = {
                "is_active": True,
                "updated_at": datetime.now(timezone.utc)
            }
            
            # Add history entry if user provided
            if updated_by:
                history_entry = {
                    "updated_by": updated_by,
                    "updated_at": datetime.now(timezone.utc),
                    "changes": {"is_active": True, "action": "reactivated"},
                }
                await self.collection.update_one(
                    {"_id": obj_id},
                    {
                        "$set": update_data,
                        "$push": {"history": history_entry}
                    }
                )
            else:
                await self.collection.update_one(
                    {"_id": obj_id},
                    {"$set": update_data}
                )
            
            # Return updated document
            updated_doc = await self.collection.find_one({"_id": obj_id})
            return self._doc_to_response(updated_doc)
            
        except PyMongoError as e:
            logger.error(f"MongoDB error reactivating product: {e}")
            raise ErrorResponse("Database error during product reactivation", status_code=503)
    
    async def search(self, 
                     search_text: str,
                     department: str = None,
                     category: str = None,
                     subcategory: str = None,
                     min_price: float = None,
                     max_price: float = None,
                     tags: List[str] = None,
                     skip: int = 0,
                     limit: int = None) -> tuple[List[ProductResponse], int]:
        """Search products with filters and pagination"""
        try:
            # Build query
            query = {"is_active": True}
            
            # Text search
            if search_text and search_text.strip():
                search_pattern = {"$regex": search_text.strip(), "$options": "i"}
                query["$or"] = [
                    {"name": search_pattern},
                    {"description": search_pattern},
                    {"tags": search_pattern},
                    {"brand": search_pattern},
                ]
            
            # Hierarchical filters - case insensitive regex (nested taxonomy)
            if department:
                query["taxonomy.department"] = {"$regex": f"^{department}$", "$options": "i"}
            if category:
                query["taxonomy.category"] = {"$regex": f"^{category}$", "$options": "i"}
            if subcategory:
                query["taxonomy.subcategory"] = {"$regex": f"^{subcategory}$", "$options": "i"}
            
            # Price range
            if min_price is not None or max_price is not None:
                price_query = {}
                if min_price is not None:
                    price_query["$gte"] = min_price
                if max_price is not None:
                    price_query["$lte"] = max_price
                query["price"] = price_query
            
            # Tags filter
            if tags:
                query["tags"] = {"$in": tags}
            
            # Get total count
            total_count = await self.collection.count_documents(query)
            
            # Execute search with pagination
            cursor = self.collection.find(query).skip(skip)
            if limit is not None:
                cursor = cursor.limit(limit)
                docs = await cursor.to_list(length=limit)
            else:
                docs = await cursor.to_list(length=None)
            
            # Convert to response models
            products = [self._doc_to_response(doc) for doc in docs]
            
            return products, total_count
            
        except PyMongoError as e:
            logger.error(f"MongoDB error during search: {e}")
            raise ErrorResponse("Database error during product search", status_code=503)
    
    async def list_products(self,
                           department: str = None,
                           category: str = None,
                           subcategory: str = None,
                           min_price: float = None,
                           max_price: float = None,
                           tags: List[str] = None,
                           skip: int = 0,
                           limit: int = None) -> tuple[List[ProductResponse], int]:
        """List products with filters and pagination"""
        try:
            query = {"is_active": True}
            
            # Log the collection name for debugging
            logger.info(
                f"Querying collection: {self.collection.name} in database: {self.collection.database.name}",
                metadata={"event": "query_debug", "collection": self.collection.name, "database": self.collection.database.name}
            )
            
            # Hierarchical filtering - case insensitive regex (nested taxonomy per PRD)
            if department:
                query["taxonomy.department"] = {"$regex": f"^{department}$", "$options": "i"}
            if category:
                query["taxonomy.category"] = {"$regex": f"^{category}$", "$options": "i"}
            if subcategory:
                query["taxonomy.subcategory"] = {"$regex": f"^{subcategory}$", "$options": "i"}
            
            # Price range filtering
            if min_price is not None or max_price is not None:
                price_query = {}
                if min_price is not None:
                    price_query["$gte"] = min_price
                if max_price is not None:
                    price_query["$lte"] = max_price
                query["price"] = price_query
            
            # Tags filtering
            if tags:
                query["tags"] = {"$in": tags}
            
            # Get total count
            total_count = await self.collection.count_documents(query)
            
            # Execute query with pagination
            cursor = self.collection.find(query).skip(skip)
            if limit is not None:
                cursor = cursor.limit(limit)
                docs = await cursor.to_list(length=limit)
            else:
                docs = await cursor.to_list(length=None)
            
            # Convert to response models
            products = [self._doc_to_response(doc) for doc in docs]
            
            return products, total_count
            
        except PyMongoError as e:
            logger.error(f"MongoDB error listing products: {e}")
            raise ErrorResponse("Database error during product listing", status_code=503)
    
    async def get_trending_categories(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get trending categories by product count (used by storefront-data endpoint only).
        This is an internal method for the combined storefront endpoint.
        """
        try:
            pipeline = [
                # Filter: only active products with valid categories
                {
                    "$match": {
                        "is_active": True,
                        "taxonomy.category": {"$exists": True, "$ne": None, "$ne": ""}
                    }
                },
                # Group by category and count
                {
                    "$group": {
                        "_id": "$taxonomy.category",
                        "product_count": {"$sum": 1},
                        "featured_product": {
                            "$first": {
                                "name": "$name",
                                "price": "$price",
                                "images": "$images"
                            }
                        }
                    }
                },
                # Sort by product count
                {"$sort": {"product_count": -1}},
                # Limit results
                {"$limit": limit},
                # Format output
                {
                    "$project": {
                        "_id": 0,
                        "name": "$_id",
                        "product_count": 1,
                        "featured_product": 1
                    }
                }
            ]
            
            cursor = self.collection.aggregate(pipeline)
            categories = await cursor.to_list(length=limit)
            
            return categories
            
        except PyMongoError as e:
            logger.error(f"MongoDB error getting trending categories: {e}")
            raise ErrorResponse("Database error during trending categories retrieval", status_code=503)
    
    async def get_trending_products_with_scores(self, limit: int = 4) -> List[Dict]:
        """
        Get trending products with pre-calculated trending scores.
        
        Algorithm:
        - Base score = average_rating × total_review_count
        - Recency boost = 1.5x for products created in last 30 days
        - Minimum 3 reviews required (with fallbacks)
        
        Note: CosmosDB for MongoDB has strict index requirements for $sort operations.
        We use simple find() queries and sort in Python to avoid index issues.
        """
        try:
            from datetime import datetime, timedelta, timezone
            
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            
            # Fetch candidate products (10x limit for filtering and sorting in Python)
            candidate_limit = limit * 10
            
            # CosmosDB-compatible approach: Use simple find() without $sort in aggregation
            # Fetch products and sort in Python to avoid index requirement errors
            
            # Try to get products with reviews first (no $sort to avoid index issues)
            cursor = self.collection.find({
                "is_active": True,
                "review_aggregates.total_review_count": {"$gte": 1}
            }).limit(candidate_limit)
            docs = await cursor.to_list(length=candidate_limit)
            
            # If not enough products with reviews, get any active products
            if len(docs) < limit:
                cursor = self.collection.find({"is_active": True}).limit(candidate_limit)
                docs = await cursor.to_list(length=candidate_limit)
            
            # Compute trending scores in Python (avoids CosmosDB aggregation/sort issues)
            for doc in docs:
                avg_rating = 0
                review_count = 0
                if doc.get("review_aggregates"):
                    avg_rating = doc["review_aggregates"].get("average_rating", 0) or 0
                    review_count = doc["review_aggregates"].get("total_review_count", 0) or 0
                
                base_score = avg_rating * review_count
                
                # Check if recent - handle both timezone-aware and naive datetimes
                created_at = doc.get("created_at")
                is_recent = False
                if created_at:
                    # Ensure timezone awareness for comparison
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    is_recent = created_at >= thirty_days_ago
                
                # Apply recency boost
                trending_score = base_score * 1.5 if is_recent else base_score
                
                doc["trending_score"] = trending_score
                doc["is_recent"] = is_recent
            
            # Sort by computed trending_score in Python
            docs.sort(key=lambda x: x.get("trending_score", 0), reverse=True)
            
            # Convert to response format with trending data
            products = []
            for doc in docs[:limit]:
                # Convert _id to id string
                if "_id" in doc:
                    doc["id"] = str(doc.pop("_id"))
                
                products.append(doc)
            
            return products
            
        except PyMongoError as e:
            logger.error(f"MongoDB error getting trending products with scores: {e}")
            raise ErrorResponse("Database error during trending products retrieval", status_code=503)
    
    async def get_stats(self) -> Dict[str, int]:
        """Get product statistics for admin dashboard"""
        try:
            # Count all products (including inactive) for accurate dashboard stats
            total = await self.collection.count_documents({})
            active = await self.collection.count_documents({"is_active": True})
            
            # Product service only manages catalog data
            # Stock management is handled by inventory service
            return {
                "total": total,
                "active": active
            }
            
        except PyMongoError as e:
            logger.error(f"MongoDB error getting stats: {e}")
            raise ErrorResponse("Database error during stats retrieval", status_code=503)
    
    async def check_sku_exists(self, sku: str, exclude_id: str = None) -> bool:
        """Check if SKU already exists (for duplicate validation)"""
        try:
            query = {"sku": sku, "is_active": True}
            if exclude_id and ObjectId.is_valid(exclude_id):
                query["_id"] = {"$ne": ObjectId(exclude_id)}
            
            result = await self.collection.find_one(query)
            return result is not None
            
        except PyMongoError as e:
            logger.error(f"MongoDB error checking SKU: {e}")
            raise ErrorResponse("Database error during SKU validation", status_code=503)
    
    async def exists(self, product_id: str) -> bool:
        """Check if product exists and is active"""
        try:
            if not ObjectId.is_valid(product_id):
                return False
            
            result = await self.collection.find_one(
                {"_id": ObjectId(product_id), "is_active": True}
            )
            return result is not None
            
        except PyMongoError as e:
            logger.error(f"MongoDB error checking product existence: {e}")
            return False

    async def get_all_categories(self) -> List[str]:
        """Get all distinct categories from active products"""
        try:
            categories = await self.collection.distinct(
                "category",
                {"is_active": True, "category": {"$ne": None, "$ne": ""}}
            )
            return sorted(categories)
        except PyMongoError as e:
            logger.error(f"MongoDB error getting categories: {e}")
            raise ErrorResponse(f"Failed to fetch categories: {str(e)}", status_code=500)

    # ==================== VARIATION METHODS ====================

    async def get_variations_by_parent_id(self, parent_id: str) -> List[ProductResponse]:
        """Get all child variations for a parent product"""
        try:
            if not ObjectId.is_valid(parent_id):
                return []
            
            cursor = self.collection.find({
                "parent_product_id": parent_id,
                "variation_type": "child",
                "is_active": True
            })
            
            variations = []
            async for doc in cursor:
                variations.append(self._doc_to_response(doc))
            
            return variations
            
        except PyMongoError as e:
            logger.error(f"MongoDB error getting variations: {e}")
            raise ErrorResponse("Database error during variations retrieval", status_code=503)

    # ==================== BADGE METHODS ====================

    async def add_badge(self, product_id: str, badge: Any) -> Optional[ProductResponse]:
        """Add a badge to a product"""
        try:
            if not ObjectId.is_valid(product_id):
                return None
            
            obj_id = ObjectId(product_id)
            
            # Convert badge to dict
            badge_dict = badge.model_dump() if hasattr(badge, 'model_dump') else dict(badge)
            
            result = await self.collection.update_one(
                {"_id": obj_id},
                {
                    "$push": {"badges": badge_dict},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )
            
            if result.matched_count == 0:
                return None
            
            updated_doc = await self.collection.find_one({"_id": obj_id})
            return self._doc_to_response(updated_doc)
            
        except PyMongoError as e:
            logger.error(f"MongoDB error adding badge: {e}")
            raise ErrorResponse("Database error during badge assignment", status_code=503)

    async def remove_badge(self, product_id: str, badge_type: str) -> bool:
        """Remove a badge from a product"""
        try:
            if not ObjectId.is_valid(product_id):
                return False
            
            obj_id = ObjectId(product_id)
            
            result = await self.collection.update_one(
                {"_id": obj_id},
                {
                    "$pull": {"badges": {"type": badge_type}},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )
            
            return result.modified_count > 0
            
        except PyMongoError as e:
            logger.error(f"MongoDB error removing badge: {e}")
            raise ErrorResponse("Database error during badge removal", status_code=503)

    # ==================== AUTOCOMPLETE METHODS ====================

    async def get_autocomplete_suggestions(self, query: str, limit: int = 10) -> Dict[str, List]:
        """
        Get autocomplete suggestions for search.
        Returns matching product names, categories, and tags.
        """
        try:
            # Regex for case-insensitive prefix matching
            regex_pattern = {"$regex": f"^{query}", "$options": "i"}
            
            # Get matching product names
            product_cursor = self.collection.find(
                {"name": regex_pattern, "is_active": True},
                {"name": 1, "_id": 1}
            ).limit(limit)
            
            products = []
            async for doc in product_cursor:
                products.append({
                    "id": str(doc["_id"]),
                    "name": doc["name"]
                })
            
            # Get matching categories
            all_categories = await self.collection.distinct(
                "category",
                {"is_active": True, "category": {"$ne": None, "$ne": ""}}
            )
            categories = [c for c in all_categories if c.lower().startswith(query.lower())][:limit]
            
            # Get matching tags
            all_tags = await self.collection.distinct(
                "tags",
                {"is_active": True, "tags": {"$ne": None}}
            )
            # Flatten and filter tags
            matching_tags = [t for t in all_tags if isinstance(t, str) and t.lower().startswith(query.lower())][:limit]
            
            # Combine all suggestions
            suggestions = []
            for p in products:
                suggestions.append({"type": "product", "text": p["name"], "id": p["id"]})
            for c in categories:
                suggestions.append({"type": "category", "text": c})
            for t in matching_tags:
                suggestions.append({"type": "tag", "text": t})
            
            return {
                "suggestions": suggestions[:limit],
                "products": products,
                "categories": categories
            }
            
        except PyMongoError as e:
            logger.error(f"MongoDB error getting autocomplete suggestions: {e}")
            raise ErrorResponse("Database error during autocomplete", status_code=503)

    # ==================== CURSOR PAGINATION METHODS ====================

    async def search_with_cursor(
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
        Uses encoded cursor for stateless pagination.
        """
        import base64
        import json
        
        try:
            # Build base query
            query = {"is_active": True}
            
            if search_text:
                query["$or"] = [
                    {"name": {"$regex": search_text, "$options": "i"}},
                    {"description": {"$regex": search_text, "$options": "i"}},
                    {"tags": {"$regex": search_text, "$options": "i"}}
                ]
            
            if department:
                query["taxonomy.department"] = {"$regex": department, "$options": "i"}
            if category:
                query["taxonomy.category"] = {"$regex": category, "$options": "i"}
            if subcategory:
                query["taxonomy.subcategory"] = {"$regex": subcategory, "$options": "i"}
            
            if min_price is not None or max_price is not None:
                query["price"] = {}
                if min_price is not None:
                    query["price"]["$gte"] = min_price
                if max_price is not None:
                    query["price"]["$lte"] = max_price
            
            if tags:
                query["tags"] = {"$in": tags}
            
            # Decode cursor if provided
            cursor_data = None
            if cursor:
                try:
                    cursor_json = base64.b64decode(cursor.encode()).decode()
                    cursor_data = json.loads(cursor_json)
                except Exception:
                    pass  # Invalid cursor, start from beginning
            
            # Apply cursor condition
            sort_direction = -1 if sort_order == "desc" else 1
            sort_field = sort if sort in ["created_at", "price", "name", "_id"] else "created_at"
            
            if cursor_data:
                cursor_value = cursor_data.get("value")
                cursor_id = cursor_data.get("id")
                
                if sort_direction == -1:  # Descending
                    query["$or"] = [
                        {sort_field: {"$lt": cursor_value}},
                        {sort_field: cursor_value, "_id": {"$lt": ObjectId(cursor_id)}}
                    ]
                else:  # Ascending
                    query["$or"] = [
                        {sort_field: {"$gt": cursor_value}},
                        {sort_field: cursor_value, "_id": {"$gt": ObjectId(cursor_id)}}
                    ]
            
            # Execute query (fetch limit + 1 to check if more exist)
            mongo_cursor = self.collection.find(query).sort([
                (sort_field, sort_direction),
                ("_id", sort_direction)
            ]).limit(limit + 1)
            
            docs = await mongo_cursor.to_list(length=limit + 1)
            
            # Check if more results exist
            has_more = len(docs) > limit
            if has_more:
                docs = docs[:limit]  # Remove extra item
            
            # Convert to responses
            products = [self._doc_to_response(doc) for doc in docs]
            
            # Generate next cursor
            next_cursor = None
            if has_more and docs:
                last_doc = docs[-1]
                cursor_obj = {
                    "value": last_doc.get(sort_field),
                    "id": str(last_doc["_id"])
                }
                next_cursor = base64.b64encode(json.dumps(cursor_obj).encode()).decode()
            
            return {
                "products": products,
                "pagination": {
                    "next_cursor": next_cursor,
                    "has_more": has_more,
                    "limit": limit
                }
            }
            
        except PyMongoError as e:
            logger.error(f"MongoDB error during cursor search: {e}")
            raise ErrorResponse("Database error during search", status_code=503)

    # ==================== SEO UPDATE METHOD ====================

    async def update_seo(self, product_id: str, seo_data: Dict[str, Any]) -> bool:
        """Update SEO metadata for a product"""
        try:
            if not ObjectId.is_valid(product_id):
                return False
            
            result = await self.collection.update_one(
                {"_id": ObjectId(product_id)},
                {
                    "$set": {
                        "seo": seo_data,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            return result.modified_count > 0
            
        except PyMongoError as e:
            logger.error(f"MongoDB error updating SEO: {e}")
            raise ErrorResponse("Database error during SEO update", status_code=503)
