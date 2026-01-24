"""
OCR Validation Module
Uses Llama 3.2 3B to validate and improve OCR output quality
Supports Smart OCR Routing with 4 tiers: SKIP, LIGHT, FULL, REVIEW
"""

import logging
import re
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger("ocr_validation")


def apply_regex_fixes(text: str) -> Tuple[str, int]:
    """
    Apply common OCR error fixes using regex patterns.
    Used for LIGHT validation tier - fast fixes without LLaMA.
    
    Returns:
        Tuple of (corrected_text, number_of_fixes)
    """
    fixes_made = 0
    result = text
    
    # Common OCR error patterns: (pattern, replacement, description)
    patterns = [
        # 0 (zero) → O (letter) when surrounded by letters
        (r'(?<=[a-zA-Z])0(?=[a-zA-Z])', 'O', '0→O in word'),
        # O (letter) → 0 (zero) when surrounded by digits
        (r'(?<=[0-9])O(?=[0-9])', '0', 'O→0 in number'),
        # 1 (one) → l (letter) in common words
        (r'\b1nvoice\b', 'Invoice', '1nvoice→Invoice'),
        (r'\b1tem\b', 'Item', '1tem→Item'),
        (r'\bTota1\b', 'Total', 'Tota1→Total'),
        # 1 (one) → I (letter) at word start before lowercase
        (r'\b1(?=[a-z])', 'I', '1→I at word start'),
        # l (letter) → 1 (one) in amounts/numbers
        (r'(?<=\$)l(?=[0-9])', '1', 'l→1 after $'),
        (r'(?<=[0-9])l(?=[0-9])', '1', 'l→1 in number'),
        # rn → m (common OCR error)
        (r'(?<=[a-z])rn(?=[a-z])', 'm', 'rn→m'),
        # 5 ↔ S fixes
        (r'\b5ale\b', 'Sale', '5ale→Sale'),
        (r'\b5ervice\b', 'Service', '5ervice→Service'),
        # 8 ↔ B fixes
        (r'\b8ank\b', 'Bank', '8ank→Bank'),
        # Common date fixes
        (r'(?<=[0-9])/O(?=[0-9])', '/0', '/O→/0 in date'),
        (r'(?<=[0-9])-O(?=[0-9])', '-0', '-O→-0 in date'),
    ]
    
    for pattern, replacement, desc in patterns:
        new_result, count = re.subn(pattern, replacement, result, flags=re.IGNORECASE)
        if count > 0:
            fixes_made += count
            logger.debug(f"  Regex fix: {desc} ({count}x)")
            result = new_result
    
    return result, fixes_made


