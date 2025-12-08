"""
================================================================================
Configuration Endpoints - Runtime Configuration Management
================================================================================

PURPOSE:
--------
Provides REST API endpoints for dynamically updating AI Service configuration
without requiring service restarts. This allows the Control Panel to toggle
features, adjust thresholds, and optimize performance in real-time.

FEATURE TOGGLES (11 Pipeline Steps):
------------------------------------
All features are ENABLED by default unless explicitly disabled:

1. ENABLE_PDF_SPLITTING         - Split multi-document PDFs into logical documents
2. ENABLE_OCR_VALIDATION        - Validate OCR text quality with Llama
3. ENABLE_CLASSIFICATION        - Classify document type (31 categories)
4. ENABLE_SIGNATURE_DETECTION   - Detect signature regions with YOLOv8n
5. ENABLE_SIGNATURE_VALIDATION  - Validate and OCR signatures with TrOCR
6. ENABLE_STRUCTURED_EXTRACTION - Extract invoice/receipt structured data
7. ENABLE_ENTITY_EXTRACTION     - Extract companies, people, dates, amounts
8. ENABLE_TABLE_EXTRACTION      - Extract tables with PPStructure + LLaMA validation
9. ENABLE_SUMMARY               - Generate summaries with Llama 3.2 3B
10. ENABLE_EMBEDDING_GENERATION - Generate embeddings for semantic search
11. ENABLE_MONGODB_STORAGE      - Store processed data in MongoDB

CONFIGURATION PRIORITY:
----------------------
1. API updates (via POST /api/v1/config) → Highest priority
2. Environment variables (.env file)     → Medium priority
3. Default values (hardcoded)            → Lowest priority

API ENDPOINTS:
-------------
    GET  /api/v1/config        - Get current configuration
    POST /api/v1/config        - Update configuration (partial updates allowed)
    POST /api/v1/config/reset  - Reset to environment defaults

USAGE EXAMPLES:
--------------
    # Get current config
    curl http://localhost:9000/api/v1/config
    
    # Disable summarization
    curl -X POST http://localhost:9000/api/v1/config \
      -H "Content-Type: application/json" \
      -d '{"ENABLE_SUMMARY": false}'
    
    # Update multiple settings
    curl -X POST http://localhost:9000/api/v1/config \
      -H "Content-Type: application/json" \
      -d '{
        "ENABLE_SIGNATURE_DETECTION": true,
        "YOLO_CONFIDENCE": 0.7,
        "OCR_DPI": 200
      }'
    
    # Reset to defaults
    curl -X POST http://localhost:9000/api/v1/config/reset

CONFIGURATION FLOW:
------------------
    1. Service starts → Loads config from environment variables
    2. Control Panel updates config → Updates RUNTIME_CONFIG dict
    3. Pipeline reads config → Uses get_runtime_config()
    4. Processing happens with updated settings
    5. Config persists until service restart (in-memory only)

PERSISTENCE:
-----------
Configuration changes are NOT persisted to disk. They exist only in memory
and will reset to environment variable values on service restart.

To make permanent changes:
    1. Update .env file
    2. Restart AI service

WHY IN-MEMORY?
-------------
- Allows quick toggling for testing
- No file write permissions needed
- No risk of corrupting config files
- Easy rollback (restart service)

INTEGRATION:
-----------
The pipeline.py module reads config before each processing job:
    
    from app.api.config_endpoints import get_runtime_config
    config = get_runtime_config()
    
    if config['ENABLE_SIGNATURE_DETECTION']:
        detect_signatures(doc)

This ensures config changes take effect immediately on next document.

================================================================================
"""

# ========================
# Standard Library Imports
# ========================
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

# ========================
# FastAPI Imports
# ========================
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# ========================
# Logging Setup
# ========================
logger = logging.getLogger("config_endpoints")


# ========================
# FastAPI Router Configuration
# ========================
# All config endpoints will be under /api/v1/config prefix
config_router = APIRouter(prefix="/api/v1/config", tags=["configuration"])


