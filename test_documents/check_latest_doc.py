"""Check table and signature data in latest document"""
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from bson import ObjectId

load_dotenv()
client = MongoClient(os.getenv('MONGODB_URI'))
db = client['aura']

# Get latest document
docs = list(db['documents'].find().sort('processing_started', -1).limit(1))
if docs:
    doc = docs[0]
    print(f"Document: {doc.get('original_filename', 'Unknown')}")
    print(f"ID: {doc['_id']}")
    print(f"Status: {doc.get('status')}")
    
    if doc.get('processed_data'):
        pd = doc['processed_data'][0]
        print()
        print('=== TABLE DATA ===')
        tables = pd.get('tables', [])
        print(f"table_count field: {pd.get('table_count')}")
        print(f"tables array length: {len(tables)}")
        
        for i, t in enumerate(tables[:5]):
            print(f"\nTable {i+1}:")
            print(f"  source: {t.get('source')}")
            print(f"  html length: {len(t.get('html', ''))} chars")
            print(f"  rows: {len(t.get('rows', []))} rows")
            if t.get('rows'):
                first_row = t['rows'][0]
                print(f"  first row sample: {first_row[:3]}..." if len(first_row) > 3 else f"  first row: {first_row}")
            print(f"  structure: {t.get('structure')}")
            if t.get('html'):
                print(f"  html preview: {t['html'][:200]}...")
        
        print()
        print('=== SIGNATURE DATA ===')
        print(f"signature_detected: {pd.get('signature_detected')}")
        print(f"signature_confidence: {pd.get('signature_confidence')}")
        print(f"signature_text: {pd.get('signature_text')}")
        print(f"signature_box: {pd.get('signature_box')}")
        print(f"signature_boxes count: {len(pd.get('signature_boxes', []))}")
        sig_img = pd.get('signature_image')
        print(f"signature_image: {'YES (' + str(len(sig_img)) + ' chars)' if sig_img else 'NO'}")
else:
    print('No documents found')
