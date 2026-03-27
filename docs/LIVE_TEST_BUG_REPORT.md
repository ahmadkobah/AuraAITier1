# Live Test Bug Report — 7 Pipeline Bugs

**Date:** 2025-03-15  
**Test Document:** `1773544847592-230491663.pdf`  
**Result:** 220s processing time, garbage output  
**Root Cause:** 7 compounding bugs — each one degrades output further down the pipeline

---

## Summary

After deploying the 8-class YOLO model and applying 37 prior fixes (28 pipeline bugs + 2 bonus + 6 LLaMA/GPU + 1 colorama), a live document test revealed 7 remaining bugs that cascade together to produce unusable output:

1. Region OCR crashes silently → no enriched text for downstream steps
2. JSON parsing grabs wrong brace → entity extraction falls to weak regex fallback
3. Table extraction times out → zero table data

---

## Verified Bug List

### Priority 1 — Critical (pipeline crash / silent failure)

#### Bug #1: `cls=True` in region_router.py

- **File:** `app/services/region_router.py` line 51
- **Code:** `result = ocr.ocr(crop_img, cls=True)`
- **Problem:** PP-OCRv5 does not accept `cls` as a keyword argument to `.ocr()`. The text classifier is now configured at init time via `use_textline_orientation=True` (already set in `loader.py` line 326). This call raises `TypeError`, which is caught in `layout_detection.py` line 142 and logged as a warning. The pipeline falls back to raw YOLO detections **without OCR text**, severely degrading all downstream extraction.
- **Impact:** Every page loses its region-level OCR text. Entity extraction and classification receive lower-quality input.
- **Fix:** Remove `cls=True` → `result = ocr.ocr(crop_img)`

#### Bug #2: `cls=True` in endpoints.py (NEW — missed in first analysis)

- **File:** `app/api/endpoints.py` line 2069
- **Code:** `result = ocr_model.ocr(img_array, cls=True)`
- **Problem:** Same PP-OCRv5 incompatibility as Bug #1, but in the `/api/ocr` endpoint. **No try/except wrapper.** This crashes the OCR API endpoint entirely.
- **Impact:** Direct API calls to `/api/ocr` return 500 errors.
- **Fix:** Wrap in `try/except TypeError` fallback (same pattern as `classifier.py` line 74 which already handles this correctly).

> **Note:** `classifier.py` line 74 has the same `cls=True` call but already wraps it in `try/except TypeError` — no fix needed there.

---

### Priority 2 — High (garbage output from malformed JSON)

#### Bug #3: `rfind('}')` in extraction.py

- **File:** `app/utils/extraction.py` line 529
- **Code:**
  ```python
  json_end = cleaned.rfind('}') + 1
  parsed = json.loads(cleaned[json_start:json_end])
  ```
- **Problem:** `rfind('}')` finds the **last** closing brace in the entire LLaMA output. When LLaMA appends explanatory text after the JSON (e.g., `"Note: I extracted the fields from..."` which may contain `}`), the slice includes trailing garbage. `json.loads()` fails → falls through to the manual regex fallback which only extracts 30-50% of fields.
- **Impact:** Entity extraction returns partial/missing fields even when LLaMA produced valid JSON.
- **Fix:** Replace `rfind('}')` with balanced brace matching — count `{`/`}` depth starting from the first `{` to find the correct closing brace.

#### Bug #4: `rfind('}')` in table_extraction.py (validate)

- **File:** `app/services/table_extraction.py` line 373
- **Code:**
  ```python
  json_end = llama_output.rfind('}') + 1
  validation = json.loads(llama_output[json_start:json_end])
  ```
- **Problem:** Same pattern as Bug #3, in `validate_table_with_llama()`. When LLaMA appends text after the JSON validation result, the slice is corrupted. `json.loads()` throws `JSONDecodeError` → logged as `"LLaMA table validation: Extra data: line 185 column 1 (char 2990)"` → entire validation skipped.
- **Impact:** Tables that PPStructure extracted correctly are not validated/enhanced by LLaMA.
- **Fix:** Same balanced brace matching as Bug #3.

#### Bug #5: `rfind('}')` in table_extraction.py (extract) — NEW

