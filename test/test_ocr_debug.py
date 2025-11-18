"""
Debug OCR Issue - Test actual invoice processing
"""
from pymongo import MongoClient
import json

# Connect to MongoDB
client = MongoClient('mongodb+srv://ahmadfredkobah_db_user:Myface-112233@aura.69ykelf.mongodb.net/projectena?retryWrites=true&w=majority&appName=Aura')
db = client['projectena']

# Find the most recent document
doc = db['documents'].find_one(
    {'_id': 'cdffbc4d-c781-4ee2-9678-a71570016186'}
)

if doc:
    print("=" * 60)
    print("DOCUMENT FOUND IN MONGODB")
    print("=" * 60)
    print(f"Document ID: {doc.get('_id')}")
    print(f"Status: {doc.get('status')}")
    print(f"Original Filename: {doc.get('original_filename')}")
    print(f"PDF Path: {doc.get('pdf_path')}")
    print(f"Error: {doc.get('error')}")
    print(f"Processing Started: {doc.get('processing_started')}")
    print(f"Processing Completed: {doc.get('processing_completed')}")
    print(f"\nProcessed Data:")
    print(f"  Documents found: {len(doc.get('processed_data', []))}")
    
    if doc.get('processed_data'):
        for idx, processed_doc in enumerate(doc['processed_data']):
            print(f"\n  Document {idx + 1}:")
            print(f"    Page range: {processed_doc.get('page_range')}")
            print(f"    Classification: {processed_doc.get('classification')}")
            text = processed_doc.get('text', '')
            print(f"    Text length: {len(text)} characters")
            print(f"    Text preview: {text[:300]}")
            print(f"    Summary: {processed_doc.get('summary', '')[:200]}")
    
    # Test if PDF file exists
    import os
    pdf_path = doc.get('pdf_path')
    if pdf_path and os.path.exists(pdf_path):
        print(f"\nPDF file exists: {pdf_path}")
        print(f"   File size: {os.path.getsize(pdf_path)} bytes")
        
        # Now test OCR on this file
        print("\n" + "=" * 60)
        print("TESTING OCR ON THIS FILE")
        print("=" * 60)
        
        from pdf2image import convert_from_path
        from paddleocr import PaddleOCR
        import numpy as np
        
        print("Converting PDF to image...")
        images = convert_from_path(pdf_path, dpi=300)
        print(f"Converted {len(images)} pages to images")
        
        print("\nInitializing PaddleOCR...")
        ocr = PaddleOCR(use_angle_cls=True, lang='en')
        print("PaddleOCR initialized")
        
        print("\nProcessing first page...")
        image_array = np.array(images[0])
        print(f"Image shape: {image_array.shape}")
        
        result = ocr.ocr(image_array, cls=True)
        print(f"\nOCR Result type: {type(result)}")
        print(f"OCR Result length: {len(result) if result else 0}")
        
        if result and len(result) > 0:
            print(f"First element type: {type(result[0])}")
            print(f"First element length: {len(result[0]) if result[0] else 0}")
            
            if result[0]:
                print(f"\nFirst line structure: {type(result[0][0]) if len(result[0]) > 0 else 'empty'}")
                if len(result[0]) > 0 and result[0][0]:
                    print(f"First line content: {result[0][0]}")
                
                # Try to extract text
                text_lines = []
                for line in result[0]:
                    if line and isinstance(line, (list, tuple)) and len(line) >= 2:
                        text_part = line[1]
                        if isinstance(text_part, (list, tuple)) and len(text_part) >= 1:
                            text_lines.append(str(text_part[0]))
                
                extracted_text = " ".join(text_lines)
                print(f"\nExtracted {len(text_lines)} lines")
                print(f"Total text length: {len(extracted_text)} characters")
                print(f"Text preview:\n{extracted_text[:500]}")
        else:
            print("❌ No OCR results returned!")
    else:
        print(f"\n❌ PDF file NOT found: {pdf_path}")
else:
    print("❌ No document found with filename containing 'invoice_10248'")

client.close()
