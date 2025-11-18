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
    try:
        # Convert PIL image to numpy array
        image_array = np.array(image)
        
        # Run OCR (without cls parameter - not supported in this PaddleOCR version)
        result = paddleocr.ocr(image_array)
        
        # Log the raw result structure for debugging
        logger.debug(f"PaddleOCR result type: {type(result)}")
        if result:
            logger.debug(f"PaddleOCR result length: {len(result)}")
            logger.debug(f"First element type: {type(result[0]) if result else None}")
        
        # Extract text from result
        text_lines = []
        
        if result and len(result) > 0:
            # PaddleOCR returns [[line1, line2, ...]] or [line1, line2, ...]
            # Handle both structures
            ocr_data = result[0] if isinstance(result[0], list) else result
            
            for line in ocr_data:
                if line and isinstance(line, (list, tuple)) and len(line) >= 2:
                    # Each line is [[x1,y1,x2,y2,x3,y3,x4,y4], (text, confidence)]
                    text_part = line[1]
                    if isinstance(text_part, (list, tuple)) and len(text_part) >= 1:
                        text_lines.append(str(text_part[0]))
                    elif isinstance(text_part, str):
                        text_lines.append(text_part)
        
        extracted_text = " ".join(text_lines)
        logger.debug(f"Extracted {len(text_lines)} text lines, {len(extracted_text)} chars total")
        
        if not extracted_text.strip():
            logger.warning("No text extracted from image - possibly blank page or OCR failed")
        
        return extracted_text
        
    except Exception as e:
        logger.error(f"Error extracting text from image: {e}", exc_info=True)
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
    logger.info(f"Splitting PDF with similarity threshold: {similarity_threshold}")
    
    # Convert PDF to images
    images = pdf_to_images(pdf_path)
    paddleocr = models['paddleocr']
    sentence_transformer = models['sentence_transformer_search']
    
    # Extract text and embeddings for each page
    page_texts = []
    page_embeddings = []
    
    logger.info(f"Extracting text from {len(images)} pages...")
    for idx, image in enumerate(images):
        text = extract_text_from_image(image, paddleocr)
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


def find_signature(image: Image.Image, models: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect signatures/handwritten marks in document using Florence-2
    
    Args:
        image: PIL Image object
        models: Dictionary with loaded models
        
    Returns:
        {
            'detected': True/False,
            'confidence': 0.85,
            'description': 'Handwritten signature in bottom-right'
        }
    """
    try:
        florence_processor = models['florence2']['processor']
        florence_model = models['florence2']['model']
        device = models['florence2']['device']
        
        # Prepare image
        inputs = florence_processor(
            text="<OD>",  # Object Detection task
            images=image,
            return_tensors="pt"
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Run model
        with torch.no_grad():
            outputs = florence_model.generate(
                **inputs,
                max_new_tokens=1024,
                early_stopping=False,
                do_sample=False,
                num_beams=3
            )
        
        # Decode results
        result_text = florence_processor.batch_decode(
            outputs,
            skip_special_tokens=False
        )[0]
        
        # Check if signature-like objects detected
        signature_keywords = [
            'signature', 'sign', 'handwriting', 'mark', 'initial',
            'autograph', 'scrawl', 'writing'
        ]
        
        detected = any(
            keyword in result_text.lower() for keyword in signature_keywords
        )
        
        return {
            'detected': detected,
            'confidence': 0.75 if detected else 0.0,
            'description': result_text if detected else 'No signature detected'
        }
        
    except Exception as e:
        logger.warning(f"Error detecting signature: {e}")
        return {
            'detected': False,
            'confidence': 0.0,
            'description': 'Detection failed'
        }
