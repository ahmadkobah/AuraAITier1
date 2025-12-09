"""Test PPStructure directly on the test invoice"""
import os
import sys

# Add the app directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from paddleocr import PPStructureV3
from PIL import Image
from pdf2image import convert_from_path
import numpy as np

# Path to test PDF
pdf_path = os.path.join(os.path.dirname(__file__), "test_invoice_with_signature.pdf")
poppler_path = r"C:\Users\Ahmad\poppler\poppler-24.08.0\Library\bin"

print(f"Testing PPStructureV3 on: {pdf_path}")
print(f"File exists: {os.path.exists(pdf_path)}")

# Convert PDF to image
print("\nConverting PDF to image...")
images = convert_from_path(pdf_path, dpi=200, poppler_path=poppler_path)
print(f"Converted to {len(images)} images")

# Convert first page to numpy array
img = images[0]
img_np = np.array(img.convert('RGB'))
print(f"Image shape: {img_np.shape}")

# Initialize PPStructureV3
print("\nInitializing PPStructureV3...")
try:
    engine = PPStructureV3(
        lang='en'
    )
    print(f"PPStructureV3 initialized")
    
    # Run prediction
    print("\nRunning PPStructureV3.predict()...")
    for result in engine.predict(
        img_np,
        use_table_recognition=True,
        use_wired_table_cells_trans_to_html=True,
        use_wireless_table_cells_trans_to_html=True
    ):
        print(f"\nResult type: {type(result)}")
        if isinstance(result, dict):
            print(f"Result keys: {list(result.keys())}")
            
            # table_res_list
            table_res = result.get('table_res_list', [])
            print(f"\ntable_res_list count: {len(table_res)}")
            for i, t in enumerate(table_res):
                print(f"\n  Table {i}:")
                if isinstance(t, dict):
                    print(f"    Keys: {list(t.keys())}")
                    print(f"    bbox: {t.get('bbox')}")
                    html = t.get('html', '')
                    print(f"    html length: {len(html) if html else 0}")
                    if html:
                        print(f"    html preview: {html[:500]}...")
                    else:
                        print(f"    html: EMPTY - checking other fields...")
                        for k, v in t.items():
                            if k != 'bbox':
                                v_str = str(v)
                                print(f"    {k}: {type(v).__name__} = {v_str[:200]}{'...' if len(v_str) > 200 else ''}")
                else:
                    print(f"    Type: {type(t)}")
            
            # layout_det_res
            layout = result.get('layout_det_res', {})
            if layout:
                boxes = layout.get('boxes', [])
                print(f"\nlayout_det_res boxes: {len(boxes)}")
                table_boxes = [b for b in boxes if b.get('label', '').lower() == 'table']
                print(f"Table boxes: {len(table_boxes)}")
                for i, b in enumerate(table_boxes):
                    print(f"  Table box {i}: score={b.get('score')}, coord={b.get('coordinate', b.get('bbox'))}")
        else:
            print(f"Result: {result}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
