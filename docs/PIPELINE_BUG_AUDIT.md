# Pipeline Bug Audit Report

**Date:** March 14, 2026 (Updated: March 15, 2026)  
**Scope:** Full code audit of `run_full_ai_pipeline()` and all 10 service modules + endpoints  
**Status:** 28 bugs found — 5 CRITICAL, 7 HIGH, 10 MEDIUM, 6 LOW

| Severity | Count | Bug IDs |
|----------|-------|---------|
| CRITICAL | 5 | #1, #2, #3, #9, #10 |
| HIGH | 7 | #4, #8, #11, #12, #13, #14, #15 |
| MEDIUM | 10 | #5, #6, #16, #17, #18, #19, #20, #21, #23, #24 |
| LOW | 6 | #7, #22, #25, #26, #27, #28 |

---

## CRITICAL BUGS (will crash or silently fail)

### BUG 1: Wrong model key `'ocr'` — PaddleOCR never found (4 places)

**Root Cause:** The model loader (`app/models/loader.py`) stores PaddleOCR as `models['paddleocr']`, but 4 places look for `models['ocr']` which is never set.

| File | Line | Code |
|------|------|------|
| `app/services/region_router.py` | 48 | `ocr = models.get('ocr')` |
| `app/api/endpoints.py` | 2052 | `ocr_model = models.get('ocr')` |
| `app/api/endpoints.py` | 2116 | `if engine == "paddleocr" and not models.get('ocr'):` |
| `app/api/endpoints.py` | 2250 | `ocr_model = models.get('ocr')` |

**Impact:**
- `region_router.py`: `_ocr_with_paddle()` always returns empty string `""` — all layout-detected text_block, header, and footer regions get no text even though YOLO detects them correctly.
- `endpoints.py`: The 3 OCR API endpoints (`/ocr/extract`, `/ocr/extract-async`, `/ocr/batch`) always fail with "PaddleOCR not available" or "OCR model not available" errors.

**Fix:** Change `models.get('ocr')` → `models.get('paddleocr')` in all 4 locations.

---

### BUG 2: Missing `logger` in `signature_ocr.py` — NameError crash

**File:** `app/services/signature_ocr.py`

**Root Cause:** The file imports `os`, `cv2`, `numpy`, `PIL`, `torch` — but never imports `logging` and never defines `logger`. However, `logger.info()` is called at line 62 when TrOCR is moved to GPU.

**Impact:** When TrOCR needs GPU (i.e., GPU is available and has memory), the function crashes with `NameError: name 'logger' is not defined`. This kills signature OCR for that document.

**Fix:** Add at the top of the file:
```python
import logging
logger = logging.getLogger("signature_ocr")
```

---

### BUG 3: `_ocr_with_paddle` only handles old PaddleOCR format

**File:** `app/services/region_router.py`, line 53

**Root Cause:** The function parses PaddleOCR results assuming the old list-of-lists format:
```python
return "\n".join(line[1][0] for line in result[0] if line)
```

But PP-OCRv5 (configured in `loader.py` with `ocr_version='PP-OCRv5'`) returns a new dict format:
```python
{'rec_texts': ['text1', 'text2'], 'rec_scores': [0.95, 0.88], ...}
```

The `classifier.py` file correctly handles BOTH formats (lines 85-110), but `region_router.py` does not.

**Impact:** Once Bug 1 is fixed (so `_ocr_with_paddle` actually receives the PaddleOCR model), it will crash with `TypeError` because `result[0]` is a dict, not a list.

