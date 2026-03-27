"""
================================================================================
Model Loader - AI Model Management & GPU Optimization
================================================================================

PURPOSE:
--------
This module manages the loading, caching, and device allocation of all AI models
used in the document processing pipeline. It implements GPU on-demand loading
to optimize memory usage and prevent constant 95% GPU utilization.

MODELS MANAGED:
--------------
1. PaddleOCR          - Printed text OCR (CPU-based, ~200MB RAM)
2. TrOCR Large        - Handwritten text OCR (GPU: ~1.5GB VRAM)
3. SentenceTransformer- Document embeddings (GPU: ~400MB VRAM)
   - paraphrase-multilingual-MiniLM-L12-v2 (classification + search, 384-dim)

GPU MANAGEMENT STRATEGY:
-----------------------
OLD APPROACH (Problem):
    • All models loaded to GPU at startup → 95% constant GPU usage
    • Models never moved back to CPU → GPU memory never freed
    • Other applications couldn't use GPU

NEW APPROACH (Solution):
    • Models load to CPU by default (GPU_ON_DEMAND=true)
    • During inference:
        1. Move model from CPU to GPU
        2. Run inference on GPU
        3. Move model back to CPU
        4. Clear GPU cache (torch.cuda.empty_cache())
    • Result: GPU idle ~5%, spikes to 80-95% only during processing

CONFIGURATION:
-------------
Environment Variables:
    GPU_ON_DEMAND=true         - Enable on-demand GPU loading (RECOMMENDED)
    AUTO_CLEANUP_GPU=true      - Clear GPU cache after inference
    FORCE_GPU=false            - Force all models to GPU (legacy mode)
    MAX_GPU_MEMORY_MB=4096     - Limit GPU memory usage

Performance Impact:
    • CPU to GPU transfer: ~50-100ms per model
    • Total overhead: ~100ms per document (acceptable)
    • GPU memory freed immediately after use

THREAD SAFETY:
-------------
The model loader uses threading.Lock to ensure models are loaded only once
even when multiple requests arrive simultaneously during startup.

USAGE EXAMPLE:
-------------
    from app.models.loader import load_all_models, get_models
    
    # Load all models (called once at startup)
    load_all_models()
    
    # Get models for use
    models = get_models()
    trocr = models['trocr']
    trocr = models['trocr']

MEMORY MANAGEMENT:
-----------------
    • CPU RAM: ~2GB for all models
    • GPU VRAM: ~0-2GB (on-demand, temporary)
    • Peak GPU usage: <5 seconds per document

TROUBLESHOOTING:
---------------
    Out of GPU Memory:
        → Ensure GPU_ON_DEMAND=true
        → Reduce MAX_GPU_MEMORY_MB
        → Check nvidia-smi for other GPU processes
    
    Models loading slowly:
        → First startup downloads models from HuggingFace
        → Subsequent startups use cached models (~15s)
    
    GPU not being used:
        → Check torch.cuda.is_available()
        → Verify CUDA toolkit installation
        → Models will fall back to CPU (slower)

================================================================================
"""

# ========================
# Standard Library Imports
# ========================
import os
import sys
import logging
import threading
from typing import Dict, Any
import warnings

# ========================
# Warning & Logging Suppression
# ========================
# Suppress verbose output from ML libraries to keep logs clean
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # TensorFlow warnings
os.environ['GLOG_minloglevel'] = '3'      # Google logging

# Set all ML library loggers to CRITICAL to suppress info/warning messages
logging.getLogger('paddle').setLevel(logging.CRITICAL)
logging.getLogger('ppocr').setLevel(logging.CRITICAL)
logging.getLogger('transformers').setLevel(logging.CRITICAL)
logging.getLogger('sentence_transformers').setLevel(logging.CRITICAL)
logging.getLogger('filelock').setLevel(logging.CRITICAL)

logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.getLogger('requests').setLevel(logging.CRITICAL)

# ========================
# Network Optimization for PaddleOCR
# ========================
# Monkey-patch socket to fail fast during PaddleOCR import
# PaddleOCR tries to check for model updates which can hang for 30+ seconds
# This patch allows only localhost connections and fails fast for external hosts
import socket
import sys
_original_getaddrinfo = socket.getaddrinfo
_original_stderr = sys.stderr

