#!/bin/bash

echo "Starting Adaptive Document Processing Services..."
echo

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$BASE_DIR/.venv/Scripts/python.exe"

# Function to start a service
start_service() {
    local name=$1
    local port=$2
    local service_dir=$3

    echo "Starting $name Service (Port $port)..."
    cd "$service_dir"
    nohup "$VENV_PYTHON" -m uvicorn main:app --host 127.0.0.1 --port $port --log-level info > "${name,,}_service.log" 2>&1 &
    echo "$name service started (PID: $!)"
    sleep 2
}

# Start services
start_service "OCR" 8000 "$BASE_DIR/python-ocr-service"
start_service "ICR" 8001 "$BASE_DIR/python-icr-service"
start_service "NLP" 8002 "$BASE_DIR/python-nlp-service"
start_service "Document Intelligence" 8004 "$BASE_DIR/python-document-intelligence-service"

echo
echo "All services started in background!"
echo
echo "Service URLs:"
echo "  OCR Service: http://127.0.0.1:8000"
echo "  ICR Service: http://127.0.0.1:8001"
echo "  NLP Service: http://127.0.0.1:8002"
echo "  Document Intelligence: http://127.0.0.1:8004"
echo
echo "Check log files for service status:"
echo "  ocr_service.log, icr_service.log, nlp_service.log, document_intelligence_service.log"
echo
echo "To stop services: kill \$(jobs -p) or find PIDs and kill them"