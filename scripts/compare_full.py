import sys, json
sys.path.insert(0, '.')
from pymongo import MongoClient
from bson import ObjectId
from config.settings import MONGO_URL, DATABASE_NAME

client = MongoClient(MONGO_URL)
db = client[DATABASE_NAME]

cloud_doc = db.documents.find_one({"_id": ObjectId("69c58478b3af377d0714e428")})
acme_doc = db.documents.find_one({"_id": ObjectId("69374541810e0e28feabbe19")})

def print_doc(label, doc):
    print("=" * 80)
    print(f"  {label}")
    print(f"  filename: {doc.get('filename')}")
    print("=" * 80)
    
    pd = doc.get('processed_data', [{}])[0] if doc.get('processed_data') else {}
    
    print("\n--- CLASSIFICATION ---")
    cls = pd.get('classification', {})
    print(f"  label: {cls.get('label')}")
    print(f"  score: {cls.get('score')}")
    print(f"  confidence: {cls.get('confidence')}")
    print(f"  llama_override: {cls.get('llama_override')}")
    print(f"  reasoning: {cls.get('reasoning', 'N/A')[:200]}")
    print(f"  key_indicators: {cls.get('key_indicators')}")
    
    print("\n--- ENTITIES ---")
    ent = pd.get('entities', {})
    for k, v in ent.items():
        print(f"  {k}: {v}")
    
    print("\n--- STRUCTURED DATA ---")
    sd = pd.get('structured_data', {})
    for k, v in sd.items():
        print(f"  {k}: {v}")
    
    print("\n--- TABLES ---")
    tables = pd.get('tables', [])
    print(f"  table_count: {pd.get('table_count', len(tables))}")
    for i, t in enumerate(tables):
        print(f"\n  Table {i+1}:")
        print(f"    source: {t.get('source')}")
        print(f"    page: {t.get('page')}")
        html = t.get('html', '')
        if html:
            print(f"    html ({len(html)} chars):")
            print(f"    {html[:800]}")
    
    print("\n--- SUMMARY ---")
    print(f"  {pd.get('summary', 'N/A')}")
    
    print("\n--- EXTRACTION CONFIDENCE ---")
    print(f"  {pd.get('extraction_confidence', 'N/A')}")
    
    # Also show extractedFields from root level
    ef = doc.get('extractedFields', {})
    if ef:
        print("\n--- EXTRACTED FIELDS (root) ---")
        for k, v in ef.items():
            print(f"  {k}: {v}")
    
    # Also show extractedMetadata from root level
    em = doc.get('extractedMetadata', {})
    if em:
        print("\n--- EXTRACTED METADATA (root) ---")
        for k, v in em.items():
            if k == 'summary':
                print(f"  {k}: {str(v)[:200]}")
            else:
                print(f"  {k}: {v}")

print_doc("CLOUD INVOICE (557717_Cloud_2026-01-03.pdf)", cloud_doc)
print()
print_doc("ACME INVOICE (INV-2025-001234_Acme_Corporation_2025-11-17.pdf)", acme_doc)

client.close()
