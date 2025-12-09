"""
Quick test to verify table extraction is working with the pred_html fix
"""
import asyncio
import os
import sys
import numpy as np
from PIL import Image
from pdf2image import convert_from_path

# Add app path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_table_extraction():
    # Test PDF
    pdf_path = r"C:\Users\Ahmad\OneDrive\Mein PC\invoice_with_signature.pdf"
    poppler_path = r"C:\Users\Ahmad\poppler\poppler-24.08.0\Library\bin"
    
    print("=" * 60)
    print("Testing Table Extraction with pred_html fix")
    print("=" * 60)
    
    # Convert PDF to images
    print("\n1. Converting PDF to images...")
    images = convert_from_path(pdf_path, dpi=200, poppler_path=poppler_path)
    print(f"   Converted {len(images)} pages")
    
    # Convert to numpy arrays
    page_images = [np.array(img.convert('RGB')) for img in images]
    print(f"   First page shape: {page_images[0].shape}")
    
    # Import and run table extraction
    print("\n2. Running extract_tables_from_pdf_pages...")
    from app.services.table_extraction import extract_tables_from_pdf_pages
    
    result = await extract_tables_from_pdf_pages(page_images, use_llama_validation=False)
    
    print(f"\n3. Results:")
    print(f"   Pages with tables: {len(result)}")
    
    for page_num, tables in result.items():
        print(f"\n   Page {page_num}: {len(tables)} tables")
        for i, table in enumerate(tables):
            html = table.get('html', '')
            rows = table.get('rows', [])
            structure = table.get('structure', {})
            print(f"     Table {i+1}:")
            print(f"       HTML: {len(html)} chars")
            print(f"       Rows: {len(rows)}")
            print(f"       Structure: {structure}")
            if html:
                print(f"       HTML preview: {html[:200]}...")
            if rows:
                print(f"       First row: {rows[0] if rows else 'N/A'}")

if __name__ == "__main__":
    asyncio.run(test_table_extraction())
