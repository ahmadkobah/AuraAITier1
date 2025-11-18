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
        # Explicit poppler path for Windows compatibility
        poppler_path = r"C:\Users\Ahmad\poppler\poppler-24.08.0\Library\bin"
        
        # Try with explicit poppler_path first
        if os.path.exists(poppler_path):
            logger.debug(f"Using explicit poppler_path: {poppler_path}")
            images = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)
        else:
            # Fallback to PATH lookup
            logger.debug("Using poppler from PATH")
            images = convert_from_path(pdf_path, dpi=300)
            
        logger.info(f"✓ Converted {len(images)} pages to images")
        return images
    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}")
        raise


def extract_text_from_image(image: Image.Image, paddleocr) -> str:
    """
    Extract text from image using PaddleOCR
    
    Args:
        image: PIL Image object
        paddleocr: PaddleOCR instance
        
    Returns:
        Extracted text
    """
    print(f"\n🟡 ENTERED: extract_text_from_image()")
    print(f"🟡 PARAMS: image={type(image).__name__} size={image.size}, paddleocr={type(paddleocr).__name__}")
    try:
        # Convert PIL image to numpy array
        image_array = np.array(image)
        print(f"[OCR DEBUG] Image array shape: {image_array.shape}, dtype: {image_array.dtype}")
        logger.info(f"Image array shape: {image_array.shape}, dtype: {image_array.dtype}")
        
        # Run OCR
        print(f"🟡 BEFORE OCR: About to call paddleocr.ocr(image_array)")
        print(f"🟡 OCR INPUT: image_array shape={image_array.shape}, dtype={image_array.dtype}")
        print("[OCR DEBUG] Calling PaddleOCR.ocr()...")
        logger.info("Calling PaddleOCR.ocr()...")
        try:
            print(f"🟡 CALLING: paddleocr.ocr()...")
            result = paddleocr.ocr(image_array)
            print(f"✅ OCR RETURNED: Call completed without exception")
            print(f"[OCR DEBUG] ✓ OCR completed. Result type: {type(result)}, is None: {result is None}")
            
            # IMMEDIATE RESULT INSPECTION
            print(f"🔍 RESULT INSPECTION:")
            print(f"   - result type: {type(result)}")
            print(f"   - result is None: {result is None}")
            print(f"   - result value: {result}")
            if result:
                print(f"   - len(result): {len(result)}")
                if len(result) > 0:
                    print(f"   - result[0] type: {type(result[0])}")
                    print(f"   - result[0] is None: {result[0] is None}")
                    print(f"   - result[0] value: {result[0]}")
                    if result[0] and hasattr(result[0], '__len__'):
                        print(f"   - len(result[0]): {len(result[0])}")
            
            logger.info(f"✓ OCR call completed without exception")
        except Exception as ocr_error:
            logger.error(f"❌ OCR call raised exception: {ocr_error}", exc_info=True)
            return ""
        
        # DETAILED LOGGING - Log the complete raw result structure
        logger.info("=" * 80)
        logger.info("PADDLEOCR RESULT DEBUG:")
        logger.info(f"Result type: {type(result)}")
        logger.info(f"Result is None: {result is None}")
        logger.info(f"Result value (first 500 chars): {str(result)[:500]}")
        
        if result:
            logger.info(f"Result length: {len(result)}")
            logger.info(f"Result[0] type: {type(result[0]) if len(result) > 0 else 'N/A'}")
            
            if len(result) > 0 and result[0]:
                logger.info(f"Result[0] is None: {result[0] is None}")
                if result[0] is not None:
                    # Check if it's a dict or list
                    if isinstance(result[0], dict):
                        logger.info(f"Result[0] is a DICT with keys: {list(result[0].keys())}")
                        logger.info(f"Result[0] content: {result[0]}")
                    elif isinstance(result[0], list):
                        logger.info(f"Result[0] is a LIST with length: {len(result[0])}")
                        # Log first 3 detections in detail
                        if len(result[0]) > 0:
                            logger.info("First 3 OCR detections:")
                            for i, detection in enumerate(result[0][:3]):
                                logger.info(f"  Detection {i}: {detection}")
                        else:
                            logger.warning("Result[0] is EMPTY list!")
                    else:
                        logger.warning(f"Result[0] has unexpected type: {type(result[0])}")
                        logger.info(f"Result[0] value: {result[0]}")
            else:
                logger.warning("Result[0] is None or empty!")
        else:
            logger.warning("Result is None or empty!")
        
        logger.info("=" * 80)
        
        # Extract text from result
        text_lines = []
        
        if result and len(result) > 0 and result[0]:
            ocr_data = result[0]
            
            # PaddleOCR 3.3.2+ returns OCRResult dict, not list
            if isinstance(ocr_data, dict) and 'rec_texts' in ocr_data:
                print(f"✅ NEW FORMAT: Found 'rec_texts' key with {len(ocr_data['rec_texts'])} texts")
                text_lines = ocr_data['rec_texts']
                logger.info(f"Extracted {len(text_lines)} text lines from OCRResult dict")
            else:
                # Fallback: old format (list of detections)
                logger.info(f"Processing {len(ocr_data)} OCR detections (old format)...")
                
                for idx, line in enumerate(ocr_data):
                    if line and isinstance(line, (list, tuple)) and len(line) >= 2:
                        coords = line[0]
                        text_part = line[1]
                        
                        logger.debug(f"Line {idx}: coords={coords}, text_part={text_part}")
                        
                        if isinstance(text_part, (list, tuple)) and len(text_part) >= 1:
                            text = str(text_part[0])
                            confidence = float(text_part[1]) if len(text_part) > 1 else 0.0
                            text_lines.append(text)
                            logger.debug(f"  → Extracted: '{text}' (confidence: {confidence:.3f})")
                        elif isinstance(text_part, str):
                            text_lines.append(text_part)
                            logger.debug(f"  → Extracted: '{text_part}'")
        
        extracted_text = " ".join(text_lines)
        logger.info(f"FINAL: Extracted {len(text_lines)} text lines, {len(extracted_text)} chars total")
        
        if not extracted_text.strip():
            logger.error("❌ NO TEXT EXTRACTED! OCR returned empty result")
        else:
            logger.info(f"✓ Text preview: {extracted_text[:100]}...")
        
        return extracted_text
        
    except Exception as e:
        logger.error(f"❌ EXCEPTION in extract_text_from_image: {e}", exc_info=True)
        return ""


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
    print(f"\n🟢 ENTERED: split_pdf_and_find_breaks(pdf_path={pdf_path})")
    logger.info(f"Splitting PDF with similarity threshold: {similarity_threshold}")
    
    # Convert PDF to images
    print(f"🟢 CALLING: pdf_to_images({pdf_path})")
    images = pdf_to_images(pdf_path)
    print(f"🟢 RETURNED: pdf_to_images returned {len(images)} images")
    
    print(f"🟢 GETTING: models['paddleocr'] - type={type(models.get('paddleocr'))}")
    paddleocr = models['paddleocr']
    sentence_transformer = models['sentence_transformer_search']
    
    if paddleocr is None:
        print(f"❌ ERROR: paddleocr is None! Cannot extract text.")
        raise ValueError("PaddleOCR model not loaded in models dict")
    else:
        print(f"✅ PaddleOCR instance retrieved successfully: {paddleocr}")
    
    # Extract text and embeddings for each page
    page_texts = []
    page_embeddings = []
    
    logger.info(f"Extracting text from {len(images)} pages...")
    for idx, image in enumerate(images):
        print(f"\n🟢 PAGE {idx+1}/{len(images)}: Calling extract_text_from_image(image_size={image.size}, paddleocr_type={type(paddleocr).__name__})")
        text = extract_text_from_image(image, paddleocr)
        print(f"🟢 PAGE {idx+1}: extract_text_from_image returned {len(text)} characters")
        print(f"🟢 PAGE {idx+1}: Text preview: {text[:100] if text else '(empty)'}")
        page_texts.append(text)
        
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
        
        logical_documents.append({
            'doc_num': doc_num,
            'start_page': start_page,
            'end_page': end_page - 1,
            'text': doc_text,
            'page_count': end_page - start_page,
            'embedding': doc_embedding.tolist(),
            'confidence': 0.85  # Placeholder; could be computed from similarity scores
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
            'Invoice', 'Contract', 'Receipt', 'Report', 'Letter',
            'Form', 'Agreement', 'Statement', 'Certificate', 'Other'
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
            k: np.exp(v - max_sim) for k, v in similarities.items()
        }
        sum_exp = sum(similarities_exp.values())
        probabilities = {
            k: v / sum_exp for k, v in similarities_exp.items()
        }
        
        # Get top label
        top_label = max(probabilities, key=probabilities.get)
        
        return {
            'label': top_label,
            'score': probabilities[top_label],
            'all_scores': probabilities
        }
        
    except Exception as e:
        logger.error(f"Error classifying text: {e}")
        return {
            'label': 'Unknown',
            'score': 0.0,
            'all_scores': {}
        }


# DEPRECATED: Legacy Florence-2 signature detection (not used in current pipeline)
# Signature detection now handled by YOLOv8n in pipeline_worker.py
# def find_signature(image: Image.Image, models: Dict[str, Any]) -> Dict[str, Any]:
#     ...
#     (code removed - see git history if needed)
