# AI Service Tier 1 - Lightweight Document Processing

A lightweight, production-ready microservice for document processing, classification, search, and question-answering. Designed for on-premise deployment with minimal dependencies and fast inference.

## Overview

**AI Service Tier 1** processes documents end-to-end:

1. **Document Splitting** - Automatically split multi-document PDFs into logical documents using embedding-based break detection
2. **Text Extraction** - OCR for both printed text (PaddleOCR) and handwriting (TrOCR)
3. **Classification** - Zero-shot document classification using sentence embeddings
4. **Signature Detection** - Detect signatures and handwritten marks using Florence-2
5. **Vector Search** - Semantic search across embeddings
6. **Question Answering** - Generate answers from document context using Llama 3.2 3B

## Architecture

```
Main Backend (Node.js/React)
         |
         | POST /api/v1/process (doc_id, pdf_path)
         v
   AI Service Tier 1 (FastAPI)
         |
    [Background Worker]
         |
    ├─ Split PDF (embedding-based)
    ├─ Extract Text (PaddleOCR + TrOCR)
    ├─ Classify (all-MiniLM-L12-v2)
    ├─ Detect Signatures (Florence-2)
    ├─ Generate Summary (Llama 3.2 3B)
    └─ Save to MongoDB
         |
         v
   MongoDB (documents collection)
         |
    [Client polls status]
```

## Model Stack

| Model | Purpose | Size | License |
|-------|---------|------|---------|
| **PaddleOCR v4** | Printed text recognition | ~200MB | Apache 2.0 |
| **TrOCR-large-handwritten** | Handwriting recognition | 1.4GB | Apache 2.0 |
| **Florence-2-base** | Object/form detection | 500MB | MIT |
| **all-MiniLM-L12-v2** | Zero-shot classification | 90MB | Apache 2.0 |
| **all-MiniLM-L6-v2** | Search embeddings | 80MB | Apache 2.0 |
| **Llama 3.2 3B GGUF** | Local LLM (Q&A) | 2-3GB | Llama 2 License |

**Total Footprint:** ~6-7GB

## Quick Start

### Local Installation

```bash
# 1. Clone repository
git clone <repo>
cd adaptive-Dokumentenverarbeitung

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup environment
cp .env.example .env
# Edit .env with your MongoDB connection

# 5. Run main server
uvicorn app.main:app --reload --port 8080
```

Main server will start on `http://localhost:8080`

### Testing (Optional)

Run the test server on a separate port (8001) to test individual components:

```bash
# In a new terminal, from the same directory
python run_test_server.py
```

Test server will start on `http://localhost:8001` with endpoints:
- `GET /test/health` - Test health check
- `GET /test/models` - List loaded models
- `POST /test/simple-ocr?image_path=<path>` - Test OCR on image
- `POST /test/embedding?text=<text>` - Test text embedding
- `POST /test/classification?text=<text>` - Test zero-shot classification

### Docker Deployment

```bash
# Build image
docker build -t ai-service-tier1:latest .

# Run container
docker run -p 8000:8000 \
  -e DATABASE_URL="mongodb://mongodb:27017" \
  -v /path/to/storage:/storage \
  ai-service-tier1:latest
```

## API Endpoints

### 1. Health Check
```http
GET /health
```

### 2. Service Status
```http
GET /api/v1/status
```

### 3. Process Document (Fire-and-Forget)
```http
POST /api/v1/process
{
  "doc_id": "doc_12345",
  "pdf_file_path": "/storage/uploads/invoice.pdf"
}
```

### 4. Vector Search
```http
POST /api/v1/search
{
  "query": "payment terms",
  "doc_id": "doc_12345",
  "top_k": 5
}
```

### 5. Question Answering
```http
POST /api/v1/query
{
  "doc_id": "doc_12345",
  "question": "What is the total amount due?"
}
```

## MongoDB Schema

Documents collection stores all processing results:

```javascript
{
  _id: "doc_12345",
  status: "COMPLETE",  // PENDING | PROCESSING | COMPLETE | FAILED
  created_at: ISODate("2025-11-15T10:00:00Z"),
  processing_started: ISODate("2025-11-15T10:05:00Z"),
  processing_completed: ISODate("2025-11-15T10:08:00Z"),
  pdf_path: "/storage/uploads/invoice.pdf",
  
  processed_data: [
    {
      logical_doc_num: 0,
      page_range: "0-2",
      page_count: 3,
      text: "Invoice #INV-001...",
      embedding: [0.123, -0.456, ...],
      classification: { label: "Invoice", score: 0.92 },
      signature_detected: true,
      summary: "Invoice from Acme Corp for $5,250...",
      processed_at: "2025-11-15T10:08:00Z"
    }
  ],
  
  document_count: 1,
  error: null
}
```

## Configuration

Copy `.env.example` to `.env`:

```bash
DATABASE_URL=mongodb://localhost:27017
MAIN_DB_NAME=document_processing
HOST=0.0.0.0
PORT=8000
MODELS_DIR=/app/models
LLAMA_MODEL_PATH=/app/models/llama-3.2-3b-gguf/model.gguf
USE_GPU=true
DOCUMENT_SPLIT_SIMILARITY_THRESHOLD=0.5
```

## Performance

- **Single Page:** 1.5-2.5 seconds
- **10-Page Document:** 8-15 seconds  
- **GPU vs CPU:** 3-5x faster with NVIDIA GPU (CUDA 11.8+)

## Troubleshooting

**Models Not Loading:**
```bash
docker logs ai-service-tier1
df -h  # Verify 8GB+ free space
```

**MongoDB Connection Failed:**
```bash
docker ps | grep mongodb
# Check DATABASE_URL in .env
```

**Out of Memory:**
```bash
USE_GPU=false  # Use CPU instead
```

## Development

```bash
# Local development with hot reload
uvicorn app.main:app --reload --port 8000

# Build Docker image
docker build -t ai-service-tier1:latest .

# Run tests
pytest tests/
```

## Integration with Main Backend

Node.js/React backend integration:

```javascript
// 1. Queue processing
await fetch('http://localhost:8080/api/v1/process', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    doc_id: 'doc_12345',
    pdf_file_path: '/storage/uploads/invoice.pdf'
  })
});

// 2. Poll MongoDB for results
const doc = await db.collection('documents').findOne({_id: 'doc_12345'});
if (doc.status === 'COMPLETE') {
  console.log(doc.processed_data);
}

// 3. Search documents
const results = await fetch('http://localhost:8080/api/v1/search', {
  method: 'POST',
  body: JSON.stringify({ query: 'payment terms', top_k: 5 })
});

// 4. Ask questions
const answer = await fetch('http://localhost:8080/api/v1/query', {
  method: 'POST',
  body: JSON.stringify({
    doc_id: 'doc_12345',
    question: 'What is the total amount?'
  })
});
```

## License

Apache 2.0
