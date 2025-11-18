"""Test if pdf2image can find Poppler in the AI service environment"""
import os
import sys

print("=" * 80)
print("POPPLER ENVIRONMENT TEST")
print("=" * 80)

# Check PATH
print("\n1. Checking PATH environment variable:")
path_dirs = os.environ.get('PATH', '').split(os.pathsep)
poppler_found = False
for path_dir in path_dirs:
    if 'poppler' in path_dir.lower():
        print(f"   ✓ Found: {path_dir}")
        poppler_found = True

if not poppler_found:
    print("   ❌ No Poppler directory in PATH!")
else:
    print("   ✅ Poppler is in PATH")

# Check if pdftoppm is accessible
print("\n2. Testing pdftoppm executable:")
import subprocess
try:
    result = subprocess.run(['pdftoppm', '-v'], capture_output=True, text=True, timeout=5)
    print(f"   ✓ pdftoppm found: {result.stderr.strip()}")
except FileNotFoundError:
    print("   ❌ pdftoppm not found! Poppler not accessible.")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test pdf2image
print("\n3. Testing pdf2image with test PDF:")
try:
    from pdf2image import convert_from_path
    
    test_pdf = r"C:\Users\Ahmad\OneDrive\Documents\GitHub\adaptive-Dokumentenverarbeitung\test_invoice_realistic.pdf"
    
    if not os.path.exists(test_pdf):
        print(f"   ❌ Test PDF not found: {test_pdf}")
    else:
        print(f"   Converting: {test_pdf}")
        
        # Try with explicit poppler path
        poppler_path = r"C:\Users\Ahmad\poppler\poppler-24.08.0\Library\bin"
        
        print(f"   Using poppler_path: {poppler_path}")
        images = convert_from_path(test_pdf, dpi=300, poppler_path=poppler_path)
        
        print(f"   ✅ SUCCESS! Converted {len(images)} page(s)")
        print(f"   First page size: {images[0].size}")
        
except Exception as e:
    print(f"   ❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
