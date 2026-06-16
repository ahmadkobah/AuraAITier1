"""
Pipeline Worker - Main background task for document processing
Orchestrates full AI pipeline: split → classify → embed → detect signatures → summarize

CRASH PREVENTION:
-----------------
This module implements comprehensive error handling to prevent crashes:
- All MongoDB operations wrapped in try-except
- File operations with cleanup in finally blocks
- GPU memory management with OOM recovery
- Input validation before processing
- Graceful degradation when services unavailable
"""

import logging
import os
import asyncio
import requests
import numpy as np
from typing import Dict, Any, Optional, Union
from datetime import datetime
import torch
import tempfile
from bson import ObjectId
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError
from app.api.config_endpoints import get_runtime_config
from app.models.loader import _MAX_GPU_MEMORY_MB

logger = logging.getLogger("pipeline_worker")


def convert_numpy_for_mongodb(obj):
    """
    Recursively convert NumPy types to Python native types for MongoDB/BSON.
    
    MongoDB cannot serialize numpy.float32, numpy.float64, numpy.int32, etc.
    This function ensures all data is JSON/BSON serializable.
    """
    if isinstance(obj, dict):
        return {k: convert_numpy_for_mongodb(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_for_mongodb(item) for item in obj]
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    else:
        return obj


def is_llamafile_healthy() -> bool:
    """
    Check if Llamafile server is responding.
    
    Returns:
        bool: True if LLaMA is healthy, False otherwise
        
    Note:
        Catches all exceptions to prevent crashes if LLaMA is down.
        Logs error only if needed for debugging.
    """
    try:
        from app.api.config_endpoints import get_runtime_config
        config = get_runtime_config()
        health_timeout = config.get('LLAMAFILE_HEALTH_TIMEOUT', 2)
        llamafile_url = os.getenv('LLAMAFILE_URL', 'http://127.0.0.1:8080')
        response = requests.get(f"{llamafile_url}/health", timeout=health_timeout)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        # LLaMA not available - this is expected if not started
        logger.debug(f"LLaMA health check failed: {e}")
        return False
    except Exception as e:
        # Unexpected error - log it
        logger.warning(f"Unexpected error checking LLaMA health: {e}")
        return False


async def run_full_ai_pipeline(
    doc_id: Union[str, ObjectId],
    pdf_file_path: str,
    db_connection,
    models: Dict[str, Any],
    config_override: Optional[Dict[str, Any]] = None
) -> None:
    """
    Full AI pipeline for document processing
    
    Workflow:
    1. Mark document as PROCESSING in MongoDB
    2. Split PDF into logical documents
    3. For each logical document:
       a. Classify document type
       b. Generate embedding for search
       c. Detect signatures/forms
       d. Generate summary using Llama (if available)
    4. Save all results to MongoDB processed_data array
    5. Mark document as COMPLETE
    
    Args:
        doc_id: Document ID in MongoDB
        pdf_file_path: Path to uploaded PDF
        db_connection: MongoDB client
        models: Loaded models dictionary
        config_override: Optional tier/company-specific configuration overrides
        
    Config Priority:
        1. config_override (highest) - Tier/company settings from Control Panel
        2. RUNTIME_CONFIG (medium) - AI Service configuration
        3. Environment defaults (lowest) - .env file settings
    """
    # ========================
    # Input Validation
    # ========================
    # Validate required models are loaded
    required_models = ['paddleocr', 'sentence_transformer_search']
    missing_models = [m for m in required_models if not models.get(m)]
    if missing_models:
        error_msg = f"Required models not loaded: {', '.join(missing_models)}"
        logger.error(error_msg)
        # Update document status in DB before raising
        try:
            db_connection['documents'].update_one(
                {'_id': ObjectId(doc_id) if isinstance(doc_id, str) else doc_id},
                {'$set': {'status': 'FAILED', 'error': error_msg, 'processing_completed': datetime.utcnow()}}
            )
        except Exception as db_err:
            logger.error(f"Failed to update document status: {db_err}")
        raise ValueError(error_msg)
    
    # Validate file exists and is readable
    if not os.path.exists(pdf_file_path):
        error_msg = f"PDF file not found: {pdf_file_path}"
        logger.error(error_msg)
        try:
            db_connection['documents'].update_one(
                {'_id': ObjectId(doc_id) if isinstance(doc_id, str) else doc_id},
                {'$set': {'status': 'FAILED', 'error': error_msg, 'processing_completed': datetime.utcnow()}}
            )
        except Exception as db_err:
            logger.error(f"Failed to update document status: {db_err}")
        raise FileNotFoundError(error_msg)
    
    # Validate file size (prevent OOM on huge files)
    try:
        file_size_mb = os.path.getsize(pdf_file_path) / (1024 * 1024)
        max_size_mb = int(os.getenv('MAX_PDF_SIZE_MB', '200'))
        if file_size_mb > max_size_mb:
            error_msg = f"PDF too large: {file_size_mb:.1f}MB (max: {max_size_mb}MB)"
            logger.error(error_msg)
            try:
                db_connection['documents'].update_one(
                    {'_id': ObjectId(doc_id) if isinstance(doc_id, str) else doc_id},
                    {'$set': {'status': 'FAILED', 'error': error_msg, 'processing_completed': datetime.utcnow()}}
                )
            except Exception as db_err:
                logger.error(f"Failed to update document status: {db_err}")
            raise ValueError(error_msg)
    except OSError as e:
        logger.error(f"Failed to check file size: {e}")
        # Continue anyway - not critical
    
    # Get runtime configuration (can be updated by Control Panel)
    config = get_runtime_config()
    
    # Merge config_override with runtime config (override takes priority)
    if config_override:
        logger.info(f"Applying config override: {list(config_override.keys())}")
        config = {**config, **config_override}
    
    # Pipeline step toggles (all 10 steps - ON by default)
    ENABLE_PDF_SPLITTING = config.get('ENABLE_PDF_SPLITTING', True)
    ENABLE_OCR_VALIDATION = config.get('ENABLE_OCR_VALIDATION', True)
    ENABLE_CLASSIFICATION = config.get('ENABLE_CLASSIFICATION', True)
    ENABLE_SIGNATURE_DETECTION = config.get('ENABLE_SIGNATURE_DETECTION', True)
    ENABLE_SIGNATURE_VALIDATION = config.get('ENABLE_SIGNATURE_VALIDATION', True)
    ENABLE_STRUCTURED_EXTRACTION = config.get('ENABLE_STRUCTURED_EXTRACTION', True)
    ENABLE_ENTITY_EXTRACTION = config.get('ENABLE_ENTITY_EXTRACTION', True)
    ENABLE_SUMMARY = config.get('ENABLE_SUMMARY', True)
    ENABLE_EMBEDDING_GENERATION = config.get('ENABLE_EMBEDDING_GENERATION', True)
    ENABLE_MONGODB_STORAGE = config.get('ENABLE_MONGODB_STORAGE', True)
    
    # ========================
    # Database Connection Setup
    # ========================
    
    def _checkpoint(step_name: str, data: dict = None):
        """Save intermediate checkpoint to MongoDB for crash recovery"""
        try:
            documents_collection.update_one(
                {'_id': doc_id},
                {'$set': {
                    'checkpoint': {
                        'step': step_name,
                        'timestamp': datetime.utcnow(),
                        'data': data or {}
                    }
                }}
            )
            logger.debug(f"Checkpoint: {step_name}")
        except Exception as e:
            logger.warning(f"⚠️ Checkpoint failed at step '{step_name}': {e}")
    
    try:
        db = db_connection
        documents_collection = db['documents']
        
        # Fix: root logger level gets set to WARNING by uvicorn/library imports
        # Restore to INFO so pipeline_worker, extraction, etc. loggers work
        root_logger = logging.getLogger()
        if root_logger.level > logging.INFO:
            root_logger.setLevel(logging.INFO)
        
        logger.info(f"PIPELINE START: doc_id={doc_id}, pdf_file_path={pdf_file_path}")
        
        # Convert doc_id to ObjectId if it's a string
        original_doc_id = doc_id
        if isinstance(doc_id, str):
            try:
                doc_id = ObjectId(doc_id)
            except Exception as e:
                error_msg = f"Invalid document ID format: {doc_id}"
                logger.error(f"{error_msg}: {e}")
                raise ValueError(error_msg)
        
        # ========================
        # Mark Document as Processing
        # ========================
        try:
            result = documents_collection.update_one(
                {'_id': doc_id},
                {
                    '$set': {
                        'status': 'PROCESSING',
                        'processing_started': datetime.utcnow(),
                        'processed_data': [],
                        'error': None  # Clear any previous errors
                    }
                },
                upsert=False  # Don't create if doesn't exist
            )
            
            if result.matched_count == 0:
                error_msg = f"Document {doc_id} not found in database"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            logger.info(f"✓ Marked {doc_id} as PROCESSING")
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            error_msg = f"MongoDB connection failed: {e}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
        except OperationFailure as e:
            error_msg = f"MongoDB operation failed: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Step 1: Split PDF and extract text
        logger.info(f"Step 1: Splitting PDF (ENABLE_PDF_SPLITTING={ENABLE_PDF_SPLITTING})")
        from app.core.classifier import (
            split_pdf_and_find_breaks,
            classify_text
        )
        
        if ENABLE_PDF_SPLITTING:
            # Read similarity threshold from Control Panel config
            similarity_threshold = config.get('SIMILARITY_THRESHOLD', 0.5)
            logger.info(f"Calling split_pdf_and_find_breaks(similarity_threshold={similarity_threshold})")
            logical_documents = split_pdf_and_find_breaks(
                pdf_file_path,
                models,
                similarity_threshold=similarity_threshold
            )
            logger.info(f"✓ Split into {len(logical_documents)} logical documents")
            
            # Don't split small PDFs (≤3 pages) — merge back into one logical document
            # Multi-page invoices/letters are typically 1-3 pages and should stay as one doc
            total_pages = max((d['end_page'] for d in logical_documents), default=0) + 1
            if total_pages <= 3 and len(logical_documents) > 1:
                logger.info(f"  PDF has {total_pages} pages (≤3) with {len(logical_documents)} splits — merging into single document")
                merged_text = "\n\n".join(d['text'] for d in logical_documents)
                first_doc = logical_documents[0]
                last_doc = logical_documents[-1]
                # Merge page images from all logical docs
                merged_pages = []
                merged_pil = []
                for d in logical_documents:
                    merged_pages.extend(d.get('pages', []))
                    merged_pil.extend(d.get('page_images_pil', []))
                # Re-embed the merged text
                search_model = models.get('sentence_transformer_search')
                merged_embedding = (search_model.encode(merged_text, convert_to_tensor=False).tolist()
                                    if search_model and merged_text.strip() else [])
                # Aggregate OCR confidence
                all_confs = [d.get('ocr_confidence', {}) for d in logical_documents]
                avg_conf = sum(c.get('avg_confidence', 0.5) for c in all_confs) / len(all_confs) if all_confs else 0.5
                min_conf = min((c.get('min_confidence', 0.5) for c in all_confs), default=0.5)
                logical_documents = [{
                    'doc_num': 0,
                    'start_page': first_doc['start_page'],
                    'end_page': last_doc['end_page'],
                    'text': merged_text,
                    'page_count': total_pages,
                    'embedding': merged_embedding,
                    'confidence': first_doc.get('confidence', 0.85),
                    'pages': merged_pages,
                    'page_images_pil': merged_pil,
                    'ocr_confidence': {'avg_confidence': avg_conf, 'min_confidence': min_conf}
                }]
                logger.info(f"  ✓ Merged into 1 logical document ({total_pages} pages, {len(merged_text)} chars)")
        else:
            # Treat entire PDF as single document
            logger.info("⏸️ PDF splitting disabled - treating as single document")
            from app.core.classifier import extract_text_basic
            result = extract_text_basic(pdf_file_path, models)
            # extract_text_basic returns a dict {'text': ..., 'ocr_confidence': ...}
            full_text = result['text'] if isinstance(result, dict) else result
            ocr_conf = (result.get('ocr_confidence', {'avg_confidence': 0.5, 'min_confidence': 0.5})
                        if isinstance(result, dict)
                        else {'avg_confidence': 0.5, 'min_confidence': 0.5})
            search_model = models.get('sentence_transformer_search')
            doc_emb = (search_model.encode(full_text, convert_to_tensor=False).tolist()
                       if search_model and full_text.strip() else [])
            logical_documents = [{
                'doc_num': 1,
                'start_page': 0,
                'end_page': 0,
                'page_count': 1,
                'text': full_text,
                'ocr_confidence': ocr_conf,
                'embedding': doc_emb
            }]
        
        _checkpoint('pdf_split', {'doc_count': len(logical_documents)})

        # ========================
        # Get Page Images (reuse from classifier or convert)
        # ========================
        images = None
        
        if ENABLE_PDF_SPLITTING and logical_documents:
            # Reuse PIL images already rendered by split_pdf_and_find_breaks (300 DPI)
            # This avoids a second expensive PDF-to-image conversion
            images = []
            for logical_doc in logical_documents:
                images.extend(logical_doc.get('page_images_pil', []))
            
            if images:
                logger.info(f"✓ Reusing {len(images)} images from classifier (no re-conversion needed)")
            else:
                logger.warning("No PIL images returned from classifier, falling back to conversion")
        
        if not images:
            # Fallback: convert PDF to images (used when splitting is disabled)
            from pdf2image import convert_from_path
            poppler_path = os.getenv('POPPLER_PATH') or None
            
            max_pages = int(os.getenv('MAX_PAGES_PER_DOCUMENT', '50'))
            dpi = int(os.getenv('PDF_CONVERSION_DPI', '200'))
            
            try:
                if poppler_path and os.path.exists(poppler_path):
                    logger.info(f"Using Poppler from: {poppler_path}")
                    images = convert_from_path(
                        pdf_file_path,
                        dpi=dpi,
                        last_page=max_pages,
                        poppler_path=poppler_path
                    )
                else:
                    logger.info("Using Poppler from system PATH")
                    images = convert_from_path(
                        pdf_file_path,
                        dpi=dpi,
                        last_page=max_pages
                    )
                
                if not images:
                    raise ValueError("PDF conversion produced no images")
                    
                logger.info(f"✓ Converted PDF to {len(images)} images (DPI: {dpi}, Max pages: {max_pages})")
                
            except FileNotFoundError as e:
                error_msg = (
                    f"Poppler not found: {e}. "
                    f"Please install Poppler and set POPPLER_PATH environment variable."
                )
                logger.error(error_msg)
                try:
                    documents_collection.update_one(
                        {'_id': doc_id},
                        {'$set': {'status': 'FAILED', 'error': error_msg, 'processing_completed': datetime.utcnow()}}
                    )
                except Exception as db_err:
                    logger.error(f"Failed to update document status: {db_err}")
                raise FileNotFoundError(error_msg)
                
            except MemoryError as e:
                error_msg = f"Out of memory while converting PDF. Try reducing PDF_CONVERSION_DPI or MAX_PAGES_PER_DOCUMENT environment variables."
                logger.error(error_msg)
                try:
                    documents_collection.update_one(
                        {'_id': doc_id},
                        {'$set': {'status': 'FAILED', 'error': error_msg, 'processing_completed': datetime.utcnow()}}
                    )
                except Exception as db_err:
                    logger.error(f"Failed to update document status: {db_err}")
                raise MemoryError(error_msg)
                
            except Exception as e:
                error_msg = f"PDF conversion failed: {str(e)}"
                logger.error(error_msg, exc_info=True)
                try:
                    documents_collection.update_one(
                        {'_id': doc_id},
                        {'$set': {'status': 'FAILED', 'error': error_msg, 'processing_completed': datetime.utcnow()}}
                    )
                except Exception as db_err:
                    logger.error(f"Failed to update document status: {db_err}")
                raise
        
        if not images:
            error_msg = "Failed to obtain page images"
            logger.error(error_msg)
            try:
                documents_collection.update_one(
                    {'_id': doc_id},
                    {'$set': {'status': 'FAILED', 'error': error_msg, 'processing_completed': datetime.utcnow()}}
                )
            except Exception as db_err:
                logger.error(f"Failed to update document status: {db_err}")
            raise ValueError(error_msg)
        
        _checkpoint('images_converted', {'page_count': len(images)})

        # Fix page range for non-split mode (Bug #4 + #7)
        if not ENABLE_PDF_SPLITTING and images and len(logical_documents) == 1:
            logical_documents[0]['end_page'] = len(images) - 1
            logical_documents[0]['page_count'] = len(images)
        
        # ========================
        # Process Each Logical Document
        # ========================
        processed_data = []
        
        for idx, logical_doc in enumerate(logical_documents):
            logger.info(f"Processing logical document {idx + 1}/{len(logical_documents)}")

            doc_text = logical_doc.get('text', '')
            doc_embedding = logical_doc.get('embedding', [])
            
            if not doc_text:
                logger.warning(f"  Logical document {idx + 1} has no text, skipping")
                continue

            # 2a. Smart OCR Validation — routes by PaddleOCR confidence
            # SKIP (≥95%): no validation | LIGHT (75-94%): regex fixes | FULL (50-74%): LLaMA | REVIEW (<50%): TrOCR+LLaMA
            ocr_validation = {'quality_score': 0.9, 'corrections_made': 0, 'issues_found': [], 'routing_tier': 'skipped'}
            ocr_confidence = logical_doc.get('ocr_confidence', None)
            if ENABLE_OCR_VALIDATION and ocr_confidence:
                logger.info(f"  Validating OCR quality (avg={ocr_confidence.get('avg_confidence', 0):.0%}, min={ocr_confidence.get('min_confidence', 0):.0%})...")
                from app.services.ocr_validation import validate_ocr_quality
                ocr_timeout = config.get('OCR_VALIDATION_TIMEOUT', 30)
                try:
                    page_img = None
                    if images:
                        start_p = logical_doc.get('start_page', 0)
                        if start_p < len(images):
                            page_img = images[start_p]
                    ocr_validation = await asyncio.wait_for(
                        validate_ocr_quality(doc_text, models, ocr_confidence, page_image=page_img),
                        timeout=float(ocr_timeout)
                    )
                    routing_tier = ocr_validation.get('routing_tier', 'unknown')
                    logger.info(f"  OCR validation tier: {routing_tier}, corrections: {ocr_validation.get('corrections_made', 0)}")
                    # Use corrected text if quality improved
                    if ocr_validation.get('corrections_made', 0) > 0 and ocr_validation.get('corrected_text'):
                        doc_text = ocr_validation['corrected_text']
                        logger.info(f"  ✓ Applied {ocr_validation['corrections_made']} OCR corrections")
                except asyncio.TimeoutError:
                    logger.warning(f"  OCR validation timed out after {ocr_timeout}s, using default")
                    ocr_validation = {'quality_score': 0.5, 'corrections_made': 0, 'issues_found': ['Validation timeout'], 'routing_tier': 'timeout'}
            elif not ENABLE_OCR_VALIDATION:
                logger.info("  ⏭️ OCR validation disabled")
            else:
                logger.info("  ⏭️ OCR validation skipped (no confidence data)")

            # 2b. Classify with Llama Reasoning (optional based on config)
            if ENABLE_CLASSIFICATION:
                logger.info("  Classifying document...")
                initial_classification = classify_text(doc_text, models)

                # Add reasoning to classification
                from app.core.classifier import classify_with_reasoning
                
                # Get timeout from config
                classification_timeout = config.get('CLASSIFICATION_TIMEOUT', 45)
                
                try:
                    classification = await asyncio.wait_for(
                        classify_with_reasoning(doc_text, models, initial_classification),
                        timeout=float(classification_timeout)
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"  Classification timed out after {classification_timeout}s, using initial classification")
                    classification = initial_classification
            else:
                logger.info("  ⏸️ Classification disabled - using 'unknown' type")
                classification = {
                    'label': 'unknown',
                    'confidence': 0.0,
                    'reasoning': 'Classification disabled in configuration'
                }
            
            # 2b. Embedding already computed in document_splitter
            
            # Log memory usage for monitoring
            if torch.cuda.is_available():
                from app.models.loader import get_gpu_memory_usage
                gpu_mem = get_gpu_memory_usage()
                logger.info(f"  GPU memory usage: {gpu_mem:.1f} MB")
                if gpu_mem > _MAX_GPU_MEMORY_MB * 0.9:  # 90% threshold
                    logger.warning(f"  ⚠️ GPU memory high ({gpu_mem:.1f} MB), clearing cache")
                    torch.cuda.empty_cache()
            
            # 2b. Detect signatures via text pattern matching in OCR output
            signature_found = False
            signature_text = ""
            signature_box = None
            signature_boxes = []
            signature_confidence = 0.0
            sig_validation = None

            if ENABLE_SIGNATURE_DETECTION and doc_text:
                logger.info("  Detecting signatures...")
                import re
                # Common signature indicators in OCR text
                sig_patterns = [
                    r'(?:Authorized\s+)?Signature[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                    r'Signed\s*(?:by)?[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                    r'Name[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:\s+Terms|\s+Payment|\s*$)',
                    r'(?:Invoice\s+)?Total\s+([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)\s+Terms',
                ]
                
                for pattern in sig_patterns:
                    match = re.search(pattern, doc_text, re.IGNORECASE)
                    if match:
                        potential_sig = match.group(1).strip()
                        # Validate it looks like a name (2-4 words, proper case)
                        words = potential_sig.split()
                        if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                            signature_found = True
                            signature_text = potential_sig
                            signature_confidence = 0.6
                            logger.info(f"  ✓ Text-based signature found: '{signature_text}'")
                            break
            
                # 2c. Validate signature with Llama (if found and enabled, with timeout)
                if ENABLE_SIGNATURE_VALIDATION and signature_found and signature_text:
                    logger.info("  Validating signature...")
                    from app.services.signature_validation import validate_signature_text
                    try:
                        sig_validation = await asyncio.wait_for(
                            validate_signature_text(signature_text, doc_text, models),
                            timeout=30.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning("  Signature validation timed out after 30s")
                        sig_validation = {'validation_status': 'timeout', 'is_valid': False, 'corrected_signature': signature_text, 'confidence': signature_confidence}

                    # Use corrected signature if validation improved it
                    corrected_sig = sig_validation.get('corrected_signature', signature_text)
                    if corrected_sig != signature_text:
                        logger.info(f"  ✓ Signature corrected: '{signature_text}' → '{corrected_sig}'")
                        signature_text = corrected_sig
                        signature_confidence = sig_validation.get('confidence', signature_confidence)
                elif signature_found and not ENABLE_SIGNATURE_VALIDATION:
                    logger.info("  ⏸️ Signature validation disabled - skipping")

            # 2d/2e/2f. Run independent LLaMA steps IN PARALLEL
            # Structured extraction, entity extraction, table extraction, and summary
            # all only need doc_text — no dependencies between them.
            from app.utils.extraction import extract_structured_data, extract_entities

            async def _do_structured_extraction():
                if not ENABLE_STRUCTURED_EXTRACTION:
                    return {'success': False, 'extracted_fields': {}}
                logger.info("  Extracting structured data...")
                doc_type = classification.get('label', 'unknown')
                try:
                    return await asyncio.wait_for(
                        extract_structured_data(doc_text, doc_type, models),
                        timeout=60.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("  Structured data extraction timed out after 60s")
                    return {'success': False, 'extracted_fields': {}, 'error': 'timeout'}

            async def _do_entity_extraction():
                if not ENABLE_ENTITY_EXTRACTION:
                    return {'companies': [], 'people': [], 'dates': [], 'amounts': [], 'addresses': [], 'emails': [], 'phone_numbers': []}
                logger.info("  Extracting entities...")
                try:
                    return await asyncio.wait_for(
                        extract_entities(doc_text, models),
                        timeout=45.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("  Entity extraction timed out after 45s")
                    return {'companies': [], 'people': [], 'dates': [], 'amounts': [], 'addresses': [], 'emails': [], 'phone_numbers': [], 'error': 'timeout'}

            async def _do_table_extraction():
                # PPStructure  Line Items (OCR + frontend parser) 
                logger.info("   Table extraction (PPStructure)  Line Items ")
                return []

            async def _do_summary():
                if not ENABLE_SUMMARY:
                    logger.info("   Summary generation disabled")
                    return ""
                logger.info("  Generating summary...")
                if is_llamafile_healthy():
                    try:
                        _summary = await asyncio.wait_for(
                            generate_summary(doc_text, models),
                            timeout=60.0
                        )
                        if not is_llamafile_healthy():
                            logger.warning("  Llamafile crashed during generation, using fallback")
                            return doc_text[:500] + "..." if len(doc_text) > 500 else doc_text
                        return _summary
                    except asyncio.TimeoutError:
                        logger.warning("  Summary generation timed out after 60s, using fallback")
                        return doc_text[:500] + "..." if len(doc_text) > 500 else doc_text
                    except (ValueError, RuntimeError, ConnectionError) as e:
                        logger.warning(f"  Summary generation failed: {e}, rechecking Llamafile...")
                        if not is_llamafile_healthy():
                            logger.error("  Llamafile crashed or disconnected")
                        return doc_text[:500] + "..." if len(doc_text) > 500 else doc_text
                else:
                    logger.warning("  Llamafile not healthy, using text fallback for summary")
                    return doc_text[:500] + "..." if len(doc_text) > 500 else doc_text

            # Run all 4 independent steps in parallel
            logger.info("  Running extraction + summary steps in parallel...")
            structured_extraction, entities, tables, summary = await asyncio.gather(
                _do_structured_extraction(),
                _do_entity_extraction(),
                _do_table_extraction(),
                _do_summary(),
            )

            # Enrich entities from structured data extraction
            # LLaMA 3B entity extraction is unreliable — structured extraction is much more accurate
            # Strategy: start fresh from structured data, then add unique LLaMA items that pass filters
            if structured_extraction.get('success') and structured_extraction.get('extracted_fields'):
                fields = structured_extraction['extracted_fields']
                llama_entities = entities if isinstance(entities, dict) else {}
                entities = {'companies': [], 'people': [], 'dates': [], 'amounts': [], 'addresses': [], 'emails': [], 'phone_numbers': []}

                def _add_unique(key, value):
                    if value and str(value).strip() and str(value).lower() not in ('null', 'none', 'n/a', 'not found', ''):
                        val_str = str(value).strip()
                        existing = [str(v).strip().lower() for v in entities.get(key, [])]
                        if val_str.lower() not in existing:
                            entities[key].append(val_str)

                # 1) Populate from structured data (high reliability)
                for f in ('vendor_name', 'company_name', 'merchant_name',
                          'sender_company', 'recipient_company', 'party_a', 'party_b',
                          'bank_name', 'employer_name', 'issuing_authority'):
                    _add_unique('companies', fields.get(f))

                for f in ('sender', 'recipient', 'customer_name', 'employee_name', 'account_name',
                          'proposer', 'insured_name'):
                    _add_unique('people', fields.get(f))

                for f in ('invoice_date', 'due_date', 'date', 'contract_date', 'effective_date',
                          'expiration_date', 'issue_date', 'start_date', 'end_date',
                          'delivery_date', 'payment_date'):
                    _add_unique('dates', fields.get(f))

                for f in ('total_amount', 'subtotal', 'tax_amount', 'amount',
                          'contract_value', 'premium_amount', 'net_salary', 'gross_salary'):
                    val = fields.get(f)
                    if val is not None:
                        _add_unique('amounts', val)

                for f in ('vendor_address', 'customer_address', 'merchant_address',
                          'delivery_address', 'address'):
                    _add_unique('addresses', fields.get(f))

                # 2) Add LLaMA entities only if they look valid and aren't duplicates
                # Known people/companies from structured data (for cross-check)
                known_names = set()
                for v in entities['companies'] + entities['people']:
                    known_names.add(v.lower())

                # 2) Add LLaMA entities ONLY when structured extraction has low confidence
                # High-confidence structured data is the single source of truth
                extraction_conf = structured_extraction.get('extraction_confidence', 0.0)
                if extraction_conf < 0.5:
                    logger.info(f"  Structured confidence {extraction_conf:.0%} < 50% — merging LLaMA entities")
                    for comp in llama_entities.get('companies', []):
                        c = str(comp).strip()
                        if len(c) > 2 and not c.replace('.', '').replace(',', '').replace(' ', '').isdigit():
                            _add_unique('companies', c)
                    for person in llama_entities.get('people', []):
                        _add_unique('people', person)
                    for date in llama_entities.get('dates', []):
                        _add_unique('dates', date)
                    structured_amt_strs = [str(v).strip() for v in entities.get('amounts', [])]
                    for amt in llama_entities.get('amounts', []):
                        amt_s = str(amt).strip()
                        try:
                            amt_val = float(amt_s.replace(',', ''))
                            if amt_val < 10:
                                continue
                            if any(amt_s in sa and amt_s != sa for sa in structured_amt_strs):
                                continue
                        except (ValueError, TypeError):
                            pass
                        _add_unique('amounts', amt)
                    for addr in llama_entities.get('addresses', []):
                        a = str(addr).strip()
                        if len(a) > 5:
                            _add_unique('addresses', a)
                else:
                    logger.info(f"  Structured confidence {extraction_conf:.0%} ≥ 50% — skipping LLaMA entities (structured data is source of truth)")

                # 3) Regex extraction for emails & phones (LLaMA misses these)
                import re as _re
                for email_match in _re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', doc_text[:5000]):
                    _add_unique('emails', email_match)
                for phone_match in _re.findall(r'(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}', doc_text[:5000]):
                    _add_unique('phone_numbers', phone_match)

                # 4) Cross-clean: remove people names from companies list
                people_lower = {str(p).strip().lower() for p in entities.get('people', [])}
                entities['companies'] = [c for c in entities['companies'] if str(c).strip().lower() not in people_lower]

                # 5) Address deduplication: remove fragments that are substrings of longer addresses
                addrs = entities.get('addresses', [])
                if len(addrs) > 1:
                    deduped = []
                    for addr in addrs:
                        # Keep only if no other address contains this one as a substring
                        if not any(addr.lower() in other.lower() and addr.lower() != other.lower() for other in addrs):
                            deduped.append(addr)
                    if len(deduped) < len(addrs):
                        logger.info(f"  Deduplicated addresses: {len(addrs)} → {len(deduped)}")
                    entities['addresses'] = deduped

                enriched_count = sum(len(v) for v in entities.values())
                if enriched_count > 0:
                    logger.info(f"  ✓ Enriched entities from structured data: {enriched_count} total")

            # Build template summary from extracted fields (zero hallucination)
            # Replaces LLaMA summary when structured data is available
            if structured_extraction.get('success') and structured_extraction.get('extracted_fields'):
                fields = structured_extraction['extracted_fields']
                doc_label = classification.get('label', 'Document')
                parts = []
                # Build from extracted fields
                if fields.get('vendor_name') or fields.get('sender') or fields.get('company_name'):
                    who = fields.get('vendor_name') or fields.get('sender') or fields.get('company_name') or fields.get('proposer', '')
                    parts.append(f"{doc_label} from {who}")
                else:
                    parts.append(doc_label)
                if fields.get('customer_name') or fields.get('recipient') or fields.get('employee_name'):
                    to_whom = fields.get('customer_name') or fields.get('recipient') or fields.get('employee_name', '')
                    parts.append(f"to {to_whom}")
                if fields.get('total_amount') or fields.get('amount') or fields.get('contract_value'):
                    amt = fields.get('total_amount') or fields.get('amount') or fields.get('contract_value', '')
                    currency = fields.get('currency', '')
                    parts.append(f"for {currency} {amt}".strip() if currency else f"for {amt}")
                date_val = fields.get('invoice_date') or fields.get('date') or fields.get('contract_date', '')
                if date_val:
                    parts.append(f"dated {date_val}")
                due = fields.get('due_date') or fields.get('expiration_date', '')
                if due:
                    parts.append(f"due {due}")
                ref = fields.get('invoice_number') or fields.get('contract_number') or fields.get('receipt_number') or fields.get('po_number', '')
                if ref:
                    parts.append(f"(Ref: {ref})")
                template_summary = ", ".join(parts) + "."
                if len(template_summary) > 20:  # Only use if meaningful
                    summary = template_summary
                    logger.info(f"  ✓ Built template summary from extracted fields ({len(summary)} chars)")

            # Store processed document with ALL enhancements
            processed_doc = {
                'logical_doc_num': logical_doc.get('doc_num', idx + 1),
                'page_range': f"{logical_doc.get('start_page', 1)}-{logical_doc.get('end_page', 1)}",
                'page_count': logical_doc.get('page_count', 1),
                'text': doc_text[:2000] + "..." if len(doc_text) > 2000 else doc_text,
                'full_text': doc_text,  # Store full text for Q&A
                'embedding': doc_embedding,

                # Enhanced Classification with Reasoning
                'classification': classification,

                # OCR Quality Validation
                'ocr_validation': {
                    'quality_score': ocr_validation.get('quality_score', 0.0),
                    'corrections_made': ocr_validation.get('corrections_made', 0),
                    'issues_found': ocr_validation.get('issues_found', [])
                },

                # Signature Detection & Validation
                'signature_detected': signature_found,
                'signature_confidence': signature_confidence,
                'signature_text': signature_text,
                'signature_box': signature_box,
                'signature_boxes': signature_boxes,
                'signature_validation': sig_validation if signature_found else None,

                # Structured Data Extraction
                'structured_data': structured_extraction.get('extracted_fields', {}),
                'extraction_confidence': structured_extraction.get('extraction_confidence', 0.0),

                # Entity Recognition
                'entities': entities,

                # Table Extraction 
                'tables': [],
                'table_count': 0,

                # Summary
                'summary': summary,
                'processed_at': datetime.utcnow().isoformat()
            }

            processed_data.append(processed_doc)
        
        # Step 3: Save results to MongoDB (optional based on config)
        if ENABLE_MONGODB_STORAGE:
            logger.info(f"Saving {len(processed_data)} processed documents to MongoDB...")
            
            # Convert any NumPy types to Python native for MongoDB compatibility
            processed_data_clean = convert_numpy_for_mongodb(processed_data)
            
            documents_collection.update_one(
                {'_id': doc_id},
                {
                    '$set': {
                        'status': 'COMPLETE',
                        'processed_data': processed_data_clean,
                        'processing_completed': datetime.utcnow(),
                        'document_count': len(
                            processed_data_clean) if processed_data_clean else 0,
                        'error': None
                    }
                }
            )
        else:
            logger.info("⏸️ MongoDB storage disabled - results not saved")
            # Still mark as complete but don't save processed_data
            documents_collection.update_one(
                {'_id': doc_id},
                {
                    '$set': {
                        'status': 'COMPLETE',
                        'processing_completed': datetime.utcnow(),
                        'error': None
                    }
                }
            )
        
        logger.info(f"✓ Pipeline complete for {doc_id}")
        
        # Invalidate FAISS index so next search includes this document
        try:
            from app.utils.vector_index import invalidate as invalidate_faiss
            invalidate_faiss()
        except Exception:
            pass  # Non-critical
        
    except Exception as e:
        logger.error(f"Error in pipeline for {doc_id}: {e}", exc_info=True)
        
        # Mark as failed
        try:
            # Convert doc_id to ObjectId if it's a string
            try:
                obj_id = ObjectId(doc_id) if isinstance(doc_id, str) else doc_id
            except Exception:
                obj_id = doc_id  # Use string _id directly
            
            # Get database collection (db is defined at start of function)
            db = db_connection
            documents_collection = db['documents']
            documents_collection.update_one(
                {'_id': obj_id},
                {
                    '$set': {
                        'status': 'FAILED',
                        'error': str(e),
                        'processing_completed': datetime.utcnow()
                    }
                }
            )
        except (ValueError, RuntimeError, ConnectionError) as db_error:
            logger.error(f"Failed to mark document as failed: {db_error}")
    finally:
        # Resource cleanup: close PIL images and release GPU memory
        try:
            if 'images' in locals() and images is not None:
                for img in images:
                    try:
                        img.close()
                    except Exception:
                        pass
                del images
            # Release GPU memory
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            # Clean up temp files for this document
            try:
                cleanup_temp_files(str(original_doc_id) if 'original_doc_id' in locals() else str(doc_id))
            except Exception:
                pass
        except Exception as cleanup_err:
            logger.warning(f"Resource cleanup error: {cleanup_err}")


async def generate_summary(text: str, models: Dict[str, Any]) -> str:
    """
    Generate document summary using Llama model
    Falls back to simple text truncation if Llama unavailable
    
    Args:
        text: Document text to summarize
        models: Loaded models dictionary
        
    Returns:
        Summary string (max 500 chars)
    """
    try:
        # Check if Llama is available
        if models.get('llama') is None:
            logger.info("Llama not available, using fallback summary")
            # Simple fallback: first N sentences
            sentences = text.split('. ')
            fallback = '. '.join(sentences[:3]) + ('.' if sentences else '')
            return fallback[:500]
        
        # Load Llama if not already loaded
        from app.models.loader import load_llama_model
        llama = models.get('llama')
        
        if llama is None:
            llama = load_llama_model()
            models['llama'] = llama
        
        if llama is None:
            # Fallback if loading failed
            sentences = text.split('. ')
            fallback = '. '.join(sentences[:3]) + ('.' if sentences else '')
            return fallback[:500]
        
        # Prepare prompt
        text_input = text[:1500]  # Limit input to avoid token overflow
        prompt = (
            "You are a document summarization assistant. "
            "Summarize ONLY the information that appears in the document below. "
            "Do not add any details, names, dates, or amounts that are not explicitly stated in the text.\n\n"
            f"Document text:\n{text_input}\n\n"
            "Summary (2-3 sentences, facts only):"
        )
        
        # Generate summary with Control Panel settings
        logger.info("Generating summary with Llama...")
        from app.api.config_endpoints import get_runtime_config
        config = get_runtime_config()
        llama_temp = config.get('LLAMA_TEMPERATURE', 0.3)
        llama_tokens = config.get('LLAMA_MAX_TOKENS', 512)
        response = await asyncio.to_thread(
            llama, prompt,
            max_tokens=llama_tokens,  # Read from Control Panel
            temperature=llama_temp,  # Read from Control Panel
            top_p=0.9
        )
        
        summary = response['choices'][0]['text'].strip()
        logger.info(f"✓ Generated summary ({len(summary)} chars)")
        
        return summary[:500]
        
    except (ValueError, RuntimeError, ConnectionError, KeyError) as e:
        logger.warning(f"Error generating summary: {e}")
        # Return simple fallback
        sentences = text.split('. ')
        fallback = '. '.join(sentences[:3]) + ('.' if sentences else '')
        return fallback[:500]


def cleanup_temp_files(doc_id: str, temp_dir: str = None) -> None:
    """
    Clean up temporary files created during processing
    """
    import shutil
    if temp_dir is None:
        from config.settings import TEMP_DIR
        temp_dir = str(TEMP_DIR)
    doc_temp = os.path.join(temp_dir, f'doc_{doc_id}')
    
    try:
        if os.path.exists(doc_temp):
            shutil.rmtree(doc_temp)
            logger.info(f"Cleaned up temporary files for {doc_id}")
    finally:
        if os.path.exists(doc_temp):
            logger.warning(f"Temp directory still exists after cleanup attempt: {doc_temp}")
