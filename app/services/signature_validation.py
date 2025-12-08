"""
Signature Validation Module
Uses Llama 3.2 3B to validate and correct TrOCR signature extraction results
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("signature_validation")


async def validate_signature_text(
    signature_text: str,
    document_text: str,
    models: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate and correct signature text extracted by TrOCR

    Args:
        signature_text: Raw signature text from TrOCR
        document_text: Full document text for cross-reference
        models: Loaded models dictionary

    Returns:
        {
            'corrected_signature': str,
            'confidence': float,
            'validation_passed': bool,
            'suggestions': [str],
            'cross_referenced_names': [str]
        }
    """
    try:
        if not signature_text or len(signature_text.strip()) < 2:
            return {
                'corrected_signature': signature_text,
                'confidence': 0.0,
                'validation_passed': False,
                'suggestions': [],
                'cross_referenced_names': []
            }

        # Get Llama model
        llama = models.get('llama')
        if llama is None:
            from app.models.loader import load_llama_model
            llama = load_llama_model()
            models['llama'] = llama

        if llama is None:
            logger.warning("Llama not available for signature validation")
            return {
                'corrected_signature': signature_text,
                'confidence': 0.5,
                'validation_passed': False,
                'suggestions': [],
                'cross_referenced_names': []
            }

        # Extract potential names from document
        names_in_doc = await extract_names_from_document(document_text, models)

        # Prepare validation prompt
        prompt = f"""A handwriting OCR system extracted this signature text: "{signature_text}"

This signature appears in a document that mentions these names: {', '.join(names_in_doc[:5]) if names_in_doc else 'none found'}

Document context (first 500 characters):
{document_text[:500]}

Tasks:
1. Correct common handwriting OCR errors
2. Suggest the most likely correct spelling
3. Match with names in the document if possible

Common errors:
- "Jahn" → "John"
- "Smth" → "Smith"
- "Mke" → "Mike"

Format your response:
Corrected: [corrected name]
Confidence: [high/medium/low]
Match: [name from document or "none"]

Response:"""

        # Read signature validation settings from Control Panel
        from app.api.config_endpoints import get_runtime_config
        config = get_runtime_config()
        sig_val_tokens = config.get('SIGNATURE_VALIDATION_MAX_TOKENS', 150)
        sig_val_temp = config.get('SIGNATURE_VALIDATION_TEMPERATURE', 0.2)
        response = llama(
            prompt,
            max_tokens=sig_val_tokens,  # Read from Control Panel
            temperature=sig_val_temp,  # Read from Control Panel
            top_p=0.9
        )

        output = response['choices'][0]['text'].strip()

        # Parse output
        corrected_sig = signature_text
        confidence_level = 'low'
        matched_name = None

        for line in output.split('\n'):
            if line.startswith('Corrected:'):
                corrected_sig = line.replace('Corrected:', '').strip()
            elif line.startswith('Confidence:'):
                confidence_level = line.replace('Confidence:', '').strip().lower()
            elif line.startswith('Match:'):
                matched_name = line.replace('Match:', '').strip()
                if matched_name.lower() == 'none':
                    matched_name = None

        # Map confidence level to score
        confidence_map = {'high': 0.9, 'medium': 0.7, 'low': 0.5}
        confidence_score = confidence_map.get(confidence_level, 0.5)

        validation_passed = confidence_score >= 0.7

        logger.info(f"✓ Signature validation: '{signature_text}' → '{corrected_sig}' (conf: {confidence_score})")

        return {
            'corrected_signature': corrected_sig,
            'confidence': confidence_score,
            'validation_passed': validation_passed,
            'suggestions': [corrected_sig] if corrected_sig != signature_text else [],
            'cross_referenced_names': names_in_doc,
            'matched_document_name': matched_name
        }

    except Exception as e:
        logger.error(f"Error validating signature: {e}", exc_info=True)
        return {
            'corrected_signature': signature_text,
            'confidence': 0.5,
            'validation_passed': False,
            'suggestions': [],
            'cross_referenced_names': []
        }