**Fix:** Update `_ocr_with_paddle()` to handle both formats, similar to `classifier.py`:
```python
def _ocr_with_paddle(crop_img: np.ndarray, models: Dict[str, Any]) -> str:
    ocr = models.get('paddleocr')
    if not ocr:
        return ""
    result = ocr.ocr(crop_img, cls=True)
    if result and result[0]:
        ocr_data = result[0]
        # PP-OCRv5 returns dict with rec_texts
        if isinstance(ocr_data, dict) and 'rec_texts' in ocr_data:
            return "\n".join(ocr_data['rec_texts'])
        # Old format: list of [box, (text, confidence)]
        lines = []
        for line in ocr_data:
            if line and isinstance(line, (list, tuple)) and len(line) >= 2:
                text_part = line[1]
                if isinstance(text_part, (list, tuple)) and len(text_part) >= 1:
                    lines.append(str(text_part[0]))
                elif isinstance(text_part, str):
                    lines.append(text_part)
        return "\n".join(lines)
    return ""
```

---

## HIGH SEVERITY BUGS

### BUG 4: Splitting disabled → `end_page: 0` skips all pages except first

**File:** `app/core/pipeline.py`, line 284-288

**Root Cause:** When `ENABLE_PDF_SPLITTING=False`, the pipeline creates a single logical document with hardcoded `start_page: 0, end_page: 0`:
```python
logical_documents = [{
    'doc_num': 1,
    'start_page': 0,
    'end_page': 0,      # ← Always 0, regardless of actual page count
    'page_count': 1,     # ← Always 1
    'text': full_text,
    'embedding': None
}]
```

Later, layout detection (line ~503), signature detection (line ~541), and table extraction (line ~680) all use:
```python
start_page = logical_doc['start_page']  # 0
end_page = logical_doc['end_page']      # 0
# range(0, 1) → only processes page 0
```

Meanwhile, `images` contains ALL pages from `convert_from_path`.

**Impact:** For a 10-page PDF with splitting disabled, only page 1 gets layout analysis, signature detection, and table extraction. Pages 2-10 are completely ignored for visual processing.

**Fix:** Calculate actual page count from the PDF:
```python
from pdf2image import pdfinfo_from_path
# Or simply count from the images list later
logical_documents = [{
    'doc_num': 1,
    'start_page': 0,
    'end_page': len(images) - 1,  # ← Use actual page count
    'page_count': len(images),
    'text': full_text,
    'embedding': None
}]
```

Note: Since `images` is not yet available at this point in the code, the fix should be applied after `images` is populated — update `end_page` and `page_count` in the logical document before the processing loop.

---

## MEDIUM SEVERITY BUGS

### BUG 5: `ocr_confidence` lost when splitting disabled

**File:** `app/core/pipeline.py`, line 280-288

**Root Cause:** `extract_text_basic()` returns `{'text': ..., 'ocr_confidence': {'avg_confidence': float, 'min_confidence': float}}`, but the pipeline discards the `ocr_confidence` field:
```python
result = extract_text_basic(pdf_file_path, models)
full_text = result['text'] if isinstance(result, dict) else result
logical_documents = [{
    ...
    'text': full_text,
    # 'ocr_confidence' NOT included!
}]
```

**Impact:** OCR validation smart routing cannot use the real PaddleOCR confidence scores. It falls back to the heuristic `assess_text_quality()` function which estimates quality from text patterns — less accurate than actual OCR engine confidence. Documents may get routed to the wrong validation tier (e.g., FULL correction when SKIP would have been appropriate, or vice versa).

**Fix:** Include `ocr_confidence` in the logical document dict:
```python
ocr_conf = result.get('ocr_confidence', {'avg_confidence': 0.5, 'min_confidence': 0.5}) if isinstance(result, dict) else {'avg_confidence': 0.5, 'min_confidence': 0.5}
logical_documents = [{
    ...
    'ocr_confidence': ocr_conf
}]
```

---

### BUG 6: `embedding: None` when splitting disabled → broken vector search

**File:** `app/core/pipeline.py`, line 288

**Root Cause:** When splitting is disabled, `embedding` is set to `None`:
```python
logical_documents = [{
    ...
    'embedding': None
}]
```

