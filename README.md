# 📦 Product Service

Product catalog management microservice for xshop.ai - handles product CRUD operations, search, categories, inventory tracking, and lifecycle events.

## 🚀 Quick Start

### Prerequisites

- **Python** 3.11+ ([Download](https://www.python.org/downloads/))
- **MongoDB** 8+ ([Download](https://www.mongodb.com/try/download/community))
- **Dapr CLI** 1.16.2+ ([Install Guide](https://docs.dapr.io/getting-started/install-dapr-cli/))
- **Docker** (for infrastructure: MongoDB, RabbitMQ, Redis)

### Setup

**1. Start Infrastructure**
```bash
cd ../../scripts/docker-compose
docker-compose -f docker-compose.infrastructure.yml up -d
docker-compose -f docker-compose.services.yml up product-mongodb -d
```

**2. Clone & Install**
```bash
git clone https://github.com/xshopai/product-service.git
cd product-service
pip install -r requirements.txt
```

**3. Configure Secrets**
```bash
# Create .dapr/secrets.json
{
  "MONGODB_CONNECTION_STRING": "mongodb://localhost:27017/product_service_db",
  "JWT_SECRET": "your-super-secret-jwt-key-change-in-production"
}
```

**4. Initialize Dapr**
```bash
# First time only
dapr init
```

**5. Run Service**
```bash
# Start with Dapr (recommended)
./run.sh       # Linux/Mac
.\run.ps1      # Windows
```

**6. Verify**
```bash
# Check health
curl http://localhost:1001/health

# Via Dapr
curl http://localhost:3501/v1.0/invoke/product-service/method/health

# API docs
Open http://localhost:1001/docs
```

### Common Commands

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app tests/

# Debug mode
python -m uvicorn main:app --reload --port 8003
```

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [📖 Developer Guide](docs/DEVELOPER_GUIDE.md) | Local setup, debugging, daily workflows |
| [📘 Technical Reference](docs/TECHNICAL.md) | Architecture, security, monitoring |
| [🤝 Contributing](docs/CONTRIBUTING.md) | Contribution guidelines and workflow |

**API Documentation**: FastAPI auto-generates interactive docs at `/docs` (Swagger UI) and `/redoc` (ReDoc).

### Products
- `GET /api/products` — List all products (with pagination)
- `POST /api/products` — Create a new product
- `GET /api/products/{id}` — Get product by ID
- `PUT /api/products/{id}` — Update product
- `DELETE /api/products/{id}` — Delete product

### Admin
- `GET /api/admin/products/stats` — Product statistics

### Operational
- `GET /health` — Health check
- `GET /health/ready` — Readiness check
- `GET /health/live` — Liveness check

---

## Development

### Debug Mode
Use VS Code "Debug" launch configuration to run with breakpoints.

### Testing
```bash
pytest
pytest --cov=app tests/
```

---

## Contributing

Contributions are welcome! Please open issues or submit pull requests.

---

## License

MIT License

---

## Contact

For questions or support, reach out to the xshop.ai dev team.
