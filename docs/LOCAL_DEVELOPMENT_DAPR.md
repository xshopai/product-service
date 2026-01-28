# Product Service - Local Development with Dapr

This guide explains how to run the Product Service locally **with Dapr sidecar** for full event-driven development. For basic development without Dapr, see [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md).

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Dapr Installation](#3-dapr-installation)
4. [Dapr Initialization](#4-dapr-initialization)
5. [Environment Configuration](#5-environment-configuration)
6. [Dapr Component Configuration](#6-dapr-component-configuration)
7. [Secrets Configuration](#7-secrets-configuration)
8. [Starting the Service with Dapr](#8-starting-the-service-with-dapr)
9. [Verifying the Setup](#9-verifying-the-setup)
10. [Dapr Dashboard](#10-dapr-dashboard)
11. [Testing Events](#11-testing-events)
12. [Stopping the Service](#12-stopping-the-service)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Overview

### Why Use Dapr?

The Product Service uses Dapr for:

- **Pub/Sub:** Publishing product events (created, updated, deleted)
- **Pub/Sub:** Consuming events from other services (reviews, inventory, analytics)
- **Service Invocation:** Communicating with other microservices
- **Secrets Management:** Secure access to configuration secrets

### Service Configuration

| Property           | Value           |
| ------------------ | --------------- |
| **Service Name**   | product-service |
| **App Port**       | 8001            |
| **Dapr HTTP Port** | 3500            |
| **Dapr gRPC Port** | 50001           |
| **Pub/Sub Name**   | xshopai-pubsub  |
| **State Store**    | statestore      |

> **Note:** All services now use the standard Dapr ports (3500 for HTTP, 50001 for gRPC). This simplifies configuration and works consistently whether running via Docker Compose or individual service runs.

### Architecture with Dapr

```
┌─────────────────────────────────────────────────────────┐
│                    Product Service                       │
│                     (Port 8001)                          │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   Dapr Sidecar                          │
│          HTTP: 3500    gRPC: 50001                      │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ Pub/Sub  │  │Secrets   │  │ Service Invocation   │  │
│  │(RabbitMQ)│  │  Store   │  │                      │  │
│  └──────────┘  └──────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Prerequisites

### Required Software

| Software | Version | Purpose                                    |
| -------- | ------- | ------------------------------------------ |
| Python   | 3.11+   | Runtime environment                        |
| Docker   | 24+     | Running infrastructure (MongoDB, RabbitMQ) |
| Dapr CLI | 1.13+   | Dapr runtime management                    |
| MongoDB  | 8.0+    | Primary database                           |
| RabbitMQ | 3.12+   | Event message broker                       |

### Verify Prerequisites

```bash
# Python version
python --version  # 3.11+

# Docker version
docker --version  # 24+

# Dapr CLI version
dapr --version    # 1.13+
```

---

## 3. Dapr Installation

### Windows (PowerShell as Administrator)

```powershell
# Install Dapr CLI using winget
winget install Dapr.CLI

# Or using PowerShell script
powershell -Command "iwr -useb https://raw.githubusercontent.com/dapr/cli/master/install/install.ps1 | iex"

# Verify installation
dapr --version
```

### macOS

```bash
# Using Homebrew
brew install dapr/tap/dapr-cli

# Verify installation
dapr --version
```

### Linux

```bash
# Download and install
wget -q https://raw.githubusercontent.com/dapr/cli/master/install/install.sh -O - | /bin/bash

# Verify installation
dapr --version
```

---

## 4. Dapr Initialization

### Initialize Dapr Runtime

```bash
# Initialize Dapr with default configuration
dapr init

# Verify Dapr is running
dapr --version
docker ps | grep dapr
```

### Expected Output

After initialization, you should see these Docker containers:

```
CONTAINER ID   IMAGE                     PORTS                    NAMES
xxx            daprio/dapr:1.13.x        ...                      dapr_placement
xxx            redis:7                   0.0.0.0:6379->6379/tcp   dapr_redis
xxx            openzipkin/zipkin         0.0.0.0:9411->9411/tcp   dapr_zipkin
```

---

## 5. Environment Configuration

### Configure Environment for Dapr Mode

Copy the Dapr environment template to `.env`:

```bash
# On Linux / Mac / Bash:
cp .env.dapr .env

# On Windows (PowerShell):
Copy-Item .env.dapr .env
```

The `.env.dapr` file contains:

```bash
# Service Configuration
NAME=product-service
VERSION=1.0.0
PORT=8001
HOST=0.0.0.0
ENVIRONMENT=development

# Logging
LOG_LEVEL=DEBUG
LOG_FORMAT=console
LOG_TO_CONSOLE=true
LOG_TO_FILE=false
LOG_FILE_PATH=./logs/product-service.log

# Dapr Configuration
DAPR_HOST=localhost
DAPR_HTTP_PORT=3500
DAPR_GRPC_PORT=50001
DAPR_APP_ID=product-service
DAPR_PUBSUB_NAME=xshopai-pubsub

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:3001

# Service Tokens (for service-to-service communication)
ORDER_SERVICE_TOKEN=svc-order-service-4ff5876fc86cc45a18d88e5d
CART_SERVICE_TOKEN=svc-cart-service-4ff5876fc86cc45a18d88e5d
INVENTORY_SERVICE_TOKEN=svc-inventory-service-4ff5876fc86cc45a18d88e5d
WEB_BFF_TOKEN=svc-web-bff-4ff5876fc86cc45a18d88e5d
```

> **Note:**
>
> - When using Dapr mode, `MONGODB_URI` and `JWT_PUBLIC_KEY` are retrieved from the Dapr secret store (configured in `.dapr/secrets.json`)
> - The Dapr sidecar handles RabbitMQ connections using the configuration in `.dapr/components/pubsub.yaml`
> - If Dapr secret store fails, the service falls back to environment variables

---

## 6. Dapr Component Configuration

### 6.1 Directory Structure

Create the `.dapr` directory structure:

```
product-service/
├── .dapr/
│   ├── components/
│   │   ├── pubsub.yaml
│   │   ├── statestore.yaml
│   │   └── secretstore.yaml
│   └── config.yaml
```

### 6.2 Pub/Sub Component (RabbitMQ)

Create `.dapr/components/pubsub.yaml`:

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: xshopai-pubsub
spec:
  type: pubsub.rabbitmq
  version: v1
  metadata:
    - name: host
      value: 'amqp://guest:guest@localhost:5672'
    - name: durable
      value: 'true'
    - name: deletedWhenUnused
      value: 'false'
    - name: autoAck
      value: 'false'
    - name: deliveryMode
      value: '2'
    - name: requeueInFailure
      value: 'true'
    - name: prefetchCount
      value: '10'
scopes:
  - product-service
```

### 6.3 State Store Component (Redis)

Create `.dapr/components/statestore.yaml`:

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: statestore
spec:
  type: state.redis
  version: v1
  metadata:
    - name: redisHost
      value: 'localhost:6379'
    - name: redisPassword
      value: ''
    - name: actorStateStore
      value: 'true'
scopes:
  - product-service
```

### 6.4 Secret Store Component (Local File)

Create `.dapr/components/secretstore.yaml`:

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: local-secret-store
spec:
  type: secretstores.local.file
  version: v1
  metadata:
    - name: secretsFile
      value: '.dapr/secrets.json'
    - name: nestedSeparator
      value: ':'
scopes:
  - product-service
```

### 6.5 Dapr Configuration

Create `.dapr/config.yaml`:

```yaml
apiVersion: dapr.io/v1alpha1
kind: Configuration
metadata:
  name: daprConfig
spec:
  tracing:
    samplingRate: '1'
    zipkin:
      endpointAddress: 'http://localhost:9411/api/v2/spans'
  metric:
    enabled: true
  logging:
    apiLogging:
      enabled: true
      obfuscateURLs: false
```

---

## 7. Secrets Configuration

### Create Secrets File

If using Dapr secret store, create `.dapr/secrets.json`:

```json
{
  "MONGODB_URI": "mongodb://admin:admin123@localhost:27017/product_service_db?authSource=admin",
  "MONGODB_DATABASE": "product_service_db",
  "JWT_PUBLIC_KEY": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...\n-----END PUBLIC KEY-----"
}
```

> **Note:** Use UPPER_SNAKE_CASE for secret names to match platform conventions (`.env` files, user-service, inventory-service, etc.).

> **Security Note:** This file is gitignored. Never commit secrets.json to version control.

---

## 8. Starting the Service with Dapr

### 8.1 Start Infrastructure First

Ensure MongoDB and RabbitMQ are running:

```bash
# Start MongoDB
docker run -d \
  --name product-mongodb \
  -p 27017:27017 \
  mongo:8.0

# Start RabbitMQ
docker run -d \
  --name product-rabbitmq \
  -p 5672:5672 \
  -p 15672:15672 \
  rabbitmq:3-management
```

### 8.2 Start Service with Dapr Sidecar

**Option A: Using Dapr CLI**

```bash
dapr run \
  --app-id product-service \
  --app-port 8001 \
  --dapr-http-port 3500 \
  --dapr-grpc-port 50001 \
  --resources-path .dapr/components \
  --config .dapr/config.yaml \
  --log-level warn \
  -- uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

**Option B: Using VS Code Task**

Use the pre-configured VS Code task (press `Ctrl+Shift+P`, then "Tasks: Run Task" → "Start Dapr Sidecar").

**Option C: Using Run Script**

**Windows:**

```powershell
.\run-dapr.ps1
```

**macOS/Linux:**

```bash
./run-dapr.sh
```

### Expected Output

```
ℹ️  Starting Dapr with id product-service. HTTP Port: 3500. gRPC Port: 50001
INFO[0000] Starting Dapr Runtime -- version 1.13.x
INFO[0000] Dapr initialized.
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

---

## 9. Verifying the Setup

### 9.1 Health Checks

```bash
# Direct service health
curl http://localhost:8001/health

# Via Dapr sidecar
curl http://localhost:3500/v1.0/healthz

# Via Dapr invoke
curl http://localhost:3500/v1.0/invoke/product-service/method/health
```

### 9.2 Check Dapr Components

```bash
# List loaded components
curl http://localhost:3500/v1.0/metadata

# Expected response includes:
# - xshopai-pubsub (pub/sub)
# - statestore (state store)
# - local-secret-store (secret store)
```

### 9.3 Test Pub/Sub

```bash
# Publish a test event
curl -X POST http://localhost:3500/v1.0/publish/xshopai-pubsub/product.test \
  -H "Content-Type: application/json" \
  -d '{"message": "Test event from Product Service"}'

# Should return HTTP 204 No Content on success
```

### 9.4 Test Service Invocation

```bash
# Invoke service via Dapr
curl http://localhost:3500/v1.0/invoke/product-service/method/api/products/search

# With parameters
curl "http://localhost:3500/v1.0/invoke/product-service/method/api/products/search?q=test"
```

---

## 10. Dapr Dashboard

### Start Dashboard

```bash
dapr dashboard
```

Open http://localhost:8080 in your browser.

### Dashboard Features

| Tab               | Description                                       |
| ----------------- | ------------------------------------------------- |
| **Overview**      | Running applications and their status             |
| **Applications**  | Detailed view of each Dapr application            |
| **Components**    | Configured Dapr components (pub/sub, state, etc.) |
| **Configuration** | Active Dapr configurations                        |

---

## 11. Testing Events

### 11.1 Publish Product Event

```bash
# Create a product to trigger product.created event
curl -X POST http://localhost:8001/api/products \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin-token>" \
  -d '{
    "name": "Test Product",
    "price": 29.99,
    "sku": "TEST-EVENT-001",
    "brand": "TestBrand"
  }'
```

### 11.2 Monitor Events in RabbitMQ

Access RabbitMQ Management UI at http://localhost:15672 (guest/guest):

1. Navigate to **Queues** tab
2. Look for queues prefixed with `product.`
3. Check message rates and counts

### 11.3 Simulate Incoming Event

```bash
# Simulate a review.created event
curl -X POST http://localhost:3500/v1.0/publish/xshopai-pubsub/review.created \
  -H "Content-Type: application/json" \
  -d '{
    "eventType": "review.created",
    "data": {
      "reviewId": "review-123",
      "productId": "507f1f77bcf86cd799439011",
      "rating": 5,
      "verified": true
    }
  }'
```

---

## 12. Stopping the Service

### Stop Dapr Application

```bash
# Stop specific app
dapr stop --app-id product-service

# Verify stopped
dapr list
```

### Stop All Dapr Applications

```bash
dapr stop --all
```

### Stop Infrastructure Containers

```bash
# Stop individual containers
docker stop product-mongodb product-rabbitmq

# Or stop all related containers
docker stop product-mongodb product-rabbitmq
docker rm product-mongodb product-rabbitmq
```

### Using VS Code Task

Press `Ctrl+Shift+P`, then "Tasks: Run Task" → "Stop Dapr Sidecar".

---

## 13. Troubleshooting

### Issue: Dapr Sidecar Not Starting

**Symptoms:** `connection refused` errors

**Solutions:**

1. Check if Dapr is initialized:

   ```bash
   dapr --version
   docker ps | grep dapr
   ```

2. Re-initialize Dapr:
   ```bash
   dapr uninstall --all
   dapr init
   ```

### Issue: Pub/Sub Not Working

**Symptoms:** Events not being published/received

**Solutions:**

1. Verify RabbitMQ is running:

   ```bash
   docker ps | grep rabbitmq
   ```

2. Check RabbitMQ Management UI: http://localhost:15672

3. Verify component configuration:

   ```bash
   curl http://localhost:3500/v1.0/metadata
   ```

4. Check Dapr logs:
   ```bash
   dapr logs --app-id product-service
   ```

### Issue: Component Not Loading

**Symptoms:** Component missing from `/v1.0/metadata`

**Solutions:**

1. Verify component file syntax:

   ```bash
   # Validate YAML
   yamllint .dapr/components/pubsub.yaml
   ```

2. Check component scopes include `product-service`

3. Restart Dapr with correct resources path:
   ```bash
   dapr run --resources-path .dapr/components ...
   ```

### Issue: Service Invocation Failing

**Symptoms:** 404 or 500 errors on Dapr invoke

**Solutions:**

1. Verify app-id matches:

   ```bash
   dapr list  # Check app-id is correct
   ```

2. Ensure service is listening on correct port

3. Check Dapr sidecar health:
   ```bash
   curl http://localhost:3500/v1.0/healthz
   ```

### Issue: Port Conflicts

**Symptoms:** `Address already in use`

**Solutions:**

```bash
# Find process using the port
# Windows
netstat -ano | findstr :8001
netstat -ano | findstr :3500

# Kill the process
taskkill /F /PID <PID>

# macOS/Linux
lsof -i :8001
kill -9 <PID>
```

---

## Quick Reference

### Dapr CLI Commands

```bash
# Start application
dapr run --app-id product-service --app-port 8001 ...

# Stop application
dapr stop --app-id product-service

# View running apps
dapr list

# View logs
dapr logs --app-id product-service

# Start dashboard
dapr dashboard

# Uninstall Dapr
dapr uninstall --all
```

### Service URLs

| URL                                | Description           |
| ---------------------------------- | --------------------- |
| http://localhost:8001              | Direct service access |
| http://localhost:8001/docs         | Swagger UI            |
| http://localhost:3500              | Dapr sidecar          |
| http://localhost:3500/v1.0/healthz | Dapr health           |
| http://localhost:8080              | Dapr Dashboard        |
| http://localhost:15672             | RabbitMQ Management   |
| http://localhost:9411              | Zipkin tracing        |

### Event Topics

| Topic                     | Direction | Description           |
| ------------------------- | --------- | --------------------- |
| `product.created`         | Outbound  | Product created       |
| `product.updated`         | Outbound  | Product updated       |
| `product.deleted`         | Outbound  | Product deleted       |
| `product.price.changed`   | Outbound  | Product price changed |
| `review.created`          | Inbound   | Review created        |
| `review.updated`          | Inbound   | Review updated        |
| `review.deleted`          | Inbound   | Review deleted        |
| `inventory.stock.updated` | Inbound   | Inventory updated     |

---

**Previous:** [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) - Development without Dapr