async def extract_names_from_document(text: str, models: Dict[str, Any]) -> List[str]:
    """
    Extract person names from document text using Llama

    Returns:
        List of person names found in document
    """
    try:
        llama = models.get('llama')
        if llama is None:
            from app.models.loader import load_llama_model
            llama = load_llama_model()
            models['llama'] = llama

        if llama is None:
            return []

        prompt = f"""Extract all person names from this document text.

Text:
{text[:1200]}

List all full names found (first and last name). Format as a comma-separated list.

Names:"""

        # Read name extraction settings from Control Panel
        from app.api.config_endpoints import get_runtime_config
        config = get_runtime_config()
        name_tokens = config.get('NAME_EXTRACTION_MAX_TOKENS', 100)
        name_temp = config.get('NAME_EXTRACTION_TEMPERATURE', 0.1)
        response = llama(
            prompt,
            max_tokens=name_tokens,  # Read from Control Panel
            temperature=name_temp  # Read from Control Panel
        )

        output = response['choices'][0]['text'].strip()

        # Parse names
        names = [name.strip() for name in output.split(',')]
        names = [n for n in names if len(n) > 3 and ' ' in n]  # Filter valid full names

        logger.info(f"✓ Extracted {len(names)} names from document")

        return names[:10]  # Return top 10 names

    except Exception as e:
        logger.error(f"Error extracting names: {e}")
        return []


async def validate_signature_authenticity(
    signature_text: str,
    document_type: str,
    document_text: str,
    models: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Check for signature authenticity indicators

    Args:
        signature_text: Extracted signature text
        document_type: Type of document
        document_text: Full document text
        models: Loaded models dictionary

    Returns:
        {
            'authenticity_score': float,
            'indicators_found': [str],
            'warnings': [str],
            'recommendation': str
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
                'authenticity_score': 0.5,
                'indicators_found': [],
                'warnings': ['Llama unavailable'],
                'recommendation': 'Manual review required'
            }

        prompt = f"""Analyze this {document_type} for signature authenticity indicators.

Signature found: "{signature_text}"

Document excerpt:
{document_text[:800]}

Check for:
1. Signature placement (appropriate location?)
2. Document completeness (all fields filled?)
3. Date consistency (signature date vs document date?)
4. Name consistency (signature matches names in document?)

Rate authenticity: high/medium/low
List any warnings or concerns.

Format:
Authenticity: [high/medium/low]
Indicators: indicator1, indicator2
Warnings: warning1, warning2
Recommendation: [recommendation]

Response:"""

        # Read authenticity check settings from Control Panel
        from app.api.config_endpoints import get_runtime_config
        config = get_runtime_config()
        auth_tokens = config.get('AUTHENTICITY_MAX_TOKENS', 200)
        auth_temp = config.get('AUTHENTICITY_TEMPERATURE', 0.3)
        response = llama(
            prompt,
            max_tokens=auth_tokens,  # Read from Control Panel
            temperature=auth_temp  # Read from Control Panel
        )

        output = response['choices'][0]['text'].strip()

        # Parse output
        authenticity_level = 'medium'
        indicators = []
        warnings = []
        recommendation = 'Manual review recommended'

        for line in output.split('\n'):
            if line.startswith('Authenticity:'):
                authenticity_level = line.replace('Authenticity:', '').strip().lower()
            elif line.startswith('Indicators:'):
                ind_str = line.replace('Indicators:', '').strip()
                indicators = [i.strip() for i in ind_str.split(',')]
            elif line.startswith('Warnings:'):
                warn_str = line.replace('Warnings:', '').strip()
                warnings = [w.strip() for w in warn_str.split(',') if w.strip()]
            elif line.startswith('Recommendation:'):
                recommendation = line.replace('Recommendation:', '').strip()

        # Map authenticity level to score
        auth_map = {'high': 0.9, 'medium': 0.6, 'low': 0.3}
        authenticity_score = auth_map.get(authenticity_level, 0.5)

        logger.info(f"✓ Signature authenticity: {authenticity_score} ({len(indicators)} indicators)")

        return {
            'authenticity_score': authenticity_score,
            'indicators_found': indicators,
            'warnings': warnings,
            'recommendation': recommendation
        }

    except Exception as e:
        logger.error(f"Error validating signature authenticity: {e}")
        return {
            'authenticity_score': 0.5,
            'indicators_found': [],
            'warnings': [str(e)],
            'recommendation': 'Error during validation - manual review required'
        }
