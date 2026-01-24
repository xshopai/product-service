# Product Service - Architecture Document

## Table of Contents

1. [Overview](#1-overview)
   - 1.1 [Purpose](#11-purpose)
   - 1.2 [Scope](#12-scope)
   - 1.3 [Service Summary](#13-service-summary)
   - 1.4 [Directory Structure](#14-directory-structure)
   - 1.5 [Key Responsibilities](#15-key-responsibilities)
   - 1.6 [References](#16-references)
2. [System Context](#2-system-context)
   - 2.1 [Context Diagram](#21-context-diagram)
   - 2.2 [External Interfaces](#22-external-interfaces)
   - 2.3 [Dependencies](#23-dependencies)
3. [Data Architecture](#3-data-architecture)
   - 3.1 [Entity Relationship Diagram](#31-entity-relationship-diagram)
   - 3.2 [Database Schema](#32-database-schema)
   - 3.3 [Indexes](#33-indexes)
   - 3.4 [Caching Strategy](#34-caching-strategy)
   - 3.5 [Database Configuration](#35-database-configuration)
4. [API Design](#4-api-design)
   - 4.1 [Endpoint Summary](#41-endpoint-summary)
   - 4.2 [Request/Response Specifications](#42-requestresponse-specifications)
   - 4.3 [Error Response Format](#43-error-response-format)
   - 4.4 [Error Code Reference](#44-error-code-reference)
   - 4.5 [Authentication](#45-authentication)
5. [Event Architecture](#5-event-architecture)
   - 5.1 [Event Summary](#51-event-summary)
   - 5.2 [Published Events](#52-published-events)
   - 5.3 [Subscribed Events](#53-subscribed-events)
   - 5.4 [Dapr Configuration](#54-dapr-configuration)
   - 5.5 [Messaging Abstraction Layer](#55-messaging-abstraction-layer)
6. [Configuration](#6-configuration)
   - 6.1 [Environment Variables](#61-environment-variables)
   - 6.2 [Messaging Provider Configuration](#62-messaging-provider-configuration)
7. [Deployment](#7-deployment)
   - 7.1 [Deployment Targets](#71-deployment-targets)
8. [Observability](#8-observability)
   - 8.1 [Distributed Tracing](#81-distributed-tracing)
   - 8.2 [Structured Logging](#82-structured-logging)
   - 8.3 [Metrics & Alerting](#83-metrics--alerting)
9. [Error Handling](#9-error-handling)
   - 9.1 [Error Response Format](#91-error-response-format)
10. [Security](#10-security)
    - 10.1 [Authentication](#101-authentication)
    - 10.2 [Authorization](#102-authorization)
    - 10.3 [Service-to-Service Communication](#103-service-to-service-communication)
    - 10.4 [Input Validation](#104-input-validation)
    - 10.5 [CORS Configuration](#105-cors-configuration)

---

## 1. Overview

### 1.1 Purpose

The Product Service is a core microservice within the xshopai e-commerce platform responsible for managing the complete product catalog, including product information, taxonomy, search, and product discovery features. It serves as the **single source of truth** for product data across the platform.

### 1.2 Scope

#### In Scope

- Product catalog CRUD operations
- Product variations (parent-child relationships)
- Hierarchical taxonomy (Department → Category → Subcategory → Product Type)
- Product search with full-text search and filters
- Badge management (manual and automated)
- Bulk product import/export operations
- SEO metadata management
- Event publishing for product lifecycle changes
- Event consumption for denormalized data (reviews, inventory, analytics)
- Admin product management operations

#### Out of Scope

- Inventory management (handled by Inventory Service)
- Product reviews content (handled by Review Service)
- Product recommendations (future enhancement)
- Shopping cart management (handled by Cart Service)
- Order processing (handled by Order Service)
- Payment processing (handled by Payment Service)
- User authentication (handled by Auth Service)

### 1.3 Service Summary

| Attribute      | Value                              |
| -------------- | ---------------------------------- |
| Service Name   | product-service                    |
| Tech Stack     | Python 3.11+ / FastAPI 0.104+      |
| Database       | MongoDB 8.0+ (Motor async driver)  |
| Authentication | JWT (validated from auth-service)  |
| API Docs       | OpenAPI/Swagger (FastAPI built-in) |
| Messaging      | Dapr Pub/Sub (RabbitMQ backend)    |
| Main Port      | 8001                               |
| Dapr HTTP Port | 3501                               |
| Dapr gRPC Port | 50001                              |

### 1.4 Directory Structure

```
product-service/
├── .dapr/                      # Dapr configuration
│   ├── components/             # Pub/sub, state store, secret store
│   │   ├── pubsub.yaml         # RabbitMQ pub/sub component
│   │   ├── secretstore.yaml    # Local secrets component
│   │   └── statestore.yaml     # State store component
│   └── config.yaml             # Dapr configuration
├── .github/                    # GitHub workflows and copilot instructions
├── .vscode/                    # VS Code settings and tasks
├── docs/                       # Documentation
│   ├── ARCHITECTURE.md         # This file
│   ├── PRD.md                  # Product requirements document
│   └── ...                     # Other documentation
├── app/                        # Application source code
│   ├── api/                    # API endpoint handlers
│   │   ├── products.py         # Public product endpoints
│   │   ├── admin.py            # Admin product endpoints
│   │   ├── search.py           # Search endpoints
│   │   ├── variations.py       # Variation endpoints
│   │   └── health.py           # Health check endpoints
│   ├── core/                   # Core utilities
│   │   ├── config.py           # Configuration management
│   │   ├── exceptions.py       # Custom exception classes
│   │   └── logging.py          # Structured logging setup
│   ├── db/                     # Database connection
│   │   └── mongodb.py          # MongoDB connection setup
│   ├── events/                 # Event publishing
│   │   ├── publisher.py        # Dapr event publisher
│   │   └── consumers/          # Event consumers
│   ├── middleware/             # FastAPI middleware
│   │   ├── auth.py             # JWT authentication
│   │   ├── correlation.py      # Correlation ID tracking
│   │   └── error_handler.py    # Global error handler
│   ├── models/                 # Pydantic models
│   │   ├── product.py          # Product model
│   │   ├── variation.py        # Variation model
│   │   └── badge.py            # Badge model
│   ├── repositories/           # Data access layer
│   │   ├── product_repository.py
│   │   └── base_repository.py
│   ├── schemas/                # Request/Response schemas
│   │   ├── product_schemas.py
│   │   └── search_schemas.py
│   ├── services/               # Business logic layer
│   │   ├── product_service.py
│   │   ├── search_service.py
│   │   └── badge_service.py
│   └── dependencies/           # FastAPI dependencies
│       └── auth.py             # Auth dependencies
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── conftest.py             # Test fixtures
├── main.py                     # Application entry point
├── requirements.txt            # Production dependencies
├── requirements-dev.txt        # Development dependencies
├── docker-compose.yml          # Local development setup
├── Dockerfile                  # Container build instructions
├── run.ps1                     # Windows run script
└── run.sh                      # Linux/macOS run script
```

### 1.5 Key Responsibilities

1. **Product Management** - CRUD operations for products and variations
2. **Product Discovery** - Search, filtering, pagination, and autocomplete
3. **Event Publishing** - Publish `product.created`, `product.updated`, `product.deleted` events
4. **Event Consumption** - Sync denormalized data from Review, Inventory, and Analytics services
5. **Admin Operations** - Bulk imports, badge management, statistics

### 1.6 References

| Document             | Link                                                                  |
| -------------------- | --------------------------------------------------------------------- |
| PRD                  | [docs/PRD.md](./PRD.md)                                               |
| Copilot Instructions | [.github/copilot-instructions.md](../.github/copilot-instructions.md) |

---

## 2. System Context

### 2.1 Context Diagram

```mermaid
flowchart TB
    subgraph Users["<b>👤 USERS</b>"]
        Customer[("👤 Customer")]
        Admin[("🧑‍💼 Admin User")]
    end

    subgraph Clients["<b>📱 CLIENT APPLICATIONS</b>"]
        CustomerUI["🛍️ Customer UI<br/><i>Web/Mobile</i>"]
        AdminUI["🖥️ Admin UI<br/><i>Web Interface</i>"]
    end

    subgraph BFF["<b>🌐 BACKEND FOR FRONTEND</b>"]
        WebBFF["🔀 Web BFF<br/><i>API Gateway</i>"]
    end

    subgraph Core["<b>🎯 CORE SERVICE</b>"]
        PRODUCT["<b>Product Service</b><br/>━━━━━━━━━━━━━━━<br/>📦 Port: 8001<br/>Manages product catalog,<br/>search & discovery"]
    end

    subgraph Services["<b>🔗 DEPENDENT SERVICES</b>"]
        direction LR
        Order["🛒 Order Service<br/><i>Order Processing</i>"]
        Cart["🛒 Cart Service<br/><i>Cart Management</i>"]
        Review["⭐ Review Service<br/><i>Product Reviews</i>"]
        Inventory["📊 Inventory Service<br/><i>Stock Management</i>"]
    end

    subgraph EventConsumers["<b>📤 EVENT CONSUMERS</b>"]
        direction LR
        Audit["📋 Audit Service<br/><i>Audit Logging</i>"]
        Search["🔍 Search Service<br/><i>Search Index</i>"]
    end

    subgraph Infrastructure["<b>⚙️ INFRASTRUCTURE</b>"]
        direction TB
        MongoDB[("🗄️ MongoDB 8.x<br/>Port: 27017")]
        RabbitMQ[("🐰 RabbitMQ<br/>Message Broker<br/>Port: 5672")]
        Dapr["📡 Dapr Sidecar<br/>HTTP: 3501"]
        OTEL["📊 OpenTelemetry<br/>Collector"]
    end

    %% User flows
    Customer -->|"Uses"| CustomerUI
    Admin -->|"Uses"| AdminUI
    CustomerUI -->|"HTTP/REST"| WebBFF
    AdminUI -->|"HTTP/REST"| WebBFF
    WebBFF -->|"HTTP/REST<br/>Product Discovery"| PRODUCT

    %% Service integrations - HTTP
    Order -->|"HTTP GET<br/>Get Product Details"| PRODUCT
    Cart -->|"HTTP GET<br/>Validate Products"| PRODUCT

    %% Event flows - Inbound (consumed)
    Review -.->|"review.*"| RabbitMQ
    Inventory -.->|"inventory.*"| RabbitMQ
    RabbitMQ -.->|"Subscribe"| Dapr
    Dapr -.->|"Events"| PRODUCT

    %% Event flows - Outbound (published)
    PRODUCT -.->|"Publish"| Dapr
    Dapr -.->|"product.*"| RabbitMQ
    RabbitMQ -.->|"product.*"| Audit
    RabbitMQ -.->|"product.*"| Search

    %% Infrastructure connections
    PRODUCT -->|"MongoDB Queries"| MongoDB
    PRODUCT -->|"OTLP Traces"| OTEL

    %% Styling
    classDef core fill:#0969da,stroke:#0550ae,color:#fff,stroke-width:3px,font-weight:bold
    classDef user fill:#8250df,stroke:#6639ba,color:#fff,stroke-width:2px
    classDef client fill:#1f6feb,stroke:#1158c7,color:#fff,stroke-width:2px
    classDef bff fill:#6366f1,stroke:#4f46e5,color:#fff,stroke-width:2px
    classDef service fill:#0891b2,stroke:#0e7490,color:#fff,stroke-width:2px
    classDef consumer fill:#65a30d,stroke:#4d7c0f,color:#fff,stroke-width:2px
    classDef database fill:#059669,stroke:#047857,color:#fff,stroke-width:2px
    classDef broker fill:#f472b6,stroke:#db2777,color:#fff,stroke-width:2px
    classDef messaging fill:#d97706,stroke:#b45309,color:#fff,stroke-width:2px

    class PRODUCT core
    class Customer,Admin user
    class CustomerUI,AdminUI client
    class WebBFF bff
    class Order,Cart,Review,Inventory service
    class Audit,Search consumer
    class MongoDB database
    class RabbitMQ broker
    class Dapr messaging
```

### 2.2 External Interfaces

| System            | Direction | Protocol    | Description                                       |
| ----------------- | --------- | ----------- | ------------------------------------------------- |
| Order Service     | In        | HTTP        | Retrieves product details for order validation    |
| Cart Service      | In        | HTTP        | Validates products and retrieves product details  |
| Web BFF           | In        | HTTP        | Product discovery, search, and admin operations   |
| Review Service    | In        | Dapr Events | Consumes review events to update aggregates       |
| Inventory Service | In        | Dapr Events | Consumes inventory events to update availability  |
| Audit Service     | Out       | Dapr Events | Publishes product change events for audit logging |
| Search Service    | Out       | Dapr Events | Publishes product events for search index updates |
| MongoDB           | Out       | MongoDB     | Persistent storage for product data               |

### 2.3 Dependencies

#### 2.3.1 Upstream Dependencies

| Service      | Dependency Type | Purpose              |
| ------------ | --------------- | -------------------- |
| Auth Service | HTTP            | JWT token validation |

#### 2.3.2 Downstream Consumers

| Consumer       | Interface   | Data Provided             |
| -------------- | ----------- | ------------------------- |
| Order Service  | HTTP        | Product validation        |
| Cart Service   | HTTP        | Product details           |
| Web BFF        | HTTP        | Product discovery APIs    |
| Audit Service  | Dapr Events | Product lifecycle events  |
| Search Service | Dapr Events | Product data for indexing |

#### 2.3.3 Infrastructure Dependencies

| Component               | Purpose                       | Port/Connection          |
| ----------------------- | ----------------------------- | ------------------------ |
| MongoDB 8.x             | Persistent storage            | 27017 (configurable)     |
| Dapr Sidecar            | Pub/sub messaging             | HTTP: 3501, gRPC: 50001  |
| RabbitMQ (via Dapr)     | Message broker backend        | Abstracted by Dapr       |
| OpenTelemetry Collector | Distributed tracing & metrics | 4317 (gRPC), 4318 (HTTP) |

---

## 3. Data Architecture

### 3.1 Entity Relationship Diagram

```mermaid
erDiagram
    products ||--o{ variations : "has"
    products ||--o{ badges : "has"
    products ||--|| review_aggregates : "has"
    products ||--|| availability_status : "has"

    products {
        ObjectId _id PK
        string sku UK
        string name
        string description
        float price
        float compareAtPrice
        string status
        object taxonomy
        string variationType
        array images
        array tags
        object seo
        datetime createdAt
        datetime updatedAt
    }

    variations {
        ObjectId _id PK
        ObjectId parentId FK
        string sku UK
        object attributes
        float price
        array images
    }

    badges {
        ObjectId _id PK
        string type
        string label
        int priority
        datetime expiresAt
    }

    review_aggregates {
        float averageRating
        int totalReviewCount
        int verifiedReviewCount
        datetime lastUpdated
    }

    availability_status {
        string status
        int availableQuantity
        datetime lastUpdated
    }
```

### 3.2 Database Schema

#### 3.2.1 products Collection

| Field                | Type     | Constraints             | Description                      |
| -------------------- | -------- | ----------------------- | -------------------------------- |
| `_id`                | ObjectId | PK, AUTO                | Primary key                      |
| `sku`                | String   | UNIQUE, NOT NULL, INDEX | Stock keeping unit               |
| `name`               | String   | NOT NULL, MAX 200       | Product name                     |
| `description`        | String   | MAX 5000                | Product description              |
| `price`              | Float    | NOT NULL, > 0           | Current price                    |
| `compareAtPrice`     | Float    | >= 0                    | Original price (for discounts)   |
| `status`             | String   | ENUM                    | active, inactive, draft, deleted |
| `taxonomy`           | Object   | Embedded                | Department/category/subcategory  |
| `variationType`      | String   | ENUM                    | standalone, parent, child        |
| `parentId`           | ObjectId | FK, INDEX               | Reference to parent product      |
| `images`             | Array    | Embedded                | Product images with URLs         |
| `tags`               | Array    | INDEX                   | Product tags for filtering       |
| `badges`             | Array    | Embedded                | Assigned badges                  |
| `reviewAggregates`   | Object   | Embedded                | Denormalized review data         |
| `availabilityStatus` | Object   | Embedded                | Denormalized inventory data      |
| `seo`                | Object   | Embedded                | SEO metadata                     |
| `createdAt`          | DateTime | AUTO                    | Record creation timestamp        |
| `updatedAt`          | DateTime | AUTO                    | Last modification timestamp      |

#### 3.2.2 taxonomy Subdocument

| Field         | Type   | Description                    |
| ------------- | ------ | ------------------------------ |
| `department`  | String | Top-level category (e.g., Men) |
| `category`    | String | Category (e.g., Clothing)      |
| `subcategory` | String | Subcategory (e.g., T-Shirts)   |
| `productType` | String | Product type (e.g., Graphic)   |

#### 3.2.3 reviewAggregates Subdocument

| Field                 | Type     | Description               |
| --------------------- | -------- | ------------------------- |
| `averageRating`       | Float    | Average rating (0-5)      |
| `totalReviewCount`    | Int      | Total number of reviews   |
| `verifiedReviewCount` | Int      | Verified purchase reviews |
| `ratingDistribution`  | Object   | Count per rating (1-5)    |
| `lastUpdated`         | DateTime | Last update timestamp     |

#### 3.2.4 availabilityStatus Subdocument

| Field               | Type     | Description                       |
| ------------------- | -------- | --------------------------------- |
| `status`            | String   | in_stock, low_stock, out_of_stock |
| `availableQuantity` | Int      | Current available quantity        |
| `lastUpdated`       | DateTime | Last update timestamp             |

### 3.3 Indexes

| Collection | Index Name          | Fields                        | Type     | Purpose               |
| ---------- | ------------------- | ----------------------------- | -------- | --------------------- |
| products   | `_id_`              | `_id`                         | B-tree   | Primary key lookup    |
| products   | `sku_1`             | `sku`                         | Unique   | SKU lookup            |
| products   | `status_1`          | `status`                      | B-tree   | Status filtering      |
| products   | `taxonomy_category` | `taxonomy.category`, `status` | Compound | Category browsing     |
| products   | `text_search`       | `name`, `description`         | Text     | Full-text search      |
| products   | `parentId_1`        | `parentId`                    | Sparse   | Variation lookup      |
| products   | `tags_1`            | `tags`                        | B-tree   | Tag-based filtering   |
| products   | `createdAt_-1`      | `createdAt`                   | B-tree   | Recent products query |

### 3.4 Caching Strategy

> **Current Status:** Caching is **not implemented** in the current codebase.

| Aspect          | Current State           | Future Recommendation                     |
| --------------- | ----------------------- | ----------------------------------------- |
| Cache Layer     | Not implemented         | Redis with Dapr State Store               |
| Product Details | Direct database queries | Cache with 5min TTL, invalidate on update |
| Search Results  | Direct database queries | Cache with 1min TTL                       |
| Categories      | Direct database queries | Cache with 1hr TTL                        |

### 3.5 Database Configuration

Database connection is configured via environment variables.

**Connection String Format:** `mongodb://{user}:{password}@{host}:{port}/{database}`

---

## 4. API Design

### 4.1 Endpoint Summary

| Method   | Endpoint                                       | Description                     | Auth      |
| -------- | ---------------------------------------------- | ------------------------------- | --------- |
| `GET`    | `/health`                                      | Liveness probe                  | None      |
| `GET`    | `/health/ready`                                | Readiness probe                 | None      |
| `GET`    | `/api/products`                                | List products with filters      | None      |
| `GET`    | `/api/products/{id}`                           | Get product by ID               | None      |
| `GET`    | `/api/products/categories`                     | Get all categories              | None      |
| `GET`    | `/api/products/internal/{id}/exists`           | Check product existence         | None      |
| `POST`   | `/api/products/batch`                          | Batch product lookup            | None      |
| `GET`    | `/api/products/{id}/variations`                | Get product variations          | None      |
| `GET`    | `/api/products/search`                         | Search (offset pagination)      | None      |
| `GET`    | `/api/products/search/cursor`                  | Search (cursor pagination)      | None      |
| `GET`    | `/api/products/category/{path}`                | Get products by category        | None      |
| `GET`    | `/api/products/autocomplete`                   | Autocomplete suggestions        | None      |
| `GET`    | `/api/products/trending`                       | Get trending products           | None      |
| `POST`   | `/api/admin/products`                          | Create product                  | Admin JWT |
| `PUT`    | `/api/admin/products/{id}`                     | Update product                  | Admin JWT |
| `DELETE` | `/api/admin/products/{id}`                     | Delete product (soft)           | Admin JWT |
| `PATCH`  | `/api/admin/products/{id}/reactivate`          | Reactivate soft-deleted product | Admin JWT |
| `POST`   | `/api/admin/products/variations`               | Create parent with variations   | Admin JWT |
| `POST`   | `/api/admin/products/{id}/variations`          | Add variation to parent         | Admin JWT |
| `POST`   | `/api/admin/products/{id}/badges`              | Assign badge to product         | Admin JWT |
| `DELETE` | `/api/admin/products/{id}/badges/{badgeId}`    | Remove badge from product       | Admin JWT |
| `POST`   | `/api/admin/products/badges/bulk`              | Bulk badge assignment           | Admin JWT |
| `PUT`    | `/api/admin/products/{id}/seo`                 | Update SEO metadata             | Admin JWT |
| `POST`   | `/api/admin/products/bulk/import`              | Bulk import (async)             | Admin JWT |
| `GET`    | `/api/admin/products/bulk/jobs/{jobId}`        | Get bulk import status          | Admin JWT |
| `GET`    | `/api/admin/products/bulk/template`            | Download import template        | Admin JWT |
| `GET`    | `/api/admin/products/bulk/jobs/{jobId}/errors` | Get bulk import errors          | Admin JWT |
| `POST`   | `/api/admin/products/bulk/images`              | Bulk image upload (ZIP)         | Admin JWT |
| `GET`    | `/api/admin/products/stats`                    | Get product statistics          | Admin JWT |

**Authentication Types:**

- **None**: Public endpoints (health checks, product discovery)
- **Admin JWT**: Admin operations requiring `role: admin` in JWT

### 4.2 Request/Response Specifications

#### 4.2.1 Get Product by ID

**Endpoint:** `GET /api/products/{id}`

**Authentication:** None (public endpoint)

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "id": "507f1f77bcf86cd799439011",
    "sku": "TS-BLK-001",
    "name": "Classic Black T-Shirt",
    "description": "Premium cotton t-shirt",
    "price": 29.99,
    "compareAtPrice": 39.99,
    "status": "active",
    "taxonomy": {
      "department": "Men",
      "category": "Clothing",
      "subcategory": "T-Shirts"
    },
    "images": [{ "url": "https://...", "alt": "Front view" }],
    "reviewAggregates": {
      "averageRating": 4.5,
      "totalReviewCount": 128
    },
    "availabilityStatus": {
      "status": "in_stock",
      "availableQuantity": 50
    }
  }
}
```

#### 4.2.2 Create Product (Admin)

**Endpoint:** `POST /api/admin/products`

**Authentication:** Admin JWT Required

**Request Body:**

```json
{
  "sku": "TS-BLK-002",
  "name": "Premium Black T-Shirt",
  "description": "Ultra-soft premium cotton",
  "price": 34.99,
  "taxonomy": {
    "department": "Men",
    "category": "Clothing",
    "subcategory": "T-Shirts"
  },
  "tags": ["cotton", "premium", "casual"]
}
```

**Response (201 Created):**

```json
{
  "success": true,
  "message": "Product created successfully",
  "data": {
    "id": "507f1f77bcf86cd799439012",
    "sku": "TS-BLK-002",
    "name": "Premium Black T-Shirt",
    "status": "active",
    "createdAt": "2025-01-24T10:30:00Z"
  }
}
```

#### 4.2.3 Search Products

**Endpoint:** `GET /api/products/search`

**Query Parameters:**

| Parameter  | Type    | Required | Default   | Description              |
| ---------- | ------- | -------- | --------- | ------------------------ |
| `q`        | string  | No       | -         | Search query             |
| `category` | string  | No       | -         | Category filter          |
| `minPrice` | float   | No       | -         | Minimum price            |
| `maxPrice` | float   | No       | -         | Maximum price            |
| `page`     | integer | No       | 1         | Page number              |
| `limit`    | integer | No       | 20        | Items per page (max 100) |
| `sort`     | string  | No       | relevance | Sort order               |

**Response (200 OK):**

```json
{
  "success": true,
  "data": {
    "products": [...],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 150,
      "pages": 8
    }
  }
}
```

### 4.3 Error Response Format

All API errors return a consistent JSON structure:

```json
{
  "success": false,
  "error": "ERROR_CODE",
  "message": "Human-readable error description",
  "details": {},
  "correlationId": "req-abc-123-def-456",
  "timestamp": "2025-01-24T10:30:00Z"
}
```

### 4.4 Error Code Reference

| Code                    | HTTP Status | Description                   |
| ----------------------- | ----------- | ----------------------------- |
| `VALIDATION_ERROR`      | 400         | Request validation failed     |
| `DUPLICATE_SKU`         | 409         | SKU already exists            |
| `PRODUCT_NOT_FOUND`     | 404         | Product does not exist        |
| `UNAUTHORIZED`          | 401         | Missing or invalid JWT        |
| `FORBIDDEN`             | 403         | Admin role required           |
| `INVALID_CATEGORY`      | 400         | Invalid taxonomy category     |
| `BULK_IMPORT_FAILED`    | 400         | Bulk import validation failed |
| `INTERNAL_SERVER_ERROR` | 500         | Unexpected server error       |

### 4.5 Authentication

> **Complete Details:** See **Section 10 - Security** for comprehensive authentication documentation.

**Quick Reference:**

| Auth Type | Header                        | Used By                   |
| --------- | ----------------------------- | ------------------------- |
| None      | -                             | Health, product discovery |
| Admin JWT | `Authorization: Bearer <jwt>` | Admin operations          |

---

## 5. Event Architecture

Product Service participates in the xshopai event-driven architecture as both a **Publisher** and **Consumer** via **Dapr Pub/Sub**.

### 5.1 Event Summary

#### Published Events

| Event Name               | Trigger          | Primary Consumer(s)         | Priority |
| ------------------------ | ---------------- | --------------------------- | -------- |
| `product.created`        | Product creation | Audit, Search Service       | High     |
| `product.updated`        | Product update   | Audit, Search Service       | Medium   |
| `product.deleted`        | Product deletion | Audit, Search, Cart Service | High     |
| `product.price.changed`  | Price change     | Cart Service, Notification  | High     |
| `product.badge.assigned` | Badge added      | Audit Service               | Low      |
| `product.badge.removed`  | Badge removed    | Audit Service               | Low      |

#### Subscribed Events

| Event Name                | Source            | Purpose                    |
| ------------------------- | ----------------- | -------------------------- |
| `review.created`          | Review Service    | Update review aggregates   |
| `review.updated`          | Review Service    | Update review aggregates   |
| `review.deleted`          | Review Service    | Update review aggregates   |
| `inventory.stock.updated` | Inventory Service | Update availability status |

---

### 5.2 Published Events

All events use **CloudEvents 1.0** envelope with `source: "product-service"`.

#### 5.2.1 product.created

**Trigger:** New product creation

**Payload:**

```json
{
  "specversion": "1.0",
  "type": "product.created",
  "source": "product-service",
  "id": "evt-550e8400-e29b-41d4-a716-446655440000",
  "time": "2025-01-24T10:30:00Z",
  "datacontenttype": "application/json",
  "data": {
    "productId": "507f1f77bcf86cd799439011",
    "sku": "TS-BLK-001",
    "name": "Classic Black T-Shirt",
    "price": 29.99,
    "status": "active",
    "category": "Clothing"
  },
  "metadata": {
    "correlationId": "req-xyz-789"
  }
}
```

#### 5.2.2 product.updated

**Trigger:** Product information changed

**Payload:**

```json
{
  "specversion": "1.0",
  "type": "product.updated",
  "source": "product-service",
  "id": "evt-660e8400-e29b-41d4-a716-446655440001",
  "time": "2025-01-24T11:00:00Z",
  "data": {
    "productId": "507f1f77bcf86cd799439011",
    "updatedFields": ["price", "description"],
    "updatedAt": "2025-01-24T11:00:00Z"
  }
}
```

---

### 5.3 Subscribed Events

Product Service consumes events to maintain denormalized data.

#### 5.3.1 Review Events

**Events:** `review.created`, `review.updated`, `review.deleted`

**Purpose:** Update `reviewAggregates` subdocument

**Processing:**

- Recalculate average rating
- Update review count
- Update rating distribution

#### 5.3.2 Inventory Events

**Events:** `inventory.stock.updated`

**Purpose:** Update `availabilityStatus` subdocument

**Processing:**

- Update available quantity
- Set status (in_stock, low_stock, out_of_stock)

---

### 5.4 Dapr Configuration

#### 5.4.1 Pub/Sub Component (RabbitMQ)

File: `.dapr/components/pubsub.yaml`

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: xshopai-pubsub
spec:
  type: pubsub.rabbitmq
  version: v1
  metadata:
    - name: connectionString
      value: 'amqp://guest:guest@127.0.0.1:5672'
    - name: durable
      value: 'true'
    - name: deliveryMode
      value: '2'
scopes:
  - product-service
```

---

### 5.5 Messaging Abstraction Layer

To support **deployment flexibility**, the Product Service implements a messaging abstraction layer.

| Deployment Target          | Dapr Available | Recommended Provider |
| -------------------------- | -------------- | -------------------- |
| **Azure Container Apps**   | ✅ Yes         | `DaprProvider`       |
| **Azure Kubernetes (AKS)** | ✅ Yes         | `DaprProvider`       |
| **Local Development**      | ✅ Optional    | `DaprProvider`       |

---

## 6. Configuration

### 6.1 Environment Variables

| Variable           | Description                 | Required | Default          |
| ------------------ | --------------------------- | -------- | ---------------- |
| `ENVIRONMENT`      | Environment mode            | No       | `development`    |
| `PORT`             | Service port                | No       | `8001`           |
| `HOST`             | Service host                | No       | `0.0.0.0`        |
| `LOG_LEVEL`        | Logging level               | No       | `INFO`           |
| `DAPR_HOST`        | Dapr sidecar host           | No       | `localhost`      |
| `DAPR_HTTP_PORT`   | Dapr HTTP port              | No       | `3501`           |
| `DAPR_GRPC_PORT`   | Dapr gRPC port              | No       | `50001`          |
| `DAPR_PUBSUB_NAME` | Dapr pub/sub component name | No       | `xshopai-pubsub` |

#### MongoDB Configuration

| Variable           | Description       | Example                     |
| ------------------ | ----------------- | --------------------------- |
| `MONGODB_URI`      | Connection string | `mongodb://localhost:27017` |
| `MONGODB_DATABASE` | Database name     | `product_service_db`        |

### 6.2 Messaging Provider Configuration

| Variable           | Description            | Required           |
| ------------------ | ---------------------- | ------------------ |
| `DAPR_HTTP_PORT`   | Dapr sidecar HTTP port | No (default: 3501) |
| `DAPR_PUBSUB_NAME` | Pub/sub component name | Yes                |

---

## 7. Deployment

### 7.1 Deployment Targets

| Target                 | Messaging Provider | Notes                           |
| ---------------------- | ------------------ | ------------------------------- |
| Local (Docker Compose) | `dapr`             | Uses Dapr sidecar with RabbitMQ |
| Azure Container Apps   | `dapr`             | Managed Dapr integration        |
| AKS                    | `dapr`             | Self-managed Dapr               |

---

## 8. Observability

### 8.1 Distributed Tracing

Every request and event carries a correlation ID for end-to-end tracing.

| Header             | Description            | Example                            |
| ------------------ | ---------------------- | ---------------------------------- |
| `X-Correlation-ID` | Request correlation ID | `req-abc-123-def-456`              |
| `X-Trace-ID`       | Distributed trace ID   | `0af7651916cd43dd8448eb211c80319c` |

---

### 8.2 Structured Logging

All logs use JSON structured format:

```json
{
  "timestamp": "2025-01-24T10:30:00.123Z",
  "level": "info",
  "service": "product-service",
  "correlationId": "req-abc-123",
  "message": "Product created successfully",
  "metadata": {
    "productId": "507f1f77bcf86cd799439011",
    "sku": "TS-BLK-001"
  }
}
```

---

### 8.3 Metrics & Alerting

#### Business Metrics

| Metric Name                | Type    | Description         |
| -------------------------- | ------- | ------------------- |
| `products_total`           | Gauge   | Total product count |
| `products_created_total`   | Counter | Products created    |
| `products_deleted_total`   | Counter | Products deleted    |
| `product_events_published` | Counter | Events published    |

#### Technical Metrics

| Metric Name                | Type      | Description         |
| -------------------------- | --------- | ------------------- |
| `http_requests_total`      | Counter   | HTTP requests count |
| `http_request_duration_ms` | Histogram | Request latency     |
| `db_query_duration_ms`     | Histogram | DB query latency    |

---

## 9. Error Handling

### 9.1 Error Response Format

All API errors return a consistent structure:

```json
{
  "success": false,
  "error": "PRODUCT_NOT_FOUND",
  "message": "Product not found",
  "correlationId": "req-abc-123-def-456",
  "timestamp": "2025-01-24T10:30:00Z"
}
```

**Error Categories:**

| HTTP Status | Category       | Retryable |
| ----------- | -------------- | --------- |
| 400         | Client Error   | No        |
| 401         | Authentication | No        |
| 403         | Authorization  | No        |
| 404         | Not Found      | No        |
| 409         | Conflict       | No        |
| 500         | Server Error   | Yes       |

---

## 10. Security

### 10.1 Authentication

Product Service uses a **layered authentication model**.

| Auth Type | Purpose                  | Used By          |
| --------- | ------------------------ | ---------------- |
| None      | Public product discovery | Customer UI      |
| Admin JWT | Admin operations         | Admin UI via BFF |

### 10.2 Authorization

| Auth Type | Authorized Operations                        |
| --------- | -------------------------------------------- |
| None      | Health endpoints, product discovery          |
| Admin JWT | Create, update, delete products, bulk import |

#### Endpoint Authorization Matrix

| Endpoint Pattern      | Required Auth | Additional Rules |
| --------------------- | ------------- | ---------------- |
| `GET /health/*`       | None          | Public           |
| `GET /api/products/*` | None          | Public           |
| `POST /api/admin/*`   | Admin JWT     | Admin role       |
| `PUT /api/admin/*`    | Admin JWT     | Admin role       |
| `DELETE /api/admin/*` | Admin JWT     | Admin role       |

### 10.3 Service-to-Service Communication

Other services call Product Service APIs using direct HTTP with service tokens.

| Header             | Value                    | Purpose             |
| ------------------ | ------------------------ | ------------------- |
| `X-Service-Token`  | Pre-shared service token | Authentication      |
| `X-Correlation-ID` | Request correlation ID   | Distributed tracing |
| `X-Service-Name`   | Calling service name     | Audit logging       |

### 10.4 Input Validation

All input is validated using Pydantic models:

| Field         | Validation Rules                      |
| ------------- | ------------------------------------- |
| `sku`         | Required, unique, max 50 chars        |
| `name`        | Required, max 200 chars               |
| `price`       | Required, > 0                         |
| `description` | Max 5000 chars                        |
| `taxonomy`    | Valid department/category/subcategory |

### 10.5 CORS Configuration

Cross-Origin Resource Sharing is configured for frontend access.

**Allowed Origins (Development):**

- `http://localhost:3000` (Customer UI)
- `http://localhost:3001` (Admin UI)

---

## Document History

| Version | Date       | Author | Changes              |
| ------- | ---------- | ------ | -------------------- |
| 1.0     | 2025-01-24 | Team   | Initial architecture |
