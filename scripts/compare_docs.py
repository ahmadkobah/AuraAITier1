import sys, json
sys.path.insert(0, '.')
from pymongo import MongoClient
from bson import ObjectId
from config.settings import MONGO_URL, DATABASE_NAME

client = MongoClient(MONGO_URL)
db = client[DATABASE_NAME]

# The _ids from the documents collection
cloud_id = ObjectId("69c58478b3af377d0714e428")
acme_id = ObjectId("69374541810e0e28feabbe19")

# Get full documents from documents collection
cloud_doc = db.documents.find_one({"_id": cloud_id})
acme_doc = db.documents.find_one({"_id": acme_id})

def safe_json(obj):
    """Convert MongoDB doc to JSON-safe dict"""
    if obj is None:
        return None
    d = dict(obj)
    d['_id'] = str(d['_id'])
    # Remove embedding arrays (huge)
    if 'embedding' in d:
        d['embedding'] = f"[{len(d['embedding'])} floats]" if isinstance(d['embedding'], list) else d['embedding']
    if 'aiResults' in d and isinstance(d['aiResults'], dict):
        for key in list(d['aiResults'].keys()):
            if key == 'embedding' and isinstance(d['aiResults'][key], list):
                d['aiResults'][key] = f"[{len(d['aiResults'][key])} floats]"
            if key == 'processed_data' and isinstance(d['aiResults'][key], list):
                for pd in d['aiResults'][key]:
                    if isinstance(pd, dict) and 'embedding' in pd:
                        pd['embedding'] = f"[{len(pd['embedding'])} floats]" if isinstance(pd['embedding'], list) else pd['embedding']
    return d

print("=" * 80)
print("CLOUD INVOICE (557717)")
print("=" * 80)
if cloud_doc:
    d = safe_json(cloud_doc)
    # Print key fields
    for key in ['_id', 'originalName', 'name', 'status', 'ocrStatus']:
        if key in d:
            print(f"  {key}: {d[key]}")
    
    ai = d.get('aiResults', {})
    if isinstance(ai, dict):
        print(f"\n  --- Classification ---")
        cls = ai.get('classification', {})
        print(f"    label: {cls.get('label')}, score: {cls.get('score')}, llama_override: {cls.get('llama_override')}")
        
        print(f"\n  --- Entities ---")
        ent = ai.get('entities', {})
        print(json.dumps(ent, indent=4, default=str))
        
        print(f"\n  --- Structured Data ---")
        sd = ai.get('structured_data', {})
        print(json.dumps(sd, indent=4, default=str))
        
        print(f"\n  --- Tables ---")
        tables = ai.get('tables', [])
        print(f"    table_count: {ai.get('table_count', len(tables))}")
        for i, t in enumerate(tables):
            print(f"    Table {i+1}: source={t.get('source')}, page={t.get('page')}")
            html = t.get('html', '')
            if html:
                # Print first 500 chars of HTML
                print(f"    HTML preview: {html[:500]}...")
        
        print(f"\n  --- Summary ---")
        print(f"    {ai.get('summary', 'N/A')}")
    else:
        print(f"  aiResults keys: {list(d.keys())}")
else:
    print("  NOT FOUND")

# Also check ai_documents collection
cloud_ai = db.ai_documents.find_one({"$or": [
    {"original_name": {"$regex": "557717"}},
    {"doc_id": {"$regex": "557717"}},
]})
if cloud_ai:
    print("\n  --- Also found in ai_documents ---")
    d = safe_json(cloud_ai)
    for key in ['_id', 'doc_id', 'original_name', 'status']:
        if key in d:
            print(f"    {key}: {d[key]}")

print()
print("=" * 80)
print("ACME INVOICE (INV-2025-001234)")
print("=" * 80)
if acme_doc:
    d = safe_json(acme_doc)
    for key in ['_id', 'originalName', 'name', 'status', 'ocrStatus']:
        if key in d:
            print(f"  {key}: {d[key]}")
    
    ai = d.get('aiResults', {})
    if isinstance(ai, dict):
        print(f"\n  --- Classification ---")
        cls = ai.get('classification', {})
        print(f"    label: {cls.get('label')}, score: {cls.get('score')}, llama_override: {cls.get('llama_override')}")
        
        print(f"\n  --- Entities ---")
        ent = ai.get('entities', {})
        print(json.dumps(ent, indent=4, default=str))
        
        print(f"\n  --- Structured Data ---")
        sd = ai.get('structured_data', {})
        print(json.dumps(sd, indent=4, default=str))
        
        print(f"\n  --- Tables ---")
        tables = ai.get('tables', [])
        print(f"    table_count: {ai.get('table_count', len(tables))}")
        for i, t in enumerate(tables):
            print(f"    Table {i+1}: source={t.get('source')}, page={t.get('page')}")
            html = t.get('html', '')
            if html:
                print(f"    HTML preview: {html[:500]}...")
        
        print(f"\n  --- Summary ---")
        print(f"    {ai.get('summary', 'N/A')}")
    else:
        print(f"  aiResults keys: {list(d.keys())}")
else:
    print("  NOT FOUND")

# Also check ai_documents collection
acme_ai = db.ai_documents.find_one({"$or": [
    {"original_name": {"$regex": "INV-2025-001234"}},
    {"doc_id": {"$regex": "INV-2025-001234"}},
]})
if acme_ai:
    print("\n  --- Also found in ai_documents ---")
    d = safe_json(acme_ai)
    for key in ['_id', 'doc_id', 'original_name', 'status']:
        if key in d:
            print(f"    {key}: {d[key]}")

client.close()
