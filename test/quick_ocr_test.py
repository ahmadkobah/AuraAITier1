"""Quick OCR test on the uploaded invoice PDF"""
import sys
from pdf2image import convert_from_path
from paddleocr import PaddleOCR
import numpy as np

# PDF file path
pdf_path = r"C:\Users\Ahmad\OneDrive\Documents\GitHub\adaptive-Dokumentenverarbeitung\uploads\cdffbc4d-c781-4ee2-9678-a71570016186_1763334470151-301190344.pdf"

print(f"Testing OCR on: {pdf_path}")
print("-" * 80)

# Convert PDF to image
print("\n1. Converting PDF to image...")
try:
    images = convert_from_path(pdf_path, dpi=300)
    print(f"   SUCCESS: Got {len(images)} page(s)")
    if images:
        img = images[0]
        print(f"   Image size: {img.size} (width x height)")
        print(f"   Image mode: {img.mode}")
except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# Initialize PaddleOCR
print("\n2. Initializing PaddleOCR...")
try:
    ocr = PaddleOCR(use_textline_orientation=False, lang='en')
    print("   SUCCESS: PaddleOCR ready")
except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# Run OCR
print("\n3. Running OCR on the image...")
try:
    img_array = np.array(img)
    result = ocr.ocr(img_array, cls=True)
    print("   SUCCESS: OCR completed")
    
    print(f"\n4. OCR Result Analysis:")
    print(f"   Result type: {type(result)}")
    print(f"   Result is None: {result is None}")
    
    if result:
        print(f"   Result length: {len(result)}")
        print(f"   First element type: {type(result[0])}")
        print(f"   First element is None: {result[0] is None}")
        
        if result[0]:
            print(f"   First element length: {len(result[0])}")
            
            # Show first few detections
            print("\n5. First 3 text detections:")
            for i, line in enumerate(result[0][:3]):
                print(f"   Detection {i+1}:")
                print(f"      Type: {type(line)}")
                print(f"      Content: {line}")
            
            # Try to extract text
            print("\n6. Extracting all text:")
            all_text = []
            for line in result[0]:
                if line and isinstance(line, (list, tuple)) and len(line) >= 2:
                    text_part = line[1]
                    if isinstance(text_part, (list, tuple)) and len(text_part) >= 1:
                        all_text.append(str(text_part[0]))
            
            print(f"   Extracted {len(all_text)} text lines")
            if all_text:
                print("\n   Full extracted text:")
                print("   " + "-" * 76)
                for line in all_text[:20]:  # First 20 lines
                    print(f"   {line}")
                if len(all_text) > 20:
                    print(f"   ... and {len(all_text) - 20} more lines")
            else:
                print("   NO TEXT EXTRACTED!")
        else:
            print("   WARNING: result[0] is None or empty")
    else:
        print("   WARNING: result is None or empty")
        
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("Test complete")
