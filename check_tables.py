"""Check if tables are being extracted and saved to MongoDB"""
from pymongo import MongoClient
import json

# MongoDB Atlas connection
MONGO_URL = "mongodb+srv://ahmadfredkobah_db_user:Myface-112233@aura.69ykelf.mongodb.net/aura?retryWrites=true&w=majority&appName=Aura"
client = MongoClient(MONGO_URL)

# Check aura database (where AI data should be)
db = client['aura']
print("Collections in aura:", db.list_collection_names())

# Check documents collection
docs_col = db['documents']
print("\nDocument counts by status:")
for status in ['COMPLETE', 'PROCESSING', 'QUEUED', 'FAILED', 'complete', 'processing', 'completed']:
    count = docs_col.count_documents({'status': status})
    if count > 0:
        print(f"  {status}: {count}")

# Get any recent document with processed_data
print("\nMost recent document with processed_data:")
doc = docs_col.find_one({'processed_data': {'$exists': True, '$ne': []}}, sort=[('processing_completed', -1)])
if doc:
    print(f"  ID: {doc.get('_id')}")
    print(f"  Status: {doc.get('status')}")
    print(f"  Filename: {doc.get('original_filename', 'Unknown')}")
    processed = doc.get('processed_data', [])
    print(f"  Processed pages: {len(processed)}")
    if processed:
        for i, p in enumerate(processed[:2]):
            tables = p.get('tables', [])
            print(f"  Page {i+1}:")
            print(f"    - tables array: {len(tables)}")
            print(f"    - table_count: {p.get('table_count', 0)}")
            print(f"    - has text: {bool(p.get('text') or p.get('full_text'))}")
            if tables:
                for t in tables:
                    print(f"    - Table: rows={len(t.get('rows', []))}, source={t.get('source')}")
else:
    print("  No documents with processed_data found")
    
    # Try finding any document
    any_doc = docs_col.find_one()
    if any_doc:
        print(f"\n  Sample document keys: {list(any_doc.keys())[:10]}")

if doc:
    print(f"Document ID: {doc.get('_id')}")
    print(f"Status: {doc.get('status')}")
    print(f"Filename: {doc.get('original_filename', 'Unknown')}")
    print()
    
    # Check processed_data for tables
    processed = doc.get('processed_data', [])
    print(f"Total pages processed: {len(processed)}")
    print()
    
    for i, page in enumerate(processed):
        print(f"Page {i+1}:")
        tables = page.get('tables', [])
        table_count = page.get('table_count', 0)
        print(f"  - table_count field: {table_count}")
        print(f"  - tables array length: {len(tables)}")
        
        if tables:
            for j, t in enumerate(tables):
                print(f"    Table {j+1}:")
                print(f"      - structure: {t.get('structure')}")
                print(f"      - rows count: {len(t.get('rows', []))}")
                print(f"      - source: {t.get('source', 'unknown')}")
                print(f"      - llama_validated: {t.get('llama_validated', False)}")
                if t.get('rows'):
                    print(f"      - first row: {t['rows'][0][:3]}...")  # First 3 cells
        else:
            print("  - No tables extracted")
        print()
else:
    print("No completed documents found")
