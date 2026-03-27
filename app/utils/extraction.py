"""
Structured Data Extraction Module
Uses Llama 3.2 3B to extract structured fields from documents
"""

import asyncio
import logging
import json
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger("extraction")


def _find_matching_brace(text: str, start: int) -> int:
    """Find the position after the closing brace that matches the opening brace at `start`."""
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == '\\':
            if in_string:
                escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i + 1
    return -1


# Document type specific extraction schemas
EXTRACTION_SCHEMAS = {
    'invoice': {
        'fields': [
            'invoice_number',
            'invoice_date',
            'due_date',
            'vendor_name',
            'vendor_address',
            'customer_name',
            'customer_address',
            'subtotal',
            'tax_amount',
            'total_amount',
            'currency',
            'payment_terms',
            'bank_name',
            'account_name',
            'account_number',
            'routing_number',
            'swift_code',
            'iban'
        ]
    },
    'contract': {
        'fields': [
            'contract_number',
            'contract_date',
            'effective_date',
            'expiration_date',
            'party_a',
            'party_b',
            'contract_value',
            'payment_terms',
            'termination_clause'
        ]
    },
    'receipt': {
        'fields': [
            'receipt_number',
            'date',
            'merchant_name',
            'merchant_address',
            'total_amount',
            'payment_method',
            'currency'
        ]
    },
    'letter': {
        'fields': [
            'date',
            'sender',
            'recipient',
            'subject',
            'reference_number'
        ]
    },
    'purchase_order': {
        'fields': [
            'po_number',
            'order_date',
            'vendor_name',
            'delivery_date',
            'delivery_address',
            'total_amount',
            'currency',
            'buyer_name',
            'terms'
        ]
    },
    'credit_note': {
        'fields': [
            'credit_note_number',
            'date',
            'original_invoice_number',
            'vendor_name',
            'credit_amount',
            'currency',
            'reason',
            'customer_name'
        ]
    },
    'debit_note': {
        'fields': [
            'debit_note_number',
            'date',
            'original_invoice_number',
            'vendor_name',
            'debit_amount',
            'currency',
            'reason'
        ]
    },
    'payment_voucher': {
        'fields': [
            'voucher_number',
            'date',
            'payee_name',
            'amount',
            'currency',
            'payment_method',
            'purpose'
        ]
    },
    'bank_statement': {
        'fields': [
            'account_number',
            'statement_period',
            'opening_balance',
            'closing_balance',
            'bank_name',
            'account_holder'
        ]
    },
    'financial_statement': {
        'fields': [
            'statement_type',
            'period',
            'date',
            'company_name',
            'fiscal_year',
            'currency'
        ]
    },
    'tax_document': {
        'fields': [
            'tax_id',
            'tax_year',
            'tax_type',
            'taxpayer_name',
            'filing_date',
            'tax_amount',
            'currency'
        ]
    },
    'non_disclosure_agreement': {
        'fields': [
            'agreement_date',
            'effective_date',
            'expiration_date',
            'party_a',
            'party_b',
            'jurisdiction',
            'purpose'
        ]
    },
    'memorandum_of_understanding': {
        'fields': [
            'mou_date',
            'effective_date',
            'parties',
            'purpose',
            'duration',
            'signatories'
        ]
    },
    'license': {
        'fields': [
            'license_number',
            'license_type',
            'issue_date',
            'expiration_date',
            'licensee_name',
            'issuing_authority'
        ]
    },
    'permit': {
        'fields': [
            'permit_number',
            'permit_type',
            'issue_date',
            'expiration_date',
            'permit_holder',
            'issuing_authority',
            'location'
        ]
    },
    'report': {
        'fields': [
            'report_type',
            'date',
            'period',
            'department',
            'author',
            'report_number'
        ]
    },
    'business_letter': {
        'fields': [
            'date',
            'sender',
            'sender_company',
            'recipient',
            'recipient_company',
            'subject',
            'reference_number'
        ]
    },
    'memo': {
        'fields': [
            'date',
            'from_person',
            'to_person',
            'subject',
            'department',
            'memo_number'
        ]
    },
    'proposal': {
        'fields': [
            'proposal_number',
            'date',
            'proposer',
            'recipient',
            'subject',
            'total_value',
            'validity_period'
        ]
    },
    'quotation': {
        'fields': [
            'quotation_number',
            'date',
            'vendor_name',
            'customer_name',
            'total_amount',
            'currency',
            'validity_period'
        ]
    },
    'tender_document': {
        'fields': [
            'tender_number',
            'tender_name',
            'issue_date',
            'submission_deadline',
            'issuing_organization',
            'estimated_value'
        ]
    },
    'form': {
        'fields': [
            'form_type',
            'form_number',
            'date',
            'applicant_name',
            'reference_number',
            'submission_date'
        ]
    },
    'delivery_note': {
        'fields': [
            'delivery_note_number',
            'delivery_date',
            'shipper_name',
            'recipient_name',
            'recipient_address',
            'order_reference',
            'carrier'
        ]
    },
    'packing_slip': {
        'fields': [
            'packing_slip_number',
            'date',
            'order_number',
            'shipper',
            'recipient',
            'total_items',
            'tracking_number'
        ]
    },
    'bill_of_lading': {
        'fields': [
            'bol_number',
            'date',
            'shipper',
            'consignee',
            'carrier',
            'origin',
            'destination',
            'shipping_date'
        ]
    },
    'shipping_document': {
        'fields': [
            'document_number',
            'shipping_date',
            'carrier',
            'tracking_number',
            'origin',
            'destination',
            'recipient'
        ]
    },
    'resume': {
        'fields': [
            'applicant_name',
            'email',
            'phone',
            'education',
            'experience_years',
            'current_position',
            'skills'
        ]
    },
    'job_application': {
        'fields': [
            'application_date',
            'applicant_name',
            'position_applied',
            'email',
            'phone',
            'availability_date'
        ]
    },
    'employment_contract': {
        'fields': [
            'contract_date',
            'start_date',
            'employee_name',
            'employer_name',
            'position',
            'salary',
            'contract_duration'
        ]
    },
    'agreement': {
        'fields': [
            'agreement_type',
            'agreement_date',
            'effective_date',
            'parties',
            'purpose',
            'duration'
        ]
    },
    'statement': {
        'fields': [
            'statement_type',
            'account_number',
            'period',
            'date',
            'account_holder'
        ]
    },
    'certificate': {
        'fields': [
            'certificate_type',
            'certificate_number',
            'issue_date',
            'expiration_date',
            'recipient_name',
            'issuing_authority'
        ]
    }
}