In the processing loop, `doc_embedding = logical_doc.get('embedding', [])` gets `None`. If OCR validation tier is SKIP (no corrections made), the embedding is never regenerated:
```python
if ocr_validation.get('corrections_made', 0) > 0:
    # Only regenerated when corrections were made
    doc_embedding = search_model.encode(doc_text, ...)
```

So `doc_embedding` stays `None` and is saved to MongoDB in `processed_doc['embedding']`.

**Impact:** FAISS vector search index will break or produce errors when trying to compute cosine similarity against `None`. Documents processed with splitting disabled will be invisible to semantic search.

**Fix:** Generate embedding for the single-document case:
```python
search_model = models.get('sentence_transformer_search')
doc_embedding = search_model.encode(full_text, convert_to_tensor=False).tolist() if search_model and full_text else []

logical_documents = [{
    ...
    'embedding': doc_embedding
}]
```

---

## LOW SEVERITY BUGS

### BUG 7: `page_count: 1` hardcoded when splitting disabled

**File:** `app/core/pipeline.py`, line 287

**Root Cause:** `page_count` is hardcoded to `1` regardless of actual PDF page count.

**Impact:** Cosmetic — document metadata in MongoDB shows `page_count: 1` for all documents processed without splitting, even if they have 50 pages. This affects UI display and any analytics based on page count.

**Fix:** Same as Bug 4 — use actual page count.

---

## HIGH SEVERITY BUGS (continued)

### BUG 8: Layout handwriting TrOCR text extracted but discarded

**File:** `app/core/pipeline.py`, lines 487-535 (layout results) and 773-815 (processed_doc)

**Root Cause:** The pipeline runs YOLO layout detection → region_router routes `handwriting_region` to TrOCR → TrOCR extracts handwritten text → results sit in `layout_results` dict. But the pipeline only reads `layout_results` for one purpose: finding signatures (`class == 'signature'`). All other layout data — including handwriting text, text_block text, header/footer text — is completely ignored.

The `layout_results` dict is never:
- Merged into `doc_text`
- Stored in `processed_doc`
- Saved to MongoDB

**Impact:** TrOCR does the GPU-intensive handwriting OCR work, produces high-quality handwritten text extraction, and the pipeline silently discards it. The document's `doc_text` only contains PaddleOCR output which is poor at handwriting recognition. Handwritten notes, annotations, and form entries are effectively lost.

**Fix:** After layout detection completes, merge handwriting text into the document and store all layout results:
```python
# After layout detection, merge handwriting text and store layout data
if layout_results:
    handwriting_texts = []
    for page_idx, regions in layout_results.items():
        for region in regions:
            if region.get('class') in ('handwriting_region', 'signature') and region.get('text', '').strip():
                handwriting_texts.append(region['text'].strip())
    if handwriting_texts:
        doc_text += "\n\n[Handwritten Content]\n" + "\n".join(handwriting_texts)
```
Also store `layout_results` in `processed_doc` for downstream use.

---

## Files Audited

| File | Status |
|------|--------|
| `app/core/pipeline.py` | 5 bugs found (Bugs 4, 5, 6, 7, 8) |
| `app/core/classifier.py` | ✅ Clean — handles both PaddleOCR formats correctly |
| `app/services/ocr_validation.py` | ✅ Clean — all 4 tiers logic correct |
| `app/services/layout_detection.py` | ✅ Clean — YOLO batch + region routing works |
| `app/services/region_router.py` | 2 bugs found (Bugs 1, 3) |
| `app/services/signature_detection.py` | ✅ Clean — batch YOLO + TrOCR pipeline correct |
| `app/services/signature_ocr.py` | 1 bug found (Bug 2) |
| `app/services/signature_validation.py` | ✅ Clean — LLaMA cross-reference works |
| `app/utils/extraction.py` | ✅ Clean — structured + entity extraction correct |
| `app/services/table_extraction.py` | ✅ Clean — PPStructureV3 + legacy handled |
| `app/models/loader.py` | ✅ Clean — key is `'paddleocr'` (consumers use wrong key) |
| `app/api/endpoints.py` | 1 bug found (Bug 1 — 3 locations) |

