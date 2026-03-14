# Pipeline Bug Fix Plan

**Created:** March 14, 2026  
**Verified:** March 14, 2026 — all 28 bug locations confirmed against live code  
**Total Bugs:** 28 (5 CRITICAL, 7 HIGH, 10 MEDIUM, 6 LOW)  
**Total Files:** 10  
**Implemented:** March 14, 2026  all 28 bugs fixed in 4 phases
**Total Edits:** ~36  

---

## Status Legend

- ✅ Not started
- 🔄 In progress
- ✅ Fixed
- 🧪 Tested

---

## PHASE 1 — CRITICAL (5 bugs, 3 files)

> Crashes or complete feature failures. Fix first.

### Bug #1: Wrong model key `'ocr'` → `'paddleocr'` (4 locations) ✅

The model loader stores PaddleOCR as `models['paddleocr']`, but 4 locations look for `models['ocr']`.

| # | File | Line | Current Code | Fix |
|---|------|------|-------------|-----|
| A | `app/services/region_router.py` | 48 | `ocr = models.get('ocr')` | `ocr = models.get('paddleocr')` |
| B | `app/api/endpoints.py` | ~2052 | `ocr_model = models.get('ocr')` | `ocr_model = models.get('paddleocr')` |
| C | `app/api/endpoints.py` | ~2116 | `not models.get('ocr')` | `not models.get('paddleocr')` |
| D | `app/api/endpoints.py` | ~2250 | `ocr_model = models.get('ocr')` | `ocr_model = models.get('paddleocr')` |

---

### Bug #2: Missing `logger` in `signature_ocr.py` → NameError crash ✅

**File:** `app/services/signature_ocr.py`  
**Problem:** No `import logging` / no `logger` defined, but `logger.info()` called at line ~62.  
**Fix:** Add after the existing imports (after `import torch`):
```python
import logging
logger = logging.getLogger("signature_ocr")
```

---

### Bug #3: `_ocr_with_paddle` only handles old PaddleOCR format ✅

**File:** `app/services/region_router.py`, lines 49–55  
**Problem:** Parses `line[1][0]` but PP-OCRv5 returns `{'rec_texts': [...]}` → TypeError.  
**Current code:**
```python
def _ocr_with_paddle(crop_img: np.ndarray, models: Dict[str, Any]) -> str:
    ocr = models.get('ocr')
    if not ocr:
        return ""
    result = ocr.ocr(crop_img, cls=True)
    if result and result[0]:
        return "\n".join(line[1][0] for line in result[0] if line)
    return ""
```
**Fix — replace entire function:**
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
        # Legacy format: list of [box, (text, confidence)]
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

### Bug #9: `_ocr_extract_sync` wrong key + old format only ✅

**File:** `app/api/endpoints.py`, `_ocr_extract_sync()` function  
**Problem (dual):**
1. Line ~2052: `models.get('ocr')` → wrong key (same as Bug 1-B)
2. Lines ~2063-2074: Only handles old `line[1][0]` format, crashes with PP-OCRv5 dict

**Current parser (lines ~2063-2074):**
```python
    extracted_text = ""
    confidence_scores = []
    if result and len(result) > 0:
        for line in result[0]:
            if line:
                text = line[1][0]
                confidence = line[1][1]
                extracted_text += text + "\n"
                confidence_scores.append(confidence)
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
```

**Fix — replace parser block:**
```python
    extracted_text = ""
    confidence_scores = []
    if result and len(result) > 0 and result[0]:
        ocr_data = result[0]
        if isinstance(ocr_data, dict) and 'rec_texts' in ocr_data:
            # PP-OCRv5 dict format
            extracted_text = "\n".join(ocr_data['rec_texts'])
            confidence_scores = list(ocr_data.get('rec_scores', []))
        else:
            # Legacy list format
            for line in ocr_data:
                if line and isinstance(line, (list, tuple)) and len(line) >= 2:
                    text_part = line[1]
                    if isinstance(text_part, (list, tuple)) and len(text_part) >= 1:
                        extracted_text += str(text_part[0]) + "\n"
                        if len(text_part) >= 2:
                            confidence_scores.append(float(text_part[1]))
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
```

