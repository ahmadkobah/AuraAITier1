"""
Table Extraction Service using PaddleOCR PPStructure
Detects and extracts tables from scanned documents
Enhanced with LLaMA validation for improved accuracy
"""

import logging
import cv2
import json
import numpy as np
import os
import requests
from typing import Dict, List, Any, Optional

logger = logging.getLogger("table_extraction")

# Global table extraction engine (lazy loaded)
_table_engine = None
_is_v3 = False  # Track which version we're using


def get_table_engine():
    """Get or initialize the PPStructure engine for table extraction"""
    global _table_engine, _is_v3
    
    if _table_engine is None:
        try:
            logger.info("Initializing PPStructure for table extraction...")
            
            # Try PPStructureV3 first (newer API)
            try:
                from paddleocr import PPStructureV3
                _table_engine = PPStructureV3(
                    use_table_recognition=True,
                    use_seal_recognition=False,
                    use_formula_recognition=False,
                    use_chart_recognition=False,
                    lang='en'
                )
                _is_v3 = True
                logger.info("✓ PPStructureV3 initialized successfully (table recognition enabled)")
            except (ImportError, RuntimeError) as e:
                logger.warning(f"PPStructureV3 unavailable: {e}")
                
                # Fallback to legacy PPStructure
                try:
                    from paddleocr import PPStructure
                    use_gpu = os.environ.get('USE_GPU', 'false').lower() == 'true'
                    _table_engine = PPStructure(
                        show_log=False,
                        recovery=True,
                        use_gpu=use_gpu
                    )
                    _is_v3 = False
                    logger.info(f"✓ PPStructure (legacy) initialized (GPU: {use_gpu})")
                except Exception as legacy_e:
                    logger.warning(f"Legacy PPStructure also unavailable: {legacy_e}")
                    logger.info("Will use LLaMA text-based table extraction as fallback")
                    _table_engine = None
                
        except Exception as e:
            logger.warning(f"PPStructure not available: {e}")
            logger.info("Will use LLaMA text-based table extraction as fallback")
            _table_engine = None
    
    return _table_engine


def run_table_engine(engine, img):
    """Run table extraction engine with correct API for version"""
    global _is_v3
    
    if _is_v3:
        # PPStructureV3 uses .predict() and returns generator
        results = []
        for result in engine.predict(img, use_table_recognition=True):
            # V3 returns dict with 'layout_det_res' containing detected regions
            if isinstance(result, dict):
                layout = result.get('layout_det_res', {})
                boxes = layout.get('boxes', [])
                for box_info in boxes:
                    if box_info.get('label', '').lower() == 'table':
                        # Extract table info
                        table_result = {
                            'type': 'table',
                            'bbox': box_info.get('coordinate', box_info.get('bbox', [])),
                            'score': box_info.get('score', 0.0),
                            'res': {'html': box_info.get('table_html', box_info.get('html', ''))}
                        }
                        results.append(table_result)
                
                # Also check table_res_list directly
                table_res = result.get('table_res_list', [])
                for table in table_res:
                    results.append({
                        'type': 'table',
                        'bbox': table.get('bbox', []),
                        'score': table.get('score', 0.9),
                        'res': {'html': table.get('html', '')}
                    })
        return results
    else:
        # Legacy PPStructure is callable directly
        return engine(img)


