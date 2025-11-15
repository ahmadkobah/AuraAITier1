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
    if torch.cuda.is_available():
        logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
        return "cuda"
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
            'trocr': (processor, model),  # Optional, lazy-loaded on first use
            'florence2': (processor, model)  # Optional, lazy-loaded on first use
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
        models['sentence_transformer_classify'] = SentenceTransformer(
            'sentence-transformers/all-MiniLM-L12-v2',
            device=device
        )
        logger.info("✓ Classification model loaded")
        
        # 2. Load SentenceTransformer for search embeddings
        logger.info("Loading all-MiniLM-L6-v2 for search embeddings...")
        models['sentence_transformer_search'] = SentenceTransformer(
            'sentence-transformers/all-MiniLM-L6-v2',
            device=device
        )
        logger.info("✓ Search embedding model loaded")
        
        # 3. Load PaddleOCR for printed text
        logger.info("Loading PaddleOCR for printed text recognition...")
        models['paddleocr'] = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            use_gpu=(device == 'cuda')
        )
        logger.info("✓ PaddleOCR loaded")
        
        # 4. TrOCR is lazy-loaded on first use (large, ~1.4GB)
        models['trocr'] = None
        logger.info("✓ TrOCR marked for lazy loading")
        
        # 5. Florence-2 is lazy-loaded on first use (large, ~500MB)
        models['florence2'] = None
        logger.info("✓ Florence-2 marked for lazy loading")
        
        # 6. Llama 3.2 3B is lazy-loaded on first use (very large, ~2-3GB)
        models['llama'] = None
        logger.info("✓ Llama 3.2 3B marked for lazy loading")
        
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
        logger.info("Lazy loading TrOCR...")
        from transformers import AutoProcessor
        from transformers import VisionEncoderDecoderModel
        
        processor = AutoProcessor.from_pretrained(
            "microsoft/trocr-large-handwritten"
        )
        model = VisionEncoderDecoderModel.from_pretrained(
            "microsoft/trocr-large-handwritten",
            trust_remote_code=True
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        
        models['trocr'] = {
            'processor': processor,
            'model': model,
            'device': device
        }
        logger.info("✓ TrOCR loaded")
        return models['trocr']
        
    except Exception as e:
        logger.error(f"Error loading TrOCR: {e}")
        return None


def load_florence2_model():
    """
    Lazy load Florence-2 on first use
    """
    global models
    
    if models.get('florence2') is not None:
        logger.info("Florence-2 model already loaded")
        return models['florence2']
    
    try:
        logger.info("Lazy loading Florence-2...")
        from transformers import AutoProcessor, AutoModelForCausalLM
        
        processor = AutoProcessor.from_pretrained(
            "microsoft/Florence-2-base",
            trust_remote_code=True
        )
        model = AutoModelForCausalLM.from_pretrained(
            "microsoft/Florence-2-base",
            trust_remote_code=True
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        
        models['florence2'] = {
            'processor': processor,
            'model': model,
            'device': device
        }
        logger.info("✓ Florence-2 loaded")
        return models['florence2']
        
    except Exception as e:
        logger.error(f"Error loading Florence-2: {e}")
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