---

### Bug #10: Batch OCR passes single model object instead of dict ✅

**File:** `app/api/endpoints.py`, `/ocr/batch` endpoint  
**Problem:** Extracts `ocr_model = models.get('ocr')` then passes raw object to `_ocr_extract_sync` which expects a dict → `AttributeError`.

**Current code (lines ~2250, ~2265-2273):**
```python
    ocr_model = models.get('ocr')
    if not ocr_model:
        raise HTTPException(status_code=503, detail="OCR model not available")
    ...
    tasks = [
        loop.run_in_executor(
            executor,
            _ocr_extract_sync,
            file_path,
            request.engine,
            ocr_model          # ← BUG: raw PaddleOCR object
        )
        for file_path in validated_paths
    ]
```

**Fix:**
1. Change guard: `if not models.get('paddleocr'):` (fixes Bug #16 too)
2. Remove `ocr_model` extraction line
3. Pass full `models` dict:
```python
    if not models.get('paddleocr'):
        raise HTTPException(status_code=503, detail="OCR model not available")
    ...
    tasks = [
        loop.run_in_executor(
            executor,
            _ocr_extract_sync,
            file_path,
            request.engine,
            models              # ← full dict
        )
        for file_path in validated_paths
    ]
```

---

## PHASE 2 — HIGH (7 bugs, 3 files)

> Silent data loss, dead features, skipped pages.

### Bug #4 + #7: `end_page=0`, `page_count=1` when splitting disabled ✅

**File:** `app/core/pipeline.py`, lines ~284-288  
**Problem:** When `ENABLE_PDF_SPLITTING=False`, hardcodes `end_page: 0, page_count: 1` regardless of actual PDF pages. Layout detection, signature detection, and table extraction only process page 1.

**Current code:**
```python
logical_documents = [{
    'doc_num': 1,
    'start_page': 0,
    'end_page': 0,
    'page_count': 1,
    'text': full_text,
    'embedding': None
}]
```

**Fix:** After `images` is populated (~line 320, after the image conversion block), patch the logical document:
```python
# Fix page range for non-split mode (Bug #4 + #7)
if not ENABLE_PDF_SPLITTING and images and len(logical_documents) == 1:
    logical_documents[0]['end_page'] = len(images) - 1
    logical_documents[0]['page_count'] = len(images)
```

---

### Bug #8 + #23: ALL layout OCR text discarded (not just handwriting) ✅

**File:** `app/core/pipeline.py`, lines ~522-537  
**Problem:** Pipeline only reads `layout_results` for `class == 'signature'`. All text from text_block, header, footer, handwriting_region is thrown away. No layout data stored in MongoDB.

**Fix:** After the existing signature-from-layout block (line ~537), add:
```python
# Collect ALL layout region data + merge handwriting text (Bug #8 + #23)
layout_enriched = []
layout_text_parts = []
if layout_available and layout_results:
    for page_offset, regions in layout_results.items():
        for region in regions:
            layout_enriched.append({
                'page': page_offset,
                'class': region.get('class'),
                'confidence': region.get('confidence', 0.0),
                'box': region.get('box'),
                'engine': region.get('engine', ''),
                'text': region.get('text', '')
            })
            # Merge handwriting text into doc_text for extraction + search
            if region.get('class') == 'handwriting_region' and region.get('text', '').strip():
                layout_text_parts.append(region['text'].strip())
    if layout_text_parts:
        doc_text += "\n\n[Handwritten Content]\n" + "\n".join(layout_text_parts)
        logger.info(f"  ✓ Merged {len(layout_text_parts)} handwriting regions into doc_text")
```

Then in `processed_doc` dict (~line 780), add two new fields:
```python
'layout_regions': layout_enriched if layout_enriched else [],
'stamp_detected': any(r.get('class') == 'stamp' for r in layout_enriched) if layout_enriched else False,
```

---

### Bug #11: FULL tier early-returns missing `routing_tier` key ✅

**File:** `app/services/ocr_validation.py`, TIER 3 (FULL) section  
**Problem:** Two early-return dicts in FULL tier lack `'routing_tier': 'full'`.

**Fix — two returns to patch:**

Return 1 (LLaMA unavailable):
```python
# Current:
return {
    'corrected_text': ocr_text,
    'quality_score': initial_quality,
    'issues_found': ['Llama model unavailable'],
    'corrections_made': 0,
    'confidence': initial_quality
}
# Fix: Add 'routing_tier': 'full'
```

Return 2 (no issues detected):
```python
# Current:
return {
    'corrected_text': ocr_text,
    'quality_score': initial_quality,
    'issues_found': [],
    'corrections_made': 0,
    'confidence': 0.95
}
# Fix: Add 'routing_tier': 'full'
```

---

### Bug #12: Pipeline never passes `page_image` to REVIEW tier ✅

**File:** `app/core/pipeline.py`, ~line 430  
**Problem:** `validate_ocr_quality(doc_text, models, ocr_confidence)` — never passes `page_image`. REVIEW tier TrOCR fallback is dead code.

**Current:**
```python
ocr_validation = await asyncio.wait_for(
    validate_ocr_quality(doc_text, models, ocr_confidence),
    timeout=float(ocr_timeout)
)
```

**Fix:**
```python
# Pass page image for REVIEW tier TrOCR fallback (Bug #12)
start_pg = logical_doc.get('start_page', 0)
page_img = images[start_pg] if images and start_pg < len(images) else None

ocr_validation = await asyncio.wait_for(
    validate_ocr_quality(doc_text, models, ocr_confidence, page_image=page_img),
    timeout=float(ocr_timeout)
)
```

---

### Bug #13: TrOCR device mismatch in concurrent requests ✅

**File:** `app/services/region_router.py`, line ~70  
**Problem:** Reads `device = trocr.get('device', 'cpu')` from shared dict. If `signature_ocr` concurrently moves model to GPU, dict and model location diverge → RuntimeError.

**Current:**
```python
device = trocr.get('device', 'cpu')
```

**Fix:** Read actual device from model at inference time:
```python
device = next(model.parameters()).device
```

---

### Bug #14 + #25: `llama_override` always False + hardcoded threshold (2 locations) ✅

**File:** `app/core/classifier.py`, `classify_with_reasoning()`  
**Problem:** `confidence` is mutated to `0.85` (override_confidence) before the override check at return. The check `0.85 < 0.15` is always False. Also uses hardcoded `0.15` in **two** places (line ~530 override trigger AND line ~548 return value).

**Current (two locations):**

Line ~530 (override trigger):
```python
if confidence < 0.15 and llama_doc_type:
```

Line ~548 (return value):
```python
'llama_override': confidence < 0.15 and llama_doc_type is not None
```

**Fix (3 changes):**
1. Save original confidence near the top of the function:
```python
original_confidence = initial_classification['score']
```
2. Fix line ~530 override trigger to use config threshold:
```python
if original_confidence < low_confidence_threshold and llama_doc_type:
```
3. Fix line ~548 return value:
```python
'llama_override': original_confidence < low_confidence_threshold and llama_doc_type is not None
```
(`low_confidence_threshold` is already loaded from config at line ~470)

---

### Bug #15: `/ocr/extract` availability guard wrong key ✅

**File:** `app/api/endpoints.py`, line ~2116  
**Problem:** Same root cause as Bug #1-C.  
**Fix:** Covered by Bug #1-C: `models.get('ocr')` → `models.get('paddleocr')`.

---

## PHASE 3 — MEDIUM (10 bugs, 7 files)

> Degraded quality, edge-case failures, blocking I/O.

### Bug #5 + #26: `ocr_confidence` lost when splitting disabled ✅

**File:** `app/core/pipeline.py`, lines ~280-288  
**Problem:** `extract_text_basic()` returns `ocr_confidence` but it's not included in `logical_documents`.

**Fix:** Include it:
```python
result = extract_text_basic(pdf_file_path, models)
full_text = result['text'] if isinstance(result, dict) else result
ocr_conf = (result.get('ocr_confidence', {'avg_confidence': 0.5, 'min_confidence': 0.5})
            if isinstance(result, dict)
            else {'avg_confidence': 0.5, 'min_confidence': 0.5})
logical_documents = [{
    ...
    'text': full_text,
    'ocr_confidence': ocr_conf,
    ...
}]
```

---

### Bug #6: `embedding=None` when splitting disabled → broken FAISS search ✅

**File:** `app/core/pipeline.py`, line ~288  
**Problem:** `'embedding': None` — never regenerated if SKIP tier. FAISS breaks on `None`.

**Fix:** Generate embedding immediately:
```python
search_model = models.get('sentence_transformer_search')
doc_emb = (search_model.encode(full_text, convert_to_tensor=False).tolist()
           if search_model and full_text.strip() else [])
logical_documents = [{
    ...
    'embedding': doc_emb,
    ...
}]
```

---

### Bug #16: Batch endpoint availability guard wrong key ✅

**File:** `app/api/endpoints.py`, line ~2250  
**Problem:** Same root cause as Bug #1-D.  
**Fix:** Covered by Bug #10 fix — guard changed to `models.get('paddleocr')`.

---

### Bug #17: String `_id` vs ObjectId mismatch for non-hex IDs ✅

**File:** `app/core/pipeline.py`, line ~870 (error handler)  
**Problem:** `ObjectId(doc_id)` crashes with `bson.errors.InvalidId` for non-hex strings.

**Current:**
```python
obj_id = ObjectId(doc_id) if isinstance(doc_id, str) else doc_id
```

**Fix:**
```python
try:
    obj_id = ObjectId(doc_id) if isinstance(doc_id, str) else doc_id
except Exception:
    obj_id = doc_id  # Use string _id directly
```

---

### Bug #18: `SuppressOutput` leaks file descriptors on error ✅

**File:** `app/models/loader.py`, lines ~175-184  
**Problem:** devnull handles opened in `__enter__` not properly tracked and closed in `__exit__` if exception occurs.

**Fix — replace class:**
```python
class SuppressOutput:
    def __enter__(self):
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._devnull_out = open(os.devnull, 'w')
        self._devnull_err = open(os.devnull, 'w')
        sys.stdout = self._devnull_out
        sys.stderr = self._devnull_err
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        try:
            self._devnull_out.close()
        except Exception:
            pass
        try:
            self._devnull_err.close()
        except Exception:
            pass
```

---

### Bug #19: TrOCR device tracking dict not atomic ✅

**File:** `app/services/signature_ocr.py`, line ~62  
**Problem:** `trocr['device']` update and model `.to()` call aren't atomic — concurrent reads can see stale device.

**Fix:** Same approach as Bug #13. Read device from model parameters, not dict:
```python
device = next(model.parameters()).device
```
And ensure `trocr['device']` is updated right after `.to()` call in the finally block.

---

### Bug #20: `get_table_engine()` not thread-safe ✅

**File:** `app/services/table_extraction.py`, line ~67  
**Problem:** No lock → double initialization possible under concurrent requests.

**Fix:** Add double-checked locking:
```python
import threading
_table_engine_lock = threading.Lock()

def get_table_engine():
    global _table_engine, _is_v3
    if _table_engine is not None:
        return _table_engine
    with _table_engine_lock:
        if _table_engine is not None:
            return _table_engine
        # ... existing initialization code unchanged ...
```

---

### Bug #21: `signature_validation.py` bypasses `ensure_llama_loaded()` ✅

**File:** `app/services/signature_validation.py`, lines ~48-52  
**Problem:** Accesses `models.get('llama')` directly + calls `load_llama_model()` instead of `ensure_llama_loaded()` which does thread-safe double-checked locking.  
**Note:** `ocr_validation.py` already uses `ensure_llama_loaded()` correctly (lines 190, 241) — only `signature_validation.py` needs this fix.

**Current:**
```python
llama = models.get('llama')
if llama is None:
    from app.models.loader import load_llama_model
    llama = load_llama_model()
    models['llama'] = llama
```

**Fix:**
```python
from app.models.loader import ensure_llama_loaded
llama = ensure_llama_loaded()
```

---

### Bug #24: Async functions call sync LLaMA → blocks event loop 2-15s ✅

**Files:** 4 files, ~9 call sites  
**Problem:** `async def` functions call `llama(prompt, ...)` synchronously — HTTP POST to llamafile blocks event loop.

**Call sites:**
| File | Lines | Function |
|------|-------|----------|
| `app/utils/extraction.py` | 457, 815, 923 | `extract_structured_data`, `extract_entities`, `extract_with_prompt` |
| `app/services/signature_validation.py` | 94, 177, 265 | `validate_signature_text`, `extract_names_from_document`, `validate_signature_authenticity` |
| `app/services/ocr_validation.py` | ~213, ~289 | `validate_ocr_quality` (REVIEW + FULL tiers) |
| `app/core/classifier.py` | ~501 | `classify_with_reasoning` |

**Fix pattern for each call:**
```python
# Before:
response = llama(prompt, max_tokens=..., temperature=...)

# After:
import asyncio
response = await asyncio.to_thread(
    llama, prompt, max_tokens=..., temperature=...
)
```

---

## PHASE 4 — LOW (6 bugs, 2 files)

> Cosmetic issues, minor code quality.

### Bug #7: `page_count: 1` hardcoded when splitting disabled ✅

**File:** `app/core/pipeline.py`, line ~287  
**Fix:** Fully covered by Bug #4 fix (same code block).

---

### Bug #22: Overlapping confidence check logic ✅

**File:** `app/core/classifier.py`  
**Impact:** Cosmetic — unreachable code paths, confusing logic. No separate fix needed; Bug #14 restructure cleans this up.

---

### Bug #25: Hardcoded `0.15` threshold (2 locations) ✅

**File:** `app/core/classifier.py`, lines ~530 and ~548  
**Fix:** Fully covered by Bug #14 fix — both locations changed to use `low_confidence_threshold` from config + `original_confidence` instead of mutated `confidence`.

---

### Bug #26: `ocr_confidence` missing (overlaps Bug #5) ✅

**Fix:** Fully covered by Bug #5 fix.

---

### Bug #27: `'images' in dir()` should be `'images' in locals()` ✅

**File:** `app/core/pipeline.py`, line ~890  
**Current:** `if 'images' in dir() and images is not None:`  
**Fix:** `if 'images' in locals() and images is not None:`

---

### Bug #28: `cleanup_temp_files` may fail with unbound variable ✅

**File:** `app/core/pipeline.py`, line ~901  
**Current:** `cleanup_temp_files(str(original_doc_id) if 'original_doc_id' in dir() else str(doc_id))`  
**Fix:** `cleanup_temp_files(str(original_doc_id) if 'original_doc_id' in locals() else str(doc_id))`

---

## Files Changed Per Phase

| File | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Bug IDs |
|------|---------|---------|---------|---------|---------|
| `app/services/region_router.py` | ✏️ | ✏️ | | | #1A, #3, #13 |
| `app/services/signature_ocr.py` | ✏️ | | ✏️ | | #2, #19 |
| `app/api/endpoints.py` | ✏️ | | | | #1B, #1C, #1D, #9, #10, #15, #16 |
| `app/core/pipeline.py` | | ✏️ | ✏️ | ✏️ | #4, #5, #6, #7, #8, #12, #17, #23, #26, #27, #28 |
| `app/services/ocr_validation.py` | | ✏️ | ✏️ | | #11, #24 |
| `app/core/classifier.py` | | ✏️ | ✏️ | | #14, #22, #24, #25 |
| `app/models/loader.py` | | | ✏️ | | #18 |
| `app/services/table_extraction.py` | | | ✏️ | | #20 |
| `app/services/signature_validation.py` | | | ✏️ | | #21, #24 |
| `app/utils/extraction.py` | | | ✏️ | | #24 |

---

## Verification Plan

After each phase:
1. Run import check: `from app.api.endpoints import app` → verify 41 routes
2. Run `get_errors` on all modified files
3. Grep for remaining `models.get('ocr')` (should be 0 after Phase 1)

After all phases:
1. Start server: `python main.py`
2. Test `/health` endpoint
3. Test `/ocr/extract` with a sample image
4. Test full pipeline with a sample PDF
5. Check MongoDB document has `layout_regions` and `stamp_detected` fields
