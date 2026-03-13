"""Tests for path validation and security measures."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestValidateFilePath:
    """Test path traversal prevention."""

    def test_rejects_path_traversal_dotdot(self):
        from app.api.endpoints import validate_file_path
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_file_path("../../etc/passwd")
        assert exc_info.value.status_code == 403

    def test_rejects_absolute_path_outside_allowed(self):
        from app.api.endpoints import validate_file_path
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_file_path("/etc/passwd")
        assert exc_info.value.status_code == 403

    def test_rejects_null_bytes(self):
        from app.api.endpoints import validate_file_path
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            validate_file_path("file\x00.pdf")
        assert exc_info.value.status_code == 403


class TestSafeDocId:
    """Test safe document ID sanitization."""

    def test_valid_objectid_passthrough(self):
        from app.api.endpoints import safe_doc_id
        result = safe_doc_id("507f1f77bcf86cd799439011")
        assert result == "507f1f77bcf86cd799439011"

    def test_strips_dangerous_chars(self):
        from app.api.endpoints import safe_doc_id
        result = str(safe_doc_id("test<script>alert(1)</script>"))
        assert "<" not in result
        assert ">" not in result

    def test_empty_string(self):
        from app.api.endpoints import safe_doc_id
        result = safe_doc_id("")
        assert result == ""
