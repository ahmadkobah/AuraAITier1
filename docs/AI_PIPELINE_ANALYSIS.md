# AI Service Pipeline — Complete Analysis

> **Generated**: March 13, 2026  
> **Project**: adaptive-Dokumentenverarbeitung (AI Service)  
> **Stack**: FastAPI · PaddleOCR · YOLOv8 · TrOCR · LLaMA 3.2 3B · Sentence Transformers · PPStructureV3

---

## Table of Contents

1. [Overview](#overview)
2. [High-Level Flow](#high-level-flow)
3. [The 11 Pipeline Steps](#the-11-pipeline-steps)
   - [Step 1: PDF Splitting & Text Extraction](#step-1-pdf-splitting--text-extraction)
   - [Step 2: OCR Quality Validation](#step-2-ocr-quality-validation)
   - [Step 3: Document Classification](#step-3-document-classification)
   - [Step 4: Signature Detection](#step-4-signature-detection)
   - [Step 5: Signature Text Extraction (OCR)](#step-5-signature-text-extraction-ocr)
   - [Step 6: Signature Text Validation](#step-6-signature-text-validation)
   - [Step 7: Signature Authenticity Check](#step-7-signature-authenticity-check)
   - [Step 8: Structured Data Extraction](#step-8-structured-data-extraction)
   - [Step 9: Named Entity Extraction](#step-9-named-entity-extraction)
   - [Step 10: Table Extraction](#step-10-table-extraction)
   - [Step 11: Summary Generation](#step-11-summary-generation)
4. [Data Flow Diagram](#data-flow-diagram)
5. [AI Models Used](#ai-models-used)
6. [Module Map](#module-map)
7. [31 Supported Document Types](#31-supported-document-types)
8. [Configuration & Runtime Parameters](#configuration--runtime-parameters)
9. [Smart Design Patterns](#smart-design-patterns)
10. [API Endpoints](#api-endpoints)
11. [Pipeline Flaws & Optimization Opportunities](#pipeline-flaws--optimization-opportunities)
12. [Quality Impact Analysis — OCR, ICR, NLP & Data Completeness](#quality-impact-analysis--ocr-icr-nlp--data-completeness)

---

## Overview

The **adaptive-Dokumentenverarbeitung** AI Service is an 11-step document processing pipeline that takes uploaded PDFs and produces structured, searchable, queryable data. It combines multiple AI models for OCR, classification, signature detection, field extraction, table parsing, and summarization — all orchestrated by a single background pipeline function and stored in MongoDB.

---

## High-Level Flow

```
PDF Upload → Split → OCR Validate → Classify → Detect Signatures
→ OCR Signatures → Validate Signatures → Extract Structured Data
→ Extract Tables → Generate Summary → Store in MongoDB
```

---

## The 11 Pipeline Steps

The main orchestrator is `run_full_ai_pipeline()` in `app/core/pipeline.py`. Each step can be individually enabled/disabled via runtime configuration.

---

### Step 1: PDF Splitting & Text Extraction

| | |
|---|---|
| **File** | `app/core/classifier.py` |
| **Function** | `split_pdf_and_find_breaks()` |
| **Models** | PaddleOCR, all-MiniLM-L6-v2 |

**Process:**
1. Convert PDF pages to images (pdf2image + Poppler)
2. OCR each page via PaddleOCR with confidence scores (`extract_text_from_image()`)
3. Generate sentence embeddings for each page (all-MiniLM-L6-v2, 384-dim)
4. Calculate cosine similarity between consecutive pages
5. Detect document breaks when similarity < threshold (default 0.5)
6. Group pages into logical documents
7. Calculate aggregate OCR confidence per logical document

**Output:**
```python
{
    'doc_num': int,
    'start_page': int,
    'end_page': int,
    'page_count': int,
    'text': str,              # Combined page text
    'embedding': [float],     # 384-dim vector
    'ocr_confidence': {
        'avg': float,
        'min': float
    },
    'pages': [numpy_arrays]   # Page images
}
```

---

### Step 2: OCR Quality Validation

| | |
|---|---|
| **File** | `app/services/ocr_validation.py` |
| **Function** | `validate_ocr_quality()` |
| **Models** | LLaMA (FULL tier only) |

**Smart Routing — 4 Tiers:**

| Tier | Confidence | Action | LLaMA Used? |
|------|------------|--------|-------------|
| SKIP | ≥ 95% | No correction needed | No |
| LIGHT | 75–94% | Regex fixes only | No |
| FULL | 50–74% | Full LLaMA correction | Yes |
| REVIEW | < 50% | Flag for review + best effort | Best effort only |

**Regex Fixes (applied in LIGHT/REVIEW):**
- `0` ↔ `O` confusion in words/numbers
- `1` ↔ `l` ↔ `I` confusion
- `rn` → `m` (common OCR error)
- `5` ↔ `S`, `8` ↔ `B`
- Date and currency pattern fixes

**FULL LLaMA Validation (50–74% confidence):**
- Prompt preserves original formatting/structure
- Temperature: 0.05 (ultra-low creativity)
- Max tokens: 2500
- Rejects if LLaMA reformats (>30% length change)

**Output:**
```python
{
    'corrected_text': str,
    'quality_score': float,
    'issues_found': [str],
    'corrections_made': int,
    'confidence': float,
    'routing_tier': 'skip' | 'light' | 'full' | 'review'
}
```

---

### Step 3: Document Classification

| | |
|---|---|
| **File** | `app/core/classifier.py` |
| **Functions** | `classify_text()`, `classify_with_reasoning()` |
| **Models** | all-MiniLM-L12-v2, LLaMA |

**Phase 1 — Embedding Classification:**
1. Encode text + 31 document type labels with MiniLM
2. Compute cosine similarities
3. Apply softmax normalization
4. Select top label if confidence ≥ 8%
5. If < 8%: classify as "Other"

**Phase 2 — LLaMA Reasoning (if confidence < 15% or always if enabled):**
1. Provide document context + initial classification to LLaMA
2. Analyze document structure, key indicators, signatures
3. LLaMA returns: reasoning + key indicators + validation
4. Can override initial classification if high confidence

**Output:**
```python
{
    'label': 'Invoice',
    'score': 0.92,
    'confidence': 0.92,
    'all_scores': {dict},           # All 31 type probabilities
    'reasoning': str,               # If LLaMA used
    'key_indicators': [str],        # If LLaMA used
    'validated': bool
}
```

---

### Step 4: Signature Detection

| | |
|---|---|
| **File** | `app/services/signature_detection.py` |
| **Function** | `detect_signature_boxes()` |
| **Model** | YOLOv8n |

**Process:**
1. Check GPU memory (need ≥ 512MB)
2. Move YOLOv8n to GPU if available
3. Run YOLO inference on page image
4. Extract bounding boxes (x, y, w, h) with confidence
5. Filter by confidence threshold (default 0.60)
6. Apply Non-Maximum Suppression (IOU threshold: 0.45)
7. Move model back to CPU, clear GPU cache

**Output:**
```python
[
    {
        'box': (x, y, w, h),
        'confidence': float,
        'image': 'base64_encoded_png'  # Optional
    }
]
```

---

### Step 5: Signature Text Extraction (OCR)

| | |
|---|---|
| **File** | `app/services/signature_ocr.py` |
| **Function** | `ocr_signature()` |
| **Model** | TrOCR Large |

**Process:**
1. Crop signature region with padding (uses best YOLO box)
2. Fallback: crop bottom 22% of page (common signature location)
3. Check GPU memory (need ≥ 1GB for TrOCR)
4. Move TrOCR to GPU if available
5. Prepare image inputs with processor
6. Generate with beam search (max 64 tokens)
7. Decode tokens to text
8. Move model back to CPU

**Output:**
```python
{
    'found': bool,
    'text': 'John Smith',
    'box': {'x': int, 'y': int, 'w': int, 'h': int},
    'confidence': float  # 0.75 if detected, 0.4 if fallback
}
```

---

### Step 6: Signature Text Validation

| | |
|---|---|
| **File** | `app/services/signature_validation.py` |
| **Function** | `validate_signature_text()` |
| **Model** | LLaMA |

**Process:**
1. Extract all person names from document via LLaMA (`extract_names_from_document()`)
2. LLaMA fixes handwriting OCR errors (e.g., "Jahn" → "John", "Smth" → "Smith")
3. Cross-reference with names found in document
4. Assess confidence (high / medium / low)

**Output:**
```python
{
    'corrected_signature': 'John Smith',
    'confidence': 0.9,
    'validation_passed': bool,
    'suggestions': [str],
    'cross_referenced_names': [str],
    'matched_document_name': 'John Smith'
}
```

---

### Step 7: Signature Authenticity Check

| | |
|---|---|
| **File** | `app/services/signature_validation.py` |
| **Function** | `validate_signature_authenticity()` |
| **Model** | LLaMA |

**LLaMA Checks:**
1. **Placement** — Is signature in correct location for document type?
2. **Completeness** — Are all required fields filled?
3. **Date consistency** — Does signature date match document date?
4. **Name consistency** — Does signature match names in document?

**Output:**
```python
{
    'authenticity_score': float,       # high=0.9, medium=0.6, low=0.3
    'indicators_found': [str],
    'warnings': [str],
    'recommendation': 'No review needed' | 'Manual review recommended' | 'Flag for review'
}
```

---

### Step 8: Structured Data Extraction

| | |
|---|---|
| **File** | `app/utils/extraction.py` |
| **Function** | `extract_structured_data()` |
| **Model** | LLaMA |

**Process:**
1. Select extraction schema based on document type (from Step 3)
2. Build LLaMA prompt with field list and document text
3. LLaMA extracts specific fields (max 500 tokens)
4. Parse JSON response
5. Validate extracted fields

**Example — Invoice Schema Fields:**
`invoice_number`, `invoice_date`, `due_date`, `vendor_name`, `vendor_address`, `customer_name`, `customer_address`, `subtotal`, `tax_amount`, `total_amount`, `currency`, `payment_terms`, `bank_name`, `account_number`, `routing_number`, `swift_code`, `IBAN`

**Output:**
```python
{
    'success': bool,
    'fields': {
        'invoice_number': '12345',
        'total_amount': 1250.00,
        'currency': 'USD',
        ...
    },
    'confidence': float,
    'missing_fields': [str]
}
```

---

### Step 9: Named Entity Extraction

| | |
|---|---|
| **File** | `app/utils/extraction.py` |
| **Status** | Infrastructure ready, not fully implemented |

**Planned capabilities:**
- Extract company names, person names, dates, amounts, phone numbers, emails
- Uses LLaMA with NER prompts

---

### Step 10: Table Extraction

| | |
|---|---|
| **File** | `app/services/table_extraction.py` |
| **Function** | `extract_tables_from_image()` |
| **Models** | PPStructureV3, LLaMA |

**Process:**
1. Initialize PPStructureV3 with table recognition enabled
2. Run table detection on page images
3. Extract HTML table structure (bordered + borderless)
4. Parse HTML to rows/columns via `parse_html_table()`
5. **LLaMA Validation** (`validate_table_with_llama()`):
   - Verify table structure (correct rows/cols?)
   - Check data consistency (numbers, currencies)
   - Validate calculations
   - Fix OCR errors in cell values
6. Apply LLaMA corrections if confidence is sufficient
7. Convert all NumPy types to Python native for MongoDB

**Output:**
```python
[
    {
        'table_id': 1,
        'bbox': [x1, y1, x2, y2],
        'confidence': float,
        'html': '<table>...</table>',
        'rows': [['header1', 'header2'], ['val1', 'val2']],
        'structure': {'num_rows': int, 'num_cols': int},
        'llama_validated': bool,
        'validation_confidence': float
    }
]
```

---

### Step 11: Summary Generation

| | |
|---|---|
| **File** | `app/api/endpoints.py` |
| **Function** | `generate_llama_summary()` |
| **Model** | LLaMA |

**Process:**
1. Call LLaMA HTTP API at `http://localhost:8080/v1/chat/completions`
2. Temperature: 0.3 (moderate creativity)
3. Max tokens: 300
4. Return 3–4 sentence natural language summary

---

## Data Flow Diagram

```
1. User uploads PDF
   ↓
2. POST /api/v1/process
   ├→ Create MongoDB document (status: PENDING)
   └→ Return process_id to user immediately
   ↓
3. Background task: run_full_ai_pipeline()
   │
   ├→ STEP 1:  split_pdf_and_find_breaks()
   │           → Logical documents + OCR confidence
   │
   ├→ STEP 2:  validate_ocr_quality()
   │           → Corrected text + quality tier
   │
   ├→ STEP 3:  classify_text() + classify_with_reasoning()
   │           → Document type + confidence
   │
   ├→ STEP 4:  detect_signature_boxes()
   │           → Signature bounding boxes
   │
   ├→ STEP 5:  ocr_signature()
   │           → Handwritten text from signatures
   │
   ├→ STEP 6:  validate_signature_text()
   │           → Corrected signature text
   │
   ├→ STEP 7:  validate_signature_authenticity()
   │           → Authenticity score + recommendation
   │
   ├→ STEP 8:  extract_structured_data()
   │           → Typed fields (invoice #, amount, etc.)
   │
   ├→ STEP 9:  (Reserved) Entity extraction
   │
   ├→ STEP 10: extract_tables_from_image()
   │           → Parsed tables with rows/columns
   │
   └→ STEP 11: generate_llama_summary()
               → Natural language summary
   ↓
4. MongoDB storage:
   processed_data: [{
       text, ocr_validation, classification,
       signatures[], extracted_fields{},
       tables[], summary, embedding[384]
   }]
   ↓
5. Document status → COMPLETE
   ↓
6. Query APIs available:
   ├→ GET  /api/v1/search   → Vector search on embeddings
   ├→ POST /api/v1/query    → Q&A with LLaMA context
   └→ GET  /api/v1/documents/{id} → Full results
```

---

## AI Models Used

| Model | Purpose | GPU Memory | Device Strategy |
|-------|---------|------------|-----------------|
| **PaddleOCR** | Printed text recognition (OCR) | Low | CPU/GPU |
| **all-MiniLM-L6-v2** | Sentence embeddings (384-dim) for similarity & search | Low | CPU/GPU |
| **YOLOv8n** | Signature bounding box detection | ≥ 512MB | GPU on-demand → CPU |
| **TrOCR Large** | Handwriting OCR on signatures | ≥ 1GB | GPU on-demand → CPU |
| **LLaMA 3.2 3B** (llamafile) | Reasoning, validation, extraction, Q&A, summarization | Separate process | HTTP API on port 8080 |
| **PPStructureV3** | Table detection and structure recognition | Low | CPU/GPU |

**Model management** is handled by `app/models/loader.py`:
- `load_all_models()` — Loads all models at startup
- `load_trocr_model()` — Lazy loads TrOCR Large
- `load_yolo_model()` — Loads YOLOv8n signature detector
- `load_llama_model()` — Creates HTTP wrapper for llamafile
- GPU utilities: `clear_gpu_cache()`, `get_gpu_memory_usage()`, `check_gpu_memory_available()`, `get_device()`, `move_model_to_device()`

---

## Module Map

```
app/
├── __init__.py                        # Package metadata (v1.0.0)
├── api/
│   ├── endpoints.py                   # FastAPI routes (health, process, search, query)
│   └── config_endpoints.py            # Runtime config management (50+ params)
├── core/
│   ├── pipeline.py                    # MAIN ORCHESTRATOR — run_full_ai_pipeline()
│   └── classifier.py                  # PDF splitting + document classification
├── services/
│   ├── ocr_validation.py              # 4-tier OCR quality routing
│   ├── signature_detection.py         # YOLOv8n signature detection
│   ├── signature_ocr.py              # TrOCR handwriting OCR
│   ├── signature_validation.py        # LLaMA signature validation + authenticity
│   └── table_extraction.py            # PPStructure table detection + LLaMA validation
├── models/
│   └── loader.py                      # Model loading & GPU memory management
├── utils/
│   ├── extraction.py                  # Structured field extraction (30+ schemas)
│   └── prompt_manager.py             # Control Panel prompt fetching + fallbacks
└── scanner/
    └── scanner_service.py             # Hardware scanner interface (WIA)
```

---

## 31 Supported Document Types

| Category | Document Types |
|----------|---------------|
| **Financial** (9) | Invoice, Receipt, Purchase Order, Credit Note, Debit Note, Payment Voucher, Bank Statement, Financial Statement, Tax Document |
| **Legal** (7) | Contract, Agreement, Non-Disclosure Agreement, Memorandum of Understanding, Certificate, License, Permit |
| **Business** (6) | Report, Business Letter, Memo, Proposal, Quotation, Tender Document |
| **Operational** (5) | Form, Delivery Note, Packing Slip, Bill of Lading, Shipping Document |
| **HR** (3) | Resume, Job Application, Employment Contract |
| **Other** (1) | Unknown / Other |

Each type has a dedicated extraction schema in `EXTRACTION_SCHEMAS` (see `app/utils/extraction.py`) defining exactly which fields to extract.

---

## Configuration & Runtime Parameters

All configuration is managed via `RUNTIME_CONFIG` in `app/api/config_endpoints.py` with 50+ parameters adjustable at runtime via API.

### Pipeline Toggles (all ON by default)

| Toggle | Controls |
|--------|----------|
| `ENABLE_PDF_SPLITTING` | Step 1 — PDF page splitting |
| `ENABLE_OCR_VALIDATION` | Step 2 — OCR quality routing |
| `ENABLE_CLASSIFICATION` | Step 3 — Document classification |
| `ENABLE_SIGNATURE_DETECTION` | Step 4 — YOLO signature detection |
| `ENABLE_SIGNATURE_VALIDATION` | Steps 5–7 — Signature OCR & validation |
| `ENABLE_STRUCTURED_EXTRACTION` | Step 8 — Field extraction |
| `ENABLE_ENTITY_EXTRACTION` | Step 9 — NER (reserved) |
| `ENABLE_TABLE_EXTRACTION` | Step 10 — Table parsing |
| `ENABLE_SUMMARY` | Step 11 — Summary generation |
| `ENABLE_EMBEDDING_GENERATION` | Embedding vectors for search |
| `ENABLE_MONGODB_STORAGE` | Persist results to MongoDB |

### Key Processing Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SIMILARITY_THRESHOLD` | 0.5 | Cosine similarity cutoff for PDF document break detection |
| `OCR_DPI` | 300 | Image resolution for OCR |
| `YOLO_CONFIDENCE` | 0.60 | Signature detection confidence threshold |
| `CLASSIFICATION_MIN_CONFIDENCE` | 0.08 | Minimum confidence to assign a document type |
| `MAX_GPU_MEMORY_MB` | 4096 | GPU memory limit |
| `MAX_PDF_SIZE_MB` | 200 | Maximum upload size |

### LLaMA Temperature Settings

| Task | Temperature | Rationale |
|------|-------------|-----------|
| OCR Validation | 0.05 | Ultra-low — must preserve original structure |
| Extraction | 0.1 | Precision-focused field extraction |
| Signature Validation | 0.2 | Low creativity for name correction |
| Table Validation | 0.2 | Low creativity for data verification |
| Classification | 0.3 | Moderate — needs reasoning flexibility |
| Summarization | 0.3 | Moderate — natural language output |

### Configuration Priority

1. **API updates** (highest) — `POST /api/v1/config`
2. **Environment variables** — `.env` file
3. **Hardcoded defaults** (lowest) — `config/settings.py`

---

## Smart Design Patterns

- **GPU on-demand loading**: Models are moved to GPU only when needed, then back to CPU — avoids constant high VRAM usage
- **Tiered OCR routing**: High-confidence text skips LLaMA entirely, saving inference time
- **LLaMA as HTTP service**: Runs as a separate llamafile process on port 8080, decoupled from the Python service
- **Async background processing**: Upload returns immediately with `process_id`; pipeline runs in background
- **Prompt management**: Fetches custom prompts from AuraControlPanel with built-in fallback prompts
- **MongoDB-native types**: All NumPy arrays/types converted before storage
- **Comprehensive error handling**: Each step has try/catch with logging; failures don't crash the pipeline
- **11 individual toggles**: Any step can be disabled without affecting others

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/status` | Service status & loaded models |
| `GET` | `/system/hardware` | CPU/GPU/memory hardware info |
| `POST` | `/api/v1/process` | Upload & process PDF |
| `GET` | `/api/v1/search` | Semantic vector search |
| `POST` | `/api/v1/query` | Q&A with LLaMA context |
| `GET` | `/api/v1/config` | Get current runtime config |
| `POST` | `/api/v1/config` | Update runtime config |
| `POST` | `/api/v1/config/reset` | Reset config to defaults |

---

## Pipeline Flaws & Optimization Opportunities

> Analysis based on deep code review of all pipeline modules.  
> Flaws are ranked by impact: **CRITICAL** (must fix), **HIGH** (significant gains), **MEDIUM** (worthwhile), **LOW** (nice to have).

---

### CRITICAL-1: PDF Is Converted to Images TWICE

**Impact: ~30-50% of total processing time wasted**

| Location | DPI | Purpose |
|----------|-----|---------|
| `classifier.py` → `split_pdf_and_find_breaks()` → `pdf_to_images()` | 300 DPI | OCR + text extraction |
| `pipeline.py` → `convert_from_path()` (line ~291) | 200 DPI | Signatures + tables |

The same PDF is rendered to images **twice** at **different DPIs**. The first set (300 DPI) is used for OCR, then its images are stored as numpy arrays in `logical_doc['pages']`. But the pipeline **ignores those stored images** and converts the PDF again at 200 DPI for signature detection and table extraction.

**What's wasted:**
- Full Poppler PDF rendering (CPU-heavy, ~2-5 seconds for a 10-page document)
- Double the peak RAM usage (both image sets in memory)
- The 300 DPI images are higher quality — the 200 DPI set is actually worse

**Fix:** Remove the second `convert_from_path()` call in `pipeline.py`. Use the images already stored in `logical_doc['pages']` from `split_pdf_and_find_breaks()`. If lower DPI is needed, downscale in-memory (instant) instead of re-rendering the entire PDF.

---

### CRITICAL-2: LlamafileWrapper Silently Caps Tokens at 512

**Impact: Breaks OCR validation, table extraction, and structured extraction**

In `app/models/loader.py`, the `LlamafileWrapper.__call__()` method enforces:

```python
max_tokens = min(max_tokens, 512)  # Cap at 512 tokens
```

But several callers request far more:
- **OCR validation** requests `2500` tokens → silently capped to `512` (too short for full-page correction)
- **Table extraction** requests `1500` tokens → capped to `512` (tables get truncated)
- **Structured extraction** requests `600` tokens → capped to `512` (some fields cut off)

The callers don't know their token limit was reduced. This means:
- OCR corrections get cut off mid-sentence
- Table validation JSON is truncated (invalid JSON → parse failure → "validation failed")
- Extraction results silently lose the last few fields

**Fix:** Remove the hard 512 cap, or raise it to at least 2500 to match the largest caller. The cap should come from the config, not be hard-coded in the wrapper.

---

### CRITICAL-3: LlamafileWrapper Silently Clamps Temperature to 0.1–0.9

**Impact: OCR validation precision is degraded**

In `LlamafileWrapper.__call__()`:

```python
temperature = max(0.1, min(temperature, 0.9))  # Clamp between 0.1-0.9
```

But OCR validation explicitly sets `temperature=0.05` for ultra-low creativity (must preserve document structure exactly). This is silently raised to `0.1`, which:
- Doubles the randomness in OCR corrections
- Increases the chance of LLaMA changing wording/formatting
- Triggers the "30% length change" rejection more often (wasting the inference)

**Fix:** Allow temperature range 0.0–1.0, or at minimum lower the floor to 0.01.

---

### HIGH-1: 7–10 Sequential LLaMA HTTP Calls Per Document

**Impact: Each LLaMA call takes 3–15 seconds → total 30–90+ seconds per document**

For each logical document, LLaMA is called sequentially for:

| Step | LLaMA Call | Typical Duration |
|------|-----------|-----------------|
| OCR Validation | Full-tier text correction | 5–15s |
| Classification | Reasoning explanation | 5–10s |
| Signature Validation | Fix handwriting errors | 3–8s |
| Signature Authenticity | Placement/date check | 3–8s |
| Structured Extraction | Field extraction | 5–10s |
| Entity Extraction | NER | 5–10s |
| Table Validation | Per-table verification | 3–8s each |
| Summary | Generate summary | 3–8s |

These are **sequential HTTP calls** — the pipeline blocks on each one before starting the next. LLaMA can only process one request at a time (single-threaded inference), but the pipeline doesn't attempt any batching or prompt combining.

**Fix options:**
1. **Combine prompts**: Merge classification reasoning + structured extraction + summary into one LLaMA call with a multi-task prompt (saves 2–3 calls)
2. **Skip unnecessary calls**: If OCR confidence is >95% (SKIP tier), don't call LLaMA for classification reasoning either
3. **Parallel where possible**: Classification reasoning and signature detection are independent — run them concurrently
4. **Batch tables**: Send all tables in one validation call instead of one per table

---

### HIGH-2: GPU Thrashing in Signature Detection Loop

**Impact: Repeated GPU↔CPU transfers add 200–500ms per page**

In the signature detection loop (`pipeline.py` lines ~490–540), for each page:
1. `torch.cuda.empty_cache()` — every 2 pages
2. Move YOLO to GPU
3. Run inference
4. Move YOLO back to CPU
5. `torch.cuda.empty_cache()`
6. Save image to temp file on disk
7. Move TrOCR to GPU
8. Run OCR
9. Move TrOCR back to CPU
10. Delete temp file

For a 5-page logical document, this means:
- **5× GPU transfers for YOLO** (500ms)
- **5× temp file writes + deletes** (unnecessary disk I/O)
- **5× GPU cache clears** (synchronization overhead)
- **Multiple TrOCR GPU transfers** (1 per detected signature)

**Fix:**
1. **Batch YOLO inference**: Run YOLO on ALL pages at once (YOLO supports batch inference). Move to GPU once, process all pages, move back once.
2. **Eliminate temp files**: Pass PIL images directly to TrOCR instead of saving to disk and reading back.
3. **Keep model on GPU during loop**: Don't move YOLO back to CPU between pages of the same document.

---

### HIGH-3: Two Sentence Transformer Models Where One Suffices

**Impact: ~400MB extra RAM, ~5s extra startup time**

Two separate models are loaded:

| Model | Dim | Purpose | Used In |
|-------|-----|---------|---------|
| `all-MiniLM-L12-v2` | 384 | Classification | `classify_text()` |
| `all-MiniLM-L6-v2` | 384 | Search + splitting | `split_pdf_and_find_breaks()`, search API |

Both produce 384-dimensional embeddings. The L12 model is slightly more accurate but both are in the same family. Using two models means:
- ~400MB extra RAM permanently occupied
- Double the startup loading time for sentence transformers
- Two different embedding spaces — classification embeddings and search embeddings are incompatible

**Fix:** Use a single model (all-MiniLM-L12-v2 or all-mpnet-base-v2) for both tasks. This halves memory usage and keeps embeddings in one consistent space.

---

### HIGH-4: No Intermediate Checkpointing

**Impact: If pipeline fails at step 8, all work from steps 1–7 is lost**

The pipeline does a single MongoDB write at the very end (`pipeline.py` ~line 790). If the process crashes or times out during step 8–11, **all previous work is discarded**. For a 50-page document that takes 5+ minutes to process, this means starting from scratch.

**Fix:** Write intermediate results to MongoDB after each major step (or at least after steps 1, 3, 5, 8). Use `$set` with dot notation to update individual fields without overwriting previous results:
```python
documents_collection.update_one(
    {'_id': doc_id},
    {'$set': {f'processed_data.{idx}.classification': classification}}
)
```

---

### MEDIUM-1: Classification Compares Text Embeddings to Bare Label Names

**Impact: Weak classification accuracy — "Invoice" as a label has almost no semantic content**

In `classify_text()`, document text is embedded and compared to embeddings of:
```python
["Invoice", "Receipt", "Purchase Order", "Contract", ...]
```

Single-word labels produce poor embeddings. The model is comparing a 2000-word document embedding against the embedding of the word "Invoice" — which is barely more informative than random.

**Fix:** Use descriptive labels:
```python
{
    "Invoice": "A commercial billing document listing items sold, prices, tax, and payment terms",
    "Receipt": "A proof of payment showing items purchased, amounts paid, and transaction date",
    "Contract": "A legal agreement between parties with terms, obligations, and signatures",
    ...
}
```
Embedding these descriptions will produce much stronger classification signals.

---

### MEDIUM-2: REVIEW Tier (<50% OCR confidence) Does the LEAST Work

**Impact: The worst-quality documents get the weakest correction**

The OCR routing logic:
- **FULL tier** (50–74%): Full LLaMA correction
- **REVIEW tier** (<50%): Only regex fixes + flag for review

Documents below 50% confidence are the ones that **need LLaMA the most**, but they're the only tier that doesn't get full LLaMA correction. The comment says "best effort" but it's actually weaker than the FULL tier.

**Fix:** Run LLaMA correction for REVIEW tier too, but with a different strategy:
- Use a more explicit prompt: "This text has severe OCR errors..."
- Lower the length-change rejection threshold (these texts will change more)
- Still flag for manual review, but provide the LLaMA-corrected version as a suggestion

---

### MEDIUM-3: Text Truncation at 2000 Characters in MongoDB

**Impact: Search and Q&A on long documents use incomplete text**

In `pipeline.py` ~line 730:
```python
'text': doc_text[:2000] + "..." if len(doc_text) > 2000 else doc_text,
'full_text': doc_text,  # Store full text for Q&A
```

Both `text` and `full_text` are stored. But if downstream queries or the frontend use the `text` field, they only see the first 2000 characters. Meanwhile, `full_text` stores everything — meaning the same text is stored twice (once truncated, once full).

**Fix:** Store only `full_text`. If a preview is needed, compute it on-read rather than doubling storage.

---

### MEDIUM-4: Embedding Re-generation After OCR Correction Doesn't Propagate

**Impact: Classification may use stale text**

After OCR validation corrects text (`pipeline.py` ~line 425), the embedding is re-generated:
```python
doc_embedding = search_model.encode(doc_text, convert_to_tensor=False).tolist()
```

But classification (`classify_text()`, line ~435) runs AFTER this and uses the corrected `doc_text` — which is correct. However, the classification uses `sentence_transformer_classify` (L12) while the embedding was generated with `sentence_transformer_search` (L6). These are **different embedding spaces**. The search embedding represents the corrected text, but the classification embedding is computed fresh from the corrected text in a different model. This is fine functionally but means the stored search embedding and classification result are in different vector spaces — this could cause confusing search results where classified-as-Invoice documents don't cluster together in search.

---

### MEDIUM-5: `convert_numpy_for_mongodb()` Runs Multiple Times

**Impact: Redundant CPU work traversing full data tree 3–4 times**

NumPy type conversion is called in:
1. `table_extraction.py` — per table, per result
2. `pipeline.py` — final `convert_numpy_for_mongodb(processed_data)` on the entire tree
3. Inside `run_table_engine()` — on raw results

The final call in pipeline.py already traverses the **entire** data structure. The earlier calls are redundant.

**Fix:** Remove intermediate conversions and do it only once before MongoDB write.

---

### LOW-1: Signature Detection Falls Back to Regex Patterns on Full Text

**Impact: False positives from text like "Name John Smith Terms"**

When YOLO finds no signatures, the pipeline falls back to regex patterns like:
```python
r'(?:Invoice\s+)?Total\s+([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)\s+Terms'
```

This matches patterns like "Total John Smith Terms" — which is clearly a table header row, not a signature. The regex fallback has high false-positive risk on invoices with proper-noun-like items.

**Fix:** Either remove the regex fallback entirely (trust YOLO — that's why it's there), or add much stricter validation (require "Signature:", "Signed by:", or bottom-of-page location).

---

### LOW-2: No Page-Level Parallelism in OCR

**Impact: OCR runs sequentially on each page in `split_pdf_and_find_breaks()`**

PaddleOCR is called in a simple `for` loop over all pages:
```python
for idx, image in enumerate(images):
    ocr_result = extract_text_from_image(image, paddleocr, return_confidence=True)
```

PaddleOCR is CPU-bound — pages could be OCR'd in parallel using a thread pool.

**Fix:** Use `concurrent.futures.ThreadPoolExecutor` to OCR multiple pages simultaneously.

---

### Summary Table

| # | Flaw | Severity | Speed Impact | Quality Impact | Fix Effort |
|---|------|----------|-------------|----------------|------------|
| C-1 | Duplicate PDF→image conversion | CRITICAL | -30–50% time | None | Small |
| C-2 | Token cap silently breaks callers | CRITICAL | None | Broken outputs | Tiny |
| C-3 | Temperature floor breaks OCR precision | CRITICAL | None | Degraded OCR | Tiny |
| H-1 | 7–10 sequential LLaMA calls | HIGH | -30–60s/doc | None | Medium |
| H-2 | GPU thrashing in signature loop | HIGH | -200–500ms/page | None | Medium |
| H-3 | Two Sentence Transformers | HIGH | -5s startup, -400MB | None | Small |
| H-4 | No intermediate checkpointing | HIGH | None (crash recovery) | Lost work | Medium |
| M-1 | Bare-word classification labels | MEDIUM | None | Weak accuracy | Small |
| M-2 | REVIEW tier gets weakest correction | MEDIUM | None | Worst docs uncorrected | Small |
| M-3 | Duplicate text storage (2000 char + full) | MEDIUM | None | Wasted storage | Tiny |
| M-4 | Mixed embedding spaces | MEDIUM | None | Inconsistent search | Small |
| M-5 | Redundant NumPy conversions | MEDIUM | Minor | None | Tiny |
| L-1 | Regex signature fallback false positives | LOW | None | False detections | Tiny |
| L-2 | Sequential page OCR | LOW | -2–5s for large PDFs | None | Small |

### Estimated Impact of Fixing Critical + High Issues

| Metric | Current (est.) | After Fixes (est.) |
|--------|---------------|-------------------|
| Processing time (10-page PDF) | ~90–180 seconds | ~40–80 seconds |
| Peak RAM usage | ~4–5 GB | ~3–3.5 GB |
| GPU transfer overhead | ~2–3 seconds | ~0.3 seconds |
| LLaMA calls per document | 7–10 | 3–5 |
| Crash recovery | Start from scratch | Resume from checkpoint |
| OCR correction quality | Silently degraded | Full precision |

---

## Quality Impact Analysis — OCR, ICR, NLP & Data Completeness

> Do the fixes actually improve result quality, or just speed?  
> Analysis by concern area: OCR (printed), ICR (handwritten), NLP (classification/extraction/summary), and data completeness.

---

### 1. OCR Quality (Printed Text — PDF & Scans)

| Fix | Impact on OCR Quality |
|-----|----------------------|
| **C-2** (token cap 512) | **Major.** OCR validation requests 2500 tokens but is silently capped to 512. For full-page documents, LLaMA's correction gets cut off mid-sentence — the bottom half of the page is returned uncorrected. Fixing this means full-page OCR correction works as intended. |
| **C-3** (temperature floor 0.1) | **Direct.** OCR correction runs at 2× the intended randomness (0.1 instead of 0.05). LLaMA occasionally changes wording or reformats text, which triggers the 30% length-change rejection — meaning the correction is thrown away and the original bad OCR text is kept. |
| **M-2** (REVIEW tier fix) | **Major for poor-quality scans.** Documents with <50% OCR confidence (faded scans, low-resolution PDFs, dirty copies) currently get only regex fixes and no LLaMA correction. These are the documents that need it most. |
| **C-1** (single PDF conversion) | **Slight.** Using 300 DPI images everywhere (instead of 200 DPI for signatures/tables) means higher resolution input for table extraction → cleaner cell text. |

---

### 2. ICR Quality (Handwritten Text — PDF & Scans)

**Current state: TrOCR (the handwriting model) is ONLY triggered on YOLO-detected signature regions.**

The pipeline flow is:
```
YOLO detects signature box → Crop that box → TrOCR reads handwriting in that box
```

This means:

| Handwritten Content | Currently Handled? |
|--------------------|--------------------|
| Signatures | Yes — YOLO + TrOCR |
| Handwritten form fields (name, address, dates) | **NO — not detected, not read** |
| Handwritten notes/annotations on documents | **NO — not detected, not read** |
| Mixed printed + handwritten pages | Only printed text via PaddleOCR; handwriting is missed or garbled |

**PaddleOCR is not designed for handwriting** — it's a printed-text OCR engine. When it encounters handwriting, it either:
- Skips it entirely (low confidence → empty result)
- Produces garbage text (misreads cursive letters)

**The proposed fixes won't change this.** To properly support ICR across entire documents, a **new pipeline step** is needed:

1. **Handwriting detection step** — detect which regions of the page are handwritten (new YOLO class or layout analysis)
2. **Route handwritten regions to TrOCR** — not just signatures but all handwritten text
3. **Merge printed + handwritten OCR results** — combine PaddleOCR output (printed) with TrOCR output (handwritten) by position on page

This is a **design gap**, not a bug fix — it requires new feature development.

---

### 3. NLP Quality (Classification, Extraction, Summary)

| Fix | Impact on NLP Quality |
|-----|----------------------|
| **C-2** (token cap 512) | **Critical for extraction.** Structured extraction requests 600 tokens but gets 512. For documents with many fields (invoices have 18 fields), the JSON output gets truncated → `json.loads()` fails → extraction returns empty. **Extracted data is being silently lost right now.** |
| **M-1** (descriptive classification labels) | **Direct improvement.** Comparing a 2000-word document to the embedding of the single word "Invoice" is semantically weak. Using descriptive labels like "A commercial billing document listing items sold, prices, tax, and payment terms" gives much stronger classification signal → correct type → correct extraction schema → correct fields extracted. |
| **C-3** (temperature floor) | **Indirect improvement.** Extraction uses temp 0.1 (as intended), but OCR correction (which runs BEFORE extraction) produces noisier text than intended → extraction receives slightly degraded input. |
| **H-4** (checkpointing) | **Data protection.** If the pipeline crashes during summary (step 11), all OCR, classification, signatures, and extraction from steps 1–8 are lost. Checkpointing preserves completed work. |

---

### 4. Data Completeness — "All Data From the Document"

This is where **C-2 (token cap)** is the most damaging flaw:

| What's Silently Lost Right Now | Root Cause | Fix |
|-------------------------------|-----------|-----|
| Bottom half of OCR corrections on long pages | Token cap truncates LLaMA output at 512 tokens | C-2 |
| Last 2–3 fields of invoice extraction | JSON truncated before closing `}` → parse failure → empty result | C-2 |
| Table validation corrections | Validation JSON cut off → parse fails → original (wrong) data kept | C-2 |
| All handwritten form text (non-signature) | TrOCR only triggered by YOLO signature boxes | **New feature needed** |
| Data from pages 6+ of large documents | Signature detection loop caps at 5 pages per logical document | Code fix in pipeline.py |

---

### Quality Impact Summary

| Concern | Do Fixes Help? | Remaining Gap? |
|---------|---------------|----------------|
| **OCR (printed text)** | Yes — significantly (C-2, C-3, M-2) | None |
| **ICR (handwritten text)** | Partially — signatures improve | **Yes — handwritten body/form text is not read at all** |
| **NLP (classification/extraction/summary)** | Yes — significantly (C-2, M-1) | None |
| **Data completeness** | Yes — major (C-2 stops silent data loss) | **Handwritten fields still missing** |

### Key Takeaway

The three **CRITICAL** fixes (C-1, C-2, C-3) are quality improvements, not just speed improvements. **C-2 alone** would immediately stop the silent data loss happening right now in extraction, OCR correction, and table validation. The biggest remaining quality gap is **full-document ICR** — handwritten text outside signature boxes is not being processed at all.
