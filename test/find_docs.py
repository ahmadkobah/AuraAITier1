"""Find the most recent document"""
from pymongo import MongoClient
from datetime import datetime

client = MongoClient('mongodb+srv://ahmadfredkobah_db_user:Myface-112233@aura.69ykelf.mongodb.net/projectena?retryWrites=true&w=majority&appName=Aura')
db = client['projectena']

print("Finding most recent documents...")
docs = db['documents'].find({}).sort('created_at', -1).limit(5)

for doc in docs:
    print("\n" + "=" * 60)
    print(f"ID: {doc.get('_id')}")
    print(f"Filename: {doc.get('original_filename', doc.get('filename', 'N/A'))}")
    print(f"Status: {doc.get('status')}")
    print(f"Created: {doc.get('created_at')}")
    print(f"PDF Path: {doc.get('pdf_path', doc.get('filePath', 'N/A'))}")
    if doc.get('error'):
        print(f"Error: {doc.get('error')}")
    if doc.get('processed_data'):
        print(f"Processed docs: {len(doc['processed_data'])}")
        if len(doc['processed_data']) > 0:
            text_len = len(doc['processed_data'][0].get('text', ''))
            print(f"First doc text length: {text_len} chars")

client.close()
