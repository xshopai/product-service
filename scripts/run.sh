#!/bin/bash

# Product Service - Run with Dapr
# Change to project root directory
cd "$(dirname "$0")/.." || exit 1

echo "Starting Product Service with Dapr..."
echo "Working directory: $(pwd)"
echo "Service will be available at: http://localhost:8001"
echo "API documentation: http://localhost:8001/docs"
echo "Dapr HTTP endpoint: http://localhost:3501"
echo "Dapr gRPC endpoint: localhost:50002"
echo ""

dapr run \
  --app-id product-service \
  --app-port 8001 \
  --dapr-http-port 3501 \
  --dapr-grpc-port 50002 \
  --log-level info \
  --config ./.dapr/config.yaml \
  --resources-path ./.dapr/components \
  -- python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload --reload-delay 2

