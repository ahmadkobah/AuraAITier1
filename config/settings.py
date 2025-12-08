"""
================================================================================
Configuration Settings - Application Configuration
================================================================================

PURPOSE:
--------
Centralized configuration management for the AI Document Processing Service.
All environment variables, paths, and constants are defined here for easy
maintenance and deployment configuration.

CONFIGURATION SOURCES:
---------------------
1. Environment Variables (.env file)
2. Default values (fallback when env var not set)
3. Runtime overrides (via API configuration endpoints)

ENVIRONMENT FILE (.env):
-----------------------
Create a .env file in the project root with these variables:

    # Server Configuration
    API_HOST=0.0.0.0
    API_PORT=9000
    
    # Database
    MONGODB_URI=mongodb://admin:password@localhost:27017
    DATABASE_NAME=aura
    
    # LLaMA Server
    LLAMAFILE_URL=http://localhost:8080
    
    # GPU Settings
    USE_GPU=true
    FORCE_GPU=false
    GPU_ON_DEMAND=true
    AUTO_CLEANUP_GPU=true
    MAX_GPU_MEMORY_MB=4096
    
    # Features (can be toggled at runtime)
    ENABLE_OCR_VALIDATION=true
    ENABLE_SIGNATURE_DETECTION=true
    ENABLE_STRUCTURED_EXTRACTION=true
    ENABLE_SUMMARY=true
    
    # Processing Limits
    MAX_UPLOAD_SIZE_MB=50
    MAX_PDF_SIZE_MB=200
    
    # Logging
    LOG_LEVEL=INFO

VARIABLE COMPATIBILITY:
----------------------
This module supports multiple variable names for backwards compatibility:
    - API_PORT or PORT → API server port
    - MONGO_URL or MONGODB_URI → Database connection string
    - DATABASE_NAME or MONGODB_DB → Database name
    - USE_GPU or FORCE_GPU → GPU usage flag

PATH STRUCTURE:
--------------
    project_root/
    ├── config/settings.py    (this file)
    ├── models/               (ML model weights)
    │   ├── sentence-transformers/
    │   ├── trocr/
    │   └── paddleocr/
    ├── data/                 (runtime data)
    │   ├── uploads/          (uploaded PDFs)
    │   └── temp/             (temporary files)
    └── logs/                 (application logs)

USAGE IN CODE:
-------------
    from config.settings import UPLOADS_DIR, MAX_UPLOAD_SIZE_MB
    
    # Use the constants
    file_path = UPLOADS_DIR / f"{doc_id}.pdf"
    if file_size_mb > MAX_UPLOAD_SIZE_MB:
        raise ValueError("File too large")

UPDATING CONFIGURATION:
----------------------
1. Edit .env file and restart service (for static config)
2. Use /api/v1/config endpoint (for runtime toggles)
3. Update this file and restart (for code-level constants)

================================================================================
"""

# ========================
# Standard Library Imports
# ========================
import os
from pathlib import Path
from dotenv import load_dotenv

# ========================
# Environment Loading
# ========================
# Load environment variables from .env file
# This must happen before reading any os.getenv() calls
load_dotenv()

# ========================
# Base Directory Setup
# ========================
# Resolve the absolute path to the project root directory
# settings.py is in config/, so parent.parent gets us to root
BASE_DIR = Path(__file__).resolve().parent.parent


# ========================
# API / Server Configuration
# ========================
# FastAPI server settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")  # Bind to all interfaces
API_PORT = int(os.getenv("API_PORT") or os.getenv("PORT") or "9000")  # Support both variable names
API_TITLE = "Adaptive Document Processing - AI Service"
API_VERSION = "2.0.0"
API_DESCRIPTION = "AI-powered document processing with OCR, classification, and search"


# ========================
# Database Configuration
# ========================
# MongoDB connection settings
MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017/"
DATABASE_NAME = os.getenv("DATABASE_NAME") or os.getenv("MONGODB_DB") or "aura"
MONGO_TIMEOUT_MS = 5000  # Connection timeout in milliseconds


# ========================
# LLaMA Server Configuration
# ========================
# LLaMA 3.2 3B server for Q&A and summarization
LLAMAFILE_URL = os.getenv("LLAMAFILE_URL", "http://localhost:8080")
LLAMA_TEMPERATURE = 0.3  # Lower = more focused, Higher = more creative
LLAMA_MAX_TOKENS = 512   # Maximum response length


# ========================
# Model Paths
# ========================
# Directories containing pre-trained model weights
MODELS_DIR = BASE_DIR / "models"
SENTENCE_TRANSFORMERS_DIR = MODELS_DIR / "sentence-transformers"  # Embedding models
TROCR_MODEL_DIR = MODELS_DIR / "trocr"                             # Handwriting OCR
YOLO_MODEL_PATH = BASE_DIR / "yolov8n.pt"                         # Signature detection


# ========================
# Data Directories
# ========================
# Runtime data storage locations
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"  # Uploaded PDF files
TEMP_DIR = DATA_DIR / "temp"        # Temporary processing files

# Ensure directories exist (create if missing)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)


# ========================
# Processing Configuration
# ========================
# Document processing limits and thresholds
MAX_UPLOAD_SIZE_MB = 50  # Maximum file size for upload endpoint
SUPPORTED_FILE_TYPES = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"]

# Confidence thresholds (0-1 or 0-100 depending on model)
OCR_CONFIDENCE_THRESHOLD = 50           # PaddleOCR confidence (0-100)
SIGNATURE_CONFIDENCE_THRESHOLD = 0.6    # YOLO detection confidence (0-1)
CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.08  # Document type classification (0-1)


# ========================
# Search Configuration
# ========================
# Semantic search and retrieval settings
SEARCH_SIMILARITY_THRESHOLD = 0.15  # Minimum cosine similarity to include result
SEARCH_TOP_K_DEFAULT = 5            # Default number of search results
TEXT_MATCH_BOOST = 0.3              # Boost score for exact text matches


# ========================
# GPU Configuration
# ========================
# GPU usage settings (see app/models/loader.py for detailed GPU management)
USE_GPU = (os.getenv("USE_GPU") or os.getenv("FORCE_GPU") or "true").lower() == "true"
GPU_LAYERS = int(os.getenv("GPU_LAYERS", "29"))  # Number of layers to offload to GPU


# ========================
# Logging Configuration
# ========================
# Application logging settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
