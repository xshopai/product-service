# Product Service - Local Development Guide

This guide explains how to set up and run the Product Service locally **without** Dapr. For development with Dapr sidecar, see [LOCAL_DEVELOPMENT_DAPR.md](LOCAL_DEVELOPMENT_DAPR.md).

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Environment Setup](#3-environment-setup)
4. [Database Setup](#4-database-setup)
5. [Starting the Service](#5-starting-the-service)
6. [Verifying the Setup](#6-verifying-the-setup)
7. [Running Tests](#7-running-tests)
8. [Common Development Tasks](#8-common-development-tasks)
9. [Debugging](#9-debugging)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Overview

### Service Summary

| Property         | Value                             |
| ---------------- | --------------------------------- |
| **Service Name** | product-service                   |
| **Language**     | Python 3.11+                      |
| **Framework**    | FastAPI 0.104+                    |
| **Database**     | MongoDB 8.0+ (Motor async driver) |
| **Default Port** | 8001                              |
| **API Docs**     | http://localhost:8001/docs        |

### When to Use This Guide

- Rapid development without event infrastructure
- Debugging API endpoints and business logic
- Running unit tests
- Quick iterations on service code

---

## 2. Prerequisites

### Required Software

| Software | Version | Installation                                   |
| -------- | ------- | ---------------------------------------------- |
| Python   | 3.11+   | https://www.python.org/downloads/              |
| MongoDB  | 8.0+    | https://www.mongodb.com/try/download/community |
| Docker   | 24+     | https://docs.docker.com/get-docker/ (optional) |
| Git      | Latest  | https://git-scm.com/downloads                  |

### Verify Installation

```bash
# Check Python version
python --version  # Should show Python 3.11.x or higher

# Check pip
pip --version

# Check MongoDB (if installed locally)
mongod --version
```

---

## 3. Environment Setup

### 3.1 Clone Repository

```bash
git clone https://github.com/xshopai/product-service.git
cd product-service
```

### 3.2 Create Virtual Environment

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**

```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**macOS/Linux:**

```bash
python -m venv venv
source venv/bin/activate
```

### 3.3 Install Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

### 3.4 Configure Environment Variables

Copy the local environment template to `.env`:

```bash
# On Linux / Mac / Bash:
cp .env.local .env

# On Windows (PowerShell):
Copy-Item .env.local .env
```

The `.env.local` file contains:

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

# Database Configuration - Direct MongoDB connection
MONGODB_URI=mongodb://admin:admin123@localhost:27017/product_service_db?authSource=admin
MONGODB_DATABASE=product_service_db
MONGODB_MAX_POOL_SIZE=10

# JWT Configuration (required for non-Dapr mode)
JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----
JWT_ALGORITHM=RS256

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
> - Event publishing is automatically disabled without Dapr sidecar
> - `MONGODB_URI` provides direct MongoDB connection (no Dapr secret store needed)
> - Service tokens must match tokens configured in calling services (order-service, cart-service, etc.)
> - For JWT public key, get this from auth-service configuration or use a test key for local development

---

## 4. Database Setup

### Option A: Docker (Recommended)

```bash
# Start MongoDB container
docker run -d \
  --name product-mongodb \
  -p 27017:27017 \
  -e MONGO_INITDB_DATABASE=product_service_db \
  -v product-mongo-data:/data/db \
  mongo:8.0

# Verify container is running
docker ps | grep product-mongodb
```

### Option B: Local MongoDB Installation

If MongoDB is installed locally:

```bash
# Start MongoDB service
# Windows
net start MongoDB

# macOS (Homebrew)
brew services start mongodb-community

# Linux (systemd)
sudo systemctl start mongod
```

### Verify Database Connection

```bash
# Using mongosh
mongosh mongodb://localhost:27017/product_service_db

# Or using Docker
docker exec -it product-mongodb mongosh product_service_db
```

### Seed Sample Data (Optional)

```bash
# Run seed script if available
python scripts/seed_data.py
```

---

## 5. Starting the Service

### Option A: Using Uvicorn Directly

```bash
# Development mode with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# Or with specific log level
uvicorn main:app --host 0.0.0.0 --port 8001 --reload --log-level debug
```

### Option B: Using the Run Script

**Windows:**

```powershell
.\run.ps1
```

**macOS/Linux:**

```bash
./run.sh
```

### Option C: Using Python

```bash
python main.py
```

### Expected Output

```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

---

## 6. Verifying the Setup

### 6.1 Health Check

```bash
# Liveness probe
curl http://localhost:8001/health

# Expected response
{
  "status": "healthy",
  "service": "product-service",
  "timestamp": "2025-01-01T00:00:00Z"
}
```

### 6.2 Readiness Check

```bash
curl http://localhost:8001/health/ready

# Expected response (with database status)
{
  "status": "ready",
  "service": "product-service",
  "dependencies": {
    "mongodb": {
      "status": "connected",
      "responseTime": "5ms"
    }
  }
}
```

### 6.3 API Documentation

Open your browser and navigate to:

- **Swagger UI:** http://localhost:8001/docs
- **ReDoc:** http://localhost:8001/redoc

### 6.4 Test Product Endpoints

```bash
# Get all products
curl http://localhost:8001/api/products/search

# Get product by ID (replace with actual ID)
curl http://localhost:8001/api/products/507f1f77bcf86cd799439011

# Search products
curl "http://localhost:8001/api/products/search?q=shirt&page=1&limit=10"
```

---

## 7. Running Tests

### Run All Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/test_product_service.py -v

# Specific test function
pytest tests/unit/test_product_service.py::test_create_product -v
```

### Run Tests with Coverage Report

```bash
pytest --cov=app --cov-report=html --cov-report=term-missing
# View HTML report in htmlcov/index.html
```

---

## 8. Common Development Tasks

### 8.1 Creating a New Product

```bash
curl -X POST http://localhost:8001/api/products \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin-jwt-token>" \
  -d '{
    "name": "Test Product",
    "description": "A test product description",
    "price": 29.99,
    "sku": "TEST-001",
    "brand": "TestBrand",
    "taxonomy": {
      "department": "Electronics",
      "category": "Accessories"
    }
  }'
```

### 8.2 Updating a Product

```bash
curl -X PUT http://localhost:8001/api/products/507f1f77bcf86cd799439011 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin-jwt-token>" \
  -d '{
    "price": 24.99,
    "description": "Updated description"
  }'
```

### 8.3 Searching Products

```bash
# Full-text search
curl "http://localhost:8001/api/products/search?q=electronics&page=1&limit=20"

# Filter by category
curl "http://localhost:8001/api/products/search?category=Electronics&minPrice=10&maxPrice=100"

# Sort by price
curl "http://localhost:8001/api/products/search?sortBy=price&sortOrder=asc"
```

### 8.4 Checking Product Existence

```bash
curl http://localhost:8001/api/products/507f1f77bcf86cd799439011/exists
```

### 8.5 Code Formatting

```bash
# Format code with Black
black app/

# Sort imports with isort
isort app/

# Lint with flake8
flake8 app/

# Type checking with mypy
mypy app/
```

---

## 9. Debugging

### 9.1 VS Code Configuration

Create or update `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Product Service (Direct)",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"],
      "jinja": true,
      "envFile": "${workspaceFolder}/.env",
      "cwd": "${workspaceFolder}",
      "console": "integratedTerminal"
    }
  ]
}
```

### 9.2 Enable Debug Logging

In your `.env` file:

```bash
LOG_LEVEL=DEBUG
```

Or set it programmatically:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 9.3 Debug Database Queries

Add to your `.env`:

```bash
MONGODB_DEBUG=true
```

This will log all MongoDB queries to the console.

---

## 10. Troubleshooting

### Issue: MongoDB Connection Failed

**Symptoms:** `ConnectionRefusedError` or timeout errors

**Solutions:**

1. Verify MongoDB is running:

   ```bash
   docker ps | grep mongodb
   # or
   mongosh mongodb://localhost:27017
   ```

2. Check `MONGODB_URI` in `.env`

3. Ensure firewall allows port 27017

### Issue: Module Not Found

**Symptoms:** `ModuleNotFoundError: No module named 'xxx'`

**Solutions:**

1. Activate virtual environment:

   ```bash
   # Windows
   .\venv\Scripts\Activate.ps1

   # macOS/Linux
   source venv/bin/activate
   ```

2. Reinstall dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Issue: JWT Validation Failed

**Symptoms:** 401 Unauthorized on admin endpoints

**Solutions:**

1. Verify `JWT_PUBLIC_KEY` in `.env` matches auth-service
2. Ensure token is not expired
3. Check token format in Authorization header

### Issue: Port Already in Use

**Symptoms:** `Address already in use` error

**Solutions:**

```bash
# Windows - find process using port 8001
netstat -ano | findstr :8001
# Kill process
taskkill /F /PID <PID>

# macOS/Linux
lsof -i :8001
kill -9 <PID>
```

### Issue: CORS Errors in Browser

**Symptoms:** `Access-Control-Allow-Origin` errors

**Solutions:**

1. Add your frontend URL to `CORS_ORIGINS` in `.env`:

   ```bash
   CORS_ORIGINS=http://localhost:3000,http://localhost:3001
   ```

2. Restart the service after changing `.env`

---

## Quick Reference

### Service Endpoints

| Endpoint               | Method | Description            |
| ---------------------- | ------ | ---------------------- |
| `/health`              | GET    | Liveness probe         |
| `/health/ready`        | GET    | Readiness probe        |
| `/docs`                | GET    | Swagger UI             |
| `/api/products/search` | GET    | Search products        |
| `/api/products/{id}`   | GET    | Get product by ID      |
| `/api/products`        | POST   | Create product (Admin) |
| `/api/products/{id}`   | PUT    | Update product (Admin) |
| `/api/products/{id}`   | DELETE | Delete product (Admin) |

### Useful Commands

```bash
# Start service
uvicorn main:app --reload --port 8001

# Run tests
pytest -v

# Format code
black app/ && isort app/

# Type check
mypy app/

# Stop MongoDB container
docker stop product-mongodb
```

---

**Next:** For development with Dapr sidecar and event-driven features, see [LOCAL_DEVELOPMENT_DAPR.md](LOCAL_DEVELOPMENT_DAPR.md).
