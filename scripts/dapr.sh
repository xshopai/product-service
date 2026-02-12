#!/bin/bash

# Product Service - Run with Dapr Pub/Sub

echo "Starting Product Service (Dapr Pub/Sub)..."
echo "Service will be available at: http://localhost:8001"
echo "API documentation: http://localhost:8001/docs"
echo "Dapr HTTP endpoint: http://localhost:3501"
echo "Dapr gRPC endpoint: localhost:50001"
echo ""

# Kill any processes using required ports (prevents "address already in use" errors)
for PORT in 8001 3501 50001; do
    for pid in $(netstat -ano 2>/dev/null | grep ":$PORT" | grep LISTENING | awk '{print $5}' | sort -u); do
        echo "Killing process $pid on port $PORT..."
        taskkill //F //PID $pid 2>/dev/null
    done
done

dapr run \
  --app-id product-service \
  --app-port 8001 \
  --dapr-http-port 3501 \
  --dapr-grpc-port 50001 \
  --log-level info \
  --config ./.dapr/config.yaml \
  --resources-path ./.dapr/components \
  -- python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload --reload-delay 2
