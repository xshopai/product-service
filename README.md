<div align="center">

# 📦 Product Service

**Enterprise-grade product catalog management microservice for the xshopai e-commerce platform**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![MongoDB](https://img.shields.io/badge/MongoDB-8.0+-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://mongodb.com)
[![Dapr](https://img.shields.io/badge/Dapr-Enabled-0D597F?style=for-the-badge&logo=dapr&logoColor=white)](https://dapr.io)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[Getting Started](#-getting-started) •
[Documentation](#-documentation) •
[API Reference](docs/PRD.md) •
[Contributing](#-contributing)

</div>

---

## 🎯 Overview

The **Product Service** is a core microservice responsible for managing the complete product catalog, including product information, taxonomy, search, and product discovery features across the xshopai platform. Built with scalability and reliability in mind, it supports multi-cloud deployments and integrates seamlessly with the broader microservices ecosystem.

---

## ✨ Key Features

<table>
<tr>
<td width="50%">

### 📦 Product Management

- Complete product CRUD operations
- Hierarchical taxonomy (Department/Category/Subcategory)
- Product variations (parent-child relationships)
- Badge management (manual & automated)

</td>
<td width="50%">

### 🔍 Product Discovery

- Full-text search with filters
- Price range filtering
- Category-based browsing
- Trending products & autocomplete

</td>
</tr>
<tr>
<td width="50%">

### 📡 Event-Driven Architecture

- CloudEvents 1.0 specification
- Pub/sub messaging via Dapr
- Product lifecycle event publishing
- Cross-service synchronization

</td>
<td width="50%">

### 🛡️ Enterprise Security

- JWT token authentication
- Role-based access control (RBAC)
- Admin-only operations
- Complete audit trail

</td>
</tr>
</table>

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- MongoDB 8.0+
- Docker & Docker Compose (optional)
- Dapr CLI (for production-like setup)

### Quick Start with Docker Compose

```bash
# Clone the repository
git clone https://github.com/xshopai/product-service.git
cd product-service

# Start all services (MongoDB, service, etc.)
docker-compose up -d

# Verify the service is healthy
curl http://localhost:8001/health
```

### Local Development Setup

<details>
<summary><b>🔧 Without Dapr (Simple Setup)</b></summary>

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Start MongoDB (Docker)
docker run -d --name product-mongodb -p 27017:27017 mongo:8

# Start the service
python main.py
```

📖 See [Local Development Guide](docs/LOCAL_DEVELOPMENT.md) for detailed instructions.

</details>

<details>
<summary><b>⚡ With Dapr (Production-like)</b></summary>

```bash
# Ensure Dapr is initialized
dapr init

# Start with Dapr sidecar
./run.sh       # Linux/Mac
.\run.ps1      # Windows

# Or manually
dapr run \
  --app-id product-service \
  --app-port 8001 \
  --dapr-http-port 3501 \
  --resources-path .dapr/components \
  --config .dapr/config.yaml \
  -- python main.py
```

📖 See [Dapr Development Guide](docs/LOCAL_DEVELOPMENT_DAPR.md) for detailed instructions.

</details>

---

## 📚 Documentation

| Document                                                         | Description                                          |
| :--------------------------------------------------------------- | :--------------------------------------------------- |
| 📘 [Local Development](docs/LOCAL_DEVELOPMENT.md)                | Step-by-step local setup without Dapr                |
| ⚡ [Local Development with Dapr](docs/LOCAL_DEVELOPMENT_DAPR.md) | Local setup with full Dapr integration               |
| ☁️ [Azure Container Apps](docs/ACA_DEPLOYMENT.md)                | Deploy to serverless containers with built-in Dapr   |
| ⎈ [Azure Kubernetes](docs/AKS_DEPLOYMENT.md)                     | Deploy to AKS with Dapr sidecar injection            |
| 📋 [Product Requirements](docs/PRD.md)                           | Complete API specification and business requirements |
| 🏗️ [Architecture](docs/ARCHITECTURE.md)                          | System design, patterns, and data flows              |
| 🔐 [Security](.github/SECURITY.md)                               | Security policies and vulnerability reporting        |

**API Documentation**: FastAPI auto-generates interactive docs at `/docs` (Swagger UI) and `/redoc` (ReDoc).

---

## 🧪 Testing

We maintain high code quality standards with comprehensive test coverage.

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage report
pytest --cov=app --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_product_service.py -v

# Run integration tests (requires running services)
pytest tests/integration/ -v
```

### Test Coverage

| Metric        | Status               |
| :------------ | :------------------- |
| Unit Tests    | ✅ Passing           |
| Code Coverage | ✅ Target 80%+       |
| Security Scan | ✅ 0 vulnerabilities |

---

## 🏗️ Project Structure

```
product-service/
├── 📁 app/                       # Application source code
│   ├── 📁 api/                   # REST API endpoints
│   ├── 📁 services/              # Business logic layer
│   ├── 📁 repositories/          # Data access layer
│   ├── 📁 models/                # Pydantic/MongoDB models
│   ├── 📁 schemas/               # Request/response schemas
│   ├── 📁 events/                # Event publishing (Dapr)
│   ├── 📁 middleware/            # Authentication, logging, tracing
│   ├── 📁 core/                  # Config, logger, errors
│   ├── 📁 db/                    # MongoDB connection setup
│   └── 📁 dependencies/          # FastAPI dependencies
├── 📁 tests/                     # Test suite
│   ├── 📁 unit/                  # Unit tests
│   ├── 📁 integration/           # Integration tests
│   └── 📁 e2e/                   # End-to-end tests
├── 📁 .dapr/                     # Dapr configuration
│   ├── 📁 components/            # Pub/sub, secrets, state stores
│   └── 📄 config.yaml            # Dapr runtime configuration
├── 📁 docs/                      # Documentation
├── 📄 docker-compose.yml         # Local containerized environment
├── 📄 Dockerfile                 # Production container image
└── 📄 requirements.txt           # Python dependencies
```

---

## 🔧 Technology Stack

| Category          | Technology                                 |
| :---------------- | :----------------------------------------- |
| 🐍 Runtime        | Python 3.11+                               |
| 🌐 Framework      | FastAPI 0.104+ with automatic OpenAPI docs |
| 🗄️ Database       | MongoDB 8.0+ with Motor async driver       |
| 📨 Messaging      | Dapr Pub/Sub (RabbitMQ backend)            |
| 📋 Event Format   | CloudEvents 1.0 Specification              |
| 🔐 Authentication | JWT Tokens + Role-based access control     |
| 🧪 Testing        | pytest with coverage reporting             |
| 📊 Observability  | Structured logging, OpenTelemetry tracing  |

---

## ⚡ Quick Reference

```bash
# 🐳 Docker Compose
docker-compose up -d              # Start all services
docker-compose down               # Stop all services
docker-compose logs -f product    # View logs

# 🐍 Local Development
python main.py                    # Run without Dapr
uvicorn main:app --reload         # Run with hot reload

# ⚡ Dapr Development
./run.sh                          # Linux/Mac
.\run.ps1                         # Windows

# 🧪 Testing
pytest tests/unit/ -v             # Run unit tests
pytest --cov=app                  # Run with coverage

# 🔍 Health Check
curl http://localhost:8001/health
curl http://localhost:8001/health/ready
```

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Write** tests for your changes
4. **Run** the test suite
   ```bash
   pytest && black . && flake8
   ```
5. **Commit** your changes
   ```bash
   git commit -m 'feat: add amazing feature'
   ```
6. **Push** to your branch
   ```bash
   git push origin feature/amazing-feature
   ```
7. **Open** a Pull Request

Please ensure your PR:

- ✅ Passes all existing tests
- ✅ Includes tests for new functionality
- ✅ Follows the existing code style
- ✅ Updates documentation as needed

---

## 🆘 Support

| Resource         | Link                                                                         |
| :--------------- | :--------------------------------------------------------------------------- |
| 🐛 Bug Reports   | [GitHub Issues](https://github.com/xshopai/product-service/issues)           |
| 📖 Documentation | [docs/](docs/)                                                               |
| 📋 API Reference | [docs/PRD.md](docs/PRD.md)                                                   |
| 💬 Discussions   | [GitHub Discussions](https://github.com/xshopai/product-service/discussions) |

---

## 📄 License

This project is part of the **xshopai** e-commerce platform.  
Licensed under the MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**[⬆ Back to Top](#-product-service)**

Made with ❤️ by the xshopai team

</div>
