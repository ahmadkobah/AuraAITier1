"""
Quick test to verify OCR service works with Hugging Face DeepSeek
"""
import requests
import base64
from pathlib import Path

# Create a simple test image with text
from PIL import Image, ImageDraw, ImageFont

# Create test image
img = Image.new('RGB', (800, 200), color='white')
d = ImageDraw.Draw(img)

# Use default font (works on all systems)
try:
    font = ImageFont.truetype("arial.ttf", 40)
except:
    font = ImageFont.load_default()

text = "PURCHASE ORDER #12345\nVendor: ABC Company\nBuyer: John Doe"
d.text((50, 50), text, fill='black', font=font)

# Save test image
test_img_path = Path("test_po.png")
img.save(test_img_path)

print(f"✅ Created test image: {test_img_path}")

# Read and encode image
with open(test_img_path, "rb") as f:
    image_data = f.read()

# Test OCR service
print("\n🔄 Testing OCR service...")
print("=" * 60)

try:
    # Upload to OCR service
    files = {"file": ("test_po.png", image_data, "image/png")}
    response = requests.post(
        "http://127.0.0.1:8000/ocr/process",
        files=files,
        timeout=60
    )
    
    if response.status_code == 200:
        result = response.json()
        print("✅ OCR SUCCESS!")
        print(f"\nExtracted Text:\n{result.get('text', 'N/A')}")
        print(f"\nEngine: {result.get('engine', 'N/A')}")
        print(f"Confidence: {result.get('confidence', 'N/A')}")
    else:
        print(f"❌ OCR FAILED: {response.status_code}")
        print(f"Error: {response.text}")
        
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)