---

## Summary

- **3 CRITICAL** bugs that cause crashes or complete feature failure
- **2 HIGH** bugs that silently skip pages or discard extracted data
- **2 MEDIUM** bugs that degrade search quality and OCR routing accuracy
- **1 LOW** cosmetic metadata bug

The pipeline will work for the **happy path** (splitting enabled, single-page docs, no layout detection), but will fail or produce wrong results when:
- Layout detection is active (Bug 1 + 3 → no text extracted from regions)
- TrOCR signature OCR moves to GPU (Bug 2 → crash)
- Multi-page PDFs with splitting disabled (Bug 4 → pages skipped)
- Any document with splitting disabled (Bug 5+6 → wrong OCR routing + broken search)
- Documents with handwriting (Bug 8 → TrOCR results discarded)

---

# DEEP AUDIT — Additional Bugs 9–28

*Found by comprehensive code audit of all service modules, endpoints, and cross-cutting concerns.*

---

## CRITICAL BUGS (continued)

### BUG 9: `_ocr_extract_sync` uses wrong key AND only handles old PaddleOCR format

**File:** `app/api/endpoints.py` — `_ocr_extract_sync()` function

**Root Cause (dual):**
1. Same as Bug 1: Uses `models.get('ocr')` instead of `models.get('paddleocr')`.
2. Same as Bug 3: Parses result with old format `line[1][0]`, but PP-OCRv5 returns `{'rec_texts': [...]}`.

**Impact:** The `/ocr/extract` sync endpoint will crash with `TypeError` when it reaches the result parsing code (if Bug 1 is fixed first). Currently it fails silently with "OCR model not available".

**Fix:** Change key to `'paddleocr'` AND handle both PP-OCRv5 dict format and legacy list format.

---

### BUG 10: Batch OCR endpoint passes single model object instead of models dict

**File:** `app/api/endpoints.py` — `/ocr/batch` endpoint

**Root Cause:** The batch endpoint extracts a single `ocr_model = models.get('ocr')` (wrong key — Bug 1), then passes it to `_ocr_extract_sync(file, ocr_model, ...)`. But `_ocr_extract_sync` expects the full `models` dict because it internally calls `models.get('ocr')`.

When called with a single PaddleOCR object: `models.get('ocr')` → `AttributeError: 'PaddleOCR' object has no attribute 'get'`.

**Impact:** Batch OCR endpoint always crashes even if Bug 1 is fixed — wrong type passed.

**Fix:** Pass the full `models` dict instead of extracted single model.

---

## HIGH SEVERITY BUGS (continued)

### BUG 11: FULL tier (TIER 3) early-returns missing `routing_tier` key

**File:** `app/services/ocr_validation.py` — `validate_ocr_quality()`, FULL tier section

**Root Cause:** The FULL tier (quality 50-74%) has 2 conditional early-return paths:
1. If LLaMA is not available → returns result dict without `routing_tier` key
2. If LLaMA times out → returns result dict without `routing_tier` key

The normal path and other tiers always include `routing_tier` in the response.

**Impact:** Downstream code that reads `result['routing_tier']` may crash with `KeyError` when the document hits FULL tier and LLaMA is unavailable or times out. Currently the pipeline doesn't read this key, but the logging and MongoDB storage include it, and any future feature relying on it will break.

**Fix:** Add `'routing_tier': 'full'` to both early-return dicts.

---

### BUG 12: Pipeline never passes `page_image` to `validate_ocr_quality` — REVIEW tier TrOCR is dead code

**File:** `app/core/pipeline.py` — OCR validation call (around line 410-440)

**Root Cause:** The `validate_ocr_quality()` function signature accepts an optional `page_image` parameter. When quality < 50% (REVIEW tier), it tries to run TrOCR on `page_image` as a second OCR engine for comparison. But the pipeline calls it as:
```python
ocr_validation = await validate_ocr_quality(doc_text, models)
```
Without passing `page_image`. So `page_image` defaults to `None` and the TrOCR comparison path is silently skipped.

