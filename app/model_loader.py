"""
Model Loader - Initialize all Tier 1 models on startup
Handles lazy loading and GPU/CPU device management
"""

import os
import logging
from typing import Dict, Any
import torch
from sentence_transformers import SentenceTransformer
from paddleocr import PaddleOCR

logger = logging.getLogger("model_loader")

# Global models cache
models: Dict[str, Any] = {}


def get_device():
    """Detect and return appropriate device (cuda/cpu)"""
    # Force GPU detection for development/testing
    # Set environment variable FORCE_GPU=false to disable
    force_gpu = os.getenv('FORCE_GPU', 'true').lower() == 'true'
    
    if torch.cuda.is_available():
        logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
        return "cuda"
    elif force_gpu:
        logger.info("GPU forced enabled (FORCE_GPU=true) - using CPU with GPU flag")
        return "cpu"  # Still use CPU but report as GPU-ready
    else:
        logger.info("Using CPU device")
        return "cpu"


def load_all_models() -> Dict[str, Any]:
    """
    Load all Tier 1 models on startup
    
    Returns:
        Dictionary with loaded models: {
            'sentence_transformer_classify': SentenceTransformer,
            'sentence_transformer_search': SentenceTransformer,
            'paddleocr': PaddleOCR,
            'trocr': (processor, model),
            'yolo': YOLO model for signature detection
        }
    """
    global models
    
    if models:
        logger.info("Models already loaded, returning cached models")
        return models
    
    logger.info("Starting model initialization...")
    device = get_device()
    
    try:
        # 1. Load SentenceTransformer for classification (zero-shot via embeddings)
        logger.info("Loading all-MiniLM-L12-v2 for classification...")
        classify_model_path = os.path.join('models', 'sentence-transformers', 'models--sentence-transformers--all-MiniLM-L12-v2', 'snapshots', 'c004d8e3e901237d8fa7e9fff12774962e391ce5')
        models['sentence_transformer_classify'] = SentenceTransformer(
            classify_model_path,
            device=device
        )
        logger.info("✓ Classification model loaded from local path")
        
        # 2. Load SentenceTransformer for search embeddings
        logger.info("Loading all-MiniLM-L6-v2 for search embeddings...")
        search_model_path = os.path.join('models', 'sentence-transformers', 'models--sentence-transformers--all-MiniLM-L6-v2', 'snapshots', 'c9745ed1d9f207416be6d2e6f8de32d1f16199bf')
        models['sentence_transformer_search'] = SentenceTransformer(
            search_model_path,
            device=device
        )
        logger.info("✓ Search embedding model loaded from local path")
        
        # 3. Load PaddleOCR for printed text
        logger.info("Loading PaddleOCR for printed text recognition...")
        # PaddleOCR manages its own model cache (C:\Users\Ahmad\.paddlex\official_models)
        # Models are already downloaded and cached
        models['paddleocr'] = PaddleOCR(
            use_textline_orientation=True,  # Replaces deprecated use_angle_cls
            lang='en',
            ocr_version='PP-OCRv5'  # Use latest OCR model
        )
        logger.info("✓ PaddleOCR loaded (using system cache)")
        
        # 4. Load TrOCR for handwritten text (preload on startup)
        logger.info("Loading TrOCR for handwritten text recognition...")
        models['trocr'] = load_trocr_model()
        if models['trocr']:
            logger.info("✓ TrOCR loaded")
        else:
            logger.warning("⚠ TrOCR failed to load - handwritten text extraction unavailable")
        
        # 5. Load YOLOv8n for signature detection (preload on startup)
        logger.info("Loading YOLOv8n for signature detection...")
        models['yolo'] = load_yolo_model()
        if models['yolo']:
            logger.info("✓ YOLOv8n loaded")
        else:
            logger.warning("⚠ YOLOv8n failed to load - signature detection unavailable")
        
        # 6. Load Llama 3.2 3B for Q&A (preload on startup if available)
        logger.info("Loading Llama 3.2 3B for question answering...")
        models['llama'] = load_llama_model()
        if models['llama']:
            logger.info("✓ Llama 3.2 3B loaded")
        else:
            logger.warning("⚠ Llama model not found - Q&A will use fallback methods")
        
        logger.info("All core models loaded successfully!")
        return models
        
    except Exception as e:
        logger.error(f"Error loading models: {e}")
        raise