def extract_tables_from_image(image_path: str, use_llama_validation: bool = True) -> List[Dict[str, Any]]:
    """
    Extract tables from a single image using PPStructure with optional LLaMA validation
    
    Args:
        image_path: Path to image file
        use_llama_validation: Whether to validate tables with LLaMA (default: True)
        
    Returns:
        List of extracted tables with structure and data
    """
    try:
        engine = get_table_engine()
        if engine is None:
            logger.warning("Table engine not available, skipping extraction")
            return []
        
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Failed to read image: {image_path}")
            return []
        
        # Run PPStructure (handles V3 vs legacy API)
        result = run_table_engine(engine, img)
        
        tables = []
        table_count = 0
        
        for item in result:
            if item['type'] == 'table':
                table_count += 1
                
                # Extract table structure
                table_info = {
                    'table_id': table_count,
                    'bbox': item.get('bbox', []),  # [x1, y1, x2, y2]
                    'confidence': float(item.get('score', 0.0)),
                    'html': item.get('res', {}).get('html', ''),
                    'rows': [],
                    'structure': {}
                }
                
                # Parse HTML table to extract cell data
                html_content = table_info['html']
                if html_content:
                    table_data = parse_html_table(html_content)
                    table_info['rows'] = table_data['rows']
                    table_info['structure'] = {
                        'num_rows': table_data['num_rows'],
                        'num_cols': table_data['num_cols']
                    }
                
                # Validate with LLaMA if enabled
                if use_llama_validation and table_info['rows']:
                    logger.info(f"🤖 Validating table {table_count} with LLaMA...")
                    table_info = validate_table_with_llama(table_info)
                
                tables.append(table_info)
                logger.info(f"✓ Extracted table {table_count}: {table_info['structure']}")
        
        logger.info(f"✓ Total tables extracted from image: {len(tables)}")
        return tables
        
    except Exception as e:
        logger.error(f"Error extracting tables from image: {e}", exc_info=True)
        return []


def validate_table_with_llama(table_data: Dict[str, Any], ocr_text: str = "") -> Dict[str, Any]:
    """
    Use LLaMA to validate and enhance extracted table data
    
    Args:
        table_data: Extracted table data from PPStructure
        ocr_text: Optional OCR text context for validation
        
    Returns:
        Enhanced table data with LLaMA validation
    """
    try:
        llamafile_url = os.getenv('LLAMAFILE_URL', 'http://localhost:8080')
        
        # Build prompt for table validation
        rows_text = "\n".join([" | ".join(row) for row in table_data.get('rows', [])])
        
        prompt = f"""You are a table validation expert. Analyze this extracted table data and validate/correct it.

Extracted Table ({table_data.get('structure', {}).get('num_rows', 0)} rows × {table_data.get('structure', {}).get('num_cols', 0)} cols):
{rows_text}

Context (if available):
{ocr_text[:500] if ocr_text else "No context provided"}

Tasks:
1. Verify the table structure (correct number of rows and columns)
2. Check if header row is correctly identified
3. Validate data consistency (numbers, currencies, calculations)
4. Fix any obvious OCR errors in cell values
5. Ensure proper alignment of data

Provide a JSON response:
{{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "corrections": [
        {{"row": 0, "col": 0, "original": "...", "corrected": "...", "reason": "..."}}
    ],
    "warnings": ["list of validation warnings"],
    "enhanced_rows": [["corrected", "table", "data"], ...]
}}

Respond ONLY with valid JSON."""

        # Read table extraction settings from Control Panel
        from app.api.config_endpoints import get_runtime_config
        config = get_runtime_config()
        table_temp = config.get('TABLE_EXTRACTION_TEMPERATURE', 0.2)
        table_tokens = config.get('TABLE_EXTRACTION_MAX_TOKENS', 1500)
        table_timeout = config.get('TABLE_EXTRACTION_TIMEOUT', 60)
        
        response = requests.post(
            f'{llamafile_url}/completion',
            json={
                'prompt': prompt,
                'temperature': table_temp,  # Read from Control Panel
                'max_tokens': table_tokens,  # Read from Control Panel
                'stop': ['\n\nExtracted', '\n\nYou are']
            },
            timeout=table_timeout  # Read from Control Panel
        )
        
        if response.status_code == 200:
            result = response.json()
            llama_output = result.get('content', '').strip()
            
            # Extract JSON
            json_start = llama_output.find('{')
            json_end = llama_output.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                validation = json.loads(llama_output[json_start:json_end])
                
                # Apply corrections if valid
                if validation.get('is_valid') and validation.get('enhanced_rows'):
                    table_data['rows'] = validation['enhanced_rows']
                    table_data['llama_validated'] = True
                    table_data['validation_confidence'] = validation.get('confidence', 0.0)
                    
                    if validation.get('corrections'):
                        logger.info(f"✅ LLaMA applied {len(validation['corrections'])} corrections to table")
                    
                    if validation.get('warnings'):
                        for warning in validation['warnings']:
                            logger.warning(f"⚠️ Table validation: {warning}")
                else:
                    logger.warning("⚠️ LLaMA validation marked table as invalid")
                    table_data['llama_validated'] = False
                
                return table_data
        
        # LLaMA unavailable - return original
        logger.info("📋 LLaMA validation unavailable, using original table data")
        table_data['llama_validated'] = False
        return table_data
        
    except Exception as e:
        logger.warning(f"Error in LLaMA table validation: {e}")
        table_data['llama_validated'] = False
        return table_data


