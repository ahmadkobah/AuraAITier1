# Port Configuration Guide

## Overview

The AI Service Tier 1 now runs on **two separate ports** to avoid conflicts:

| Port | Service | Purpose | Status |
|------|---------|---------|--------|
| **8080** | Main App | Production API endpoints | Active/Required |
| **8001** | Test Server | Development & testing | Optional |

## Running the Services

### Terminal 1: Main Application (Port 8080)

```powershell
# Windows
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080

# Or with reload for development
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

**Endpoints available:**
- `GET /health` - Health check
- `GET /api/v1/status` - Service status
- `POST /api/v1/process` - Queue document
- `POST /api/v1/search` - Vector search
- `POST /api/v1/query` - Question answering

### Terminal 2: Test Server (Port 8001) - Optional

```powershell
# Windows - using PowerShell script
.\run_test_server.ps1

# Or direct command
python -m uvicorn app.test_server:test_app --host 0.0.0.0 --port 8001

# Or using Python launcher
python run_test_server.py
```

**Test endpoints available:**
- `GET /test/health` - Test health status
- `GET /test/models` - List loaded models
- `POST /test/simple-ocr?image_path=C:\path\to\image.jpg` - Test OCR
- `POST /test/embedding?text=Your text here` - Test embeddings
- `POST /test/classification?text=Your text here` - Test classification

## Testing Individual Components

### 1. Test Health Status
```powershell
curl http://localhost:8001/test/health
```

**Response:**
```json
{
  "status": "healthy",
  "port": 8001,
  "models_ready": true,
  "gpu_available": true
}
```

### 2. Test Available Models
```powershell
curl http://localhost:8001/test/models
```

**Response:**
```json
{
  "loaded_models": ["sentence_transformer_classify", "sentence_transformer_search", "paddleocr"],
  "total_models": 6,
  "models_ready": true,
  "gpu": true
}
```

### 3. Test OCR
```powershell
# Windows format
curl -X POST "http://localhost:8001/test/simple-ocr?image_path=C:\Users\Ahmad\test.jpg"
```

**Response:**
```json
{
  "status": "success",
  "image_path": "C:\\Users\\Ahmad\\test.jpg",
  "text": "Extracted text from image...",
  "lines_extracted": 5
}
```

### 4. Test Text Embedding
```powershell
$text = "This is a test document"
curl -X POST "http://localhost:8001/test/embedding?text=$text"
```

**Response:**
```json
{
  "status": "success",
  "text": "This is a test document",
  "embedding_dim": 384,
  "embedding": [0.123, -0.456, 0.789, ...]
}
```

### 5. Test Classification
```powershell
$text = "Invoice #INV-001 for $5,000 due in 30 days"
curl -X POST "http://localhost:8001/test/classification?text=$text"
```

**Response:**
```json
{
  "status": "success",
  "text": "Invoice #INV-001 for $5,000 due in 30 days",
  "top_label": "Invoice",
  "confidence": 0.92,
  "all_labels": {
    "Invoice": 0.92,
    "Receipt": 0.05,
    "Report": 0.03,
    ...
  }
}
```

## Docker Compose Setup

Both ports are automatically configured in `docker-compose.yml`:

```yaml
ai-service:
  ports:
    - "8080:8080"  # Main app
    - "8001:8001"  # Test server (optional)
```

To run with Docker Compose:
```bash
docker-compose up -d
```

Then access:
- Main app: http://localhost:8080
- Test server: http://localhost:8001

## Troubleshooting

### Port Already in Use

If you get "Address already in use" error:

```powershell
# Check what's using the port
netstat -ano | findstr ":8080"
netstat -ano | findstr ":8001"

# Kill process by ID
taskkill /PID <PID> /F
```

### Can't Reach Server

1. Check if uvicorn started successfully
2. Verify ports are accessible:
   ```powershell
   Test-NetConnection localhost -port 8080
   Test-NetConnection localhost -port 8001
   ```
3. Check firewall settings
4. Ensure MongoDB is running for main app

### GPU Not Available

If tests show GPU unavailable:
```powershell
# Check NVIDIA GPU
nvidia-smi

# Models will fall back to CPU (slower)
```

## Performance Notes

- **Main App (Port 8080)**: Production-ready, handles all API requests
- **Test Server (Port 8001)**: For development, tests run in-memory
- **Startup Time**: 
  - Main app: ~60-90 seconds (loads core models)
  - Test server: ~30-40 seconds (shares loaded models)
- **First Model Load**: Can take longer due to HuggingFace downloads

## Next Steps

1. ✅ Start main app on port 8080: `python -m uvicorn app.main:app --port 8080`
2. ✅ Start test server on port 8001: `.\run_test_server.ps1`
3. ✅ Test endpoints individually
4. ✅ Integrate with Node/React backend (calls port 8080)

---

**Remember:** Port 8080 is for production use with your Node/React backend. Port 8001 is optional and only for development/testing.