# ========================
# Runtime Configuration Store
# ========================
# In-memory configuration dictionary loaded from environment variables
# DEFAULT PHILOSOPHY: All features ON unless explicitly disabled
# This dictionary is read by pipeline.py before processing each document
# NOTE: Current defaults = Tier 1 (Basic) configuration
RUNTIME_CONFIG = {
    # Pipeline Step Toggles (10 steps - all ON by default for Tier 1)
    "ENABLE_PDF_SPLITTING": os.getenv('ENABLE_PDF_SPLITTING', 'true').lower() == 'true',
    "ENABLE_OCR_VALIDATION": os.getenv('ENABLE_OCR_VALIDATION', 'true').lower() == 'true',
    "ENABLE_CLASSIFICATION": os.getenv('ENABLE_CLASSIFICATION', 'true').lower() == 'true',
    "ENABLE_SIGNATURE_DETECTION": os.getenv('ENABLE_SIGNATURE_DETECTION', 'true').lower() == 'true',
    "ENABLE_SIGNATURE_VALIDATION": os.getenv('ENABLE_SIGNATURE_VALIDATION', 'true').lower() == 'true',
    "ENABLE_STRUCTURED_EXTRACTION": os.getenv('ENABLE_STRUCTURED_EXTRACTION', 'true').lower() == 'true',
    "ENABLE_ENTITY_EXTRACTION": os.getenv('ENABLE_ENTITY_EXTRACTION', 'true').lower() == 'true',
    "ENABLE_TABLE_EXTRACTION": os.getenv('ENABLE_TABLE_EXTRACTION', 'true').lower() == 'true',
    "ENABLE_SUMMARY": os.getenv('ENABLE_SUMMARY', 'true').lower() == 'true',
    "ENABLE_EMBEDDING_GENERATION": os.getenv('ENABLE_EMBEDDING_GENERATION', 'true').lower() == 'true',
    "ENABLE_MONGODB_STORAGE": os.getenv('ENABLE_MONGODB_STORAGE', 'true').lower() == 'true',
    
    # Processing Parameters (4 existing)
    "SIMILARITY_THRESHOLD": float(os.getenv('SIMILARITY_THRESHOLD', '0.5')),  # Document splitting threshold
    "OCR_DPI": int(os.getenv('OCR_DPI', '300')),                              # Image resolution for OCR
    "YOLO_CONFIDENCE": float(os.getenv('YOLO_CONFIDENCE', '0.5')),           # Signature detection threshold
    "CLASSIFICATION_MIN_CONFIDENCE": float(os.getenv('CLASSIFICATION_MIN_CONFIDENCE', '0.08')),  # Classification confidence threshold
    
    # Advanced Parameters (14 total - Tier 1 defaults)
    "LLAMA_TEMPERATURE": float(os.getenv('LLAMA_TEMPERATURE', '0.3')),                      # LLaMA creativity (0-1)
    "LLAMA_MAX_TOKENS": int(os.getenv('LLAMA_MAX_TOKENS', '512')),                        # Max summary length
    "OCR_CONFIDENCE_THRESHOLD": int(os.getenv('OCR_CONFIDENCE_THRESHOLD', '50')),          # PaddleOCR quality (0-100)
    "SIGNATURE_CONFIDENCE_THRESHOLD": float(os.getenv('SIGNATURE_CONFIDENCE_THRESHOLD', '0.6')),  # YOLOv8n threshold
    "SEARCH_TOP_K_DEFAULT": int(os.getenv('SEARCH_TOP_K_DEFAULT', '5')),                  # Search results count
    "MAX_GPU_MEMORY_MB": int(os.getenv('MAX_GPU_MEMORY_MB', '4096')),                     # GPU memory limit
    "GPU_LAYERS": int(os.getenv('GPU_LAYERS', '29')),                                      # LLaMA GPU layers
    "MAX_PDF_SIZE_MB": int(os.getenv('MAX_PDF_SIZE_MB', '200')),                          # Max document size
    
    # LLaMA Validation Parameters (6 existing)
    "OCR_VALIDATION_TIMEOUT": int(os.getenv('OCR_VALIDATION_TIMEOUT', '30')),             # OCR validation timeout (seconds)
    "OCR_VALIDATION_TEMPERATURE": float(os.getenv('OCR_VALIDATION_TEMPERATURE', '0.05')),  # ✨ Ultra-low to preserve formatting
    "OCR_VALIDATION_MAX_TOKENS": int(os.getenv('OCR_VALIDATION_MAX_TOKENS', '2500')),     # ✨ Full page support
    "CLASSIFICATION_TIMEOUT": int(os.getenv('CLASSIFICATION_TIMEOUT', '45')),              # Classification timeout (seconds)
    "CLASSIFICATION_REASONING_TEMPERATURE": float(os.getenv('CLASSIFICATION_REASONING_TEMPERATURE', '0.3')),  # Classification LLaMA temp
    "CLASSIFICATION_LOW_CONFIDENCE_THRESHOLD": float(os.getenv('CLASSIFICATION_LOW_CONFIDENCE_THRESHOLD', '0.15')),  # Low confidence threshold
    
    # Structured Extraction Parameters (4 new)
    "EXTRACTION_MAX_TOKENS": int(os.getenv('EXTRACTION_MAX_TOKENS', '500')),              # Invoice/receipt field extraction tokens
    "EXTRACTION_TEMPERATURE": float(os.getenv('EXTRACTION_TEMPERATURE', '0.1')),           # Structured data extraction precision
    "ENTITY_EXTRACTION_MAX_TOKENS": int(os.getenv('ENTITY_EXTRACTION_MAX_TOKENS', '400')),  # Entity extraction tokens
    "ENTITY_EXTRACTION_TEMPERATURE": float(os.getenv('ENTITY_EXTRACTION_TEMPERATURE', '0.1')),  # Entity extraction precision
    
    # Signature Validation Parameters (6 new)
    "SIGNATURE_VALIDATION_MAX_TOKENS": int(os.getenv('SIGNATURE_VALIDATION_MAX_TOKENS', '150')),  # Signature text validation tokens
    "SIGNATURE_VALIDATION_TEMPERATURE": float(os.getenv('SIGNATURE_VALIDATION_TEMPERATURE', '0.2')),  # Signature validation precision
    "NAME_EXTRACTION_MAX_TOKENS": int(os.getenv('NAME_EXTRACTION_MAX_TOKENS', '100')),    # Extract names from document tokens
    "NAME_EXTRACTION_TEMPERATURE": float(os.getenv('NAME_EXTRACTION_TEMPERATURE', '0.1')),  # Name extraction precision
    "AUTHENTICITY_MAX_TOKENS": int(os.getenv('AUTHENTICITY_MAX_TOKENS', '200')),          # Signature authenticity check tokens
    "AUTHENTICITY_TEMPERATURE": float(os.getenv('AUTHENTICITY_TEMPERATURE', '0.3')),       # Authenticity analysis precision
    
    # OCR Validation Additional Parameters (3 new)
    "OCR_QUALITY_SKIP_THRESHOLD": float(os.getenv('OCR_QUALITY_SKIP_THRESHOLD', '0.95')),  # Skip validation if OCR quality above this
    "VALIDATION_QUALITY_MAX_TOKENS": int(os.getenv('VALIDATION_QUALITY_MAX_TOKENS', '200')),  # Number/date validation tokens
    "VALIDATION_QUALITY_TEMPERATURE": float(os.getenv('VALIDATION_QUALITY_TEMPERATURE', '0.1')),  # Validation precision
    
    # Table Extraction Parameters (3 new)
    "TABLE_EXTRACTION_TIMEOUT": int(os.getenv('TABLE_EXTRACTION_TIMEOUT', '20')),         # HTTP timeout for llamafile
    "TABLE_EXTRACTION_TEMPERATURE": float(os.getenv('TABLE_EXTRACTION_TEMPERATURE', '0.2')),  # Table extraction precision
    "TABLE_EXTRACTION_MAX_TOKENS": int(os.getenv('TABLE_EXTRACTION_MAX_TOKENS', '1500')),  # Table data extraction tokens
    
    # YOLO Detection Parameters (1 new)
    "YOLO_IOU_THRESHOLD": float(os.getenv('YOLO_IOU_THRESHOLD', '0.45')),                 # Non-maximum suppression threshold
    
    # Classification Parameters (1 new)
    "LLAMA_OVERRIDE_CONFIDENCE": float(os.getenv('LLAMA_OVERRIDE_CONFIDENCE', '0.85')),   # Confidence when LLaMA overrides classification
    
    # Document Splitting Parameters (1 new)
    "LLAMAFILE_HEALTH_TIMEOUT": int(os.getenv('LLAMAFILE_HEALTH_TIMEOUT', '2')),         # Health check timeout seconds
    
    # Metadata
    "last_updated": datetime.utcnow().isoformat(),
    "source": "environment_variables",
    "tier": "basic"  # Current tier level
}


