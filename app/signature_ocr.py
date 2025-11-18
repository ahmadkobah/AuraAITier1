import os
from typing import Dict, Any, List, Tuple, Optional
import cv2
import numpy as np
from PIL import Image
import torch

from . import model_loader
# signature boxes are expected from YOLOv8n upstream; no local detector import


def crop_image(image_bgr: np.ndarray, box: Tuple[int, int, int, int]) -> Image.Image:
    x, y, w, h = box
    x2, y2 = x + w, y + h
    x, y = max(0, x), max(0, y)
    crop_bgr = image_bgr[y:y2, x:x2]
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(crop_rgb)


def ocr_signature(image_path: str, max_new_tokens: int = 64, boxes: Optional[List[Tuple[int,int,int,int]]] = None) -> Dict[str, Any]:
    # Load image
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        return {"found": False, "reason": "Could not read image"}

    # Detect candidate signature regions (unless provided)
    if boxes is None:
        boxes = []
    if not boxes:
        # Fallback: crop a bottom band likely to contain signatures
        h_img, w_img = image_bgr.shape[:2]
        band_h = int(0.22 * h_img)
        band_w = int(0.75 * w_img)
        x = int((w_img - band_w) * 0.6)  # bias to right side
        y = max(0, h_img - band_h - int(0.03 * h_img))
        boxes = [(x, y, band_w, band_h)]
        fallback = True
    else:
        fallback = False

    # Use best box (already sorted by detector)
    best_box = boxes[0]
    crop_pil = crop_image(image_bgr, best_box)

    # Load TrOCR
    trocr = model_loader.load_trocr_model()
    if not trocr:
        return {"found": False, "reason": "TrOCR not available"}

    processor = trocr['processor']
    model = trocr['model']
    device = trocr['device']

    # Prepare input
    inputs = processor(images=crop_pil, return_tensors="pt")
    pixel_values = inputs["pixel_values"].to(device)

    # Ensure config tokens
    if getattr(model.config, 'decoder_start_token_id', None) is None and hasattr(processor, 'tokenizer'):
        model.config.decoder_start_token_id = getattr(processor.tokenizer, 'bos_token_id', None)
    if getattr(model.config, 'pad_token_id', None) is None and hasattr(processor, 'tokenizer'):
        model.config.pad_token_id = getattr(processor.tokenizer, 'pad_token_id', 0)

    # Generate text
    with torch.no_grad():
        generated_ids = model.generate(
            pixel_values=pixel_values,
            max_new_tokens=max_new_tokens,
            num_beams=1,
            do_sample=False,
            early_stopping=True
        )
    text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

    return {
        "found": True,
        "box": {
            "x": int(best_box[0]), "y": int(best_box[1]),
            "w": int(best_box[2]), "h": int(best_box[3])
        },
        "text": text,
        "boxes": boxes,
        "confidence": 0.4 if fallback else 0.75
    }