def load_trocr_model():
    """
    Lazy load TrOCR on first use
    """
    global models
    
    if models.get('trocr') is not None:
        logger.info("TrOCR model already loaded")
        return models['trocr']
    
    try:
        logger.info("Lazy loading TrOCR (handwriting) model...")
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        # Prefer env path; else default to HF hub id
        local_official_path = os.path.join('models', 'trocr', 'official')
        trocr_source = os.getenv('TROCR_MODEL_PATH') or (local_official_path if os.path.isdir(local_official_path) else 'microsoft/trocr-large-handwritten')

        processor = TrOCRProcessor.from_pretrained(
            trocr_source,
            local_files_only=os.path.isdir(trocr_source)
        )
        model = VisionEncoderDecoderModel.from_pretrained(
            trocr_source,
            trust_remote_code=True,
            local_files_only=os.path.isdir(trocr_source)
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)

        # Ensure decoder config tokens
        if getattr(model.config, 'decoder_start_token_id', None) is None and hasattr(processor, 'tokenizer'):
            model.config.decoder_start_token_id = getattr(processor.tokenizer, 'bos_token_id', None)
        if getattr(model.config, 'pad_token_id', None) is None and hasattr(processor, 'tokenizer'):
            model.config.pad_token_id = getattr(processor.tokenizer, 'pad_token_id', 0)

        models['trocr'] = {
            'processor': processor,
            'model': model,
            'device': device
        }
        logger.info(f"✓ TrOCR loaded from: {trocr_source}")
        return models['trocr']
        
    except Exception as e:
        logger.error(f"Error loading TrOCR: {e}")
        return None


def load_yolo_model():
    """
    Load YOLOv8n for signature detection
    Uses pre-trained model or fine-tuned signature model if available
    """
    global models
    
    if models.get('yolo') is not None:
        logger.info("YOLOv8n model already loaded")
        return models['yolo']
    
    try:
        logger.info("Loading YOLOv8n for signature detection...")
        from ultralytics import YOLO
        
        # Check for custom signature model, else use YOLOv8n default
        custom_model_path = os.path.join('models', 'yolo', 'signature_detector.pt')
        
        if os.path.exists(custom_model_path):
            logger.info(f"Loading custom signature model: {custom_model_path}")
            model = YOLO(custom_model_path)
        else:
            logger.info("Loading default YOLOv8n model")
            model = YOLO('yolov8n.pt')  # Will auto-download on first use
        
        models['yolo'] = model
        logger.info("✓ YOLOv8n loaded")
        return models['yolo']
        
    except Exception as e:
        logger.error(f"Error loading YOLOv8n: {e}")
        return None


def load_llama_model():
    """
    Lazy load Llama 3.2 3B GGUF model on first use
    """
    global models
    
    if models.get('llama') is not None:
        logger.info("Llama model already loaded")
        return models['llama']
    
    try:
        logger.info("Lazy loading Llama 3.2 3B GGUF...")
        
        llama_path = os.getenv(
            'LLAMA_MODEL_PATH',
            'models/llama-3.2-3b-gguf/model.gguf'
        )
        
        if not os.path.exists(llama_path):
            logger.warning(f"Llama model not found at {llama_path}")
            logger.warning("Skipping Llama loading - will use fallback summaries")
            return None
        
        from llama_cpp import Llama
        
        models['llama'] = Llama(
            model_path=llama_path,
            n_gpu_layers=-1 if torch.cuda.is_available() else 0,
            n_ctx=2048,
            verbose=False
        )
        logger.info("✓ Llama 3.2 3B loaded")
        return models['llama']
        
    except Exception as e:
        logger.error(f"Error loading Llama: {e}")
        logger.warning("Continuing without Llama model")
        return None


def get_models() -> Dict[str, Any]:
    """
    Get cached models dictionary
    """
    global models
    if not models:
        load_all_models()
    return models


def models_ready() -> bool:
    """
    Check if all core models are loaded
    """
    global models
    required_models = [
        'sentence_transformer_classify',
        'sentence_transformer_search',
        'paddleocr'
    ]
    return all(key in models and models[key] is not None for key in required_models)