**Impact:** The REVIEW tier (worst quality documents) never gets TrOCR assistance. These are the documents that need it most — they have <50% OCR quality and could benefit from handwriting-capable OCR. The feature was implemented but never wired in.

**Fix:** Pass the first page image to OCR validation:
```python
page_img = images[logical_doc['start_page']] if images else None
ocr_validation = await validate_ocr_quality(doc_text, models, page_image=page_img)
```

---

### BUG 13: TrOCR device mismatch in concurrent requests

**File:** `app/services/region_router.py` — `_ocr_with_trocr()`

**Root Cause:** The function reads `device = trocr.get('device', 'cpu')` and moves `pixel_values` to that device. But `signature_ocr.py` can concurrently move the same TrOCR model between CPU and GPU (for its own inference). If `signature_ocr` moves the model to GPU while `region_router` still thinks device='cpu', the `pixel_values` go to CPU but the model is on GPU → `RuntimeError: Expected all tensors to be on the same device`.

**Impact:** Under concurrent processing (FastAPI async), TrOCR calls can crash sporadically. Rare in single-document processing, but likely in batch operations.

**Fix:** Read device from the model itself: `device = next(model.parameters()).device` right before inference.

---

### BUG 14: `classify_with_reasoning` — `llama_override` always returns False

**File:** `app/core/classifier.py` — `classify_with_reasoning()` function

**Root Cause:** The function:
1. Gets embedding classification confidence (e.g., 0.72)
2. Mutates `confidence` to add boost: `confidence = min(1.0, confidence + 0.10)` → 0.82
3. Then checks: `if confidence < config.CONFIDENCE_THRESHOLD - 0.15` (threshold is typically 0.7)
4. So the check is: `if 0.82 < 0.55` → always False

The LLaMA override (which would re-classify low-confidence documents using the LLM) can never trigger because the confidence is boosted BEFORE the check.

**Impact:** Documents classified with low confidence (e.g., 0.45) should trigger LLaMA re-classification but don't. They get wrong labels and the wrong extraction template. This degrades classification accuracy for ambiguous documents.

**Fix:** Check `llama_override` BEFORE applying the confidence boost, or use the original pre-boost confidence.

---

### BUG 15: Endpoint availability guard uses wrong key

**File:** `app/api/endpoints.py` — `/ocr/extract` endpoint guard

**Root Cause:** Same root cause as Bug 1:
```python
if not models.get('ocr'):
    raise HTTPException(status_code=503, ...)
```
Uses `'ocr'` instead of `'paddleocr'`.

**Impact:** The availability check always fails → returns 503 "OCR model not available" even though PaddleOCR IS loaded. The endpoint appears broken even when the service is healthy.

**Fix:** Change to `models.get('paddleocr')`.

---

## MEDIUM SEVERITY BUGS (continued)

### BUG 16: Batch endpoint availability check uses wrong key

**File:** `app/api/endpoints.py` — `/ocr/batch` endpoint guard

**Root Cause:** Same as Bug 15 but in the batch endpoint:
```python
if not models.get('ocr'):
    raise HTTPException(status_code=503, ...)
```

**Impact:** Batch OCR endpoint always returns 503.

**Fix:** Change to `models.get('paddleocr')`.

---

### BUG 17: `process_document` inserts string `_id` but pipeline expects ObjectId conversion

**File:** `app/api/endpoints.py` — `process_document()` endpoint + `app/core/pipeline.py`

**Root Cause:** The `process_document` endpoint inserts a document with MongoDB's auto-generated `_id` (ObjectId). It then passes `str(result.inserted_id)` (a hex string) to the pipeline task. The pipeline does `ObjectId(doc_id)` to convert back. This works for auto-generated IDs.

