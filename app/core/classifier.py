"""
Document Splitter - Split PDFs into logical documents
Uses PaddleOCR for text extraction and embeddings for break detection
"""

import logging
import os
from typing import List, Dict, Any, Tuple
from PIL import Image
import numpy as np
from pdf2image import convert_from_path
import PyPDF2

logger = logging.getLogger("document_splitter")


def pdf_to_images(pdf_path: str) -> List[Image.Image]:
    """
    Convert PDF to list of PIL Image objects
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        List of PIL Image objects
    """
    logger.info(f"Converting PDF to images: {pdf_path}")
    try:
        # Get poppler path from environment or use default
        poppler_path = os.getenv('POPPLER_PATH', r"C:\Users\Ahmad\poppler\poppler-24.08.0\Library\bin")
        
        # Read OCR DPI from Control Panel config
        from app.api.config_endpoints import get_runtime_config
        runtime_config = get_runtime_config()
        ocr_dpi = runtime_config.get('OCR_DPI', 300)
        
        # Try with explicit poppler_path first
        if os.path.exists(poppler_path):
            logger.debug(f"Using explicit poppler_path: {poppler_path}")
            images = convert_from_path(pdf_path, dpi=ocr_dpi, poppler_path=poppler_path)
        else:
            # Fallback to PATH lookup
            logger.debug("Using poppler from PATH")
            images = convert_from_path(pdf_path, dpi=ocr_dpi)
            
        logger.info(f"✓ Converted {len(images)} pages to images")
        return images
    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}")
        raise


def extract_text_from_image(image: Image.Image, paddleocr, return_confidence: bool = False):
    """
    Extract text from image using PaddleOCR
    
    Args:
        image: PIL Image object
        paddleocr: PaddleOCR instance
        return_confidence: If True, return dict with confidence scores
        
    Returns:
        If return_confidence=False: Extracted text (str) - backward compatible
        If return_confidence=True: Dict with text and confidence scores
    """
    try:
        # Convert PIL image to numpy array
        image_array = np.array(image)
        
        # Run OCR - try both .ocr() and .predict() methods
        try:
            # Try standard .ocr() method first
            if hasattr(paddleocr, 'ocr'):
                # Try with cls parameter, fall back without it
                try:
                    result = paddleocr.ocr(image_array, cls=True)
                except TypeError:
                    # cls parameter not supported in this version
                    result = paddleocr.ocr(image_array)
            elif hasattr(paddleocr, 'predict'):
                result = paddleocr.predict(image_array)
            else:
                logger.error(f"PaddleOCR object has neither .ocr() nor .predict() method. Available methods: {[m for m in dir(paddleocr) if not m.startswith('_')]}")
                return "" if not return_confidence else {'text': '', 'avg_confidence': 0.0, 'min_confidence': 0.0}
        except Exception as ocr_error:
            logger.error(f"OCR call failed: {ocr_error}")
            return "" if not return_confidence else {'text': '', 'avg_confidence': 0.0, 'min_confidence': 0.0}
        
        # Extract text and confidence scores from result
        text_lines = []
        rec_scores = []
        
        if result and len(result) > 0 and result[0]:
            ocr_data = result[0]
            
            # PaddleOCR 3.3.2+ returns OCRResult dict with rec_texts and rec_scores
            if isinstance(ocr_data, dict) and 'rec_texts' in ocr_data:
                text_lines = ocr_data['rec_texts']
                rec_scores = ocr_data.get('rec_scores', [])  # Capture confidence scores
            else:
                # Fallback: old format (list of detections)
                for line in ocr_data:
                    if line and isinstance(line, (list, tuple)) and len(line) >= 2:
                        text_part = line[1]
                        if isinstance(text_part, (list, tuple)) and len(text_part) >= 1:
                            text_lines.append(str(text_part[0]))
                            # Old format: confidence is second element of tuple
                            if len(text_part) >= 2:
                                rec_scores.append(float(text_part[1]))
                        elif isinstance(text_part, str):
                            text_lines.append(text_part)
        
        extracted_text = " ".join(text_lines)
        
        # Calculate confidence metrics
        avg_confidence = sum(rec_scores) / len(rec_scores) if rec_scores else 0.5
        min_confidence = min(rec_scores) if rec_scores else 0.5
        
        # Return based on flag (backward compatible)
        if not return_confidence:
            return extracted_text
        else:
            return {
                'text': extracted_text,
                'avg_confidence': avg_confidence,
                'min_confidence': min_confidence,
                'word_count': len(text_lines)
            }
        
    except Exception as e:
        logger.error(f"❌ EXCEPTION in extract_text_from_image: {e}", exc_info=True)
        return "" if not return_confidence else {'text': '', 'avg_confidence': 0.0, 'min_confidence': 0.0}