def parse_html_table(html: str) -> Dict[str, Any]:
    """
    Parse HTML table string into structured data
    
    Args:
        html: HTML table string
        
    Returns:
        Dictionary with rows and structure info
    """
    try:
        from html.parser import HTMLParser
        
        class TableParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.rows = []
                self.current_row = []
                self.current_cell = ''
                self.in_table = False
                self.in_row = False
                self.in_cell = False
            
            def handle_starttag(self, tag, attrs):
                if tag == 'table':
                    self.in_table = True
                elif tag == 'tr':
                    self.in_row = True
                    self.current_row = []
                elif tag in ['td', 'th']:
                    self.in_cell = True
                    self.current_cell = ''
            
            def handle_endtag(self, tag):
                if tag == 'table':
                    self.in_table = False
                elif tag == 'tr':
                    self.in_row = False
                    if self.current_row:
                        self.rows.append(self.current_row)
                elif tag in ['td', 'th']:
                    self.in_cell = False
                    self.current_row.append(self.current_cell.strip())
            
            def handle_data(self, data):
                if self.in_cell:
                    self.current_cell += data
        
        parser = TableParser()
        parser.feed(html)
        
        num_rows = len(parser.rows)
        num_cols = max([len(row) for row in parser.rows]) if parser.rows else 0
        
        # Normalize rows to have same number of columns
        normalized_rows = []
        for row in parser.rows:
            while len(row) < num_cols:
                row.append('')
            normalized_rows.append(row)
        
        return {
            'rows': normalized_rows,
            'num_rows': num_rows,
            'num_cols': num_cols
        }
        
    except Exception as e:
        logger.error(f"Error parsing HTML table: {e}")
        return {
            'rows': [],
            'num_rows': 0,
            'num_cols': 0
        }


async def extract_tables_from_pdf_pages(rendered_pages: List[np.ndarray], use_llama_validation: bool = True) -> Dict[int, List[Dict[str, Any]]]:
    """
    Extract tables from all pages of a rendered PDF with optional LLaMA validation
    
    Args:
        rendered_pages: List of page images as numpy arrays
        use_llama_validation: Whether to validate tables with LLaMA (default: True)
        
    Returns:
        Dictionary mapping page numbers to lists of tables
    """
    try:
        engine = get_table_engine()
        if engine is None:
            logger.warning("Table engine not available")
            return {}
        
        page_tables = {}
        
        for page_num, page_img in enumerate(rendered_pages, start=1):
            try:
                # Run PPStructure on page (handles V3 vs legacy API)
                result = run_table_engine(engine, page_img)
                
                tables = []
                for item in result:
                    if item['type'] == 'table':
                        table_info = {
                            'bbox': item.get('bbox', []),
                            'confidence': float(item.get('score', 0.0)),
                            'html': item.get('res', {}).get('html', ''),
                            'rows': [],
                            'structure': {}
                        }
                        
                        # Parse HTML
                        html_content = table_info['html']
                        if html_content:
                            table_data = parse_html_table(html_content)
                            table_info['rows'] = table_data['rows']
                            table_info['structure'] = {
                                'num_rows': table_data['num_rows'],
                                'num_cols': table_data['num_cols']
                            }
                        
                        # Validate with LLaMA if enabled
                        if use_llama_validation and table_info['rows']:
                            logger.info(f"🤖 Validating page {page_num} table with LLaMA...")
                            table_info = validate_table_with_llama(table_info)
                        
                        tables.append(table_info)
                
                if tables:
                    page_tables[page_num] = tables
                    logger.info(f"✓ Page {page_num}: Found {len(tables)} tables")
            
            except Exception as e:
                logger.error(f"Error processing page {page_num}: {e}")
                continue
        
        logger.info(f"✓ Total pages with tables: {len(page_tables)}")
        return page_tables
        
    except Exception as e:
        logger.error(f"Error extracting tables from PDF: {e}", exc_info=True)
        return {}