async def extract_structured_data(
    text: str,
    doc_type: str,
    models: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract structured data from document text using Llama

    Args:
        text: Document text content
        doc_type: Document type (invoice, contract, receipt, etc.)
        models: Loaded models dictionary

    Returns:
        Dictionary with extracted fields and metadata
    """
    try:
        # Normalize document type
        doc_type_normalized = doc_type.lower().replace('_', ' ').strip()

        # Get extraction schema for document type (try full match first, then first-word fallback)
        schema_key = doc_type_normalized.replace(' ', '_')
        schema = EXTRACTION_SCHEMAS.get(schema_key) or EXTRACTION_SCHEMAS.get(doc_type_normalized.split()[0], None)

        if not schema:
            logger.warning(f"No extraction schema for document type: {doc_type}")
            return {
                'success': False,
                'error': f'No extraction schema for document type: {doc_type}',
                'extracted_fields': {}
            }

        # Get Llama model
        llama = models.get('llama')
        if llama is None:
            from app.models.loader import load_llama_model
            llama = load_llama_model()
            models['llama'] = llama

        if llama is None:
            logger.error("Llama model not available for extraction")
            return {
                'success': False,
                'error': 'Llama model not available',
                'extracted_fields': {}
            }

        # Prepare extraction prompt with clear field definitions
        fields_list = ', '.join(schema['fields'])  # Extract ALL fields, not just first 6
        
        # Add specific instructions for invoice addresses and amount disambiguation
        address_instructions = ""
        if doc_type_normalized in ['invoice', 'receipt', 'purchase order']:
            address_instructions = """
IMPORTANT - Address Rules:
- vendor_address: The address of the company/business ISSUING this document (the seller/supplier)
- customer_address: The address of the person/company RECEIVING this document (the buyer)
- Look for labels like "From:", "Sender:", "Issued by:" for vendor address
- Look for labels like "Bill to:", "Ship to:", "Customer:", "Recipient:" for customer address

IMPORTANT - Amount Rules:
- subtotal: The sum of line items BEFORE tax (the smaller amount)
- tax_amount: ONLY the tax/VAT amount
- total_amount: The FINAL amount AFTER adding tax (the largest amount, what is owed)
- Rule: subtotal + tax_amount = total_amount. If only two amounts exist, the larger one is total_amount.
"""
        
        # Smart text selection: send top + bottom of document
        # Top captures headers, dates, invoice numbers; bottom captures banking, payment, totals
        if len(text) > 4500:
            doc_excerpt = text[:3000] + "\n...\n" + text[-1500:]
        else:
            doc_excerpt = text
        
        prompt = f"""Extract fields from this {doc_type_normalized}. You MUST return ONLY valid JSON. Do not add explanations, notes, or extra text.{address_instructions}

Document Text:
{doc_excerpt}

Required Fields: {fields_list}

CRITICAL RULES:
1. Return ONLY valid JSON - no markdown, no explanations, no extra text
2. Start response with {{ and end with }}
3. Use null for missing fields (not "null", "none", "not found")
4. Preserve exact dates, numbers, and amounts from the document
5. Do not add any text after the closing }}

