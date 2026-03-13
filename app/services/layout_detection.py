"""
Document Layout Detection — Full-page layout analysis using YOLO.

Detects 8 region classes on each page, then routes each region to the
appropriate OCR engine via region_router.

Classes:
    0: text_block   → PaddleOCR
    1: table        → PPStructure
    2: figure       → skip
    3: signature    → TrOCR
    4: stamp        → skip
    5: handwriting  → TrOCR
    6: header       → PaddleOCR
    7: footer       → PaddleOCR
"""

import logging
from typing import Any, Dict, List

import numpy as np
import torch
from PIL import Image

logger = logging.getLogger("layout_detection")

# Class ID → class name (must match data.yaml)
LAYOUT_CLASSES = {
    0: 'text_block',
    1: 'table',
    2: 'figure',
    3: 'signature',
    4: 'stamp',
    5: 'handwriting_region',
    6: 'header',
    7: 'footer',
}


def detect_layout_single(image: Image.Image, models: Dict[str, Any], conf: float = 0.4, iou: float = 0.45) -> List[Dict]:
    """
    Detect layout regions on a single page image.
    
    Returns list of dicts: {class, confidence, box: {x, y, w, h}}
    """
    yolo_layout = models.get('yolo_layout')
    if not yolo_layout:
        return []

    model = yolo_layout['model']
    img_array = np.array(image)

    results = model(img_array, conf=conf, iou=iou, verbose=False)
    
    detections = []
    if results and len(results) > 0:
        result = results[0]
        if result.boxes is not None and len(result.boxes) > 0:
            boxes = result.boxes.xyxy.cpu().numpy()
            confidences = result.boxes.conf.cpu().numpy()
            class_ids = result.boxes.cls.cpu().numpy().astype(int)

            for box, confidence, cls_id in zip(boxes, confidences, class_ids):
                x1, y1, x2, y2 = box
                class_name = LAYOUT_CLASSES.get(cls_id, f'unknown_{cls_id}')
                detections.append({
                    'class': class_name,
                    'class_id': int(cls_id),
                    'confidence': float(confidence),
                    'box': {
                        'x': int(x1),
                        'y': int(y1),
                        'w': int(x2 - x1),
                        'h': int(y2 - y1),
                    },
                })

    return detections


def detect_layout_batch(
    page_images: List[Image.Image],
    models: Dict[str, Any],
    conf: float = 0.4,
    iou: float = 0.45,
    route_ocr: bool = True,
) -> Dict[int, List[Dict]]:
    """
    Detect layout regions across multiple pages in a single GPU session,
    then optionally route each region to the appropriate OCR engine.

    Args:
        page_images: List of PIL Images (one per page)
        models: Global models dict (must contain 'yolo_layout')
        conf: Detection confidence threshold
        iou: NMS IoU threshold
        route_ocr: If True, run region_router to OCR each detected region

    Returns:
        Dict mapping page_index → list of enriched region dicts
    """
    from app.models.loader import check_gpu_memory_available, clear_gpu_cache

    yolo_layout = models.get('yolo_layout')
    if not yolo_layout:
        return {}

    model = yolo_layout['model']
    original_device = yolo_layout.get('original_device', 'cpu')

    # Move to GPU for batch inference
    use_gpu = torch.cuda.is_available() and check_gpu_memory_available(256)
    if use_gpu and str(model.device) == 'cpu':
        clear_gpu_cache()
        model.to('cuda')
        logger.debug("Layout YOLO moved to GPU")

    try:
        # Read runtime config for thresholds
        try:
            from app.api.config_endpoints import get_runtime_config
            runtime_config = get_runtime_config()
            conf = runtime_config.get('YOLO_CONFIDENCE', conf)
            iou = runtime_config.get('YOLO_IOU_THRESHOLD', iou)
        except Exception:
            pass

        all_results = {}

        for page_idx, image in enumerate(page_images):
            detections = detect_layout_single(image, models, conf=conf, iou=iou)

            # Route through OCR engines if requested
            if route_ocr and detections:
                try:
                    import cv2
                    from app.services.region_router import route_regions
                    img_array = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                    enriched = route_regions(img_array, detections, models)
                    all_results[page_idx] = enriched
                except Exception as e:
                    logger.warning(f"Region routing failed for page {page_idx}: {e}")
                    all_results[page_idx] = detections
            else:
                all_results[page_idx] = detections

        return all_results

    finally:
        # Return model to CPU to free VRAM
        if use_gpu:
            model.to('cpu')
            clear_gpu_cache()
            logger.debug("Layout YOLO returned to CPU")
