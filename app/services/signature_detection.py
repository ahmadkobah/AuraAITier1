"""
YOLOv8n Signature Detection Module
Detects signature regions using lightweight YOLOv8n object detector
"""

import logging
import base64
import io
from typing import List, Tuple, Dict, Any, Optional
from PIL import Image
import numpy as np

logger = logging.getLogger("yolo_signature")


def crop_signature_region(image: Image.Image, box: Tuple[int, int, int, int], padding: int = 10) -> Optional[str]:
    """
    Crop a signature region from the image and return as base64.
    
    Args:
        image: PIL Image to crop from
        box: (x, y, w, h) bounding box
        padding: Extra pixels to include around the box
        
    Returns:
        Base64 encoded PNG image string, or None if failed
    """
    try:
        x, y, w, h = box
        img_width, img_height = image.size
        
        # Add padding but stay within image bounds
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(img_width, x + w + padding)
        y2 = min(img_height, y + h + padding)
        
        # Crop the region
        cropped = image.crop((x1, y1, x2, y2))
        
        # Convert to base64
        buffer = io.BytesIO()
        cropped.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)
        base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        logger.debug(f"Cropped signature region: {w}x{h} -> base64 length: {len(base64_image)}")
        return base64_image
        
    except Exception as e:
        logger.error(f"Error cropping signature region: {e}")
        return None


def detect_signature_boxes(image: Image.Image, models, return_images: bool = False) -> List[Dict[str, Any]]:
    """
    Use YOLOv8n to detect signature-like regions.
    
    Args:
        image: PIL Image to detect signatures in
        models: Global models dictionary containing 'yolo' model
        return_images: If True, include cropped base64 images for each box
        
    Returns:
        List of dicts with 'box' (x, y, w, h), 'confidence', and optionally 'image' (base64)
    """
    from app.models.loader import load_yolo_model
    
    import torch
    
    # Ensure YOLO model is loaded
    yolo_dict = models.get('yolo')
    if yolo_dict is None:
        yolo_dict = load_yolo_model()
        models['yolo'] = yolo_dict
    
    if not yolo_dict:
        logger.warning("YOLO model not available, returning empty boxes")
        return []
    
    # Handle both old format (direct model) and new format (dict)
    if isinstance(yolo_dict, dict):
        yolo = yolo_dict['model']
        original_device = yolo_dict.get('original_device', 'cpu')
    else:
        yolo = yolo_dict
        original_device = 'cpu'
    
    # Move to GPU only if available and memory permits
    from app.models.loader import check_gpu_memory_available, clear_gpu_cache
    use_gpu = torch.cuda.is_available() and check_gpu_memory_available(512)
    
    if use_gpu and str(yolo.device) == 'cpu':
        clear_gpu_cache()  # Clear cache before loading
        yolo.to('cuda')
        logger.info("YOLO moved to GPU for inference")
    
    try:
        # Convert PIL Image to numpy array (RGB)
        img_array = np.array(image)
        
        # Get confidence threshold from Control Panel config
        from app.api.config_endpoints import get_runtime_config
        runtime_config = get_runtime_config()
        confidence_threshold = runtime_config.get('YOLO_CONFIDENCE', 0.60)
        
        # Run YOLO inference
        # conf: Confidence threshold for detection (from Control Panel, default 0.60)
        # iou: IoU threshold for NMS (non-maximum suppression) - read from Control Panel
        # verbose=False: Suppress console output
        iou_threshold = runtime_config.get('YOLO_IOU_THRESHOLD', 0.45)
        results = yolo.predict(
            source=img_array,
            conf=confidence_threshold,
            iou=iou_threshold,  # Read from Control Panel
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
                        box_data = {
                            'box': (x1, y1, w, h),
                            'confidence': float(conf)
                        }
                        
                        # Crop and encode signature image if requested
                        if return_images:
                            base64_img = crop_signature_region(image, (x1, y1, w, h))
                            if base64_img:
                                box_data['image'] = base64_img
                        
                        boxes.append(box_data)
                        logger.debug(f"Detected signature box {i+1}: ({x1}, {y1}, {w}, {h}) conf={conf:.2f}")
        
        logger.info(f"YOLOv8n detected {len(boxes)} signature(s)")
        return boxes
        
    except Exception as e:
        logger.error(f"Error during YOLO signature detection: {e}")
        return []
    
    finally:
        # Move model back to CPU and clear GPU cache
        if use_gpu and str(yolo.device) == 'cuda' and original_device == 'cpu':
            yolo.to('cpu')
            if isinstance(yolo_dict, dict):
                yolo_dict['model'] = yolo
            torch.cuda.empty_cache()
