# 🚀 Production Deployment Guide

**Adaptive Document Processing System**  
**Version:** 1.0.0  
**Date:** November 1, 2025

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Starting Services](#starting-services)
5. [Health Checks](#health-checks)
6. [Configuration](#configuration)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)
9. [Scaling](#scaling)

---

## 🎯 System Overview

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Applications                      │
│         (Projectena, Network Scanners, Web Apps)            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │ Document Intelligence Service│
        │        (Port 8003/8004)       │
        │      Main Orchestrator        │
        └─────────┬───────┬────────┬────┘
                  │       │        │
        ┌─────────▼──┐ ┌──▼────┐ ┌▼─────────┐
        │ OCR Service│ │  ICR  │ │   NLP    │
        │ (Port 8000)│ │(8001) │ │  (8002)  │
        └────────────┘ └───────┘ └──────────┘
             │             │          │
             └─────────────┴──────────┘
                       │
                  Pre-trained
                  ML Models
```

### Services

| Service | Port | Purpose | Model |
|---------|------|---------|-------|
| **OCR** | 8000 | Printed text extraction | microsoft/trocr-base-printed |
| **ICR** | 8001 | Handwriting & signatures | microsoft/trocr-base-handwritten |
| **NLP** | 8002 | Text analysis | RoBERTa, BERT, BART |
| **Document Intelligence** | 8003 | Orchestration & routing | N/A (coordinator) |

---

## ✅ Prerequisites

### System Requirements

**Minimum:**
- CPU: 4 cores
- RAM: 8 GB
- Disk: 20 GB
- Python: 3.9+

**Recommended (for GPU):**
- CPU: 8+ cores
- RAM: 16 GB
- Disk: 50 GB
- GPU: NVIDIA with 6GB+ VRAM
- CUDA: 11.8+
- Python: 3.9-3.13

### Software Dependencies

- Python 3.9+
- CUDA Toolkit 11.8+ (if using GPU)
- Git

---

## 📦 Installation

### 1. Clone Repository

```bash
git clone https://github.com/ahmadkobah/adaptive-Dokumentenverarbeitung.git
cd adaptive-Dokumentenverarbeitung
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

**Option A: Install All Services**
```bash
# OCR Service
cd python-ocr-service
pip install -r requirements.txt
cd ..

# ICR Service
cd python-icr-service
pip install -r requirements.txt
cd ..

# NLP Service
cd python-nlp-service
pip install -r requirements.txt
cd ..

# Document Intelligence Service
cd python-document-intelligence-service
pip install -r requirements.txt
cd ..
```

**Option B: Use Provided Scripts**
```bash
# Windows
.\install_all.ps1

# Linux/Mac
bash install_all.sh
```

---

## 🚀 Starting Services

### Method 1: Manual Start (Development)

Open 4 separate terminals:

**Terminal 1: OCR Service**
```bash
cd python-ocr-service
python main.py
```

**Terminal 2: ICR Service**
```bash
cd python-icr-service
python main.py
```

**Terminal 3: NLP Service**
```bash
cd python-nlp-service
python main.py
```

**Terminal 4: Document Intelligence**
```bash
cd python-document-intelligence-service
python main.py
```

### Method 2: Automated Start (Recommended)

**Windows:**
```powershell
.\start_services.ps1
```

**Linux/Mac:**
```bash
bash start_services.sh
```

### Method 3: Background Processes (Production)

```bash
# Use process manager like systemd, supervisor, or PM2

# Example with nohup (simple)
nohup python python-ocr-service/main.py > logs/ocr.log 2>&1 &
nohup python python-icr-service/main.py > logs/icr.log 2>&1 &
nohup python python-nlp-service/main.py > logs/nlp.log 2>&1 &
nohup python python-document-intelligence-service/main.py > logs/doc-intel.log 2>&1 &
```

---

## 🏥 Health Checks

### Verify All Services Running

```bash
# OCR Service
curl http://localhost:8000/health

# ICR Service
curl http://localhost:8001/health

# NLP Service
curl http://localhost:8002/health

# Document Intelligence
curl http://localhost:8003/health
```

### Expected Responses

All should return:
```json
{
  "status": "ok",
  "model": "<model_name>",
  "device": "cuda",  // or "cpu"
  "using_gpu": true   // or false
}
```

### Check Ports

```bash
# Windows
netstat -ano | findstr "8000 8001 8002 8003"

# Linux/Mac
netstat -tuln | grep '800[0-3]'
```

---

## ⚙️ Configuration

### Environment Variables

Create `.env` files in each service directory:

**python-ocr-service/.env**
```env
OCR_MODEL_NAME=microsoft/trocr-base-printed
OCR_OUTPUT_DIR=./ocr_outputs
OCR_DEFAULT_PROMPT=<image>\n<|grounding|>Convert the document to markdown.
```

**python-icr-service/.env**
```env
ICR_MODEL_PATH=./models
TRAINING_DATA_PATH=./training_data
MAX_IMAGE_SIZE=2048
ENABLE_TRAINING_COLLECTION=false
```

**python-nlp-service/.env**
```env
NLP_MODEL_CACHE=./models/cache
SENTIMENT_MODEL=cardiffnlp/twitter-roberta-base-sentiment-latest
NER_MODEL=dbmdz/bert-large-cased-finetuned-conll03-english
SUMMARIZATION_MODEL=facebook/bart-large-cnn
```

**python-document-intelligence-service/.env**
```env
OCR_SERVICE_URL=http://localhost:8000
ICR_SERVICE_URL=http://localhost:8001
NLP_SERVICE_URL=http://localhost:8002
```

### GPU Configuration

To disable GPU (use CPU only):
```bash
export CUDA_VISIBLE_DEVICES=""
# or
set CUDA_VISIBLE_DEVICES=
```

To use specific GPU:
```bash
export CUDA_VISIBLE_DEVICES=0  # Use first GPU
```

---

## 📊 Monitoring

### Logs

Each service creates logs:
```
python-ocr-service/ocr_service.log
python-icr-service/icr_service.log
python-nlp-service/nlp_service.log
python-document-intelligence-service/document_intelligence.log
```

### Monitor in Real-Time

```bash
# Windows
Get-Content document_intelligence.log -Wait -Tail 50

# Linux/Mac
tail -f document_intelligence.log
```

### Key Metrics to Monitor

- **Processing Time**: Should be < 5 seconds per document
- **Confidence Scores**: Should be > 0.80 for good results
- **Error Rates**: Should be < 5%
- **Memory Usage**: Monitor for leaks
- **GPU Utilization**: Should be high during processing

---

## 🐛 Troubleshooting

### Service Won't Start

**Problem:** Port already in use
```bash
# Windows
netstat -ano | findstr "8000"
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :8000
kill <PID>
```

**Problem:** Module not found
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**Problem:** CUDA/GPU errors
```bash
# Check CUDA installation
python -c "import torch; print(torch.cuda.is_available())"

# If False, use CPU mode
export CUDA_VISIBLE_DEVICES=""
```

### Slow Processing

**Problem:** Using CPU instead of GPU
- Verify CUDA installation
- Check `using_gpu: true` in health check
- Install GPU-enabled PyTorch

**Problem:** Model download slow
- Pre-download models:
```python
from transformers import pipeline
pipeline('image-to-text', model='microsoft/trocr-base-printed')
```

### Low Accuracy

**Problem:** Poor OCR results
- Ensure images are high resolution (300 DPI+)
- Check image quality (not blurry/skewed)
- Consider fine-tuning model

**Problem:** Poor handwriting recognition
- Try preprocessing (deskew, denoise)
- Collect training data for fine-tuning

---

## 📈 Scaling

### Horizontal Scaling

Run multiple instances behind a load balancer:

```nginx
# nginx.conf example
upstream ocr_service {
    server 127.0.0.1:8000;
    server 127.0.0.1:8010;
    server 127.0.0.1:8020;
}

server {
    listen 80;
    location /ocr {
        proxy_pass http://ocr_service;
    }
}
```

### Docker Deployment

```dockerfile
# Dockerfile example (python-ocr-service)
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "main.py"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  ocr:
    build: ./python-ocr-service
    ports:
      - "8000:8000"
    environment:
      - CUDA_VISIBLE_DEVICES=0
  
  icr:
    build: ./python-icr-service
    ports:
      - "8001:8001"
  
  nlp:
    build: ./python-nlp-service
    ports:
      - "8002:8002"
  
  doc-intel:
    build: ./python-document-intelligence-service
    ports:
      - "8003:8003"
    depends_on:
      - ocr
      - icr
      - nlp
```

---

## 🔒 Security

### Production Checklist

- [ ] Enable authentication (API keys, OAuth)
- [ ] Use HTTPS/TLS
- [ ] Implement rate limiting
- [ ] Validate file uploads (type, size)
- [ ] Sanitize extracted text
- [ ] Use environment variables for secrets
- [ ] Enable CORS restrictions
- [ ] Set up firewall rules
- [ ] Regular security updates
- [ ] Monitor for anomalies

---

## 📝 Next Steps

1. ✅ Services running
2. ✅ Health checks passing
3. → [Integrate with Projectena](./PROJECTENA_INTEGRATION.md)
4. → Configure network scanners
5. → Set up monitoring/alerting
6. → Plan backup strategy

---

**For Projectena integration, see [PROJECTENA_INTEGRATION.md](./PROJECTENA_INTEGRATION.md)**
