import asyncio, sys, json
sys.path.insert(0, '.')
from pymongo import MongoClient
from config.settings import MONGO_URL, DATABASE_NAME

def main():
    client = MongoClient(MONGO_URL)
    db = client[DATABASE_NAME]
    
    # Find Cloud invoice
    cloud_doc = db.documents.find_one({"$or": [
        {"original_name": {"$regex": "557717"}},
        {"doc_id": {"$regex": "557717"}},
        {"filename": {"$regex": "557717"}}
    ]})
    
    # Find Acme invoice  
    acme_doc = db.documents.find_one({"$or": [
        {"original_name": {"$regex": "INV-2025-001234"}},
        {"doc_id": {"$regex": "INV-2025-001234"}},
        {"filename": {"$regex": "INV-2025-001234"}}
    ]})
    
    print("=== CLOUD DOC ===")
    if cloud_doc:
        print(f"doc_id: {cloud_doc.get('doc_id', 'N/A')}")
        print(f"original_name: {cloud_doc.get('original_name', 'N/A')}")
        print(f"status: {cloud_doc.get('status', 'N/A')}")
    else:
        print("NOT FOUND in 'documents' collection")
    
    print()
    print("=== ACME DOC ===")
    if acme_doc:
        print(f"doc_id: {acme_doc.get('doc_id', 'N/A')}")
        print(f"original_name: {acme_doc.get('original_name', 'N/A')}")
        print(f"status: {acme_doc.get('status', 'N/A')}")
    else:
        print("NOT FOUND in 'documents' collection")
    
    # Also check what collections exist
    print()
    print("=== COLLECTIONS ===")
    collections = db.list_collection_names()
    print(collections)
    
    # Try searching in all collections for these filenames
    for coll_name in collections:
        coll = db[coll_name]
        for keyword in ["557717", "INV-2025-001234"]:
            doc = coll.find_one({"$or": [
                {"original_name": {"$regex": keyword}},
                {"doc_id": {"$regex": keyword}},
                {"filename": {"$regex": keyword}},
                {"originalName": {"$regex": keyword}},
                {"name": {"$regex": keyword}},
            ]})
            if doc:
                print(f"  Found '{keyword}' in collection '{coll_name}': _id={doc.get('_id')}, doc_id={doc.get('doc_id', 'N/A')}")
    
    client.close()

main()
