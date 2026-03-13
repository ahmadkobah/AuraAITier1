"""
FAISS-based vector search index for document embeddings.
Replaces brute-force in-memory cosine similarity with an efficient ANN index.
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np

logger = logging.getLogger("vector_index")

# Module-level singleton
_index_lock = threading.Lock()
_faiss_index: Optional[faiss.IndexFlatIP] = None  # Inner Product (= cosine sim on normalized vectors)
_doc_metadata: List[Dict[str, Any]] = []  # Parallel list: metadata per vector
_last_rebuild: float = 0.0
_REBUILD_INTERVAL = 300  # Rebuild at most every 5 minutes


def _normalize(vectors: np.ndarray) -> np.ndarray:
    """L2-normalize vectors so inner product equals cosine similarity."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return vectors / norms


def build_index(db, search_filter: Optional[Dict] = None) -> Tuple[Optional[faiss.IndexFlatIP], List[Dict[str, Any]]]:
    """
    Build a FAISS index from MongoDB document embeddings.
    Returns (index, metadata_list).
    """
    if db is None:
        return None, []

    documents = db['documents']
    query_filter = dict(search_filter or {})
    query_filter['status'] = 'COMPLETE'

    all_docs = list(documents.find(query_filter))
    vectors = []
    metadata = []

    for doc in all_docs:
        for processed_doc in doc.get('processed_data', []):
            embedding = processed_doc.get('embedding', [])
            if embedding:
                vectors.append(embedding)
                metadata.append({
                    '_id': doc['_id'],
                    'logical_doc_num': processed_doc.get('logical_doc_num'),
                    'text': processed_doc.get('text', ''),
                    'page_range': processed_doc.get('page_range', 'N/A'),
                })

    if not vectors:
        return None, []

    dim = len(vectors[0])
    arr = np.array(vectors, dtype=np.float32)
    arr = _normalize(arr)

    index = faiss.IndexFlatIP(dim)
    index.add(arr)

    logger.info(f"Built FAISS index with {index.ntotal} vectors (dim={dim})")
    return index, metadata


def search(
    query_embedding: List[float],
    db,
    top_k: int = 10,
    doc_id_filter: Optional[str] = None,
    query_text: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search the FAISS index. Rebuilds lazily if stale or missing.
    Returns list of result dicts with similarity_score and document info.
    """
    global _faiss_index, _doc_metadata, _last_rebuild

    now = time.time()

    # Rebuild if missing or stale
    if _faiss_index is None or (now - _last_rebuild) > _REBUILD_INTERVAL:
        with _index_lock:
            # Double-check after acquiring lock
            if _faiss_index is None or (now - _last_rebuild) > _REBUILD_INTERVAL:
                _faiss_index, _doc_metadata = build_index(db)
                _last_rebuild = time.time()

    if _faiss_index is None or _faiss_index.ntotal == 0:
        return []

    # Prepare query
    q = np.array([query_embedding], dtype=np.float32)
    q = _normalize(q)

    # Search more than top_k to allow for post-filtering
    search_k = min(top_k * 5, _faiss_index.ntotal)
    scores, indices = _faiss_index.search(q, search_k)

    query_lower = query_text.lower() if query_text else None
    results = []

    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        meta = _doc_metadata[idx]

        # Filter by doc_id if requested
        if doc_id_filter and str(meta['_id']) != doc_id_filter:
            continue

        sim = float(score)

        # Boost for exact text match
        if query_lower and query_lower in meta['text'].lower():
            sim = min(1.0, sim + 0.3)

        if sim > 0.15 or (query_lower and query_lower in meta['text'].lower()):
            results.append({
                'similarity_score': sim,
                'document': {
                    '_id': meta['_id'],
                    'logical_doc_num': meta['logical_doc_num'],
                    'text': meta['text'],
                    'page_range': meta['page_range'],
                },
            })

        if len(results) >= top_k:
            break

    results.sort(key=lambda x: x['similarity_score'], reverse=True)
    return results[:top_k]


def invalidate():
    """Force index rebuild on next search (e.g., after new document processed)."""
    global _faiss_index, _last_rebuild
    with _index_lock:
        _faiss_index = None
        _last_rebuild = 0.0