async def validate_ocr_quality(
    ocr_text: str,
    models: Dict[str, Any],
    ocr_confidence: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Validate OCR quality using Smart Routing based on PaddleOCR confidence scores.
    
    Routing Tiers:
    - SKIP (≥95%): High confidence, no validation needed
    - LIGHT (75-94%): Medium confidence, apply regex fixes only
    - FULL (50-74%): Low confidence, full LLaMA validation
    - REVIEW (<50%): Very poor, flag for manual review

    Args:
        ocr_text: Raw text extracted by PaddleOCR
        models: Loaded models dictionary
        ocr_confidence: Dict with 'avg_confidence' and 'min_confidence' from PaddleOCR

    Returns:
        {
            'corrected_text': str,
            'quality_score': float,
            'issues_found': [str],
            'corrections_made': int,
            'confidence': float,
            'routing_tier': str  # 'skip', 'light', 'full', or 'review'
        }
    """
    try:
        # Get routing thresholds from config
        from app.api.config_endpoints import get_runtime_config
        config = get_runtime_config()
        
        skip_threshold = config.get('OCR_QUALITY_SKIP_THRESHOLD', 0.95)
        medium_threshold = config.get('OCR_ROUTING_MEDIUM_THRESHOLD', 0.75)
        low_threshold = config.get('OCR_ROUTING_LOW_THRESHOLD', 0.50)
        
        # Get actual OCR confidence from PaddleOCR (if provided)
        if ocr_confidence:
            avg_conf = ocr_confidence.get('avg_confidence', 0.0)
            min_conf = ocr_confidence.get('min_confidence', 0.0)
        else:
            # Fallback to heuristic assessment if no confidence provided
            avg_conf = assess_text_quality(ocr_text)
            min_conf = avg_conf
        
        # ==========================================
        # TIER 1: SKIP (confidence ≥ skip_threshold)
        # ==========================================
        if avg_conf >= skip_threshold:
            logger.info(f"🟢 OCR confidence {avg_conf:.0%} ≥ {skip_threshold:.0%} → SKIP validation")
            return {
                'corrected_text': ocr_text,
                'quality_score': avg_conf,
                'issues_found': [],
                'corrections_made': 0,
                'confidence': 0.99,
                'routing_tier': 'skip'
            }
        
        # ==========================================
        # TIER 2: LIGHT (confidence ≥ medium_threshold)
        # ==========================================
        if avg_conf >= medium_threshold:
            logger.info(f"🟡 OCR confidence {avg_conf:.0%} → LIGHT validation (regex fixes)")
            corrected_text, fixes_made = apply_regex_fixes(ocr_text)
            
            return {
                'corrected_text': corrected_text,
                'quality_score': avg_conf,
                'issues_found': [f'{fixes_made} regex fixes applied'] if fixes_made > 0 else [],
                'corrections_made': fixes_made,
                'confidence': 0.90,
                'routing_tier': 'light'
            }
        
        # ==========================================
        # TIER 4: REVIEW (confidence < low_threshold)
        # ==========================================
        if avg_conf < low_threshold:
            logger.warning(f"🔴 OCR confidence {avg_conf:.0%} < {low_threshold:.0%} → FLAG for manual review")
            # Still apply regex fixes as a best effort
            corrected_text, fixes_made = apply_regex_fixes(ocr_text)
            
            return {
                'corrected_text': corrected_text,
                'quality_score': avg_conf,
                'issues_found': ['Very low OCR confidence - manual review recommended'],
                'corrections_made': fixes_made,
                'confidence': avg_conf,
                'routing_tier': 'review',
                'requires_review': True
            }
        
        # ==========================================
        # TIER 3: FULL (confidence between low and medium)
        # ==========================================
        logger.info(f"🟠 OCR confidence {avg_conf:.0%} → FULL LLaMA validation")
        
        # Quick quality assessment (heuristic)
        initial_quality = assess_text_quality(ocr_text)

        # Get Llama model
        llama = models.get('llama')
        if llama is None:
            from app.models.loader import load_llama_model
            llama = load_llama_model()
            models['llama'] = llama

        if llama is None:
            logger.warning("Llama not available, returning uncorrected text")
            return {
                'corrected_text': ocr_text,
                'quality_score': initial_quality,
                'issues_found': ['Llama model unavailable'],
                'corrections_made': 0,
                'confidence': initial_quality
            }

        # Detect potential issues
        issues = detect_ocr_issues(ocr_text)

        if not issues:
            logger.info("No OCR issues detected")
            return {
                'corrected_text': ocr_text,
                'quality_score': initial_quality,
                'issues_found': [],
                'corrections_made': 0,
                'confidence': 0.95
            }

        logger.info(f"Detected {len(issues)} potential OCR issues")

        # NEW APPROACH: Preserve formatting while fixing errors
        prompt = f"""You are an OCR correction expert. Your task is to fix ONLY character-level OCR errors while preserving ALL formatting.

Common OCR errors:
- 0 (zero) ↔ O (letter O)
- 1 (one) ↔ l (lowercase L) or I (uppercase i)  
- 5 ↔ S
- 8 ↔ B

CRITICAL RULES:
1. Keep EVERY line break exactly as it appears
2. Keep ALL spaces and indentation
3. Keep table/column alignment
4. Fix ONLY wrong characters (e.g., "0ct0ber" → "October")
5. Do NOT reformat, reflow, or reorganize text
6. Do NOT add explanations or notes
7. Return the corrected text immediately

Text to correct:
{ocr_text[:2000]}

Corrected text:"""

        # Get settings from Control Panel config
        from app.api.config_endpoints import get_runtime_config
        config = get_runtime_config()
        ocr_temp = config.get('OCR_VALIDATION_TEMPERATURE', 0.05)  # Even lower for minimal creativity
        ocr_max_tokens = config.get('OCR_VALIDATION_MAX_TOKENS', 2500)  # Enough for full pages

        response = llama(
            prompt,
            max_tokens=ocr_max_tokens,
            temperature=ocr_temp,  # Very low to preserve structure
            top_p=0.85,
            stop=["\n\nThe only", "\n\nNote that", "\n\nPlease", "\n\nCorrections made:", "\n\nExplanation:"]
        )

        corrected_text = response['choices'][0]['text'].strip()
        
        # Additional cleanup: Remove any explanations that slipped through
        explanation_markers = [
            "The only corrections",
            "Corrections made",
            "Note that",
            "Please note",
            "If you need",
            "Explanation:",
            "I corrected",
            "I fixed"
        ]
        
        for marker in explanation_markers:
            if marker in corrected_text:
                # Find the marker and remove everything after it
                corrected_text = corrected_text.split(marker)[0].strip()
                logger.info(f"Removed explanation starting with: '{marker}'")
                break
        
        # If LLaMA significantly changed the length, it probably reformatted - use original
        length_diff_ratio = abs(len(corrected_text) - len(ocr_text)) / len(ocr_text)
        if length_diff_ratio > 0.3:  # More than 30% length change
            logger.warning(f"LLaMA output length changed by {length_diff_ratio:.1%}, using original text")
            corrected_text = ocr_text

        # Calculate corrections made
        corrections_made = count_differences(ocr_text, corrected_text)

        # Recalculate quality score
        final_quality = assess_text_quality(corrected_text)

        logger.info(f"✓ OCR validation: {corrections_made} corrections, quality: {final_quality:.2f}")

        return {
            'corrected_text': corrected_text,
            'quality_score': final_quality,
            'issues_found': issues,
            'corrections_made': corrections_made,
            'confidence': 0.85 if corrections_made > 0 else 0.95,
            'routing_tier': 'full'
        }

    except Exception as e:
        logger.error(f"Error validating OCR: {e}", exc_info=True)
        return {
            'corrected_text': ocr_text,
            'quality_score': 0.5,
            'issues_found': [str(e)],
            'corrections_made': 0,
            'confidence': 0.5,
            'routing_tier': 'error'
        }


def assess_text_quality(text: str) -> float:
    """
    Quick heuristic assessment of text quality (0.0 - 1.0)
    
    NOTE: This is a FALLBACK when PaddleOCR confidence is not available.
    It should be CONSERVATIVE (return lower scores) to trigger FULL validation
    when unsure, rather than accidentally skipping validation.

    Checks:
    - Ratio of alphabetic characters
    - Presence of common words
    - Sentence structure
    - Unusual character patterns
    """
    if not text or len(text) < 10:
        return 0.0

    # Start at 0.7 (not 1.0) - be conservative when using heuristics
    # This ensures we don't skip validation just because heuristics look OK
    score = 0.7

    # Check 1: Alphabetic character ratio (boost score if good)
    alpha_ratio = sum(c.isalpha() or c.isspace() for c in text) / len(text)
    if alpha_ratio >= 0.8:
        score += 0.1
    elif alpha_ratio < 0.6:
        score -= 0.2

    # Check 2: Unusual character sequences (OCR artifacts) - penalize heavily
    unusual_patterns = [
        r'\d[A-Z]{2,}',  # Number followed by uppercase letters
        r'[A-Z]{1}\d[A-Z]{1}',  # Letter-number-letter pattern
        r'\s{3,}',  # Multiple consecutive spaces
        r'[^\w\s\.,;:!?\-\'\"(){}\[\]]{2,}'  # Multiple special chars
    ]

    for pattern in unusual_patterns:
        matches = len(re.findall(pattern, text))
        if matches > 0:
            score -= min(0.15 * matches, 0.4)  # Heavier penalty

    # Check 3: Common English/German words presence
    common_words = ['the', 'and', 'to', 'of', 'in', 'for', 'is', 'on', 'that', 'a',
                    'der', 'die', 'das', 'und', 'in', 'von', 'für', 'ist', 'mit', 'auf']
    text_lower = text.lower()
    words_found = sum(1 for word in common_words if f' {word} ' in text_lower)
    if words_found >= 4:
        score += 0.1
    elif words_found < 2:
        score -= 0.15

    # Check 4: Proper sentence structure (capital letter after period)
    sentences = text.split('.')
    if len(sentences) > 1:
        proper_caps = sum(1 for s in sentences[1:] if s.strip() and s.strip()[0].isupper())
        cap_ratio = proper_caps / max(len(sentences) - 1, 1)
        if cap_ratio >= 0.7:
            score += 0.05
        elif cap_ratio < 0.5:
            score -= 0.1

    # Cap at 0.85 max for heuristic assessment (never skip validation on heuristics alone)
    return max(0.0, min(0.85, score))


def detect_ocr_issues(text: str) -> List[str]:
    """
    Detect potential OCR issues in text

    Returns list of issue descriptions
    """
    issues = []

    # Issue 1: Number-letter confusion patterns
    if re.search(r'\b[O0]{2,}\d+\b|\b\d+[O0]{2,}\b', text):
        issues.append("Potential 0/O confusion in numbers")

    # Issue 2: Lowercase L / uppercase I / number 1 confusion
    if re.search(r'\bl{2,}\b|\bI{2,}[a-z]', text):
        issues.append("Potential l/I/1 confusion")

    # Issue 3: Missing spaces in common words
    compound_pattern = r'\b[a-z]+[A-Z][a-z]+\b'
    if len(re.findall(compound_pattern, text)) > 3:
        issues.append("Possible missing spaces between words")

    # Issue 4: Unusual punctuation
    if re.search(r'[,;.]{2,}', text):
        issues.append("Duplicate punctuation detected")

    # Issue 5: Inconsistent capitalization
    words = text.split()
    if len(words) > 10:
        caps_words = sum(1 for w in words if w and w[0].isupper())
        if caps_words > len(words) * 0.4 and caps_words < len(words) * 0.9:
            issues.append("Inconsistent capitalization")

    return issues


def count_differences(text1: str, text2: str) -> int:
    """
    Count number of character differences between two texts
    Simple Levenshtein-like distance
    """
    if text1 == text2:
        return 0

    # Split into words for better comparison
    words1 = text1.split()
    words2 = text2.split()

    # Count differing words
    max_len = max(len(words1), len(words2))
    differences = 0

    for i in range(max_len):
        word1 = words1[i] if i < len(words1) else ''
        word2 = words2[i] if i < len(words2) else ''

        if word1 != word2:
            differences += 1

    return differences


async def validate_numbers_and_dates(text: str, models: Dict[str, Any]) -> Dict[str, Any]:
    """
    Specifically validate numbers and dates in OCR text using Llama

    Returns:
        {
            'numbers_found': [float],
            'dates_found': [str],
            'validation_passed': bool,
            'issues': [str]
        }
    """
    try:
        llama = models.get('llama')
        if llama is None:
            from app.models.loader import load_llama_model
            llama = load_llama_model()
            models['llama'] = llama

        if llama is None:
            return {
                'numbers_found': [],
                'dates_found': [],
                'validation_passed': False,
                'issues': ['Llama unavailable']
            }

        prompt = f"""Extract and validate all numbers and dates from this text. Check for OCR errors in numbers (0/O confusion, etc.).

Text:
{text[:1000]}

List all numbers (amounts, IDs, quantities) and dates found. Format:
Numbers: 123.45, 678.90
Dates: 2025-11-17, 2025-12-15

Output:"""

        # Read validation quality settings from Control Panel
        from app.api.config_endpoints import get_runtime_config
        config = get_runtime_config()
        val_tokens = config.get('VALIDATION_QUALITY_MAX_TOKENS', 200)
        val_temp = config.get('VALIDATION_QUALITY_TEMPERATURE', 0.1)
        response = llama(
            prompt,
            max_tokens=val_tokens,  # Read from Control Panel
            temperature=val_temp  # Read from Control Panel
        )

        output = response['choices'][0]['text'].strip()

        # Parse numbers and dates
        numbers = extract_numbers_from_text(output)
        dates = extract_dates_from_text(output)

        logger.info(f"✓ Validated {len(numbers)} numbers, {len(dates)} dates")

        return {
            'numbers_found': numbers,
            'dates_found': dates,
            'validation_passed': True,
            'issues': []
        }

    except Exception as e:
        logger.error(f"Error validating numbers/dates: {e}")
        return {
            'numbers_found': [],
            'dates_found': [],
            'validation_passed': False,
            'issues': [str(e)]
        }


def extract_numbers_from_text(text: str) -> List[float]:
    """Extract numeric values from text"""
    numbers = []
    # Match numbers with optional decimals and commas
    pattern = r'\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b'
    matches = re.findall(pattern, text)

    for match in matches:
        try:
            # Remove commas and convert to float
            num = float(match.replace(',', ''))
            numbers.append(num)
        except ValueError:
            continue

    return numbers


def extract_dates_from_text(text: str) -> List[str]:
    """Extract date strings from text"""
    dates = []

    # Common date patterns
    patterns = [
        r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
        r'\d{2}-\d{2}-\d{4}',  # DD-MM-YYYY
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        dates.extend(matches)

    return list(set(dates))  # Remove duplicates
