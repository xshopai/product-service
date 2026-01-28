#!/usr/bin/env pwsh
# Run Product Service with Dapr sidecar
# Usage: .\run.ps1

$Host.UI.RawUI.WindowTitle = "Product Service"

Write-Host "Starting Product Service with Dapr..." -ForegroundColor Green
Write-Host "Service will be available at: http://localhost:8001" -ForegroundColor Cyan
Write-Host "API documentation: http://localhost:8001/docs" -ForegroundColor Cyan
Write-Host "Dapr HTTP endpoint: http://localhost:3500" -ForegroundColor Cyan
Write-Host "Dapr gRPC endpoint: localhost:50001" -ForegroundColor Cyan
Write-Host ""

dapr run `
  --app-id product-service `
  --app-port 8001 `
  --dapr-http-port 3500 `
  --dapr-grpc-port 50001 `
  --resources-path .dapr/components `
  --config .dapr/config.yaml `
  --log-level warn `
  -- python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload --reload-delay 2
