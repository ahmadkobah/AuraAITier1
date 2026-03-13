"""
Re-embed all existing documents after Sentence Transformer model change.

Usage:
    python scripts/migrate_embeddings.py [--dry-run] [--batch-size 50]

This script:
1. Connects to MongoDB
2. Finds all documents with status=COMPLETE
3. Re-encodes each document's text with the new model
4. Updates the embedding field in-place
5. Invalidates the FAISS index
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import argparse
import logging
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def migrate(dry_run=False, batch_size=50):
    # Load new model
    model_name = os.getenv('SENTENCE_TRANSFORMER_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')
    cache_dir = os.path.join(os.path.dirname(__file__), '..', 'models', 'sentence-transformers')
    model = SentenceTransformer(model_name, cache_folder=cache_dir)
    dim = model.get_sentence_embedding_dimension()
    logger.info(f"Loaded model: {model_name} ({dim} dimensions)")

    # Connect to MongoDB (support all env var names used in the project)
    mongo_uri = os.getenv('MONGO_URL') or os.getenv('MONGODB_URI') or os.getenv('DB') or 'mongodb://localhost:27017'
    db_name = os.getenv('DATABASE_NAME') or os.getenv('MONGODB_DB') or 'aura'
    client = MongoClient(mongo_uri)
    db = client[db_name]
    documents = db['documents']

    # Find all completed documents
    query = {'status': 'COMPLETE', 'processed_data': {'$exists': True}}
    total = documents.count_documents(query)
    logger.info(f"Found {total} documents to re-embed")

    if total == 0:
        logger.info("Nothing to migrate.")
        client.close()
        return

    updated = 0
    errors = 0
    cursor = documents.find(query, batch_size=batch_size)

    for doc in cursor:
        doc_id = doc['_id']
        processed_data = doc.get('processed_data', [])
        changed = False

        for i, pd in enumerate(processed_data):
            text = pd.get('full_text') or pd.get('text', '')
            if not text:
                continue

            new_embedding = model.encode(text, convert_to_tensor=False).tolist()

            if not dry_run:
                processed_data[i]['embedding'] = new_embedding
                changed = True

            logger.debug(f"  Doc {doc_id} sub-doc {i}: {len(text)} chars -> {len(new_embedding)}d vector")

        if changed and not dry_run:
            try:
                documents.update_one(
                    {'_id': doc_id},
                    {'$set': {
                        'processed_data': processed_data,
                        'embedding_model': model_name,
                        'embedding_migrated_at': datetime.utcnow(),
                    }}
                )
                updated += 1
            except Exception as e:
                logger.error(f"Failed to update {doc_id}: {e}")
                errors += 1
        elif dry_run:
            updated += 1

        if updated % 10 == 0 and updated > 0:
            logger.info(f"Progress: {updated}/{total} documents {'(dry run)' if dry_run else 'updated'}")

    logger.info(f"Migration complete: {updated} updated, {errors} errors out of {total} total")

    if not dry_run:
        # Invalidate FAISS index so it rebuilds with new embeddings
        try:
            from app.utils.vector_index import invalidate
            invalidate()
            logger.info("FAISS index invalidated - will rebuild on next search")
        except Exception:
            logger.warning("Could not invalidate FAISS index (service may not be running)")

    client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Re-embed documents after model change')
    parser.add_argument('--dry-run', action='store_true', help='Count documents without modifying')
    parser.add_argument('--batch-size', type=int, default=50, help='MongoDB cursor batch size')
    args = parser.parse_args()
    migrate(dry_run=args.dry_run, batch_size=args.batch_size)
