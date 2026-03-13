"""Tests for OCR validation logic (regex fixes, quality assessment)."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.ocr_validation import apply_regex_fixes, assess_text_quality, detect_ocr_issues


class TestApplyRegexFixes:
    """Test common OCR error corrections."""

    def test_zero_to_O_in_word(self):
        text = "0ct0ber"
        corrected, fixes = apply_regex_fixes(text)
        assert "October" in corrected or "OctOber" in corrected
        assert fixes > 0

    def test_l_to_1_after_dollar(self):
        text = "$l00"
        corrected, fixes = apply_regex_fixes(text)
        assert "100" in corrected
        assert fixes > 0

    def test_1nvoice_fix(self):
        text = "1nvoice Number"
        corrected, fixes = apply_regex_fixes(text)
        assert "Invoice" in corrected

    def test_no_changes_for_clean_text(self):
        text = "This is a normal sentence without OCR errors."
        corrected, fixes = apply_regex_fixes(text)
        assert corrected == text
        assert fixes == 0


class TestAssessTextQuality:
    """Test heuristic text quality scoring."""

    def test_good_text_scores_high(self):
        text = "The invoice was sent to the company on November 17, 2025. The total amount is due within 30 days."
        score = assess_text_quality(text)
        assert score >= 0.6

    def test_garbage_text_scores_low(self):
        text = "x#@! 3$% ^&* {{}}"
        score = assess_text_quality(text)
        assert score < 0.5

    def test_empty_text_returns_zero(self):
        assert assess_text_quality("") == 0.0
        assert assess_text_quality("abc") == 0.0  # < 10 chars

    def test_never_exceeds_085(self):
        # Heuristic should cap at 0.85 to be conservative
        text = "The quick brown fox jumps over the lazy dog. " * 10
        score = assess_text_quality(text)
        assert score <= 0.85


class TestDetectOcrIssues:
    """Test OCR issue detection."""

    def test_detects_duplicate_punctuation(self):
        issues = detect_ocr_issues("Hello.. World,,")
        assert any("punctuation" in i.lower() for i in issues)

    def test_no_issues_for_clean_text(self):
        issues = detect_ocr_issues("This is a perfectly clean sentence.")
        assert len(issues) == 0
