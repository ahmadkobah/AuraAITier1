"""
YOLOv8n Signature Detection Module
Detects signature regions using lightweight YOLOv8n object detector
"""

import logging
from typing import List, Tuple
from PIL import Image
import numpy as np

logger = logging.getLogger("yolo_signature")


def detect_signature_boxes(image: Image.Image, models) -> List[Tuple[int, int, int, int]]:
    """
    Use YOLOv8n to detect signature-like regions.
    
    Args:
        image: PIL Image to detect signatures in
        models: Global models dictionary containing 'yolo' model
        
    Returns:
        List of (x, y, w, h) tuples representing signature bounding boxes
    """
    from .model_loader import load_yolo_model
    
    # Ensure YOLO model is loaded
    yolo = models.get('yolo')
    if yolo is None:
        yolo = load_yolo_model()
        models['yolo'] = yolo
    
    if not yolo:
        logger.warning("YOLO model not available, returning empty boxes")
        return []
    
    try:
        # Convert PIL Image to numpy array (RGB)
        img_array = np.array(image)
        
        # Run YOLO inference
        # conf=0.25: Confidence threshold for detection
        # iou=0.45: IoU threshold for NMS (non-maximum suppression)
        # verbose=False: Suppress console output
        results = yolo.predict(
            source=img_array,
            conf=0.25,
            iou=0.45,
            verbose=False
        )
        
        # Extract bounding boxes
        boxes = []
        if results and len(results) > 0:
            result = results[0]  # Single image inference
            
            # Check if any detections found
            if result.boxes is not None and len(result.boxes) > 0:
                # Get xyxy format boxes (x1, y1, x2, y2)
                xyxy = result.boxes.xyxy.cpu().numpy()
                confidences = result.boxes.conf.cpu().numpy()
                
                for i, (box, conf) in enumerate(zip(xyxy, confidences)):
                    x1, y1, x2, y2 = map(int, box)
                    w = x2 - x1
                    h = y2 - y1
                    
                    # Validate box dimensions
                    if w > 0 and h > 0:
                        boxes.append((x1, y1, w, h))
                        logger.debug(f"Detected signature box {i+1}: ({x1}, {y1}, {w}, {h}) conf={conf:.2f}")
        
        logger.info(f"YOLOv8n detected {len(boxes)} signature(s)")
        return boxes
        
    except Exception as e:
        logger.error(f"Error during YOLO signature detection: {e}")
        return []