class ConfigUpdateRequest(BaseModel):
    """Request model for config updates - 10 pipeline steps + 11 parameters (21 total)"""
    # Pipeline Step Toggles (10)
    ENABLE_PDF_SPLITTING: Optional[bool] = None
    ENABLE_OCR_VALIDATION: Optional[bool] = None
    ENABLE_CLASSIFICATION: Optional[bool] = None
    ENABLE_SIGNATURE_DETECTION: Optional[bool] = None
    ENABLE_SIGNATURE_VALIDATION: Optional[bool] = None
    ENABLE_STRUCTURED_EXTRACTION: Optional[bool] = None
    ENABLE_ENTITY_EXTRACTION: Optional[bool] = None
    ENABLE_TABLE_EXTRACTION: Optional[bool] = None
    ENABLE_SUMMARY: Optional[bool] = None
    ENABLE_EMBEDDING_GENERATION: Optional[bool] = None
    ENABLE_MONGODB_STORAGE: Optional[bool] = None
    
    # Basic Parameters (4)
    SIMILARITY_THRESHOLD: Optional[float] = None
    OCR_DPI: Optional[int] = None
    YOLO_CONFIDENCE: Optional[float] = None
    CLASSIFICATION_MIN_CONFIDENCE: Optional[float] = None
    
    # Advanced Parameters (14 total)
    LLAMA_TEMPERATURE: Optional[float] = None
    LLAMA_MAX_TOKENS: Optional[int] = None
    OCR_CONFIDENCE_THRESHOLD: Optional[int] = None
    SIGNATURE_CONFIDENCE_THRESHOLD: Optional[float] = None
    SEARCH_TOP_K_DEFAULT: Optional[int] = None
    MAX_GPU_MEMORY_MB: Optional[int] = None
    GPU_LAYERS: Optional[int] = None
    MAX_PDF_SIZE_MB: Optional[int] = None
    
    # LLaMA Validation Parameters (6 existing)
    OCR_VALIDATION_TIMEOUT: Optional[int] = None
    OCR_VALIDATION_TEMPERATURE: Optional[float] = None
    OCR_VALIDATION_MAX_TOKENS: Optional[int] = None
    CLASSIFICATION_TIMEOUT: Optional[int] = None
    CLASSIFICATION_REASONING_TEMPERATURE: Optional[float] = None
    CLASSIFICATION_LOW_CONFIDENCE_THRESHOLD: Optional[float] = None
    
    # Structured Extraction Parameters (4 new)
    EXTRACTION_MAX_TOKENS: Optional[int] = None
    EXTRACTION_TEMPERATURE: Optional[float] = None
    ENTITY_EXTRACTION_MAX_TOKENS: Optional[int] = None
    ENTITY_EXTRACTION_TEMPERATURE: Optional[float] = None
    
    # Signature Validation Parameters (6 new)
    SIGNATURE_VALIDATION_MAX_TOKENS: Optional[int] = None
    SIGNATURE_VALIDATION_TEMPERATURE: Optional[float] = None
    NAME_EXTRACTION_MAX_TOKENS: Optional[int] = None
    NAME_EXTRACTION_TEMPERATURE: Optional[float] = None
    AUTHENTICITY_MAX_TOKENS: Optional[int] = None
    AUTHENTICITY_TEMPERATURE: Optional[float] = None
    
    # OCR Validation Additional Parameters (3 new)
    OCR_QUALITY_SKIP_THRESHOLD: Optional[float] = None
    VALIDATION_QUALITY_MAX_TOKENS: Optional[int] = None
    VALIDATION_QUALITY_TEMPERATURE: Optional[float] = None
    
    # Table Extraction Parameters (3 new)
    TABLE_EXTRACTION_TIMEOUT: Optional[int] = None
    TABLE_EXTRACTION_TEMPERATURE: Optional[float] = None
    TABLE_EXTRACTION_MAX_TOKENS: Optional[int] = None
    
    # YOLO Detection Parameters (1 new)
    YOLO_IOU_THRESHOLD: Optional[float] = None
    
    # Classification Parameters (1 new)
    LLAMA_OVERRIDE_CONFIDENCE: Optional[float] = None
    
    # Document Splitting Parameters (1 new)
    LLAMAFILE_HEALTH_TIMEOUT: Optional[int] = None


