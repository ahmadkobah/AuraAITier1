# Starting All Services

## Overview

The Adaptive Document Processing system consists of 4 microservices that work together:

- **OCR Service** (Port 8000): Optical Character Recognition using TrOCR
- **ICR Service** (Port 8001): Intelligent Character Recognition for handwriting
- **NLP Service** (Port 8002): Natural Language Processing and text analysis
- **Document Intelligence Service** (Port 8004): Main orchestrator and document processing pipeline

## Prerequisites

1. Python virtual environment activated
2. All dependencies installed (see individual service READMEs)
3. All import issues resolved

## Quick Start Methods

### Method 1: Automated Scripts (Recommended)

#### Windows (Batch Script)
```cmd
start_services.bat
```

#### Windows (PowerShell)
```powershell
.\start_services.ps1
```

#### Linux/Mac (Shell Script)
```bash
chmod +x start_services.sh
./start_services.sh
```

### Method 2: Manual Start (Individual Terminals)

Open 4 separate terminals and run:

**Terminal 1 - OCR Service:**
```bash
cd python-ocr-service
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --log-level info
```

**Terminal 2 - ICR Service:**
```bash
cd python-icr-service
python -m uvicorn main:app --host 127.0.0.1 --port 8001 --log-level info
```

**Terminal 3 - NLP Service:**
```bash
cd python-nlp-service
python -m uvicorn main:app --host 127.0.0.1 --port 8002 --log-level info
```

**Terminal 4 - Document Intelligence:**
```bash
cd python-document-intelligence-service
python -m uvicorn main:app --host 127.0.0.1 --port 8004 --log-level info
```

### Method 3: Background Start (Single Terminal)

For Windows PowerShell:
```powershell
# Start services in background
Start-Job -ScriptBlock { cd python-ocr-service; python -m uvicorn main:app --host 127.0.0.1 --port 8000 }
Start-Job -ScriptBlock { cd python-icr-service; python -m uvicorn main:app --host 127.0.0.1 --port 8001 }
Start-Job -ScriptBlock { cd python-nlp-service; python -m uvicorn main:app --host 127.0.0.1 --port 8002 }
Start-Job -ScriptBlock { cd python-document-intelligence-service; python -m uvicorn main:app --host 127.0.0.1 --port 8004 }

# Check running jobs
Get-Job
```

## Service URLs

Once started, services will be available at:

- **OCR Service**: http://127.0.0.1:8000
  - Health: `GET /health`
  - Process: `POST /ocr/process`

- **ICR Service**: http://127.0.0.1:8001
  - Health: `GET /health`
  - Process: `POST /icr/process`

- **NLP Service**: http://127.0.0.1:8002
  - Health: `GET /health`
  - Analyze: `POST /nlp/analyze`

- **Document Intelligence**: http://127.0.0.1:8004
  - Health: `GET /health`
  - Analyze: `POST /intelligence/analyze`

## Testing the Pipeline

1. Start all services using one of the methods above
2. Test individual services with health checks
3. Use the Document Intelligence service for full pipeline testing

## Troubleshooting

- **Port conflicts**: Change ports in the scripts if needed
- **Import errors**: Run the import check script first
- **Model loading**: Some services load ML models on startup (may take time)
- **Memory issues**: Close other applications if services fail to start

## Stopping Services

- **Windows**: Close the command windows or use Task Manager
- **PowerShell Jobs**: `Get-Job | Stop-Job`
- **Linux/Mac**: `pkill -f uvicorn` or find PIDs and kill them