Return JSON with extracted values:
{{"""

        logger.info(f"Extracting {len(schema['fields'])} fields for {doc_type_normalized}")

        # Generate extraction with sufficient tokens for all fields (read from Control Panel)
        from app.api.config_endpoints import get_runtime_config
        config = get_runtime_config()
        extraction_tokens = config.get('EXTRACTION_MAX_TOKENS', 1200)
        extraction_temp = config.get('EXTRACTION_TEMPERATURE', 0.1)
        response = await asyncio.to_thread(
            llama,
            prompt,
            max_tokens=extraction_tokens,
            temperature=extraction_temp,
            top_p=0.9,
            stop=["}\n\nNote", "}\n\nThe", "}\n\nExplanation", "}\n\nI "]
        )

        raw_output = response['choices'][0]['text'].strip()
        # Prompt ended with opening '{' — prepend it to make complete JSON
        if raw_output and not raw_output.lstrip().startswith('{'):
            raw_output = '{' + raw_output
        logger.debug(f"Raw Llama output: {raw_output[:200]}")

        # Parse JSON response
        extracted_fields = parse_extraction_output(raw_output, schema['fields'])

        if not extracted_fields:
            logger.warning("Extraction parsing returned empty result — marking as failed")
            return {
                'success': False,
                'error': 'Failed to parse extraction output',
                'document_type': doc_type,
                'extracted_fields': {},
                'extraction_confidence': 0.0,
                'fields_extracted': 0,
                'fields_requested': len(schema['fields'])
            }

        # Post-process and validate fields
        validated_fields = validate_extracted_fields(extracted_fields, doc_type_normalized)

        logger.info(f"✓ Extracted {len([v for v in validated_fields.values() if v is not None])} fields")

        return {
            'success': True,
            'document_type': doc_type,
            'extracted_fields': validated_fields,
            'extraction_confidence': calculate_extraction_confidence(validated_fields, schema['fields']),
            'fields_extracted': len([v for v in validated_fields.values() if v is not None]),
            'fields_requested': len(schema['fields'])
        }

    except Exception as e:
        logger.error(f"Error extracting structured data: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'extracted_fields': {}
        }


def parse_extraction_output(raw_output: str, expected_fields: List[str]) -> Dict[str, Any]:
    """
    Parse Llama's extraction output into structured dictionary
    Uses json_repair for robust JSON parsing, with regex fallback
    """
    try:
        # Clean up the raw output
        cleaned = raw_output.strip()
        
        # Remove markdown code blocks
        if '```' in cleaned:
            cleaned = re.sub(r'^```json\s*', '', cleaned)
            cleaned = re.sub(r'^```\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
        
        # Remove any explanatory text after the JSON
        for marker in ['\n\nNote:', '\n\nThe only', '\n\nExplanation:', '\n\nI extracted']:
            if marker in cleaned:
                cleaned = cleaned.split(marker)[0].strip()
        
        # Try json_repair first (handles malformed JSON robustly)
        try:
            from json_repair import repair_json
            repaired = repair_json(cleaned, return_objects=True)
            if isinstance(repaired, dict):
                logger.debug(f"json_repair parsed {len(repaired)} fields")
                return repaired
        except Exception:
            pass
        
        # Try standard JSON parsing on the extracted JSON block
        try:
            json_start = cleaned.find('{')
            if json_start >= 0:
                json_end = _find_matching_brace(cleaned, json_start)
                if json_end > json_start:
                    parsed = json.loads(cleaned[json_start:json_end])
                    logger.debug(f"Standard JSON parsed {len(parsed)} fields")
                    return parsed
        except json.JSONDecodeError:
            pass
        
        # Fallback: Manual parsing with improved regex
        logger.warning("Using manual regex parsing fallback")
        result = {}
        
        for field in expected_fields:
            patterns = [
                rf'"{field}"\s*:\s*"([^"]*)"',
                rf'"{field}"\s*:\s*(\[[^\]]*\])',  # Array values
                rf'"{field}"\s*:\s*([^,}}\s]+)',
                rf'{field}\s*:\s*"([^"]*)"',
                rf'{field}\s*:\s*([^,}}\s]+)',
                rf"'{field}'\s*:\s*'([^']*)'",
            ]
            
            for pattern in patterns:
                match = re.search(pattern, cleaned, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    if value.lower() not in ['null', 'none', 'n/a', 'not found', '']:
                        # Try to parse array values
                        if value.startswith('['):
                            try:
                                result[field] = json.loads(value)
                            except json.JSONDecodeError:
                                result[field] = value
                        else:
                            result[field] = value
                    break
        
        logger.debug(f"Manual parsing extracted {len(result)} fields")
        return result

    except Exception as e:
        logger.error(f"Error parsing extraction output: {e}", exc_info=True)
        return {}

    # If we got here with an empty dict, all parsing methods failed
    if not result:
        logger.warning("All extraction parsing methods returned empty result")
    return result


def validate_extracted_fields(fields: Dict[str, Any], doc_type: str) -> Dict[str, Any]:
    """
    Validate and clean extracted fields
    """
    validated = {}

    for key, value in fields.items():
        # Skip null/empty values
        if value is None or value == '' or str(value).lower() in ['null', 'none', 'n/a', 'not found']:
            validated[key] = None
            continue

        # Validate dates
        if 'date' in key.lower():
            validated[key] = validate_date(value)

        # Validate amounts
        elif any(term in key.lower() for term in ['amount', 'total', 'subtotal', 'tax', 'price', 'value']):
            validated[key] = validate_amount(value)

        # Clean text fields
        else:
            validated[key] = str(value).strip()

    # Fix 1: Subtotal/total swap detection — LLaMA 3B sometimes confuses these
    sub = validated.get('subtotal')
    total = validated.get('total_amount')
    if sub is not None and total is not None and isinstance(sub, (int, float)) and isinstance(total, (int, float)):
        if sub > total > 0:
            logger.warning(f"Subtotal ({sub}) > total_amount ({total}) — swapping (LLaMA likely confused them)")
            validated['subtotal'], validated['total_amount'] = total, sub

    return validated


def validate_date(date_str: str) -> Optional[str]:
    """
    Validate and normalize date strings with locale-aware parsing.
    Returns ISO format date or None.
    
    Heuristic for ambiguous dates like 03/04/2025:
    - If first number > 12, it must be day-first (European: dd/mm/yyyy)
    - Otherwise, try both and prefer the one that seems more reasonable
    """
    try:
        from datetime import datetime
        import re

        date_str_clean = str(date_str).strip()

        # Unambiguous formats first (no mm/dd vs dd/mm ambiguity)
        unambiguous_formats = [
            '%Y-%m-%d',           # 2025-11-17
            '%B %d, %Y',          # November 17, 2025
            '%b %d, %Y',          # Nov 17, 2025
            '%Y/%m/%d',           # 2025/11/17
            '%Y.%m.%d',           # 2025.11.17
            '%B %d %Y',           # November 17 2025
            '%b %d %Y',           # Nov 17 2025
            '%d %B %Y',           # 17 November 2025
            '%d %b %Y',           # 17 Nov 2025
            '%d.%m.%Y',           # 17.11.2025 (European convention: dd.mm.yyyy)
        ]

        for fmt in unambiguous_formats:
            try:
                dt = datetime.strptime(date_str_clean, fmt)
                if 1900 <= dt.year <= 2100:
                    return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue

        # Ambiguous formats: mm/dd/yyyy vs dd/mm/yyyy and mm-dd-yyyy vs dd-mm-yyyy
        # Use heuristic: if first number > 12, it must be a day
        slash_match = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$', date_str_clean)
        if slash_match:
            first, second, year = int(slash_match.group(1)), int(slash_match.group(2)), int(slash_match.group(3))
            if 1900 <= year <= 2100:
                if first > 12 and 1 <= second <= 12:
                    # First number can't be a month, so dd/mm/yyyy
                    try:
                        return datetime(year, second, first).strftime('%Y-%m-%d')
                    except ValueError:
                        pass
                elif second > 12 and 1 <= first <= 12:
                    # Second number can't be a day > 12 for month, so mm/dd/yyyy
                    try:
                        return datetime(year, first, second).strftime('%Y-%m-%d')
                    except ValueError:
                        pass
                else:
                    # Ambiguous (both <= 12): try day-first (European) as default for this system
                    try:
                        return datetime(year, second, first).strftime('%Y-%m-%d')
                    except ValueError:
                        try:
                            return datetime(year, first, second).strftime('%Y-%m-%d')
                        except ValueError:
                            pass

        # Regex fallback for embedded dates
        date_pattern = r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})'
        match = re.search(date_pattern, date_str_clean)
        if match:
            year, month, day = match.groups()
            try:
                dt = datetime(int(year), int(month), int(day))
                if 1900 <= dt.year <= 2100:
                    return dt.strftime('%Y-%m-%d')
            except ValueError:
                pass

        logger.debug(f"Could not parse date format: {date_str_clean}")
        return date_str_clean

    except Exception as e:
        logger.debug(f"Error validating date '{date_str}': {e}")
        return str(date_str).strip()


def validate_amount(amount_str: str) -> Optional[float]:
    """
    Validate and parse monetary amounts with European format support.
    Handles:
      - US/UK: 1,234.56
      - European: 1.234,56
      - Space-separated: 1 234.56 or 1 234,56
      - Parenthetical negatives: (1,234.56)
      - Currency symbols: $, €, £, ¥, CHF, etc.
    Returns float or None
    """
    try:
        cleaned = str(amount_str).strip()

        # Detect and handle parenthetical negatives: (1,234.56)
        is_negative = False
        if cleaned.startswith('(') and cleaned.endswith(')'):
            is_negative = True
            cleaned = cleaned[1:-1].strip()
        elif cleaned.startswith('-'):
            is_negative = True
            cleaned = cleaned[1:].strip()

        # Remove currency symbols and words
        cleaned = re.sub(r'[$€£¥]', '', cleaned)
        cleaned = re.sub(r'\b(CHF|EUR|USD|GBP|SEK|NOK|DKK)\b', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()

        if not cleaned:
            return None

        # Remove spaces used as thousand separators (e.g., 1 234.56 or 1 234,56)
        cleaned = re.sub(r'(\d)\s+(\d)', r'\1\2', cleaned)

        # Detect European vs US format by looking at last separator
        # European: 1.234,56 (period=thousands, comma=decimal)
        # US/UK: 1,234.56 (comma=thousands, period=decimal)
        has_comma = ',' in cleaned
        has_period = '.' in cleaned

        if has_comma and has_period:
            last_comma = cleaned.rfind(',')
            last_period = cleaned.rfind('.')
            if last_comma > last_period:
                # European: 1.234,56 — period is thousands, comma is decimal
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                # US: 1,234.56 — comma is thousands, period is decimal
                cleaned = cleaned.replace(',', '')
        elif has_comma and not has_period:
            # Could be European decimal (3,50) or US thousands (1,000)
            # If exactly 3 digits after comma, treat as thousands separator
            parts = cleaned.split(',')
            if len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) >= 1:
                # Likely thousands: 1,000
                cleaned = cleaned.replace(',', '')
            else:
                # Likely decimal: 3,50 or 1234,56
                cleaned = cleaned.replace(',', '.')
        # If only period, it's already in standard format

        amount = float(cleaned)
        if is_negative:
            amount = -amount
        return round(amount, 2)

    except (ValueError, TypeError):
        return None


def calculate_extraction_confidence(fields: Dict[str, Any], expected_fields: List[str]) -> float:
    """
    Calculate confidence score based on fields extracted
    """
    if not expected_fields:
        return 0.0

    extracted_count = len([v for v in fields.values() if v is not None])
    confidence = extracted_count / len(expected_fields)

    return round(confidence, 2)


async def extract_entities(text: str, models: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Extract named entities from document text using Llama

    Returns:
        Dictionary with entity types and lists of found entities
    """
    try:
        llama = models.get('llama')
        if llama is None:
            from app.models.loader import load_llama_model
            llama = load_llama_model()
            models['llama'] = llama

        if llama is None:
            return {
                'companies': [],
                'people': [],
                'dates': [],
                'amounts': [],
                'addresses': [],
                'emails': [],
                'phone_numbers': []
            }

        prompt = f"""Extract every named entity from this document text. List ALL companies, people, dates, money amounts, and addresses you find. Do not leave any field empty if the information exists in the text.

Document text:
{text[:3000]}

Extract into this exact JSON format (fill every field):
{{
  "companies": ["every company or organization name"],
  "people": ["every person name mentioned"],
  "dates": ["every date found, in YYYY-MM-DD format"],
  "amounts": ["every money amount as a number"],
  "addresses": ["every physical address"],
  "emails": ["every email address"],
  "phone_numbers": ["every phone number"]
}}

JSON:
{{"""

        # Read entity extraction settings from Control Panel
        from app.api.config_endpoints import get_runtime_config
        config = get_runtime_config()
        entity_tokens = config.get('ENTITY_EXTRACTION_MAX_TOKENS', 800)
        entity_temp = config.get('ENTITY_EXTRACTION_TEMPERATURE', 0.1)
        response = await asyncio.to_thread(
            llama,
            prompt,
            max_tokens=entity_tokens,
            temperature=entity_temp,
            top_p=0.9,
            stop=["}\n\n", "}\n\nNote", "}\n\nThe", "}\n\nExplanation"]
        )

        raw_output = response['choices'][0]['text'].strip()
        logger.info(f"Entity extraction raw output ({len(raw_output)} chars): {raw_output[:500]}")

        # Prompt ended with "{" — prepend it since LLaMA continues after the brace
        raw_output = '{' + raw_output
        
        # Ensure the JSON object is closed (stop sequence consumes the closing brace)
        if raw_output and not raw_output.rstrip().endswith('}'):
            raw_output = raw_output.rstrip() + '}'

        # Parse entities
        entities = parse_extraction_output(raw_output, [
            'companies', 'people', 'dates', 'amounts',
            'addresses', 'emails', 'phone_numbers'
        ])
        
        logger.info(f"Entity extraction parsed {len(entities)} keys: {list(entities.keys())}")

        # Ensure all keys exist with empty lists
        default_entities = {
            'companies': [],
            'people': [],
            'dates': [],
            'amounts': [],
            'addresses': [],
            'emails': [],
            'phone_numbers': []
        }

        # Update with extracted entities, coercing to lists when needed
        for key in default_entities.keys():
            if key in entities:
                val = entities[key]
                if isinstance(val, list):
                    default_entities[key] = val
                elif isinstance(val, str):
                    # Comma-separated string from regex fallback → split into list
                    items = [item.strip().strip('"\'') for item in val.split(',')]
                    default_entities[key] = [item for item in items if item]
                elif val is not None:
                    default_entities[key] = [str(val)]

        logger.info(f"✓ Extracted entities: {sum(len(v) for v in default_entities.values())} total")

        return default_entities

    except Exception as e:
        logger.error(f"Error extracting entities: {e}", exc_info=True)
        return {
            'companies': [],
            'people': [],
            'dates': [],
            'amounts': [],
            'addresses': [],
            'emails': [],
            'phone_numbers': []
        }


async def extract_with_prompt(
    text: str,
    doc_type: str,
    models: Dict[str, Any],
    prompt_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract structured data using dynamic prompt from Control Panel
    
    Args:
        text: Document text content
        doc_type: Document type
        models: Loaded models dictionary
        prompt_data: Prompt configuration from Control Panel with:
            - prompt: Prompt text with variables already replaced
            - llm_config: LLM configuration (maxTokens, temperature, etc.)
            - metadata: Prompt metadata
    
    Returns:
        Dictionary with extracted fields and metadata
    """
    try:
        # Get Llama model
        llama = models.get('llama')
        if llama is None:
            from app.models.loader import load_llama_model
            llama = load_llama_model()
            models['llama'] = llama

        if llama is None:
            logger.error("Llama model not available for extraction")
            return {
                'success': False,
                'error': 'Llama model not available',
                'extracted_fields': {},
                'prompt_used': prompt_data['metadata']['name']
            }

        # Get LLM config from prompt
        llm_config = prompt_data.get('llm_config', {})
        max_tokens = llm_config.get('maxTokens', 500)
        temperature = llm_config.get('temperature', 0.1)
        top_p = llm_config.get('topP', 0.9)
        top_k = llm_config.get('topK', 40)
        
        prompt_text = prompt_data['prompt']
        
        logger.info(f"Extracting with prompt '{prompt_data['metadata']['name']}' "
                   f"(maxTokens={max_tokens}, temp={temperature})")
        
        # Generate extraction
        try:
            response = await asyncio.to_thread(
                llama,
                prompt_text,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                stop=llm_config.get('stopSequences', []),
                echo=False
            )
            
            generated_text = response.get('choices', [{}])[0].get('text', '').strip()
            
            # Try to parse as JSON
            try:
                # Clean response - remove markdown formatting if present
                cleaned = generated_text
                if '```json' in cleaned:
                    cleaned = cleaned.split('```json')[1].split('```')[0].strip()
                elif '```' in cleaned:
                    cleaned = cleaned.split('```')[1].split('```')[0].strip()
                
                # Add opening brace if prompt ended with it
                if not cleaned.startswith('{'):
                    cleaned = '{' + cleaned
                
                extracted_data = json.loads(cleaned)
                
                logger.info(f"✓ Successfully extracted {len(extracted_data)} fields using dynamic prompt")
                
                return {
                    'success': True,
                    'extracted_fields': extracted_data,
                    'prompt_used': prompt_data['metadata']['name'],
                    'prompt_priority': prompt_data['metadata']['priority'],
                    'company_specific': prompt_data['metadata']['company_specific'],
                    'confidence': 'high',
                    'llm_config_used': {
                        'maxTokens': max_tokens,
                        'temperature': temperature
                    }
                }
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from prompt response: {e}")
                logger.debug(f"Raw response: {generated_text}")
                
                # Return raw text if JSON parsing fails
                return {
                    'success': False,
                    'error': f'JSON parsing failed: {str(e)}',
                    'raw_response': generated_text,
                    'extracted_fields': {},
                    'prompt_used': prompt_data['metadata']['name']
                }
                
        except Exception as llm_error:
            logger.error(f"LLM generation error: {llm_error}")
            return {
                'success': False,
                'error': f'LLM error: {str(llm_error)}',
                'extracted_fields': {},
                'prompt_used': prompt_data['metadata']['name']
            }
            
    except Exception as e:
        logger.error(f"Error in extract_with_prompt: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'extracted_fields': {},
            'prompt_used': prompt_data['metadata'].get('name', 'unknown')
        }
