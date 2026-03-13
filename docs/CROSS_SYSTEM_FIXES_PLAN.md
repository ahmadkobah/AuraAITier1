# Cross-System Fixes — Detailed Implementation Plan

**Version:** 2.0  
**Date:** 2026-03-14  
**Scope:** 3 remaining fixes that span multiple codebases  
**Status:** IN PROGRESS — implementation starting with Fix 0.2 → 0.5 → 6.3

### Complete Call Site Audit (v2.0 additions)

In addition to the original inventory, the following call sites were found:

**AuraControlPanel Backend — Additional Files:**
- `routes/admin/tierStatusRoutes.js` — 1 call: `GET ${serviceUrl}/api/v1/status` (per tier ×3)
- `routes/admin/tierConfigRoutes.js` — 1 call: `POST ${aiServiceUrl}/api/v1/config` (sync config)
- `routes/admin/promptRoutes.js` — 3 calls: test prompt, fetch prompts, bulk-update prompts
- `routes/admin/searchRoutes.js` — 2 calls: fetch search config, bulk-update search config
- `routes/admin/securityRoutes.js` — 1 call: `GET ${AI_SERVICE_URL}/health` (connection test)
- `routes/discoveryRoutes.js` — No HTTP calls (reads endpoints.py file only); hardcodes `base_url: 'http://localhost:9000'` in metadata

**Total revised count: 13 files, ~30 call sites across 3 projects**

---

## Table of Contents

