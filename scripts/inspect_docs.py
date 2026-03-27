import sys, json
sys.path.insert(0, '.')
from pymongo import MongoClient
from bson import ObjectId
from config.settings import MONGO_URL, DATABASE_NAME

client = MongoClient(MONGO_URL)
db = client[DATABASE_NAME]

# Check what fields exist on each document
cloud_doc = db.documents.find_one({"_id": ObjectId("69c58478b3af377d0714e428")})
acme_doc = db.documents.find_one({"_id": ObjectId("69374541810e0e28feabbe19")})

print("=== CLOUD DOC KEYS ===")
if cloud_doc:
    for k, v in cloud_doc.items():
        vtype = type(v).__name__
        if isinstance(v, str):
            print(f"  {k}: ({vtype}) {v[:100]}")
        elif isinstance(v, (list, dict)):
            print(f"  {k}: ({vtype}) len={len(v)}")
        else:
            print(f"  {k}: ({vtype}) {v}")

print()
print("=== ACME DOC KEYS ===")
if acme_doc:
    for k, v in acme_doc.items():
        vtype = type(v).__name__
        if isinstance(v, str):
            print(f"  {k}: ({vtype}) {v[:100]}")
        elif isinstance(v, (list, dict)):
            print(f"  {k}: ({vtype}) len={len(v)}")
        else:
            print(f"  {k}: ({vtype}) {v}")

# Now check ai_documents collection
print()
print("=== AI_DOCUMENTS COLLECTION ===")
count = db.ai_documents.count_documents({})
print(f"Total docs in ai_documents: {count}")

# Search for our docs
for keyword in ["557717", "557718", "INV-2025-001234", "Cloud", "Acme", "ACME"]:
    results = list(db.ai_documents.find({"$or": [
        {"original_name": {"$regex": keyword, "$options": "i"}},
        {"doc_id": {"$regex": keyword, "$options": "i"}},
    ]}).limit(3))
    if results:
        for r in results:
            print(f"  Found '{keyword}': doc_id={r.get('doc_id','N/A')}, original_name={r.get('original_name','N/A')}, status={r.get('status','N/A')}")

# Also get all unique doc_ids from ai_documents
print()
print("=== RECENT AI_DOCUMENTS (last 10) ===")
recent = list(db.ai_documents.find({}).sort("_id", -1).limit(10))
for r in recent:
    print(f"  doc_id={r.get('doc_id','N/A')}, original_name={r.get('original_name','N/A')}, status={r.get('status','N/A')}")

client.close()