def split_pdf_and_find_breaks(
    pdf_path: str,
    models: Dict[str, Any],
    similarity_threshold: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Split PDF into logical documents using embedding similarity
    
    Algorithm:
    1. Convert each page to image
    2. Extract text via PaddleOCR
    3. Embed text with all-MiniLM-L6-v2
    4. Detect significant drops in cosine similarity (document breaks)
    5. Group pages into logical documents
    
    Args:
        pdf_path: Path to PDF file
        models: Dictionary with loaded models
        similarity_threshold: Cosine similarity threshold for document breaks (0-1)
        
    Returns:
        List of logical documents with metadata:
        [
            {
                'doc_num': 1,
                'start_page': 0,
                'end_page': 2,
                'text': 'combined text',
                'page_count': 3,
                'embedding': [...],
                'confidence': 0.92
            },
            ...
        ]
    """
    logger.info(f"Splitting {pdf_path} (threshold: {similarity_threshold})")
    
    # Convert PDF to images
    images = pdf_to_images(pdf_path)
    logger.info(f"Converted {len(images)} pages")
    
    paddleocr = models['paddleocr']
    sentence_transformer = models['sentence_transformer_search']
    
    if paddleocr is None:
        raise ValueError("PaddleOCR model not loaded")
    
    # Extract text, embeddings, and confidence for each page
    page_texts = []
    page_embeddings = []
    page_confidences = []  # Store OCR confidence per page
    
    logger.info(f"Extracting text from {len(images)} pages...")
    for idx, image in enumerate(images):
        ocr_result = extract_text_from_image(image, paddleocr, return_confidence=True)
        text = ocr_result['text']
        page_texts.append(text)
        page_confidences.append({
            'avg_confidence': ocr_result['avg_confidence'],
            'min_confidence': ocr_result['min_confidence']
        })
        if (idx + 1) % 3 == 0:
            logger.info(f"  Progress: {idx + 1}/{len(images)} pages")
        
        if text.strip():
            embedding = sentence_transformer.encode(text, convert_to_tensor=False)
            page_embeddings.append(embedding)
        else:
            # Empty page gets zero embedding
            page_embeddings.append(np.zeros(384))  # all-MiniLM-L6-v2 output size
        
        if (idx + 1) % 5 == 0:
            logger.info(f"  Processed {idx + 1}/{len(images)} pages")
    
    # Detect document breaks using embedding similarity
    document_breaks = [0]  # First page always starts new document
    
    logger.info("Detecting document breaks via embedding similarity...")
    for i in range(1, len(page_embeddings)):
        current = page_embeddings[i]
        previous = page_embeddings[i - 1]
        
        # Cosine similarity
        if np.linalg.norm(current) > 0 and np.linalg.norm(previous) > 0:
            similarity = np.dot(current, previous) / (
                np.linalg.norm(current) * np.linalg.norm(previous)
            )
        else:
            similarity = 0
        
        # Large drop in similarity indicates document break
        if similarity < similarity_threshold:
            document_breaks.append(i)
            logger.debug(f"  Document break detected at page {i} (similarity: {similarity:.3f})")
    
    document_breaks.append(len(page_texts))  # End marker
    
    # Group pages into logical documents
    logical_documents = []
    
    for doc_num, (start_page, end_page) in enumerate(
        zip(document_breaks[:-1], document_breaks[1:])
    ):
        doc_text = " ".join(page_texts[start_page:end_page])
        
        # Embed the combined document
        doc_embedding = sentence_transformer.encode(doc_text, convert_to_tensor=False)
        
        # Extract page images for this logical document (for table extraction)
        doc_page_images = []
        for page_idx in range(start_page, end_page):
            if page_idx < len(images):
                # Convert PIL Image to numpy array for PPStructure
                doc_page_images.append(np.array(images[page_idx]))
        
        # Calculate aggregate OCR confidence for this logical document
        doc_confidences = page_confidences[start_page:end_page]
        if doc_confidences:
            avg_ocr_conf = sum(c['avg_confidence'] for c in doc_confidences) / len(doc_confidences)
            min_ocr_conf = min(c['min_confidence'] for c in doc_confidences)
        else:
            avg_ocr_conf = 0.5
            min_ocr_conf = 0.5
        
        logical_documents.append({
            'doc_num': doc_num,
            'start_page': start_page,
            'end_page': end_page - 1,
            'text': doc_text,
            'page_count': end_page - start_page,
            'embedding': doc_embedding.tolist(),
            'confidence': 0.85,  # Placeholder; could be computed from similarity scores
            'pages': doc_page_images,  # Page images as numpy arrays for table extraction
            'ocr_confidence': {  # NEW: OCR confidence for smart routing
                'avg_confidence': avg_ocr_conf,
                'min_confidence': min_ocr_conf
            }
        })
    
    logger.info(f"✓ Split PDF into {len(logical_documents)} logical documents")
    return logical_documents


def classify_text(
    text: str,
    models: Dict[str, Any],
    candidate_labels: List[str] = None
) -> Dict[str, Any]:
    """
    Classify document text using zero-shot classification
    
    Args:
        text: Document text to classify
        models: Dictionary with loaded models
        candidate_labels: List of possible document types
        
    Returns:
        {
            'label': 'Invoice',
            'score': 0.92,
            'all_scores': {'Invoice': 0.92, 'Report': 0.05, 'Letter': 0.03}
        }
    """
    if not candidate_labels:
        candidate_labels = [
            # Financial Documents (9 types)
            'Invoice',
            'Receipt',
            'Purchase Order',
            'Credit Note',
            'Debit Note',
            'Payment Voucher',
            'Bank Statement',
            'Financial Statement',
            'Tax Document',
            
            # Legal Documents (7 types)
            'Contract',
            'Agreement',
            'Non-Disclosure Agreement',
            'Memorandum of Understanding',
            'Certificate',
            'License',
            'Permit',
            
            # Business Documents (6 types)
            'Report',
            'Business Letter',
            'Memo',
            'Proposal',
            'Quotation',
            'Tender Document',
            
            # Operational Documents (5 types)
            'Form',
            'Delivery Note',
            'Packing Slip',
            'Bill of Lading',
            'Shipping Document',
            
            # HR Documents (3 types)
            'Resume',
            'Job Application',
            'Employment Contract',
            
            # Fallback
            'Other'
        ]
    
    try:
        # Embed text and labels
        sentence_transformer = models['sentence_transformer_classify']
        
        text_embedding = sentence_transformer.encode(text, convert_to_tensor=False)
        label_embeddings = sentence_transformer.encode(
            candidate_labels,
            convert_to_tensor=False
        )
        
        # Compute cosine similarities
        similarities = {}
        text_norm = np.linalg.norm(text_embedding)
        
        for label, label_embedding in zip(candidate_labels, label_embeddings):
            label_norm = np.linalg.norm(label_embedding)
            similarity = np.dot(text_embedding, label_embedding) / (
                text_norm * label_norm + 1e-8
            )
            similarities[label] = float(similarity)
        
        # Normalize to probabilities (softmax)
        max_sim = max(similarities.values())
        similarities_exp = {
            k: float(np.exp(v - max_sim)) for k, v in similarities.items()
        }
        sum_exp = sum(similarities_exp.values())
        # Convert to native Python float for MongoDB/JSON compatibility
        # Note: np.exp returns np.float64, division result also np.float64
        # So we must explicitly convert to Python float
        probabilities = {
            k: float(v / sum_exp) for k, v in similarities_exp.items()
        }
        
        # Get top label
        top_label = max(probabilities, key=probabilities.get)
        top_score = float(probabilities[top_label])
        
        # Get minimum confidence threshold from Control Panel config
        from app.api.config_endpoints import get_runtime_config
        runtime_config = get_runtime_config()
        MIN_CONFIDENCE_THRESHOLD = runtime_config.get('CLASSIFICATION_MIN_CONFIDENCE', 0.08)
        
        # If confidence is too low, classify as "Unknown" or "Other"
        # Note: With 10 categories + softmax, even clear documents get 10-25% scores
        # Only flag as "Other" if confidence is extremely low (default < 8%, configurable in Control Panel)
        if top_score < MIN_CONFIDENCE_THRESHOLD:
            logger.info(f"Very low confidence ({top_score:.2%}) for '{top_label}', classifying as 'Other'")
            # Check if 'Other' exists in candidates, otherwise use 'Unknown'
            fallback_label = 'Other' if 'Other' in probabilities else 'Unknown'
            return {
                'label': fallback_label,
                'score': top_score,  # Keep original score for transparency
                'all_scores': probabilities,
                'low_confidence': True,
                'original_prediction': top_label
            }
        
        return {
            'label': top_label,  # Just the label, no confidence in display
            'score': top_score,
            'confidence': top_score,  # For internal use
            'all_scores': probabilities
        }
        
    except Exception as e:
        logger.error(f"Error classifying text: {e}")
        return {
            'label': 'Unknown',
            'score': 0.0,
            'all_scores': {}
        }


async def classify_with_reasoning(
    text: str,
    models: Dict[str, Any],
    initial_classification: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Enhanced classification with Llama reasoning

    Args:
        text: Document text to classify
        models: Dictionary with loaded models
        initial_classification: Initial classification from embedding model

    Returns:
        {
            'label': 'Invoice',
            'score': 0.92,
            'reasoning': 'Document contains...',
            'key_indicators': ['invoice_number', 'line_items'],
            'validated': True,
            'all_scores': {...}
        }
    """
    try:
        # Get initial classification if not provided
        if initial_classification is None:
            initial_classification = classify_text(text, models)

        # Get Llama model
        llama = models.get('llama')
        if llama is None:
            from app.models.loader import load_llama_model
            llama = load_llama_model()
            models['llama'] = llama

        if llama is None:
            # Return initial classification without reasoning
            logger.warning("Llama not available for classification reasoning")
            return {
                **initial_classification,
                'reasoning': 'Llama model not available',
                'key_indicators': [],
                'validated': False
            }

        # Prepare reasoning prompt
        doc_type = initial_classification['label']
        confidence = initial_classification['score']
        
        # Get low confidence threshold from Control Panel config
        from app.api.config_endpoints import get_runtime_config
        config = get_runtime_config()
        low_confidence_threshold = config.get('CLASSIFICATION_LOW_CONFIDENCE_THRESHOLD', 0.15)
        
        # If confidence is very low, ask Llama to determine the type
        if confidence < low_confidence_threshold:  # Below threshold (default 15%)
            prompt = f"""What type of document is this? Choose from: Invoice, Contract, Receipt, Report, Letter, Form, Agreement, Statement, Certificate, Other.

Document text (first 800 characters):
{text[:800]}

Respond in format:
Type: [document type]
Reasoning: [brief explanation]
Key indicators: [comma-separated list]

Response:"""
        else:
            prompt = f"""Analyze this document and explain why it is classified as a {doc_type}.

Document text (first 800 characters):
{text[:800]}

Classification: {doc_type} (confidence: {confidence:.2f})

Provide:
1. Brief reasoning (2-3 sentences)
2. Key indicators found (comma-separated list)

Format:
Reasoning: [Your explanation]
Key indicators: indicator1, indicator2, indicator3

Response:"""

        # Get temperature from config (already loaded above)
        reasoning_temp = config.get('CLASSIFICATION_REASONING_TEMPERATURE', 0.3)

        response = llama(
            prompt,
            max_tokens=200,
            temperature=reasoning_temp,
            top_p=0.9
        )

        output = response['choices'][0]['text'].strip()

        # Parse reasoning and key indicators
        reasoning = ""
        key_indicators = []
        llama_doc_type = None

        for line in output.split('\n'):
            if line.startswith('Type:'):
                llama_doc_type = line.replace('Type:', '').strip()
            elif line.startswith('Reasoning:'):
                reasoning = line.replace('Reasoning:', '').strip()
            elif line.startswith('Key indicators:'):
                indicators_str = line.replace('Key indicators:', '').strip()
                key_indicators = [ind.strip() for ind in indicators_str.split(',')]

        # Override classification if initial confidence was very low and Llama provided a type
        if confidence < 0.15 and llama_doc_type:
            logger.info(f"✓ Overriding low-confidence classification: '{doc_type}' ({confidence:.2%}) → '{llama_doc_type}' (Llama)")
            doc_type = llama_doc_type
            # Read override confidence from Control Panel
            override_confidence = config.get('LLAMA_OVERRIDE_CONFIDENCE', 0.85)
            confidence = override_confidence  # Set higher confidence for Llama override

        # Validate classification
        validated = len(key_indicators) >= 2 and len(reasoning) > 20

        logger.info(f"✓ Classification reasoning: {len(key_indicators)} indicators found")

        return {
            'label': doc_type,  # Use potentially updated doc_type
            'score': confidence,  # Use potentially updated confidence
            'confidence': confidence,
            'all_scores': initial_classification.get('all_scores', {}),
            'reasoning': reasoning or f"Classified as {doc_type} based on content analysis.",
            'key_indicators': key_indicators,
            'validated': validated,
            'llama_override': confidence < 0.15 and llama_doc_type is not None
        }

    except Exception as e:
        logger.error(f"Error generating classification reasoning: {e}", exc_info=True)
        return {
            'label': initial_classification['label'],
            'score': initial_classification['score'],
            'confidence': initial_classification['score'],
            'all_scores': initial_classification.get('all_scores', {}),
            'reasoning': f"Error generating reasoning: {str(e)}",
            'key_indicators': [],
            'validated': False,
            'llama_override': False
        }


def extract_text_basic(pdf_file_path: str, models: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract text from entire PDF without splitting.
    Used when ENABLE_PDF_SPLITTING is disabled.
    
    Args:
        pdf_file_path: Path to PDF file
        models: Dictionary containing 'paddleocr' model
        
    Returns:
        Dict with:
            - 'text': Concatenated text from all pages
            - 'ocr_confidence': {'avg_confidence': float, 'min_confidence': float}
    """
    from pdf2image import convert_from_path
    import os
    
    poppler_path = os.getenv('POPPLER_PATH', r"C:\Users\Ahmad\poppler\poppler-24.08.0\Library\bin")
    
    # Convert PDF to images
    try:
        images = convert_from_path(
            pdf_file_path,
            dpi=200,
            poppler_path=poppler_path if os.path.exists(poppler_path) else None
        )
    except Exception as e:
        logger.error(f"Failed to convert PDF to images: {e}")
        return {'text': '', 'ocr_confidence': {'avg_confidence': 0.0, 'min_confidence': 0.0}}
    
    # Get PaddleOCR model
    paddleocr = models.get('paddleocr') or models.get('paddle_ocr')
    if paddleocr is None:
        logger.error("PaddleOCR model not found in models dictionary")
        return {'text': '', 'ocr_confidence': {'avg_confidence': 0.0, 'min_confidence': 0.0}}
    
    # Extract text and confidence from each page
    all_text = []
    all_confidences = []
    
    for i, img in enumerate(images):
        try:
            result = extract_text_from_image(img, paddleocr, return_confidence=True)
            if result['text']:
                all_text.append(result['text'])
                all_confidences.append(result['avg_confidence'])
        except Exception as e:
            logger.warning(f"Failed to extract text from page {i+1}: {e}")
            continue
    
    # Calculate aggregate confidence
    avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0.5
    min_conf = min(all_confidences) if all_confidences else 0.5
    
    return {
        'text': " ".join(all_text),
        'ocr_confidence': {
            'avg_confidence': avg_conf,
            'min_confidence': min_conf
        }
    }


# DEPRECATED: Legacy Florence-2 signature detection (not used in current pipeline)
# Signature detection now handled by YOLOv8n in pipeline_worker.py
# def find_signature(image: Image.Image, models: Dict[str, Any]) -> Dict[str, Any]:
#     ...
#     (code removed - see git history if needed)
