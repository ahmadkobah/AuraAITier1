# Adaptive Document Processing - AI Service (Tier 1)

The AI service behind the Aura document platform. It reads scanned PDFs, splits them into
individual documents, recognises their type, extracts structured data, and makes every
document searchable and answerable in natural language.

---

## Table of Contents

1. [Overview](#overview)
2. [Project Status](#project-status)
3. [How It Works](#how-it-works)
4. [Processing Pipeline](#processing-pipeline)
5. [Components](#components)
6. [AI Models](#ai-models)
7. [Technology Stack](#technology-stack)
8. [Project Structure](#project-structure)
9. [Getting Started](#getting-started)
10. [Configuration](#configuration)
11. [API Reference](#api-reference)
12. [Integration with Aura and the Control Panel](#integration-with-aura-and-the-control-panel)
13. [Security](#security)
14. [Testing](#testing)
15. [Known Issues](#known-issues)
16. [License](#license)

---

## Overview

### Purpose

Companies receive large batches of mixed paper documents: invoices, contracts, delivery notes,
letters and forms, often scanned together into one PDF file. Sorting these pages, typing their
key fields into business systems and finding a document again later costs a lot of manual work.

This service automates that work. It is a Python REST API that:

- reads printed text from scanned pages (OCR) and handwriting (ICR),
- detects where one document ends and the next begins inside a single PDF,
- classifies each document into one of 31 business document types,
- extracts structured fields (for example invoice number, date, total) and entities
  (companies, people, dates, amounts, addresses, e-mail addresses, phone numbers),
- writes a short summary of each document,
- creates semantic search vectors, so users can find documents by meaning, not only by exact words,
- answers questions about the documents in natural language.

All processing runs locally. Documents are not sent to external AI services. The language
model (Llama 3.2 3B) runs on the same machine through Llamafile.

### Intended users

- **The Aura backend**, which uploads documents and reads the results.
- **The Aura Control Panel**, which manages prompts, classifications, search settings and
  feature toggles for this service.
- **Developers** who need document AI through a REST API.

### Part of the Aura platform

| System | Role | Default port |
|--------|------|--------------|
| Aura backend | Main application, users, companies, documents | 8000 |
| Aura Control Panel | Administration and configuration | 4000 |
| **AI Service (this repository)** | **Document processing, search and Q&A** | **9000** |
| Llamafile (Llama 3.2 3B) | Local language model server | 8080 |
| MongoDB | Shared database (`aura`) | 27017 |

---

## Project Status

Version 2.0.0. The core pipeline is in active use and development.

| Feature | Status |
|---------|--------|
| PDF splitting into logical documents | Working |
| OCR with PaddleOCR | Working |
| Rule-based and LLM-based OCR correction | Working (optional) |
| Document classification (31 types) | Working |
| Structured field extraction | Working |
| Entity extraction | Working (optional) |
| Summaries | Working (optional) |
| Semantic search (FAISS) | Working |
| Question answering and conversational search | Working |
| Runtime configuration through the API | Working |
| Physical scanner support (Windows WIA) | Working on Windows only |
| Signature detection | Text-pattern based; image-based detection is not active |
| Table extraction | Disabled in the pipeline; line items come from OCR text |
| YOLO layout model (DocLayNet) | Trained; not yet used by the pipeline |
| Docker deployment | Not working yet (see [Known Issues](#known-issues)) |

---

## How It Works

```
   Aura backend / Control Panel / scanner
                    |
                    | REST (JSON, multipart)       X-API-Key
                    v
   +-------------------------------------------+
   |  AI Service  (FastAPI, port 9000)          |
   |                                           |
   |  /api/v1/upload  -->  background task      |
   |                         |                 |
   |                         v                 |
   |             AI processing pipeline        |
   |   split > OCR > correct > classify >      |
   |   extract > summarise > embed > store     |
   +----+----------------+----------------+----+
        |                |                |
        v                v                v
   +---------+    +-------------+   +-------------------+
   | MongoDB |    | Llamafile   |   | Local AI models   |
   | `aura`  |    | Llama 3.2 3B|   | PaddleOCR, TrOCR, |
   |         |    | port 8080   |   | MiniLM embeddings |
   +---------+    +-------------+   +-------------------+
```

1. A client uploads a PDF to `/api/v1/upload`, or asks the service to process a file that
   already exists (`/api/v1/process`).
2. The service saves the file, creates or updates a record in the `documents` collection
   with status `PROCESSING`, and returns at once.
3. The pipeline runs as a background task.
4. When it finishes, the record contains a `processed_data` array (one entry per logical
   document) and the status changes to `COMPLETE`.
5. The client polls `/api/v1/documents/{doc_id}/status`, then uses search, Q&A and extraction
   endpoints on the result.

---

## Processing Pipeline

Implemented in `app/core/pipeline.py`. Every optional step can be turned on or off through
environment variables, the runtime configuration API, or a per-request override sent by the
Control Panel.

| Step | What it does | Technology | Toggle |
|------|--------------|------------|--------|
| 1. PDF splitting | Converts pages to images, reads text, and finds where one document ends and the next begins by comparing page embeddings | pdf2image, PaddleOCR, Sentence Transformers | `ENABLE_PDF_SPLITTING` |
| 2. OCR validation | Fixes common OCR mistakes (for example `0`/`O`, `l`/`1`) with rules, and optionally with the language model; skipped when OCR quality is already high | Rules + Llama 3.2 3B | `ENABLE_OCR_VALIDATION` |
| 3. Classification | Picks one of 31 document types by embedding similarity; the language model confirms or corrects uncertain results | Sentence Transformers + Llama 3.2 3B | `ENABLE_CLASSIFICATION` |
| 4. Signature detection | Finds signer names from patterns such as "Signed by" or "Authorized Signature" | Regular expressions | `ENABLE_SIGNATURE_DETECTION` |
| 5. Signature validation | Checks and corrects the detected name | Llama 3.2 3B | `ENABLE_SIGNATURE_VALIDATION` |
| 6. Structured extraction | Extracts type-specific fields such as invoice number, dates, totals and parties | Llama 3.2 3B | `ENABLE_STRUCTURED_EXTRACTION` |
| 7. Entity extraction | Extracts companies, people, dates, amounts, addresses, e-mail addresses and phone numbers | Llama 3.2 3B | `ENABLE_ENTITY_EXTRACTION` |
| 8. Summary | Writes a short summary; falls back to the first 500 characters if the model is not available | Llama 3.2 3B | `ENABLE_SUMMARY` |
| 9. Embedding | Creates a 384-dimension vector for semantic search | paraphrase-multilingual-MiniLM-L12-v2 | `ENABLE_EMBEDDING_GENERATION` |
| 10. Storage | Saves all results to MongoDB and refreshes the search index | MongoDB, FAISS | `ENABLE_MONGODB_STORAGE` |

Steps 6, 7 and 8 run in parallel. Every model call has a time limit, so a slow or stopped
language model never blocks the pipeline.

### Supported document types

Invoice, Receipt, Purchase Order, Credit Note, Debit Note, Payment Voucher, Bank Statement,
Financial Statement, Tax Document, Contract, Agreement, Non-Disclosure Agreement, Memorandum of
Understanding, Certificate, License, Permit, Report, Business Letter, Memo, Proposal, Quotation,
Tender Document, Form, Delivery Note, Packing Slip, Bill of Lading, Shipping Document, Resume,
Job Application, Employment Contract, Other.

---

## Components

| Path | Responsibility |
|------|----------------|
| `main.py` | Entry point. Checks MongoDB, starts Llamafile, waits until it is ready, starts the API on port 9000, and stops Llamafile on shutdown |
| `app/api/endpoints.py` | Main REST API: processing, status, search, Q&A, extraction, OCR, scanner and health endpoints |
| `app/api/config_endpoints.py` | Runtime configuration: read, change and reset settings without a restart |
| `app/api/sync_endpoints.py` | Synchronisation with Aura and the Control Panel: document deletion, search settings, classifications, prompts |
| `app/core/pipeline.py` | The processing pipeline described above |
| `app/core/classifier.py` | PDF splitting, text extraction and document classification |
| `app/models/loader.py` | Loads all models once, chooses GPU or CPU, and manages GPU memory |
| `app/services/ocr_validation.py` | OCR quality scoring and correction |
| `app/services/signature_validation.py`, `signature_ocr.py` | Signature checks and handwriting reading |
| `app/services/table_extraction.py` | Table extraction with PaddleOCR PPStructure (currently not called by the pipeline) |
| `app/utils/extraction.py` | Structured data and entity extraction, date and amount normalisation |
| `app/utils/vector_index.py` | FAISS search index; rebuilt at most every 5 minutes, or right after new documents |
| `app/utils/prompt_manager.py` | Loads prompts from the Control Panel by company, tier and document type |
| `app/scanner/scanner_service.py` | Access to physical scanners through Windows Image Acquisition (WIA) |
| `config/settings.py` | Central settings: paths, limits, thresholds |
| `scripts/` | Start scripts, CUDA setup, Llamafile monitor, dataset and training tools |
| `tests/` | Unit tests |

---

## AI Models

All models run locally. Model files are not stored in Git (see `.gitignore`); place them in
`models/` or let the libraries download them on first start.

| Model | Purpose | Location |
|-------|---------|----------|
| PaddleOCR | Printed text recognition | Downloaded by PaddleOCR |
| TrOCR Large Handwritten (`microsoft/trocr-large-handwritten`) | Handwriting recognition | `models/trocr/official/`, `TROCR_MODEL_PATH`, or download |
| paraphrase-multilingual-MiniLM-L12-v2 | Embeddings for splitting, classification and search (384 dimensions, supports German and English) | `models/sentence-transformers/` or download |
| Llama 3.2 3B (Llamafile) | OCR correction, classification reasoning, extraction, summaries, Q&A | `models/llamafile/llama-3.2-3b.exe` |
| YOLOv8n layout model | Document layout detection (8 classes, trained on DocLayNet); not yet used by the pipeline | `yolov8n.pt`, `models/yolo/` |

---

## Technology Stack

| Area | Technology | Purpose |
|------|------------|---------|
| API | FastAPI, Uvicorn, Pydantic 2 | REST API, validation, OpenAPI documentation |
| OCR | PaddleOCR, PaddlePaddle | Printed text recognition |
| Handwriting | Hugging Face Transformers (TrOCR) | Handwriting recognition |
| Language model | Llama 3.2 3B through Llamafile | Reasoning, extraction, summaries, Q&A |
| Embeddings | Sentence Transformers | Semantic vectors |
| Vector search | FAISS (`faiss-cpu`) | Fast similarity search |
| Machine learning | PyTorch | Model runtime, GPU (CUDA) support |
| Images and PDF | pdf2image (Poppler), OpenCV, Pillow, PyPDF2 | Page rendering and image processing |
| Database | MongoDB, PyMongo | Documents and results |
| Utilities | json_repair, pandas, psutil, requests, httpx, python-dotenv | Robust JSON parsing, data handling, monitoring |
| Scanner | pywin32 (WIA) | Physical scanner access on Windows |
| Tests | pytest | Unit tests |

---

## Project Structure

```
AuraAITier1/
|-- main.py                     Entry point (starts Llamafile and the API)
|-- app/
|   |-- api/                    REST endpoints (main, configuration, synchronisation)
|   |-- core/                   Pipeline and classifier
|   |-- models/                 Model loading and GPU management
|   |-- services/               OCR validation, signatures, tables
|   |-- utils/                  Extraction, FAISS index, prompt manager
|   `-- scanner/                Windows scanner integration
|-- config/
|   `-- settings.py             Central configuration
|-- models/                     Model files (not in Git)
|-- data/                       Uploads and temporary files (created at start-up)
|-- scripts/                    Start, setup, dataset and training scripts
|-- tests/                      Unit tests
|-- test_documents/             Manual debugging scripts
|-- requirements.txt
|-- Dockerfile
`-- docker-compose.yml
```

---

## Getting Started

### Prerequisites

- Windows 10 or 11 (Llamafile is started as a Windows executable, and scanner support uses WIA)
- Python 3.10 or later
- MongoDB 7, local or MongoDB Atlas
- Poppler (for PDF conversion); set `POPPLER_PATH` if it is not on your `PATH`
- Optional: NVIDIA GPU with CUDA for faster processing (the service also runs on CPU)
- At least 8 GB RAM

### 1. Clone and install

```bash
git clone https://github.com/ahmadkobah/AuraAITier1.git
cd AuraAITier1
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Add the language model

Place the Llama 3.2 3B Llamafile at `models/llamafile/llama-3.2-3b.exe`.

### 3. Configure

Create a `.env` file in the project root (see [Configuration](#configuration)). The minimum is
the MongoDB connection.

### 4. Start

```bash
python main.py
```

This starts Llamafile on port 8080, waits until it is ready (up to 90 seconds), and starts the
API on port 9000. Press `Ctrl+C` to stop both.

To start only the API (when Llamafile already runs):

```bash
uvicorn main:app --host 0.0.0.0 --port 9000
```

### 5. Check

```bash
curl http://localhost:9000/health
```

Interactive API documentation: `http://localhost:9000/docs`

---

## Configuration

Settings are read in this order (highest first):

1. Per-request overrides sent by the Control Panel (company or tier settings)
2. Runtime configuration changed through `/api/v1/config`
3. Environment variables from `.env`
4. Built-in defaults

### Main settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DB` | `mongodb://admin:password@localhost:27017` | MongoDB connection string used by the API |
| `DATABASE_NAME` or `MONGODB_DB` | `aura` | Database name |
| `LLAMAFILE_URL` | `http://127.0.0.1:8080` | Llamafile server address |
| `AI_SERVICE_API_KEY` | empty | API key for all requests; empty means no check (development only) |
| `CORS_ORIGINS` | `http://localhost:3000,4000,5173,8000` | Allowed browser origins, comma-separated |
| `CONTROL_PANEL_URL` | `http://localhost:4000` | Control Panel address for prompts |
| `ENABLE_DEBUG_ENDPOINTS` | `false` | Turns on the `/api/v1/test-*` endpoints |
| `POPPLER_PATH` | not set | Folder of the Poppler binaries |

### GPU and models

| Variable | Default | Description |
|----------|---------|-------------|
| `FORCE_GPU` / `USE_GPU` | `true` | Use the GPU when available |
| `MAX_GPU_MEMORY_MB` | `4096` | GPU memory limit |
| `GPU_LAYERS` | `29` | Model layers loaded on the GPU |
| `SENTENCE_TRANSFORMER_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Embedding model |
| `TROCR_MODEL_PATH` | not set | Local TrOCR model folder |
| `LLAMA_CONTEXT_WINDOW` | `8192` | Language model context size |

### Processing limits

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_PDF_SIZE_MB` | `200` | Largest accepted PDF |
| `MAX_PAGES_PER_DOCUMENT` | `50` | Page limit per document |
| `PDF_CONVERSION_DPI` | `200` | Resolution for page images |
| `OCR_CONFIDENCE_THRESHOLD` | `50` | Minimum OCR confidence (0 to 100) |
| `OCR_QUALITY_SKIP_THRESHOLD` | `0.95` | Skip OCR correction above this quality |
| `CLASSIFICATION_MIN_CONFIDENCE` | `0.08` | Minimum classification confidence |
| `LLAMA_OVERRIDE_CONFIDENCE` | `0.85` | Confidence needed for the language model to change a classification |
| `SIGNATURE_CONFIDENCE_THRESHOLD` | `0.6` | Minimum signature confidence |
| `SEARCH_TOP_K_DEFAULT` | `5` | Default number of search results |

### Feature toggles

`ENABLE_PDF_SPLITTING`, `ENABLE_OCR_VALIDATION`, `ENABLE_CLASSIFICATION`,
`ENABLE_SIGNATURE_DETECTION`, `ENABLE_SIGNATURE_VALIDATION`, `ENABLE_STRUCTURED_EXTRACTION`,
`ENABLE_ENTITY_EXTRACTION`, `ENABLE_SUMMARY`, `ENABLE_EMBEDDING_GENERATION`,
`ENABLE_MONGODB_STORAGE`. All accept `true` or `false`.

Each language model task also has its own `*_TEMPERATURE`, `*_MAX_TOKENS` and `*_TIMEOUT`
setting. The full list is in `app/api/config_endpoints.py`.

---

## API Reference

All endpoints except `/health`, `/docs`, `/redoc` and `/openapi.json` require the header
`X-API-Key` when `AI_SERVICE_API_KEY` is set.

### Processing

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/upload` | Upload a PDF (multipart) and start processing |
| POST | `/api/v1/process` | Process a file that is already stored |
| GET | `/api/v1/documents/{doc_id}/status` | Processing status and results |
| DELETE | `/api/v1/documents/{doc_id}` | Delete a document and remove it from the search index |

### Search and questions

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/search` | Semantic search |
| POST | `/api/v1/conversational-search` | Search with an answer written by the language model |
| POST | `/api/v1/query` | Ask a question about documents (`/api/v1/qa` is an alias) |

### Analysis

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/summarize` | Summarise a document |
| POST | `/api/v1/extract` | Extract structured fields |
| POST | `/api/v1/entities` | Extract entities |
| POST | `/api/v1/validate-ocr` | Check and correct OCR text |
| POST | `/ocr/extract`, `/ocr/extract/batch` | OCR on one or more files |
| POST | `/ocr/validate` | OCR quality check |
| POST | `/classify` | Classify a text |
| POST | `/extraction/structured`, `/extraction/entities` | Extraction on raw text |
| POST | `/embeddings/generate` | Create an embedding vector |

### Scanner

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/scanners` | List connected scanners (Windows) |
| POST | `/api/v1/scan` | Scan a page and process it |

### Configuration and synchronisation

| Method | Path | Description |
|--------|------|-------------|
| GET, POST | `/api/v1/config/` | Read or change the runtime configuration |
| POST | `/api/v1/config/reset` | Restore the defaults |
| GET | `/api/v1/search/config` | Search settings |
| POST | `/api/v1/search/config/bulk-update` | Update search settings |
| GET | `/api/v1/classifications` | Classification definitions |
| POST | `/api/v1/classifications/bulk-update` | Update classifications |
| GET | `/api/v1/prompts` | Prompt settings |
| POST | `/api/v1/prompts/bulk-update` | Update prompts |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (no API key needed) |
| GET | `/api/v1/status` | Service and model status |
| GET | `/system/hardware` | CPU, GPU and memory usage |

Example:

```bash
curl -X POST http://localhost:9000/api/v1/upload \
  -H "X-API-Key: <your-key>" \
  -F "file=@scan.pdf"
```

---

## Integration with Aura and the Control Panel

- **Aura backend** uploads documents, reads processing results from the shared `documents`
  collection, and calls `DELETE /api/v1/documents/{id}` when a user deletes a document.
- **Aura Control Panel** manages search settings, classifications, prompts and feature toggles
  through the synchronisation and configuration endpoints, and can send company or tier
  overrides with each processing request.
- Prompts are loaded from the Control Panel and chosen by company, tier and document type.

---

## Security

- **API key.** Every request is checked against `AI_SERVICE_API_KEY` with a constant-time
  comparison. Always set a key outside development.
- **CORS.** Only the origins in `CORS_ORIGINS` are allowed.
- **File access.** File paths are limited to the upload and temporary folders, to block path
  traversal.
- **Input cleaning.** Document IDs are cleaned before they are used in database queries and logs.
- **Debug endpoints.** Test endpoints are off unless `ENABLE_DEBUG_ENDPOINTS=true`.
- **Local processing.** Documents and model calls stay on your own machine.

---

## Testing

```bash
pytest tests/
pytest --cov=app tests/
```

The unit tests cover date and amount normalisation, JSON repair, OCR correction and quality
scoring, path-traversal protection, document ID cleaning and vector normalisation.

---

## Known Issues

- **Docker:** the `Dockerfile` copies only `app/` (not `main.py` or `config/`), exposes port 8000
  instead of 9000, and `requirements.txt` includes `pywin32`, which does not install on Linux.
  `docker-compose.yml` also maps the service to port 8080, which Llamafile uses. Use the local
  setup until these are fixed.
- **Docker Compose credentials:** `docker-compose.yml` uses fixed development passwords. Do not
  use it in production as it is.
- **Missing requirements:** `torch`, `PyPDF2` and `httpx` are used in the code but are not
  listed in `requirements.txt`. PyTorch comes in through Sentence Transformers; install the
  other two by hand.
- **Configuration names:** the API reads the database address from `DB`, while
  `config/settings.py` reads `MONGO_URL` or `MONGODB_URI`. Set both to the same value.
- **Upload format:** `/api/v1/upload` accepts PDF files only.
- **Platform:** `main.py` starts a Windows Llamafile executable. On Linux or macOS, start
  Llamafile yourself and run only the API with `uvicorn`.
- **Start scripts:** `scripts/start_services.ps1` starts older separate services
  (`python-ocr-service` and others) that are no longer in this repository. Use `python main.py`.

---

## License

MIT License.

Author: Ahmad Kobah