def fast_fail_getaddrinfo(host, port, *args, **kwargs):
    """
    Custom getaddrinfo that fails fast for non-localhost connections.
    Prevents PaddleOCR from hanging during import when checking for updates.
    """
    # Only allow localhost connections during import
    if host in ('localhost', '127.0.0.1', '::1'):
        return _original_getaddrinfo(host, port, *args, **kwargs)
    # Fail fast for external hosts to avoid hanging
    raise socket.gaierror(socket.EAI_NONAME, f"Fast-fail: {host}")

socket.getaddrinfo = fast_fail_getaddrinfo

# ========================
# Core Library Imports
# ========================
import torch
from sentence_transformers import SentenceTransformer

# Import PaddleOCR with fast-fail network and suppressed stderr
try:
    # Suppress "No model hoster is available" warning by redirecting stderr
    sys.stderr = open(os.devnull, 'w')
    from paddleocr import PaddleOCR
finally:
    # Restore originals after import
    sys.stderr.close() if sys.stderr != _original_stderr else None
    sys.stderr = _original_stderr
    socket.getaddrinfo = _original_getaddrinfo

# ========================
# Output Suppression Utility
# ========================
class SuppressOutput:
    """
    Context manager to suppress stdout and stderr temporarily.
    
    Used during model loading to prevent verbose library output
    from cluttering the application logs.
    
    Usage:
        with SuppressOutput():
            model = load_noisy_library()
    """
    def __enter__(self):
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._devnull_out = open(os.devnull, 'w')
        self._devnull_err = open(os.devnull, 'w')
        sys.stdout = self._devnull_out
        sys.stderr = self._devnull_err
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        try:
            self._devnull_out.close()
        except Exception:
            pass
        try:
            self._devnull_err.close()
        except Exception:
            pass

logger = logging.getLogger("model_loader")

# ========================
# Global State
# ========================
# Models cache - stores all loaded models to avoid reloading
models: Dict[str, Any] = {}

# Thread lock for thread-safe model loading
# Prevents race conditions when multiple requests arrive during startup
_models_lock = threading.Lock()

# ========================
# GPU Management Configuration
# ========================
# CRITICAL: These settings prevent constant 95% GPU usage
_GPU_ON_DEMAND = True  # ALWAYS true - load models to CPU, move to GPU only for inference
_AUTO_CLEANUP_GPU = True  # ALWAYS true - clear GPU cache after inference
_MAX_GPU_MEMORY_MB = int(os.getenv('MAX_GPU_MEMORY_MB', '4096'))  # Max GPU memory per model

# ========================
# GPU Utility Functions
# ========================

def clear_gpu_cache():
    """
    Clear CUDA GPU cache to free memory.
    
    This is called automatically after each model inference to ensure
    GPU memory is freed for other processes. Without this, GPU memory
    would stay allocated even after inference completes.
    
    Steps:
        1. empty_cache() - Frees cached memory back to GPU
        2. synchronize() - Waits for all GPU operations to complete
    """
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        logger.info("GPU cache cleared")


def get_gpu_memory_usage():
    """
    Get current GPU memory usage in MB.
    
    Returns:
        float: Memory usage in megabytes, or 0 if GPU not available
        
    Used for monitoring and debugging GPU memory consumption.
    """
    if not torch.cuda.is_available():
        return 0
    try:
        return torch.cuda.memory_allocated(0) / (1024 * 1024)
    except Exception:
        return 0


def check_gpu_memory_available(required_mb: int = 1024) -> bool:
    """Check if enough GPU memory is available"""
    if not torch.cuda.is_available():
        return False
    try:
        current_usage = get_gpu_memory_usage()
        return (current_usage + required_mb) < _MAX_GPU_MEMORY_MB
    except Exception:
        return False


def move_model_to_device(model, device: str):
    """Move model to specified device"""
    if hasattr(model, 'to'):
        return model.to(device)
    elif isinstance(model, dict) and 'model' in model:
        model['model'] = model['model'].to(device)
        model['device'] = device
        return model
    return model


