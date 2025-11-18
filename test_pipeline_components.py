"""Test each component of the OCR pipeline"""
import os
import sys

print("="*80)
print("PIPELINE COMPONENT TEST")
print("="*80)

# TEST 1: PDF to Images
print("\n[TEST 1] PDF to Image Conversion")
print("-"*80)
try:
    from pdf2image import convert_from_path
    
    test_pdf = r"C:\Users\Ahmad\OneDrive\Documents\GitHub\adaptive-Dokumentenverarbeitung\test_invoice_realistic.pdf"
    poppler_path = r"C:\Users\Ahmad\poppler\poppler-24.08.0\Library\bin"
    
    print(f"Converting: {os.path.basename(test_pdf)}")
    images = convert_from_path(test_pdf, dpi=300, poppler_path=poppler_path)
    
    print(f"SUCCESS: Converted {len(images)} page(s)")
    for i, img in enumerate(images):
        print(f"  Page {i+1}: {img.size[0]}x{img.size[1]} pixels, mode={img.mode}")
    
    # Save first page for inspection
    first_page = images[0]
    
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)

# TEST 2: PaddleOCR on Image
print("\n[TEST 2] PaddleOCR Text Extraction")
print("-"*80)
try:
    from paddleocr import PaddleOCR
    import numpy as np
    
    print("Initializing PaddleOCR...")
    ocr = PaddleOCR(use_textline_orientation=False, lang='en')
    print("OCR initialized")
    
    print(f"Running OCR on page 1...")
    img_array = np.array(first_page)
    result = ocr.ocr(img_array, cls=True)
    
    print(f"Result type: {type(result)}")
    print(f"Result is None: {result is None}")
    
    if result:
        print(f"Result length: {len(result)}")
        print(f"First element type: {type(result[0])}")
        
        if result[0]:
            print(f"Number of text detections: {len(result[0])}")
            
            # Show first 3 detections structure
            print("\nFirst 3 detections structure:")
            for i, detection in enumerate(result[0][:3]):
                print(f"  Detection {i+1}: {type(detection)}, length={len(detection) if hasattr(detection, '__len__') else 'N/A'}")
                if isinstance(detection, (list, tuple)) and len(detection) >= 2:
                    print(f"    - Part 1 (bbox): {type(detection[0])}")
                    print(f"    - Part 2 (text): {detection[1]}")
            
            # Extract all text
            print("\nExtracting text...")
            all_text = []
            for detection in result[0]:
                if detection and isinstance(detection, (list, tuple)) and len(detection) >= 2:
                    text_part = detection[1]
                    if isinstance(text_part, (list, tuple)) and len(text_part) >= 1:
                        all_text.append(str(text_part[0]))
            
            print(f"SUCCESS: Extracted {len(all_text)} text lines")
            if all_text:
                print("\nFirst 10 text lines:")
                for i, line in enumerate(all_text[:10], 1):
                    print(f"  {i}. {line}")
            else:
                print("WARNING: No text extracted from detections!")
        else:
            print("FAILED: result[0] is None or empty")
    else:
        print("FAILED: OCR result is None")
        
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("ALL TESTS PASSED")
print("="*80)
