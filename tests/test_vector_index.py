"""Tests for FAISS vector index module."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.vector_index import _normalize, search, invalidate
import numpy as np


class TestNormalize:
    """Test vector normalization."""

    def test_unit_vectors(self):
        vecs = np.array([[3.0, 4.0]], dtype=np.float32)
        normed = _normalize(vecs)
        assert abs(np.linalg.norm(normed[0]) - 1.0) < 1e-6

    def test_zero_vector_safe(self):
        vecs = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
        normed = _normalize(vecs)
        assert not np.isnan(normed).any()

    def test_batch_normalization(self):
        vecs = np.random.randn(10, 128).astype(np.float32)
        normed = _normalize(vecs)
        norms = np.linalg.norm(normed, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)


class TestSearchWithNoDb:
    """Test search gracefully handles missing database."""

    def test_search_returns_empty_without_db(self):
        invalidate()
        results = search(
            query_embedding=[0.1] * 384,
            db=None,
            top_k=5,
        )
        assert results == []