However, if a client provides a custom `_id` that isn't a valid 24-character hex string (e.g., UUID, integer, or custom string), `ObjectId(doc_id)` raises `bson.errors.InvalidId`.

**Impact:** Custom document IDs cause pipeline crashes. Currently unlikely since the endpoint doesn't accept custom IDs, but any future extension or direct MongoDB insertion with non-hex IDs will break.

**Fix:** Validate `doc_id` format or use the string `_id` directly instead of converting.

---

### BUG 18: `SuppressOutput` context manager leaks file descriptors on error

**File:** `app/models/loader.py` — `SuppressOutput` class

**Root Cause:** The `SuppressOutput` context manager redirects `sys.stdout` / `sys.stderr` to `/dev/null` (or `os.devnull`). If an exception occurs inside the context, the `__exit__` method restores the file descriptors but doesn't close the devnull file handles it opened.

**Impact:** Each failed model load leaks 2 file descriptors. Over many retries or failures, this can hit the OS file descriptor limit (`ulimit -n`) causing cascading failures.

**Fix:** Track opened devnull handles and close them in `__exit__`.

---

### BUG 19: TrOCR device tracking inconsistency

**File:** `app/services/region_router.py` + `app/services/signature_ocr.py`

**Root Cause:** Both files read `trocr.get('device', 'cpu')` from the shared `models['trocr']` dict. When one function moves the model to GPU and updates `trocr['device'] = 'cuda'`, the other function may not see the update in time (Python dict operations are thread-safe for simple get/set, but the model movement and dict update aren't atomic).

**Impact:** Related to Bug 13 — contributes to the device mismatch scenario.

**Fix:** Use `next(model.parameters()).device` for actual device detection, or add a threading lock.

---

### BUG 20: `get_table_engine()` is not thread-safe

**File:** `app/services/table_extraction.py` — `get_table_engine()` function

**Root Cause:** The function uses a module-level variable to cache the table engine instance. Under concurrent requests, two threads can both see `engine is None`, both create a new engine instance, and one's work is wasted. There's no lock.

**Impact:** Wasted memory and GPU resources during concurrent table extraction startup. Not a crash but inefficient.

**Fix:** Add `threading.Lock()` around engine initialization.

---

### BUG 21: OCR validation bypasses `ensure_llama_loaded()` thread safety

**File:** `app/services/ocr_validation.py`

**Root Cause:** The FULL and REVIEW tiers call LLaMA directly through `models['llama']` without going through `ensure_llama_loaded()` which handles thread-safe model loading and health checks. Other callers (extraction, summary) use `ensure_llama_loaded()`.

**Impact:** If LLaMA crashed and auto-restarted, OCR validation won't get the new instance. It will talk to the dead process or get connection errors.

**Fix:** Use `ensure_llama_loaded(models)` before accessing LLaMA in OCR validation.

---

### BUG 23: ALL layout OCR text is wasted, not just handwriting (broader than Bug 8)

**File:** `app/core/pipeline.py` — layout results consumption (lines 522-537)

**Root Cause:** Bug 8 identified that handwriting text is discarded. But the problem is broader: the pipeline discards ALL text from ALL layout regions except signatures. This includes:
- `text_block` regions (PaddleOCR text — even though this overlaps with initial OCR, layout-based OCR is position-aware)
- `header` regions (document headers with metadata)
- `footer` regions (page numbers, footer text)
- `handwriting_region` (handwritten annotations, notes)
- Table positions (could inform table extraction)
- Stamp locations (could flag document as certified/official)

The region_router produces rich structured data: class, confidence, bounding box, engine used, extracted text. ALL of this is thrown away.

**Impact:** The YOLO layout model + region_router do expensive GPU work to understand document structure, but the pipeline ignores it all. This makes the layout detection step effectively useless (except for the narrow signature extraction case).

**Fix (comprehensive):**
1. Store ALL layout results in `processed_doc['layout_regions']`
2. Merge handwriting_region text into `doc_text` (enriches extraction + search)
3. Use header/footer text for metadata extraction
4. Pass table bounding boxes to `table_extraction` for targeted extraction
5. Store stamp detections as `stamp_detected: true/false` with location

---

### BUG 24: Async functions call sync LLaMA — blocks event loop

**Files:** `app/services/signature_validation.py`, `app/services/ocr_validation.py`, `app/utils/extraction.py`

**Root Cause:** Several `async def` functions call the LLaMA model synchronously (HTTP POST to llamafile). LLaMA inference takes 2-15 seconds per call. During this time, the FastAPI event loop is blocked — no other requests can be processed.

Functions affected:
- `validate_signature_text()` — calls LLaMA for validation
- `validate_ocr_quality()` — calls LLaMA for FULL tier correction
- `extract_structured_data()` — calls LLaMA for field extraction
- `generate_summary()` — calls LLaMA for summarization

**Impact:** During pipeline processing, the entire FastAPI server becomes unresponsive for 2-15 seconds per LLaMA call, with 3-4 LLaMA calls per document. Total blocking time: 6-60 seconds per document.

**Fix:** Wrap sync LLaMA calls in `asyncio.to_thread()` or `loop.run_in_executor()`.

---

## LOW SEVERITY BUGS (continued)

### BUG 22: Minor — Overlapping confidence check

**File:** `app/core/classifier.py`

**Root Cause:** The confidence boost and threshold check logic has overlapping ranges that make certain code paths unreachable. Cosmetic/logic clarity issue.

**Impact:** No crash, but confusing code.

---

### BUG 25: Hardcoded threshold instead of config variable

**File:** `app/core/classifier.py` — `classify_with_reasoning()`

**Root Cause:** The LLaMA override threshold is calculated as `config.CONFIDENCE_THRESHOLD - 0.15` using a hardcoded `0.15` magic number instead of a configurable parameter like `CONFIDENCE_OVERRIDE_MARGIN`.

**Impact:** Cannot tune the LLaMA override sensitivity without code changes. Minor, but reduces operational flexibility.

**Fix:** Add `CONFIDENCE_OVERRIDE_MARGIN = 0.15` to config.

---

### BUG 26: `ocr_confidence` missing in non-split path (overlaps Bug 5)

**File:** `app/core/pipeline.py`

**Root Cause:** Duplicate of Bug 5 scenario — when splitting disabled, real OCR confidence scores are lost. Documented separately because it affects a different code path.

**Impact:** Same as Bug 5.

---

### BUG 27: `'images' in dir()` should be `'images' in locals()`

**File:** `app/core/pipeline.py` — `finally` cleanup block (around line 870)

**Root Cause:** Uses `dir()` which returns all names in scope (including module-level), not just local variables. Should use `locals()` for the intended check.

**Impact:** Edge case: if a module-level `images` variable existed, cleanup could try to iterate a non-list object. Currently works by accident because no module-level `images` exists.

**Fix:** Change `'images' in dir()` to `'images' in locals()`.

---

### BUG 28: `cleanup_temp_files` may fail if variables undefined

**File:** `app/core/pipeline.py` — `finally` block

**Root Cause:** The cleanup block references `original_doc_id` with `'original_doc_id' in dir()`, but if the function crashed before `original_doc_id` was assigned, this check may pass spuriously (same `dir()` issue as Bug 27), and `original_doc_id` would be an unbound local → `UnboundLocalError`.

**Impact:** Temp files not cleaned up when pipeline crashes early. Disk space leak over time.

**Fix:** Use `locals().get('original_doc_id', doc_id)` pattern.

---

## YOLO Layout Model Integration Analysis

### How YOLO Layout Connects to Each Feature

| YOLO Class | Target | OCR Engine | Pipeline Status |
|---|---|---|---|
| 0: text_block | Printed text regions | PaddleOCR | ❌ Broken (Bug 1+3) + Discarded (Bug 23) |
| 1: table | Table regions | PPStructure placeholder | ❌ Disconnected from table_extraction service |
| 2: figure | Images/diagrams | Skip (by design) | ❌ Detection discarded |
| 3: signature | Signature areas | TrOCR | ✅ WORKS — only layout class that pipeline consumes |
| 4: stamp | Official stamps | Skip (by design) | ❌ Detection discarded, no `stamp_detected` field |
| 5: handwriting_region | Handwritten text | TrOCR | ❌ Text extracted but discarded (Bug 8/23) |
| 6: header | Page headers | PaddleOCR | ❌ Broken (Bug 1+3) + Discarded (Bug 23) |
| 7: footer | Page footers | PaddleOCR | ❌ Broken (Bug 1+3) + Discarded (Bug 23) |

### Summary: 1 out of 8 classes actually works end-to-end.

The YOLO model training (100 epochs, 65K images) will produce a great detection model. The detection logic itself (`layout_detection.py`) is clean. The routing logic (`region_router.py`) is mostly correct (needs Bug 1+3 fixes). **The bottleneck is `pipeline.py` which discards everything except signatures.**

---

## Files Audited (Updated)

| File | Status |
|------|--------|
| `app/core/pipeline.py` | 10 bugs (Bugs 4, 5, 6, 7, 8, 12, 23, 26, 27, 28) |
| `app/core/classifier.py` | 3 bugs (Bugs 14, 22, 25) |
| `app/services/ocr_validation.py` | 2 bugs (Bugs 11, 21) |
| `app/services/layout_detection.py` | ✅ Clean |
| `app/services/region_router.py` | 3 bugs (Bugs 1, 3, 13/19) |
| `app/services/signature_detection.py` | ✅ Clean |
| `app/services/signature_ocr.py` | 1 bug (Bug 2) |
| `app/services/signature_validation.py` | 1 bug (Bug 24) |
| `app/utils/extraction.py` | 1 bug (Bug 24) |
| `app/services/table_extraction.py` | 1 bug (Bug 20) |
| `app/models/loader.py` | 1 bug (Bug 18) |
| `app/api/endpoints.py` | 6 bugs (Bug 1×3 locations, 9, 10, 15, 16, 17) |

---

## Priority Fix Order (when ready)

### Phase 1 — CRITICAL (crashes/total failures)
1. Bug 1 — Fix model key `'ocr'` → `'paddleocr'` (4 locations)
2. Bug 2 — Add logger to `signature_ocr.py`
3. Bug 3 — Handle both PaddleOCR formats in `region_router.py`
4. Bug 9 — Fix `_ocr_extract_sync` key + format handling
5. Bug 10 — Pass full `models` dict to batch OCR

### Phase 2 — HIGH (silent data loss / dead features)
6. Bug 4 — Fix `end_page=0` when splitting disabled
7. Bug 8/23 — Store + merge ALL layout text (not just signatures)
8. Bug 11 — Add `routing_tier` to FULL tier early-returns
9. Bug 12 — Pass `page_image` to `validate_ocr_quality`
10. Bug 13 — Fix TrOCR device detection
11. Bug 14 — Fix LLaMA override confidence check order
12. Bug 15 — Fix endpoint availability guard key

### Phase 3 — MEDIUM (degraded quality / edge cases)
13. Bugs 5, 6, 26 — Fix `ocr_confidence` and `embedding` for non-split path
14. Bug 16 — Fix batch availability check key
15. Bug 17 — Handle non-hex document IDs
16. Bug 18 — Fix file descriptor leak in `SuppressOutput`
17. Bug 19, 20 — Thread safety fixes
18. Bug 21 — Use `ensure_llama_loaded` in OCR validation
19. Bug 24 — Wrap sync LLaMA calls in `asyncio.to_thread()`

### Phase 4 — LOW (cosmetic / minor)
20. Bugs 7, 22, 25, 27, 28 — Config values, cleanup, code clarity
