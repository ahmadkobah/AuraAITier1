# Adaptive Document Processing - AI Service

**Version 2.0** | AI-powered document processing with OCR, classification, and intelligent search

## ?? Overview

Professional document management system featuring:
- **OCR/ICR**: Text extraction from images and PDFs (PaddleOCR + TrOCR)
- **Signature Detection**: YOLO-based signature localization
- **Document Classification**: 10 document types with zero-shot learning
- **Semantic Search**: Vector embeddings with text matching (all-MiniLM-L6-v2)
- **Conversational Q&A**: Llama 3.2 3B for natural language queries
- **GPU Acceleration**: CUDA-optimized (NVIDIA RTX 3060)

## ??? Project Structure

```
adaptive-Dokumentenverarbeitung/
+-- app/                          # Application code
¦   +-- api/                      # FastAPI endpoints
¦   ¦   +-- __init__.py
¦   ¦   +-- endpoints.py          # All API routes
¦   +-- core/                     # Core business logic
¦   ¦   +-- __init__.py
¦   ¦   +-- pipeline.py           # Document processing pipeline
¦   ¦   +-- classifier.py         # Document classification
¦   +-- models/                   # ML model management
¦   ¦   +-- __init__.py
¦   ¦   +-- loader.py             # Model loading & caching
¦   +-- services/                 # Specialized services
¦   ¦   +-- __init__.py
¦   ¦   +-- signature_detection.py
¦   ¦   +-- signature_ocr.py
¦   ¦   +-- signature_validation.py
¦   ¦   +-- ocr_validation.py
¦   +-- utils/                    # Utility functions
¦   ¦   +-- __init__.py
¦   ¦   +-- extraction.py         # Entity extraction
¦   +-- __init__.py
¦
+-- config/                       # Configuration
¦   +-- __init__.py
¦   +-- settings.py               # Centralized settings
¦
+-- data/                         # Data storage
¦   +-- uploads/                  # Uploaded documents
¦   +-- temp/                     # Temporary files
¦
+-- docs/                         # Documentation
¦   +-- COMPLETE_APP_ARCHITECTURE.md
¦   +-- INTEGRATION_QUICK_START.md
¦   +-- CUDA_GPU_SETUP_GUIDE.md
¦   +-- ...
¦
+-- models/                       # Pre-trained models
¦   +-- sentence-transformers/    # Embedding models
¦   +-- trocr/                    # OCR models
¦
+-- scripts/                      # Utility scripts
¦   +-- start_services.ps1
¦   +-- start_services.bat
¦   +-- monitor_llamafile.ps1
¦
+-- tests/                        # Test suite
¦   +-- test_*.py                 # Unit tests
¦   +-- ...
¦
+-- main.py                       # Application entry point
+-- requirements.txt              # Python dependencies
+-- docker-compose.yml            # Docker configuration
+-- .env.example                  # Environment template
+-- README.md                     # This file
```

## ?? Quick Start

### 1. **Prerequisites**

- Python 3.13+
- MongoDB (local or Atlas)
- NVIDIA GPU (optional, for acceleration)
- 8GB+ RAM

### 2. **Installation**

```bash
# Clone repository
git clone https://github.com/ahmadkobah/adaptive-Dokumentenverarbeitung.git
cd adaptive-Dokumentenverarbeitung

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your settings
```

### 3. **Start Services**

#### Option A: Using Scripts (Recommended)
```powershell
# Windows
.\scripts\start_services.ps1

# Linux/Mac
./scripts/start_services.sh
```

#### Option B: Manual Start
```bash
# Terminal 1: Start Llamafile
.\llama-3.2-3b.exe --server --host 0.0.0.0 --port 8080 --n-gpu-layers 29

# Terminal 2: Start AI Service
uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

### 4. **Verify Installation**

```bash
curl http://localhost:9000/health
```

Expected response:
```json
{
  "status": "healthy",
  "models_loaded": true,
  "gpu_available": true,
  "message": "All models loaded and ready"
}
```

## ?? API Endpoints

### Document Processing
- `POST /api/v1/upload` - Upload & process document
- `POST /api/v1/process` - Process existing document
- `GET /api/v1/documents/{doc_id}/status` - Check processing status

### Search & Q&A
- `POST /api/v1/search` - Semantic vector search
- `POST /api/v1/conversational-search` - LLaMA-powered conversational search
- `POST /api/v1/query` - Q&A over documents
- `POST /api/v1/qa` - Alias for /query

### Analysis
- `POST /api/v1/summarize` - Generate summaries
- `POST /api/v1/extract` - Extract structured data
- `POST /api/v1/entities` - Extract entities (names, dates, amounts)
- `POST /api/v1/validate-ocr` - Validate OCR quality

### System
- `GET /health` - Service health check
- `GET /models` - List loaded models
- `GET /docs` - Interactive API documentation

## ?? Configuration

Edit `config/settings.py` or set environment variables in `.env`:

```env
# API Configuration
API_HOST=0.0.0.0
API_PORT=9000

# MongoDB
MONGO_URL=mongodb://localhost:27017/
DATABASE_NAME=Aura

# Llamafile
LLAMAFILE_URL=http://localhost:8080

# GPU
USE_GPU=true
GPU_LAYERS=29
```

## ?? Testing

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_pipeline_components.py

# With coverage
pytest --cov=app tests/
```

## ?? Performance

- **Processing Speed**: 3-5s per page
- **Search Latency**: 200-500ms (semantic), 2-4s (conversational)
- **GPU Memory**: 2.85GB VRAM
- **Model Loading**: ~15s (lazy loading)

## ??? Tech Stack

**Backend:**
- FastAPI (API framework)
- PyMongo (MongoDB driver)
- Uvicorn (ASGI server)

**AI/ML:**
- Llama 3.2 3B (llamafile)
- Sentence Transformers (embeddings)
- YOLOv8n (signature detection)
- TrOCR (handwriting OCR)
- PaddleOCR (printed text OCR)

**GPU:**
- CUDA 11.8
- PyTorch 2.5.1
- NVIDIA RTX 3060

## ?? Documentation

- [Complete Architecture](docs/COMPLETE_APP_ARCHITECTURE.md)
- [Integration Guide](docs/INTEGRATION_QUICK_START.md)
- [CUDA Setup](docs/CUDA_GPU_SETUP_GUIDE.md)

## ?? Integration

This service integrates with **Aura** (main app):
- Aura Backend: `http://localhost:8000`
- Aura Frontend: `http://localhost:3000`
- AI Service: `http://localhost:9000`

See [Integration Quick Start](docs/INTEGRATION_QUICK_START.md) for details.

## ?? License

MIT License - See LICENSE file for details

## ?? Author

Ahmad Kobah

---

**Need help?** Check the [docs](docs/) or open an issue on GitHub.