1. [Fix 0.2 — API Key Authentication](#fix-02--api-key-authentication)
2. [Fix 0.5 — CORS Allowlist Lockdown](#fix-05--cors-allowlist-lockdown)
3. [Fix 6.3 — Sentence Transformer Upgrade](#fix-63--sentence-transformer-upgrade)
4. [Implementation Order](#implementation-order)
5. [Rollback Plan](#rollback-plan)

---

## Fix 0.2 — API Key Authentication

### Problem

The AI Service (port 9000) accepts unauthenticated HTTP requests from any source. All 19+ call sites across Aura and AuraControlPanel send requests without credentials.

### Architecture

```
┌────────────────────┐     ┌──────────────────────┐     ┌────────────────────────┐
│  Aura Frontend     │     │  AuraControlPanel FE  │     │  Any HTTP client       │
│  (port 5173)       │     │  (port 3000)          │     │  (curl, Postman, etc)  │
└───────┬────────────┘     └───────┬──────────────┘     └───────┬────────────────┘
        │ ❌ No API Key            │ ❌ No API Key              │ ❌ No API Key
        ▼                          ▼                             ▼
┌────────────────────┐     ┌──────────────────────┐             │
│  Aura Backend      │     │  AuraControlPanel BE  │             │
│  (port 8000)       │     │  (port 4000)          │             │
└───────┬────────────┘     └───────┬──────────────┘             │
        │ ❌ No API Key            │ ❌ No API Key              │
        ▼                          ▼                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  AI Service (port 9000) — NO AUTH MIDDLEWARE                     │
│  All endpoints open: /process, /config, /scan, /qa, /search...  │
└──────────────────────────────────────────────────────────────────┘
```

### Target Architecture

```
┌────────────────────┐     ┌──────────────────────┐     ┌────────────────────────┐
│  Aura Frontend     │     │  AuraControlPanel FE  │     │  Unauthorized client   │
│  (port 5173)       │     │  (port 3000)          │     │                        │
└───────┬────────────┘     └───────┬──────────────┘     └───────┬────────────────┘
        │ via Aura BE proxy        │ via CP BE proxy             │ ❌ 401 Rejected
        ▼                          ▼                             ▼
┌────────────────────┐     ┌──────────────────────┐     ┌────────────────────────┐
│  Aura Backend      │     │  AuraControlPanel BE  │     │  AI Service middleware │
│  X-API-Key: ***    │     │  X-API-Key: ***       │     │  → 401 Unauthorized   │
└───────┬────────────┘     └───────┬──────────────┘     └────────────────────────┘
        │ ✅ Authenticated         │ ✅ Authenticated
        ▼                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  AI Service (port 9000) — API Key Middleware                     │
│  Validates X-API-Key header on every request                    │
│  Exempt: /health (monitoring probes need access)                 │
└──────────────────────────────────────────────────────────────────┘
```

### Complete Call Site Inventory

#### Aura Backend — `backend/src/app.js` (6 calls)

| # | Line | Method | Endpoint | Current Headers |
|---|------|--------|----------|-----------------|
| 1 | ~70 | GET | `/health` | None |
| 2 | ~75 | GET | `/health` (LLaMA 8080) | None (different service) |
| 3 | ~81 | POST | `/api/v1/qa` | None |
| 4 | ~89 | POST | `/api/v1/summarize` | None |
| 5 | ~200 | POST | `/api/v1/conversational-search` | None |
| 6 | ~225 | POST | `/api/v1/conversational-search` | None (fallback) |

#### Aura Frontend — `frontend/src/pages/Documents.jsx` (2 calls)

| # | Line | Method | Endpoint | Current Headers |
|---|------|--------|----------|-----------------|
| 7 | ~199 | GET | `/api/v1/scanners` | None |
| 8 | ~295 | POST | `/api/v1/scan` | None |

> **DESIGN DECISION:** Frontend calls (7–8) should be proxied through Aura Backend instead of calling AI Service directly. This keeps the API key server-side only.

#### AuraControlPanel Backend — `backend/src/server.js` (3 calls)

| # | Line | Method | Endpoint | Current Headers |
|---|------|--------|----------|-----------------|
| 9 | ~124 | GET | `/health` | None |
| 10 | ~163 | GET | `/health` | None (in /status/services) |
| 11 | ~170 | GET | `/system/hardware` | None |

#### AuraControlPanel Backend — `backend/src/controllers/aiConfigController.js` (5 calls, fetch)

| # | Line | Method | Endpoint | Current Headers |
|---|------|--------|----------|-----------------|
| 12 | ~16 | GET | `/api/v1/config` | None |
| 13 | ~55 | POST | `/api/v1/config` | Content-Type only |
| 14 | ~138 | POST | `/api/v1/config` | Content-Type only |
| 15 | ~176 | POST | `/api/v1/config/reset` | None |
| 16 | ~218 | POST | `/api/v1/config` | Content-Type only |

#### AuraControlPanel Backend — `backend/src/routes/admin/classificationRoutes.js` (~2 calls)

| # | Line | Method | Endpoint | Current Headers |
|---|------|--------|----------|-----------------|
| 17 | — | GET | `/api/v1/classifications` | None |
| 18 | — | POST | `/api/v1/classifications/bulk-update` | None |

#### AuraControlPanel Backend — `backend/src/routes/admin/tierRoutes.js` (1 call)

| # | Line | Method | Endpoint | Current Headers |
|---|------|--------|----------|-----------------|
| 19 | ~53 | GET | `/health` | None |

#### AuraControlPanel Frontend — `frontend/src/pages/Classifications.jsx` (3 calls, DIRECT to AI Service)

| # | Line | Method | Endpoint | Current Headers |
|---|------|--------|----------|-----------------|
| 20 | ~101 | GET | `/health` (ports 9000/9001/9002) | None |
| 21 | ~110 | POST | `/classify` (ports 9000/9001/9002) | None |

> **DESIGN DECISION:** Frontend calls (20–21) should be proxied through AuraControlPanel Backend. Never expose the API key in browser JavaScript.

### Implementation Steps

#### Step 1 — AI Service: Add API Key Middleware

**File:** `app/api/endpoints.py`

```python
# --- Add after imports, before app creation ---

import secrets
import hmac

# API Key from environment variable
_API_KEY = os.getenv('AI_SERVICE_API_KEY', '')

async def verify_api_key(request: Request):
    """Middleware to verify X-API-Key header on all requests."""
    # Exempt health endpoint for monitoring probes
    if request.url.path in ('/health', '/docs', '/openapi.json'):
        return
    # If no API key configured, skip validation (dev mode)
    if not _API_KEY:
        return
    provided_key = request.headers.get('X-API-Key', '')
    if not hmac.compare_digest(provided_key, _API_KEY):
        raise HTTPException(status_code=401, detail='Invalid or missing API key')
```

Add as a dependency to the FastAPI app or use middleware:

```python
from fastapi import Depends

# Option A: Global dependency
app = FastAPI(dependencies=[Depends(verify_api_key)])

# OR Option B: Middleware approach
@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if request.url.path not in ('/health', '/docs', '/openapi.json'):
        if _API_KEY:
            provided_key = request.headers.get('X-API-Key', '')
            if not hmac.compare_digest(provided_key, _API_KEY):
                return JSONResponse(status_code=401, content={'detail': 'Invalid or missing API key'})
    return await call_next(request)
```

**Environment variable:**
```
AI_SERVICE_API_KEY=<generate-64-char-random-string>
```

Generate with: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

#### Step 2 — Aura Backend: Add X-API-Key to All Calls

**File:** `Aura/backend/src/app.js`

```javascript
// Add at top of file
const AI_SERVICE_API_KEY = process.env.AI_SERVICE_API_KEY || '';

// Create a reusable axios instance
const aiServiceClient = axios.create({
  baseURL: config.ai.serviceUrl,
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': AI_SERVICE_API_KEY,
  },
});
```

Then replace all 6 direct `axios.get/post('http://localhost:9000/...')` calls with `aiServiceClient.get/post('/...')`.

**Environment variable:** Add to `Aura/backend/.env`:
```
AI_SERVICE_API_KEY=<same-64-char-string-as-ai-service>
```

#### Step 3 — Aura Frontend: Proxy Scanner Calls Through Backend

**Problem:** `Documents.jsx` calls AI Service directly from the browser (lines ~199, ~295). The API key cannot be in frontend code.

**Solution:** Create 2 proxy routes in Aura Backend:

**File:** `Aura/backend/src/routes/scannerRoutes.js` (NEW)

```javascript
const router = require('express').Router();
const aiServiceClient = require('../lib/aiServiceClient'); // shared instance

// GET /api/scanners → proxy to AI Service
router.get('/scanners', async (req, res) => {
  try {
    const { data } = await aiServiceClient.get('/api/v1/scanners');
    res.json(data);
  } catch (err) {
    res.status(err.response?.status || 502).json({ error: 'AI Service unavailable' });
  }
});

// POST /api/scan → proxy to AI Service
router.post('/scan', async (req, res) => {
  try {
    const { data } = await aiServiceClient.post('/api/v1/scan', req.body);
    res.json(data);
  } catch (err) {
    res.status(err.response?.status || 502).json({ error: 'Scan failed' });
  }
});

module.exports = router;
```

**File:** `Aura/frontend/src/pages/Documents.jsx` — Change URLs:

```javascript
// BEFORE: Direct to AI Service
const aiServiceApi = axios.create({ baseURL: 'http://localhost:9000' });
aiServiceApi.get('/api/v1/scanners');
aiServiceApi.post('/api/v1/scan', ...);

// AFTER: Through Aura Backend
api.get('/api/scanners');      // Aura BE on port 8000
api.post('/api/scan', ...);    // Aura BE on port 8000
```

#### Step 4 — AuraControlPanel Backend: Add X-API-Key to All Calls

**File:** `AuraControlPanel/backend/src/server.js`

```javascript
// Add at top
const AI_SERVICE_API_KEY = process.env.AI_SERVICE_API_KEY || '';

// For axios calls in server.js — add headers:
axios.get(`${AI_SERVICE_URL}/health`, {
  headers: { 'X-API-Key': AI_SERVICE_API_KEY }
});

axios.get(`${AI_SERVICE_URL}/system/hardware`, {
  headers: { 'X-API-Key': AI_SERVICE_API_KEY }
});
```

**File:** `AuraControlPanel/backend/src/controllers/aiConfigController.js`

```javascript
// For fetch calls — add header to all 5 calls:
const response = await fetch(`${AI_SERVICE_URL}/api/v1/config`, {
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': process.env.AI_SERVICE_API_KEY || '',
  },
});
```

**Files:** `routes/admin/classificationRoutes.js`, `routes/admin/tierRoutes.js` — same pattern.

**Environment variable:** Add to `AuraControlPanel/backend/.env`:
```
AI_SERVICE_API_KEY=<same-64-char-string>
```

#### Step 5 — AuraControlPanel Frontend: Proxy Direct Calls Through Backend

**Problem:** `Classifications.jsx` calls AI Service directly from browser (lines ~101, ~110) hitting ports 9000/9001/9002.

**Solution:** Create proxy routes in AuraControlPanel Backend:

**File:** `AuraControlPanel/backend/src/routes/admin/aiProxyRoutes.js` (NEW)

```javascript
// GET /api/admin/ai-health/:port → proxy health check
// POST /api/admin/ai-classify/:port → proxy classification test
```

**File:** `AuraControlPanel/frontend/src/pages/Classifications.jsx` — change direct URLs to backend proxy URLs.

#### Step 6 — Test & Verify

1. Generate API key: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
2. Set `AI_SERVICE_API_KEY` in all 3 `.env` files (same value)
3. Restart all 3 services
4. Verify: `curl http://localhost:9000/api/v1/status` → should return 401
5. Verify: `curl -H "X-API-Key: <key>" http://localhost:9000/api/v1/status` → should return 200
6. Verify: `curl http://localhost:9000/health` → should return 200 (exempt)
7. Test Aura FE scan workflow, Q&A, search
8. Test Control Panel config sync, classifications

### File Change Summary

| File | Project | Changes |
|------|---------|---------|
| `app/api/endpoints.py` | AI Service | Add API key middleware |
| `.env` | AI Service | Add `AI_SERVICE_API_KEY` |
| `backend/src/app.js` | Aura | Add `aiServiceClient` with API key header, update 6 calls |
| `backend/src/routes/scannerRoutes.js` | Aura | NEW — proxy 2 scanner endpoints |
| `frontend/src/pages/Documents.jsx` | Aura | Change 2 URLs from AI Service to Aura Backend |
| `backend/.env` | Aura | Add `AI_SERVICE_API_KEY` |
| `backend/src/server.js` | AuraControlPanel | Add API key headers to 3 calls |
| `backend/src/controllers/aiConfigController.js` | AuraControlPanel | Add API key headers to 5 calls |
| `backend/src/routes/admin/classificationRoutes.js` | AuraControlPanel | Add API key headers to 2 calls |
| `backend/src/routes/admin/tierRoutes.js` | AuraControlPanel | Add API key header to 1 call |
| `backend/src/routes/admin/aiProxyRoutes.js` | AuraControlPanel | NEW — proxy 2 frontend direct calls |
| `frontend/src/pages/Classifications.jsx` | AuraControlPanel | Change direct URLs to backend proxy |
| `backend/.env` | AuraControlPanel | Add `AI_SERVICE_API_KEY` |

**Total: 13 files across 3 projects (2 new, 11 modified)**

---

## Fix 0.5 — CORS Allowlist Lockdown

### Problem

The AI Service CORS configuration includes `"*"` (allow all origins), which makes the explicit origin list redundant:

```python
# Current — endpoints.py line 322-333
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",           # ← This makes everything below pointless
        "http://localhost:3000",
        "http://localhost:4000",
        "http://localhost:5173",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

AuraControlPanel Backend also allows all origins:
```javascript
// Current — server.js line 18
app.use(cors({ origin: (o, cb) => cb(null, true), credentials: true }));
```

### Current Port Map

| Service | Port | Needs CORS to AI Service? |
|---------|------|--------------------------|
| Aura Frontend | 5173 | YES (if direct calls remain) / NO (after Fix 0.2 proxying) |
| Aura Backend | 8000 | NO (server-to-server, CORS doesn't apply) |
| AuraControlPanel Frontend | 3000 | YES (if direct calls remain) / NO (after Fix 0.2 proxying) |
| AuraControlPanel Backend | 4000 | NO (server-to-server, CORS doesn't apply) |
| AI Service | 9000 | Self — not applicable |

### Implementation Steps

#### Step 1 — AI Service: Remove `"*"` from CORS Origins

**File:** `app/api/endpoints.py` (line ~322)

```python
# BEFORE
allow_origins=[
    "*",
    "http://localhost:3000",
    "http://localhost:4000",
    "http://localhost:5173",
    "http://localhost:8000",
],

# AFTER (environment-driven)
_cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(',')

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)
```

**Environment variable:**
```
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

> **Note:** After Fix 0.2 is complete and all frontend calls go through backends, the CORS list can be reduced further or even left empty (only backend-to-backend calls, which don't trigger CORS).

#### Step 2 — AuraControlPanel Backend: Add Explicit Origin List

**File:** `AuraControlPanel/backend/src/server.js` (line ~18)

```javascript
// BEFORE
app.use(cors({ origin: (o, cb) => cb(null, true), credentials: true }));

// AFTER
const ALLOWED_ORIGINS = (process.env.CORS_ORIGINS || 'http://localhost:3000').split(',');
app.use(cors({
  origin: function(origin, cb) {
    if (!origin) return cb(null, true); // Allow server-to-server
    if (ALLOWED_ORIGINS.includes(origin)) return cb(null, true);
    return cb(new Error('Not allowed by CORS'));
  },
  credentials: true,
}));
```

#### Step 3 — Aura Backend: Already Correct

Aura Backend (`app.js`) already has a proper origin check via `config.cors.origins` from `env.js`:
```javascript
origins: (process.env.CORS_ORIGINS || 'http://localhost:5173,http://127.0.0.1:5173').split(',')
```
**No changes needed here.**

#### Step 4 — Verify

1. Remove `"*"` from AI Service CORS
2. Restart AI Service
3. Open Aura Frontend → verify scanner/upload workflows still work
4. Open Control Panel Frontend → verify config sync still works
5. Open browser DevTools Network tab → check no CORS errors
6. Test from unknown origin (e.g., `curl -H "Origin: http://evil.com"`) → should get no `Access-Control-Allow-Origin` header back

### Dependency on Fix 0.2

| Scenario | CORS List Needed |
|----------|-----------------|
| **Before Fix 0.2** (frontends call AI Service directly) | `http://localhost:5173,http://localhost:3000` |
| **After Fix 0.2** (all calls proxied through backends) | Can be empty — no browser ever talks to AI Service directly |

**Recommendation:** Implement Fix 0.2 first, then Fix 0.5 becomes trivial (empty CORS or minimal list).

### File Change Summary

| File | Project | Change |
|------|---------|--------|
| `app/api/endpoints.py` | AI Service | Remove `"*"`, use env-driven origin list |
| `.env` | AI Service | Add `CORS_ORIGINS` |
| `backend/src/server.js` | AuraControlPanel | Replace allow-all with explicit origin check |

**Total: 3 files across 2 projects**

---

## Fix 6.3 — Sentence Transformer Upgrade

### Problem

The current models (`all-MiniLM-L6-v2` and `all-MiniLM-L12-v2`, both 384-dim) are general-purpose English models. For a German/European document processing system, a multilingual or domain-specific model would produce better embeddings for:
- Document classification (German labels, invoices, receipts)
- Semantic search (German queries, mixed-language documents)
- Page-break detection (similarity between adjacent pages)

### Current Embedding Lifecycle

```
MODEL LOADING                    EMBEDDING CREATION              STORAGE
─────────────                    ──────────────────              ───────
loader.py                        classifier.py                   pipeline.py
  ├─ L12-v2 (classify)           ├─ Page text → 384d vector     ├─ MongoDB: documents.processed_data[].embedding
  └─ L6-v2  (search)             ├─ Label text → 384d vector    └─ FAISS: vector_index.py (in-memory)
                                  pipeline.py
                                  ├─ Doc text → 384d vector
                                  endpoints.py
                                  └─ Query text → 384d vector

SEARCH
──────
endpoints.py → /api/v1/search
  ├─ Encode query with L6-v2
  ├─ Try MongoDB Atlas Vector Search
  └─ Fallback: FAISS (vector_index.py)
       ├─ Read all embeddings from MongoDB
       ├─ Build IndexFlatIP(384)
       └─ k-NN search
```

### Encoding Locations (4 files, 6 call sites)

| # | File | Line | Purpose | Model Used |
|---|------|------|---------|------------|
| 1 | `app/core/classifier.py` | ~150 | Page text embeddings for break detection | L12-v2 (classify) |
| 2 | `app/core/classifier.py` | ~200 | Label description embeddings for classification | L12-v2 (classify) |
| 3 | `app/core/classifier.py` | ~201 | Zero vector fallback (384-dim hardcoded) | N/A |
| 4 | `app/core/pipeline.py` | ~415 | Document embedding for search (re-embed after OCR correction) | L6-v2 (search) |
| 5 | `app/api/endpoints.py` | ~890 | Query embedding for search endpoint | L6-v2 (search) |
| 6 | `app/utils/vector_index.py` | ~45 | FAISS index dimension (reads stored embeddings) | Dimension must match |

### Candidate Replacement Models

| Model | Dimensions | Languages | Size | Notes |
|-------|-----------|-----------|------|-------|
| **`paraphrase-multilingual-MiniLM-L12-v2`** | 384 | 50+ languages incl. German | 471 MB | **Drop-in replacement** — same 384 dimensions |
| `multilingual-e5-base` | 768 | 100+ languages | 1.1 GB | Better quality, but dimension change → migration |
| `distiluse-base-multilingual-cased-v2` | 512 | 15 languages incl. German | 539 MB | Dimension change → migration |

**Recommended: `paraphrase-multilingual-MiniLM-L12-v2`** — same 384 dimensions means no code changes to FAISS index or MongoDB schema.

### Implementation Steps

#### Step 1 — Download New Model

```powershell
cd c:\Users\Ahmad\OneDrive\Documents\GitHub\adaptive-Dokumentenverarbeitung
python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', cache_folder='models/sentence-transformers')
print(f'Loaded: {model.get_sentence_embedding_dimension()} dimensions')
"
```

This downloads to `models/sentence-transformers/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/`.

#### Step 2 — Update Model Loading

**File:** `app/models/loader.py`

Change model names from:
```python
# Current
'all-MiniLM-L12-v2'   # classification
'all-MiniLM-L6-v2'    # search
```

To:
```python
# New — single multilingual model for both tasks
EMBEDDING_MODEL = os.getenv('SENTENCE_TRANSFORMER_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')
```

Since both the old and new models output 384 dimensions, the same model can serve both classification and search.

#### Step 3 — Update Hardcoded Dimension References

**File:** `app/core/classifier.py` (line ~201):
```python
# Currently hardcoded — verify it stays 384 with new model
page_embeddings.append(np.zeros(384))  # fallback zero vector
```
No change needed if using 384-dim model. If switching to a different dimension, update this.

**File:** `app/utils/vector_index.py`:
```python
# FAISS index reads dimension from first vector — no hardcoded dim
# No change needed
```

#### Step 4 — Write Re-Embedding Migration Script

**File:** `scripts/migrate_embeddings.py` (NEW)

```python
"""
Re-embed all existing documents after Sentence Transformer model change.

Usage:
    python scripts/migrate_embeddings.py [--dry-run] [--batch-size 50]

This script:
1. Connects to MongoDB
2. Finds all documents with status=COMPLETE
3. Re-encodes each document's text with the new model
4. Updates the embedding field in-place
5. Invalidates the FAISS index
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import argparse
import logging
from datetime import datetime
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

def migrate(dry_run=False, batch_size=50):
    # Load new model
    model_name = os.getenv('SENTENCE_TRANSFORMER_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')
    cache_dir = os.path.join(os.path.dirname(__file__), '..', 'models', 'sentence-transformers')
    model = SentenceTransformer(model_name, cache_folder=cache_dir)
    dim = model.get_sentence_embedding_dimension()
    logger.info(f"Loaded model: {model_name} ({dim} dimensions)")

    # Connect to MongoDB
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
    db_name = os.getenv('DB_NAME', 'aura')
    client = MongoClient(mongo_uri)
    db = client[db_name]
    documents = db['documents']

    # Find all completed documents
    query = {'status': 'COMPLETE', 'processed_data': {'$exists': True}}
    total = documents.count_documents(query)
    logger.info(f"Found {total} documents to re-embed")

    updated = 0
    errors = 0
    cursor = documents.find(query, batch_size=batch_size)

    for doc in cursor:
        doc_id = doc['_id']
        processed_data = doc.get('processed_data', [])
        changed = False

        for i, pd in enumerate(processed_data):
            text = pd.get('full_text') or pd.get('text', '')
            if not text:
                continue

            new_embedding = model.encode(text, convert_to_tensor=False).tolist()

            if not dry_run:
                processed_data[i]['embedding'] = new_embedding
                changed = True

            logger.debug(f"  Doc {doc_id} sub-doc {i}: {len(text)} chars → {len(new_embedding)}d vector")

        if changed and not dry_run:
            try:
                documents.update_one(
                    {'_id': doc_id},
                    {'$set': {
                        'processed_data': processed_data,
                        'embedding_model': model_name,
                        'embedding_migrated_at': datetime.utcnow(),
                    }}
                )
                updated += 1
            except Exception as e:
                logger.error(f"Failed to update {doc_id}: {e}")
                errors += 1
        elif dry_run:
            updated += 1

        if updated % 10 == 0:
            logger.info(f"Progress: {updated}/{total} documents {'(dry run)' if dry_run else 'updated'}")

    logger.info(f"Migration complete: {updated} updated, {errors} errors out of {total} total")

    if not dry_run:
        # Invalidate FAISS index so it rebuilds with new embeddings
        try:
            from app.utils.vector_index import invalidate
            invalidate()
            logger.info("FAISS index invalidated — will rebuild on next search")
        except Exception:
            logger.warning("Could not invalidate FAISS index (service may not be running)")

    client.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Re-embed documents after model change')
    parser.add_argument('--dry-run', action='store_true', help='Count documents without modifying')
    parser.add_argument('--batch-size', type=int, default=50, help='MongoDB cursor batch size')
    args = parser.parse_args()
    migrate(dry_run=args.dry_run, batch_size=args.batch_size)
```

#### Step 5 — Deployment Sequence

```
1.  Stop AI Service
2.  Download new model (Step 1)
3.  Update loader.py model name (Step 2)
4.  Run migration: python scripts/migrate_embeddings.py --dry-run  (verify count)
5.  Run migration: python scripts/migrate_embeddings.py            (actual update)
6.  Start AI Service
7.  Test search: POST /api/v1/search with a German query
8.  Verify classification still works on a new PDF upload
```

#### Step 6 — Verify

- Upload a German invoice → classification should improve
- Search for "Rechnungsnummer" → should find relevant documents
- Search for "invoice number" → should ALSO find German documents (multilingual)
- Compare search quality before/after with test queries

### File Change Summary

| File | Project | Change |
|------|---------|--------|
| `app/models/loader.py` | AI Service | Change model name to multilingual variant |
| `app/core/classifier.py` | AI Service | Verify dimension constant (no change if 384) |
| `scripts/migrate_embeddings.py` | AI Service | NEW — re-embedding migration script |
| `models/sentence-transformers/` | AI Service | New model files downloaded |

**Total: 3 files modified/created in AI Service only + model download**

### Risk: Incompatible Embeddings

If you switch to a model with DIFFERENT dimensions (e.g., 768-dim), additional changes are needed:

| What | Where | Change |
|------|-------|--------|
| Zero vector fallback | classifier.py line ~201 | `np.zeros(384)` → `np.zeros(768)` |
| FAISS index | vector_index.py | Auto-detects from data, no change |
| MongoDB vectors | migration script | Re-embed all docs (already covered) |

**Using `paraphrase-multilingual-MiniLM-L12-v2` avoids this entirely** — same 384 dimensions.

---

## Implementation Order

```
ORDER   FIX    RISK    REASON
─────   ────   ────    ──────
  1     0.2    HIGH    Must be done first — enables API key headers everywhere.
                       Without this, Fix 0.5 could break frontends.

  2     0.5    LOW     Remove "*" from CORS. After Fix 0.2, all frontend calls
                       go through backends (no browser-to-AI-Service calls).
                       CORS becomes nearly irrelevant.

  3     6.3    MED     Sentence Transformer swap. Independent of 0.2/0.5.
                       Requires downtime for migration. Test thoroughly.
```

**Do NOT implement Fix 0.5 before Fix 0.2.** If you lock down CORS before proxying the frontend calls through backends, the Aura Frontend scanner and Control Panel classification pages will break.

---

## Rollback Plan

### Fix 0.2 — Rollback

Set `AI_SERVICE_API_KEY=` (empty) in AI Service `.env` → middleware skips validation → all calls work without key.

### Fix 0.5 — Rollback

Set `CORS_ORIGINS=*` in AI Service `.env` → back to allow-all.

### Fix 6.3 — Rollback

1. Change model name back in `loader.py`
2. Re-run `scripts/migrate_embeddings.py` (it uses whatever model is configured)
3. Restart AI Service

**Or:** Keep a MongoDB backup before migration:
```powershell
mongodump --db aura --collection documents --out backups/pre-embedding-migration
```

Restore with:
```powershell
mongorestore --db aura --collection documents backups/pre-embedding-migration/aura/documents.bson
```
