"""
Direct debug script - test table and signature extraction step by step
"""
import os
import sys
import numpy as np
from PIL import Image
from pdf2image import convert_from_path

# Add app path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test PDF - using a real document with signature from desktop
pdf_path = r"C:\Users\Ahmad\OneDrive\Mein PC\invoice_with_signature.pdf"
poppler_path = r"C:\Users\Ahmad\poppler\poppler-24.08.0\Library\bin"

print("=" * 60)
print("STEP 1: Convert PDF to images")
print("=" * 60)
images = convert_from_path(pdf_path, dpi=200, poppler_path=poppler_path)
print(f"  Converted {len(images)} pages")
img = images[0]
img_np = np.array(img.convert('RGB'))
print(f"  Image shape: {img_np.shape}")

print("\n" + "=" * 60)
print("STEP 2: Initialize PPStructureV3")
print("=" * 60)
from paddleocr import PPStructureV3
engine = PPStructureV3(lang='en')
print("  PPStructureV3 initialized")

print("\n" + "=" * 60)
print("STEP 3: Run PPStructureV3.predict() with HTML generation")
print("=" * 60)
for result in engine.predict(
    img_np,
    use_table_recognition=True,
    use_wired_table_cells_trans_to_html=True,
    use_wireless_table_cells_trans_to_html=True
):
    print(f"  Result type: {type(result).__name__}")
    print(f"  Result keys: {list(result.keys())}")
    
    # Table results
    table_res = result.get('table_res_list', [])
    print(f"\n  table_res_list: {len(table_res)} tables")
    
    for i, table in enumerate(table_res):
        print(f"\n    Table {i}:")
        print(f"      Keys: {list(table.keys())}")
        
        # Check for HTML - PPStructureV3 uses 'pred_html' not 'html'
        html = table.get('html', '')
        pred_html = table.get('pred_html', '')
        
        print(f"      'html' field: {len(html)} chars")
        print(f"      'pred_html' field: {len(pred_html)} chars")
        
        # Show the HTML that exists
        actual_html = pred_html or html
        if actual_html:
            print(f"      HTML preview (first 500 chars):")
            print(f"      {actual_html[:500]}")
        else:
            print(f"      NO HTML FOUND - listing all fields:")
            for k, v in table.items():
                v_str = str(v)[:200]
                print(f"        {k}: {v_str}...")

    # Check for seal/stamp detection (might catch signatures)
    seal_res = result.get('seal_res_list', [])
    print(f"\n  seal_res_list: {len(seal_res)} seals/stamps")
    for i, seal in enumerate(seal_res):
        print(f"    Seal {i}: {seal}")
    
    # Check layout detection for signature-like regions
    layout = result.get('layout_det_res', {})
    if layout:
        boxes = layout.get('boxes', [])
        print(f"\n  layout_det_res: {len(boxes)} detected regions")
        for i, box in enumerate(boxes):
            label = box.get('label', 'unknown')
            score = box.get('score', 0)
            coord = box.get('coordinate', box.get('bbox', []))
            print(f"    Region {i}: {label} (score={score:.2f}) at {coord[:4] if len(coord)>=4 else coord}")

print("\n" + "=" * 60)
print("STEP 4: Check OCR Text for Signature Patterns")
print("=" * 60)

# Get the OCR text from the result
overall_ocr = result.get('overall_ocr_res', {})
if overall_ocr:
    rec_texts = overall_ocr.get('rec_texts', [])
    full_text = ' '.join(rec_texts)
    print(f"  OCR extracted {len(rec_texts)} text regions")
    print(f"  Full text preview (first 1000 chars):")
    print(f"  {full_text[:1000]}...")
    
    # Test the signature regex patterns
    import re
    sig_patterns = [
        r'(?:Authorized\s+)?Signature[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        r'Signed\s*(?:by)?[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        r'Name[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:\s+Terms|\s+Payment|\s*$)',
        r'(?:Invoice\s+)?Total\s+([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)\s+Terms',
    ]
    
    print(f"\n  Testing signature patterns against OCR text:")
    for i, pattern in enumerate(sig_patterns):
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            print(f"    Pattern {i+1} MATCHED: '{match.group(0)}'")
            print(f"    Captured group: '{match.group(1)}'")
        else:
            print(f"    Pattern {i+1}: No match")
else:
    print("  No OCR results found")

print("\n" + "=" * 60)
print("STEP 5: Test Signature Detection with YOLO")
print("=" * 60)

# Import signature detection
from app.services.signature_detection import detect_signature_boxes, crop_signature_region
from app.models.loader import get_models, load_all_models

# Load models
print("\n  Loading AI models...")
load_all_models()
models = get_models()
print(f"  Models loaded: {list(models.keys())}")

# Convert numpy to PIL for signature detection
pil_img = Image.fromarray(img_np)

# Test YOLO-based detection
print("\n  Testing YOLO-based signature detection:")
try:
    boxes = detect_signature_boxes(pil_img, models, return_images=True)
    print(f"    Found {len(boxes)} signature boxes")
    for i, box in enumerate(boxes):
        print(f"    Box {i}:")
        print(f"      Confidence: {box.get('confidence')}")
        print(f"      Bbox: {box.get('box')}")
        print(f"      Has image: {'Yes' if box.get('image') else 'No'}")
        if box.get('image'):
            print(f"      Image preview (first 100 chars): {box.get('image')[:100]}...")
except Exception as e:
    print(f"    Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("DEBUG COMPLETE")
print("=" * 60)