def get_device():
    """Detect and return appropriate device (cuda/cpu)"""
    # For on-demand GPU, always return CPU initially
    # Models will be moved to GPU only when needed
    if _GPU_ON_DEMAND:
        if torch.cuda.is_available():
            logger.info(f"GPU on-demand mode enabled (GPU: {torch.cuda.get_device_name(0)})")
        return "cpu"
    
    # Original behavior: load all to GPU
    force_gpu = os.getenv('FORCE_GPU', 'true').lower() == 'true'
    
    if torch.cuda.is_available():
        logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
        return "cuda"
    elif force_gpu:
        logger.info("GPU forced enabled (FORCE_GPU=true) - using CPU with GPU flag")
        return "cpu"
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
        }
    """
    global models
    
    if models:
        return models
    
    device = get_device()
    
    try:
        logger.info("Loading AI models...")
        
        # 1. Load SentenceTransformer (multilingual, used for both classification and search)
        _st_model_name = os.getenv('SENTENCE_TRANSFORMER_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')
        _st_model_path = os.path.join('models', 'sentence-transformers', f'models--sentence-transformers--{_st_model_name}', 'snapshots', 'e8f8c211226b894fcb81acc59f3b34ba3efd5f42')
        with SuppressOutput():
            _shared_st = SentenceTransformer(
                _st_model_path,
                device=device
            )
        models['sentence_transformer_classify'] = _shared_st
        models['sentence_transformer_search'] = _shared_st
        
        # 3. Load PaddleOCR for printed text (optional - may not work with Python 3.14+)
        try:
            with SuppressOutput():
                models['paddleocr'] = PaddleOCR(
                    use_textline_orientation=True,
                    lang='en',
                    ocr_version='PP-OCRv5'
                )
            logger.info("PaddleOCR loaded successfully")
        except Exception as e:
            logger.warning(f"PaddleOCR not available: {e}")
            models['paddleocr'] = None
        
        # 4. Load TrOCR for handwritten text (preload on startup)
        models['trocr'] = load_trocr_model()
        
        # 5. Load Llama 3.2 3B for Q&A (preload on startup if available)
        models['llama'] = load_llama_model()
        
        # Log status summary
        logger.info("AI Models Status:")
        logger.info(f"  PaddleOCR: {'Ready' if models.get('paddleocr') else 'Not Available'}")
        logger.info(f"  TrOCR: {'Ready' if models.get('trocr') else 'Failed'}")
        logger.info(f"  Llama 3.2: {'Ready' if models.get('llama') else 'Not Available'}")
        logger.info(f"  Sentence Transformers: Ready")
        
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
        return models['trocr']
    
    try:
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        local_official_path = os.path.join('models', 'trocr', 'official')
        trocr_source = os.getenv('TROCR_MODEL_PATH') or (local_official_path if os.path.isdir(local_official_path) else 'microsoft/trocr-large-handwritten')

        with SuppressOutput():
            processor = TrOCRProcessor.from_pretrained(
                trocr_source,
                local_files_only=os.path.isdir(trocr_source)
            )
            model = VisionEncoderDecoderModel.from_pretrained(
                trocr_source,
                trust_remote_code=True,
                local_files_only=os.path.isdir(trocr_source)
            )
        
        # Use CPU by default for on-demand GPU
        device = "cpu" if _GPU_ON_DEMAND else ("cuda" if torch.cuda.is_available() else "cpu")
        model = model.to(device)

        # Ensure decoder config tokens
        if getattr(model.config, 'decoder_start_token_id', None) is None and hasattr(processor, 'tokenizer'):
            model.config.decoder_start_token_id = getattr(processor.tokenizer, 'bos_token_id', None)
        if getattr(model.config, 'pad_token_id', None) is None and hasattr(processor, 'tokenizer'):
            model.config.pad_token_id = getattr(processor.tokenizer, 'pad_token_id', 0)

        models['trocr'] = {
            'processor': processor,
            'model': model,
            'device': device,
            'original_device': device  # Track original device
        }
        return models['trocr']
        
    except Exception as e:
        return None


def load_llama_model():
    """
    Connect to llamafile server (HTTP API)
    Returns a callable wrapper that mimics llama-cpp-python API
    """
    global models
    
    if models.get('llama') is not None:
        return models['llama']
    
    try:
        import requests
        
        llamafile_url = os.getenv('LLAMAFILE_URL', 'http://127.0.0.1:8080')
        
        # Test connection
        try:
            response = requests.get(f"{llamafile_url}/health", timeout=2)
            if response.status_code != 200:
                return None
        except requests.exceptions.RequestException:
            return None
        
        # Create HTTP wrapper that mimics llama-cpp-python API
        class LlamafileWrapper:
            """Wrapper that provides llama-cpp-python compatible interface"""
            
            def __init__(self, base_url):
                self.base_url = base_url
                self.session = requests.Session()
            
            def __call__(self, prompt, max_tokens=256, temperature=0.3, top_p=0.9, stop=None, **kwargs):
                """
                Call Llamafile API with llama-cpp-python compatible interface
                
                Returns:
                    {'choices': [{'text': '...'}]}
                """
                # Dynamic context window check: llamafile started with -c 8192
                context_window = int(os.getenv('LLAMA_CONTEXT_WINDOW', '8192'))
                # Rough estimate: 1 token ≈ 4 chars for English text
                estimated_prompt_tokens = len(prompt) // 4
                available_tokens = context_window - estimated_prompt_tokens
                # Ensure at least 64 output tokens, cap at available space
                max_tokens = min(max_tokens, max(available_tokens, 64))
                # Clamp temperature to valid range (0.0–2.0) — allow 0.0 for deterministic output
                temperature = max(0.0, min(temperature, 2.0))
                
                # Build stop sequences carefully - llamafile is sensitive to format
                stop_sequences = ['<|eot_id|>', '<|end_of_text|>']  # Llama 3.2 EOS tokens
                if stop:
                    if isinstance(stop, list):
                        stop_sequences.extend(stop)
                    else:
                        stop_sequences.append(stop)
                
                payload = {
                    'prompt': prompt,
                    'n_predict': max_tokens,  # Token limit
                    'temperature': temperature,
                    'top_p': top_p,
                    'stop': stop_sequences,
                    'cache_prompt': True,  # KV cache for speed
                }
                
                # Dynamic timeout based on expected generation + prompt processing time
                # Prompt processing: ~0.01s per estimated prompt token
                # Generation: ~0.05s per output token (assuming ~20 tokens/sec on GPU)
                prompt_time = estimated_prompt_tokens * 0.01
                generation_time = max_tokens * 0.05
                dynamic_timeout = 10 + prompt_time + generation_time
                timeout = max(15, min(dynamic_timeout, 120))  # Between 15-120 seconds
                
                try:
                    response = self.session.post(
                        f"{self.base_url}/completion",
                        json=payload,
                        timeout=timeout
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    # Convert llamafile response format to llama-cpp-python format
                    # Llamafile returns: {"content": "..."}
                    # We need: {"choices": [{"text": "..."}]}
                    if 'content' in result:
                        return {'choices': [{'text': result['content']}]}
                    else:
                        return result  # Already in correct format
                        
                except requests.exceptions.Timeout:
                    logging.getLogger('loader').warning(f"LLaMA request timed out after {timeout:.0f}s (max_tokens={max_tokens})")
                    try:
                        self.session.get(f"{self.base_url}/health", timeout=2)
                    except:
                        logging.getLogger('loader').error("LLaMA health check failed after timeout — server may be crashed")
                    # Retry once with reduced tokens
                    try:
                        retry_tokens = max(64, max_tokens // 2)
                        payload['n_predict'] = retry_tokens
                        logging.getLogger('loader').info(f"LLaMA retry with {retry_tokens} tokens...")
                        response = self.session.post(
                            f"{self.base_url}/completion",
                            json=payload,
                            timeout=timeout
                        )
                        response.raise_for_status()
                        result = response.json()
                        if 'content' in result:
                            return {'choices': [{'text': result['content']}]}
                        return result
                    except Exception as retry_err:
                        logging.getLogger('loader').warning(f"LLaMA retry also failed: {retry_err}")
                    return {'choices': [{'text': ''}]}
                except Exception as e:
                    logging.getLogger('loader').error(f"LLaMA request failed: {e}")
                    return {'choices': [{'text': ''}]}
        
        models['llama'] = LlamafileWrapper(llamafile_url)
        return models['llama']
        
    except Exception as e:
        return None


def get_models() -> Dict[str, Any]:
    """
    Get cached models dictionary (thread-safe)
    """
    global models
    if not models:
        with _models_lock:
            # Double-check pattern to avoid race condition
            if not models:
                load_all_models()
    return models


def ensure_llama_loaded() -> Any:
    """
    Thread-safe lazy loading of LLaMA model.
    Returns the LLaMA wrapper instance or None if unavailable.
    Use this instead of directly checking models.get('llama') and calling load_llama_model().
    """
    global models
    if models.get('llama') is not None:
        return models['llama']
    with _models_lock:
        # Double-check after acquiring lock
        if models.get('llama') is not None:
            return models['llama']
        llama = load_llama_model()
        if llama:
            models['llama'] = llama
        return llama


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