class ConfigResponse(BaseModel):
    """Response model for config"""
    config: Dict[str, Any]
    message: str
    timestamp: str


def get_runtime_config() -> Dict[str, Any]:
    """Get current runtime configuration"""
    return RUNTIME_CONFIG.copy()


def update_runtime_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update runtime configuration"""
    global RUNTIME_CONFIG
    
    for key, value in updates.items():
        if value is not None and key in RUNTIME_CONFIG:
            RUNTIME_CONFIG[key] = value
            logger.info(f"Config updated: {key} = {value}")
    
    RUNTIME_CONFIG["last_updated"] = datetime.utcnow().isoformat()
    RUNTIME_CONFIG["source"] = "control_panel"
    
    return RUNTIME_CONFIG.copy()


@config_router.get("/", response_model=ConfigResponse)
async def get_config():
    """
    Get current AI Service configuration
    
    Returns all runtime configuration including feature toggles
    """
    return ConfigResponse(
        config=get_runtime_config(),
        message="Current configuration retrieved successfully",
        timestamp=datetime.utcnow().isoformat()
    )


@config_router.post("/", response_model=ConfigResponse)
async def update_config(request: ConfigUpdateRequest):
    """
    Update AI Service configuration dynamically
    
    Control Panel can update feature toggles without restarting AI Service
    """
    try:
        # Convert request to dict, excluding None values
        updates = request.dict(exclude_none=True)
        
        if not updates:
            raise HTTPException(
                status_code=400,
                detail="No configuration updates provided"
            )
        
        # Validate thresholds
        if "SIMILARITY_THRESHOLD" in updates:
            if not 0.0 <= updates["SIMILARITY_THRESHOLD"] <= 1.0:
                raise HTTPException(
                    status_code=400,
                    detail="SIMILARITY_THRESHOLD must be between 0.0 and 1.0"
                )
        
        if "YOLO_CONFIDENCE" in updates:
            if not 0.0 <= updates["YOLO_CONFIDENCE"] <= 1.0:
                raise HTTPException(
                    status_code=400,
                    detail="YOLO_CONFIDENCE must be between 0.0 and 1.0"
                )
        
        if "OCR_DPI" in updates:
            if updates["OCR_DPI"] < 72 or updates["OCR_DPI"] > 600:
                raise HTTPException(
                    status_code=400,
                    detail="OCR_DPI must be between 72 and 600"
                )
        
        # Update configuration
        updated_config = update_runtime_config(updates)
        
        logger.info(f"Configuration updated from Control Panel: {updates}")
        
        return ConfigResponse(
            config=updated_config,
            message=f"Configuration updated successfully. {len(updates)} setting(s) changed.",
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating configuration: {str(e)}"
        )


@config_router.post("/reset", response_model=ConfigResponse)
async def reset_config():
    """
    Reset configuration to environment variable defaults
    """
    global RUNTIME_CONFIG
    
    RUNTIME_CONFIG = {
        "ENABLE_OCR_VALIDATION": os.getenv('ENABLE_OCR_VALIDATION', 'false').lower() == 'true',
        "ENABLE_SIGNATURE_DETECTION": os.getenv('ENABLE_SIGNATURE_DETECTION', 'false').lower() == 'true',
        "ENABLE_STRUCTURED_EXTRACTION": os.getenv('ENABLE_STRUCTURED_EXTRACTION', 'true').lower() == 'true',
        "ENABLE_ENTITY_EXTRACTION": os.getenv('ENABLE_ENTITY_EXTRACTION', 'false').lower() == 'true',
        "ENABLE_SUMMARY": os.getenv('ENABLE_SUMMARY', 'false').lower() == 'true',
        "SIMILARITY_THRESHOLD": float(os.getenv('SIMILARITY_THRESHOLD', '0.5')),
        "OCR_DPI": int(os.getenv('OCR_DPI', '300')),
        "YOLO_CONFIDENCE": float(os.getenv('YOLO_CONFIDENCE', '0.5')),
        "last_updated": datetime.utcnow().isoformat(),
        "source": "environment_variables"
    }
    
    logger.info("Configuration reset to environment variable defaults")
    
    return ConfigResponse(
        config=get_runtime_config(),
        message="Configuration reset to environment defaults",
        timestamp=datetime.utcnow().isoformat()
    )