- **File:** `app/services/table_extraction.py` line 651
- **Code:**
  ```python
  json_end = llama_output.rfind('}') + 1
  parsed = json.loads(llama_output[json_start:json_end])
  ```
- **Problem:** Third instance of the same `rfind` bug, in `extract_tables_from_text_with_llama()`. Same failure mode — LLaMA trailing text corrupts the JSON slice.
- **Impact:** Text-based table extraction (the fallback when PPStructure finds no visual tables) also fails to parse LLaMA output.
- **Fix:** Same balanced brace matching as Bugs #3 and #4.

---

### Priority 3 — Medium (timeout values too aggressive)

#### Bug #6: PPStructure table extraction timeout (90s)

- **File:** `app/core/pipeline.py` line 752
- **Code:**
  ```python
  page_tables = await asyncio.wait_for(
      extract_tables_from_pdf_pages(page_images),
      timeout=90.0
  )
  ```
- **Problem:** PPStructure takes ~20-30 seconds per page for table detection. With LLaMA validation adding ~10 seconds per table, a 3-page document with tables easily exceeds 90 seconds. The test document hit this timeout.
- **Impact:** All visual table data is discarded. Pipeline falls back to text-based extraction (which also times out — see Bug #7).
- **Fix:** Increase timeout to **180s** (covers 3-4 page documents comfortably on RTX 3060).

#### Bug #7: Text-based table extraction timeout (30s)

- **File:** `app/core/pipeline.py` line 776
- **Code:**
  ```python
  text_tables = await asyncio.wait_for(
      extract_tables_from_text_with_llama(doc_text, models),
      timeout=30.0
  )
  ```
- **Problem:** LLaMA 3.2 3B on RTX 3060 needs ~20-32 seconds to analyze text and produce table JSON. The 30-second timeout is at the lower edge, causing frequent timeouts. The test document hit this timeout.
- **Impact:** Zero table data in final output — neither visual nor text-based tables are returned.
- **Fix:** Increase timeout to **60s** (gives LLaMA 3B a comfortable margin).

---

## Cascading Effect

These 7 bugs fire in sequence during pipeline execution, each one compounding the damage:

```
Bug #1 fires → Region OCR crashes silently
  → Pipeline uses raw YOLO detections WITHOUT OCR text
    → Entity extraction receives lower-quality input text
      → Bug #3 fires → LLaMA JSON parsing fails
        → Regex fallback extracts only 30-50% of fields
          → Bug #6 fires → PPStructure table extraction times out
            → Bug #4 fires → Table validation JSON parsing also broken
              → Bug #7 fires → Text-based table fallback times out
                → Bug #5 fires → Text table JSON parsing also broken
                  → RESULT: Partial entities + zero tables = "garbage output"
```

---

## Recommended Fix Plan

### Batch 1 — Remove `cls=True` (Bugs #1, #2)

**Files:** `region_router.py`, `endpoints.py`  
**Effort:** Minimal — 2 line changes  
**Risk:** None — `cls` functionality is already configured at PaddleOCR init time  
**Expected impact:** Dramatically improves output quality because region OCR text feeds into all downstream steps

### Batch 2 — Fix JSON parsing with balanced brace matching (Bugs #3, #4, #5)

**Files:** `extraction.py`, `table_extraction.py` (2 locations)  
**Effort:** Small — create a shared `find_matching_brace()` helper, replace 3 `rfind` calls  
**Risk:** Low — only changes the JSON extraction boundary, all other logic unchanged  
**Expected impact:** Entity extraction and table validation will parse LLaMA output correctly instead of falling to weak fallbacks

### Batch 3 — Increase timeouts (Bugs #6, #7)

**Files:** `pipeline.py` (2 locations)  
**Effort:** Minimal — 2 number changes  
**Risk:** None — only increases allowed processing time, doesn't change behavior  
**Expected impact:** Table extraction will complete instead of being killed prematurely

---

## Reference

- **Prior fixes:** See `PIPELINE_BUG_AUDIT.md` (28 bugs), `DEEP_AUDIT_REPORT.md` (6 LLaMA/GPU fixes)
- **YOLO model:** 8-class, 50 epochs, mAP@50: 0.925, deployed to `models/yolo/document_layout.pt`
- **Test environment:** Python 3.13, RTX 3060, LLaMA 3.2 3B (llamafile), PaddleOCR PP-OCRv5
