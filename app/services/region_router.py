"""
Region Router — Routes detected document regions to the appropriate OCR engine.

After YOLO detects regions (text_block, table, signature, handwriting, etc.),
this module crops each region and sends it to the best-suited OCR engine.

Routing rules:
    text_block, header, footer → PaddleOCR (printed text)
    handwriting_region, signature → TrOCR Large (handwritten text)
    table → PPStructure (table extraction)
    stamp, figure → skip OCR (visual-only)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger("region_router")

# Region class → OCR engine mapping
ROUTING_TABLE = {
    'text_block': 'paddleocr',
    'header': 'paddleocr',
    'footer': 'paddleocr',
    'handwriting_region': 'trocr',
    'signature': 'trocr',
    'table': 'ppstructure',
    'stamp': 'skip',
    'figure': 'skip',
}


def crop_region(image: np.ndarray, box: Dict[str, int], pad: int = 5) -> np.ndarray:
    """Crop a region from the page image with optional padding."""
    h, w = image.shape[:2]
    x1 = max(0, box['x'] - pad)
    y1 = max(0, box['y'] - pad)
    x2 = min(w, box['x'] + box['w'] + pad)
    y2 = min(h, box['y'] + box['h'] + pad)
    return image[y1:y2, x1:x2]


def _ocr_with_paddle(crop_img: np.ndarray, models: Dict[str, Any]) -> str:
    """Run PaddleOCR on a cropped region."""
    ocr = models.get('ocr')
    if not ocr:
        return ""
    result = ocr.ocr(crop_img, cls=True)
    if result and result[0]:
        return "\n".join(line[1][0] for line in result[0] if line)
    return ""


def _ocr_with_trocr(crop_img: np.ndarray, models: Dict[str, Any]) -> str:
    """Run TrOCR on a cropped region (handwriting/signature)."""
    trocr = models.get('trocr')
    if not trocr:
        return ""

    import torch
    processor = trocr['processor']
    model = trocr['model']
    device = trocr.get('device', 'cpu')

    pil_img = Image.fromarray(cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB))
    inputs = processor(images=pil_img, return_tensors="pt")
    pixel_values = inputs["pixel_values"].to(device)

    with torch.no_grad():
        generated_ids = model.generate(
            pixel_values=pixel_values,
            max_new_tokens=128,
            num_beams=1,
            do_sample=False,
            early_stopping=True,
        )
    return processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()


def route_regions(
    page_image: np.ndarray,
    detections: List[Dict[str, Any]],
    models: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Route each detected region to the appropriate OCR engine.

    Args:
        page_image: Full page image (BGR numpy array)
        detections: List of dicts with keys: class, confidence, box {x, y, w, h}
        models: Loaded models dict (must contain 'ocr', optionally 'trocr')

    Returns:
        List of enriched detection dicts with added 'text' field.
    """
    results = []

    for det in detections:
        region_class = det.get('class', 'unknown')
        engine = ROUTING_TABLE.get(region_class, 'paddleocr')
        box = det.get('box', {})

        if not box or box.get('w', 0) < 5 or box.get('h', 0) < 5:
            continue

        crop_img = crop_region(page_image, box)
        text = ""

        if engine == 'paddleocr':
            text = _ocr_with_paddle(crop_img, models)
        elif engine == 'trocr':
            text = _ocr_with_trocr(crop_img, models)
            if not text:
                # Fallback to PaddleOCR if TrOCR fails or is unavailable
                text = _ocr_with_paddle(crop_img, models)
        elif engine == 'ppstructure':
            # Table extraction is handled by the table_extraction service
            text = "[TABLE]"
        # 'skip' → no OCR

        results.append({
            'class': region_class,
            'confidence': det.get('confidence', 0.0),
            'box': box,
            'engine': engine,
            'text': text,
        })

        logger.debug(f"Region '{region_class}' → {engine}: {len(text)} chars")

    logger.info(f"Routed {len(results)} regions ({len([r for r in results if r['text']])} with text)")
    return results
