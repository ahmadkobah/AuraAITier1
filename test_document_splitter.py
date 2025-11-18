"""Direct test of document_splitter functions"""
import sys
sys.path.insert(0, '.')

from app.document_splitter import pdf_to_images, extract_text_from_image
from paddleocr import PaddleOCR

print("="*80)
print("TESTING DOCUMENT_SPLITTER FUNCTIONS")
print("="*80)

# Test PDF to images
print("\n[1] Testing pdf_to_images()...")
pdf_path = "test_invoice_realistic.pdf"
try:
    images = pdf_to_images(pdf_path)
    print(f"SUCCESS: Got {len(images)} images")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)

# Test extract_text_from_image
print("\n[2] Testing extract_text_from_image()...")
try:
    print("Initializing PaddleOCR...")
    ocr = PaddleOCR(use_textline_orientation=False, lang='en')
    print("OCR ready")
    
    print("Extracting text from first page...")
    text = extract_text_from_image(images[0], ocr)
    
    print(f"\nRESULT:")
    print(f"Text length: {len(text)} characters")
    
    if len(text) > 0:
        print(f"\nSUCCESS! Extracted text:")
        print("-"*80)
        print(text[:1000])  # First 1000 chars
        if len(text) > 1000:
            print(f"\n... ({len(text)-1000} more characters)")
    else:
        print("FAILED: No text extracted!")
        
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