async def extract_tables_from_text_with_llama(text: str, models: Dict) -> List[Dict[str, Any]]:
    """
    Extract text-formatted tables using LLaMA when visual detection fails
    
    Detects tables formatted with spaces/alignment (e.g., invoice line items)
    that don't have visual borders/cells.
    
    Args:
        text: Full OCR text from document
        models: Dictionary containing LLaMA model instance
        
    Returns:
        List of table dictionaries with rows, structure, and confidence
    """
    try:
        # Check if LLaMA is available
        llamafile_url = os.environ.get('LLAMAFILE_URL', 'http://localhost:8080')
        
        # Read settings from Control Panel
        from app.api.config_endpoints import get_runtime_config
        config = get_runtime_config()
        table_temp = config.get('TABLE_EXTRACTION_TEMPERATURE', 0.2)
        table_tokens = config.get('TABLE_EXTRACTION_MAX_TOKENS', 1500)
        table_timeout = config.get('TABLE_EXTRACTION_TIMEOUT', 60)
        
        prompt = f"""You are a table extraction expert. Analyze the following text and identify any tables formatted with spaces or alignment.

CRITICAL RULES:
1. Look for patterns like:
   - Header rows (Item, Description, Qty, Price, Total, etc.)
   - Data rows with aligned columns (spaces/tabs between values)
   - Repeated structures (multiple rows with similar format)
   - Currency symbols ($, €, etc.)
   - Numeric patterns (quantities, prices, totals)

2. A valid table has:
   - At least 2 columns
   - At least 2 data rows (excluding header)
   - Consistent alignment across rows
   - Clear column boundaries

3. Extract ALL tables found, even if formatting is imperfect

4. Response format (valid JSON only):
{{
    "tables": [
        {{
            "rows": [["Header1", "Header2", ...], ["Row1Col1", "Row1Col2", ...], ...],
            "num_rows": <number>,
            "num_cols": <number>,
            "confidence": <0.0-1.0>,
            "table_type": "invoice_items|price_list|summary|other",
            "description": "Brief description of table content"
        }}
    ]
}}

TEXT TO ANALYZE:
{text[:4000]}

Respond ONLY with valid JSON. If no tables found, return {{"tables": []}}."""

        response = requests.post(
            f'{llamafile_url}/completion',
            json={
                'prompt': prompt,
                'temperature': table_temp,
                'max_tokens': table_tokens,
                'stop': ['\n\nEXTRACTED', '\n\nYou are']
            },
            timeout=table_timeout
        )
        
        if response.status_code != 200:
            logger.warning(f"LLaMA text table extraction failed: {response.status_code}")
            return []
        
        result = response.json()
        llama_output = result.get('content', '').strip()
        
        # Extract JSON
        json_start = llama_output.find('{')
        json_end = llama_output.rfind('}') + 1
        
        if json_start < 0 or json_end <= json_start:
            logger.warning("No valid JSON in LLaMA table extraction response")
            return []
        
        parsed = json.loads(llama_output[json_start:json_end])
        extracted_tables = parsed.get('tables', [])
        
        if not extracted_tables:
            logger.info("LLaMA found no text-formatted tables")
            return []
        
        # Convert to pipeline format
        formatted_tables = []
        for idx, table in enumerate(extracted_tables):
            rows = table.get('rows', [])
            if len(rows) < 2:  # Need at least header + 1 data row
                continue
            
            formatted_table = {
                'rows': rows,
                'num_rows': len(rows),
                'num_cols': len(rows[0]) if rows else 0,
                'confidence': table.get('confidence', 0.8),
                'table_type': table.get('table_type', 'other'),
                'description': table.get('description', f'Text-formatted table {idx + 1}'),
                'source': 'llama_text_extraction',
                'page': 1  # Default to page 1 for text-based extraction
            }
            
            formatted_tables.append(formatted_table)
        
        logger.info(f"✅ LLaMA extracted {len(formatted_tables)} text-formatted tables")
        return formatted_tables
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"LLaMA unavailable for text table extraction: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLaMA table extraction JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Error in text-based table extraction: {e}", exc_info=True)
        return []
