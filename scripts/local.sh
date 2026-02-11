#!/bin/bash

# Product Service - Run without Dapr (local development)

echo "Starting Product Service (without Dapr)..."
echo "Service will be available at: http://localhost:8001"
echo ""
echo "Note: Event publishing and service-to-service calls will fail without Dapr."
echo "This mode is suitable for isolated development and testing."
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
