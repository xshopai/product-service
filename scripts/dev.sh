#!/bin/bash

# Product Service - Run with direct RabbitMQ (local development)

echo "Starting Product Service (Direct RabbitMQ)..."
echo "Service will be available at: http://localhost:8001"
echo ""

# Kill any process using port 8001 (prevents "address already in use" errors)
PORT=8001
for pid in $(netstat -ano 2>/dev/null | grep ":$PORT" | grep LISTENING | awk '{print $5}' | sort -u); do
    echo "Killing process $pid on port $PORT..."
    taskkill //F //PID $pid 2>/dev/null
done

# Copy .env.http to .env for local development (HTTP mode, no Dapr)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(dirname "$SCRIPT_DIR")"
cd "$SERVICE_DIR"

if [ -f ".env.http" ]; then
    cp ".env.http" ".env"
    echo "✅ Copied .env.http → .env"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

# Install dependencies if needed
if [ ! -f "venv/.deps_installed" ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt -q
    touch venv/.deps_installed
fi

# Run with uvicorn (only watch app folder, not venv)
uvicorn main:app --host 0.0.0.0 --port 8001 --reload --reload-dir app
