"""
FastAPI Server - AI Service Tier 1
Main endpoints for document processing, search, and Q&A
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Request, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import torch
import requests
from dotenv import load_dotenv

from app.models.loader import load_all_models, get_models, models_ready
from app.core.pipeline import run_full_ai_pipeline
from config.settings import UPLOADS_DIR, TEMP_DIR

# Load environment variables from .env file
load_dotenv()


# ========================
# Security Helpers
# ========================

# Allowed base directories for file access (uploads + temp)
_ALLOWED_BASE_DIRS = [
    os.path.realpath(str(UPLOADS_DIR)),
    os.path.realpath(str(TEMP_DIR)),
]


def validate_file_path(file_path: str) -> str:
    """
    Validate that a file path is within allowed directories.
    Prevents path traversal attacks (e.g., ../../etc/passwd).
    
    Returns the resolved real path if valid.
    Raises HTTPException 403 if path escapes allowed directories.
    """
    resolved = os.path.realpath(file_path)
    if not any(resolved.startswith(base) for base in _ALLOWED_BASE_DIRS):
        raise HTTPException(
            status_code=403,
            detail="Access denied: file path outside allowed directories"
        )
    return resolved


def safe_doc_id(doc_id: str):
    """
    Convert a document ID string to ObjectId if valid, otherwise return raw string.
    Handles both ObjectId hex strings and arbitrary string IDs consistently.
    """
    from bson import ObjectId
    if isinstance(doc_id, ObjectId):
        return doc_id
    try:
        return ObjectId(doc_id)
    except Exception:
        return doc_id

# Configure logging - Write to both console AND file with NO BUFFERING
import logging.handlers
import sys

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None  # type: ignore
sys.stderr.reconfigure(line_buffering=True) if hasattr(sys.stderr, 'reconfigure') else None  # type: ignore

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
os.makedirs(logs_dir, exist_ok=True)
log_file = os.path.join(logs_dir, 'ai-service.log')

# Create file handler with immediate flush
file_handler = logging.handlers.RotatingFileHandler(
    log_file,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Create console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler],
    force=True
)

logger = logging.getLogger("ai_service")
logger.setLevel(logging.INFO)
logger.info(f"📝 Logging to file: {log_file}")
logger.info(f"📝 Log handlers: {len(logger.handlers)} handlers configured")

# ========================
# Pydantic Models
# ========================

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    models_loaded: bool
    gpu_available: bool
    message: str


class StatusResponse(BaseModel):
    """Service status response"""
    status: str
    models_loaded: List[str]
    ready: bool
    gpu_available: bool
    available_models: int
    timestamp: datetime
    database_connected: bool = False
    database_name: Optional[str] = None


class ProcessRequest(BaseModel):
    """Request to process a document"""
    doc_id: str = Field(..., description="Document ID in MongoDB")
    pdf_file_path: str = Field(..., description="Path to uploaded PDF file")


class ProcessResponse(BaseModel):
    """Response after queuing document for processing"""
    doc_id: str
    status: str = "QUEUED"
    message: str
    timestamp: datetime


class DocumentStatusResponse(BaseModel):
    """Document processing status response"""
    doc_id: str
    status: str  # PENDING, PROCESSING, COMPLETE, FAILED
    processing_started: Optional[datetime] = None
    processing_completed: Optional[datetime] = None
    document_count: Optional[int] = None
    error: Optional[str] = None
    processed_data: Optional[List[Dict[str, Any]]] = None


class SearchRequest(BaseModel):
    """Vector search request"""
    query: str = Field(..., description="Search query text")
    doc_id: Optional[str] = Field(None, description="Limit search to specific document")
    top_k: int = Field(5, description="Number of results to return")


class SearchResult(BaseModel):
    """Search result item"""
    document_id: str
    score: float
    text_excerpt: str
    page_range: str


class QueryRequest(BaseModel):
    """Question answering request"""
    doc_id: Optional[str] = Field(None, description="Document to query (optional for summarize)")
    question: str = Field(..., description="Question to answer")
    context_size: int = Field(2000, description="Context window for answer generation")


class QueryResponse(BaseModel):
    """Question answering response"""
    doc_id: str
    question: str
    answer: str
    confidence: float
    timestamp: datetime


class ScanRequest(BaseModel):
    """Scanner endpoint request validation"""
    scanner_name: Optional[str] = None
    color_mode: str = Field(default='color', pattern=r'^(color|gray|lineart)$')
    dpi: int = Field(default=300, ge=150, le=1200)
    scan_mode: str = Field(default='flatbed', pattern=r'^(flatbed|adf)$')
    doc_id: str
    config_override: Optional[Dict[str, Any]] = None


# ========================
# Global State
# ========================

db_client: Optional[MongoClient] = None
db = None

# Thread pool for CPU-bound operations (PaddleOCR, etc.)
# This allows async endpoints to offload blocking operations without blocking the event loop
executor = ThreadPoolExecutor(max_workers=4)  # 4 concurrent OCR operations


# ========================
# Startup/Shutdown Hooks
# ========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Async context manager for application lifecycle
    Loads models on startup, closes connections on shutdown
    """
    global db_client, db
    
    # Startup
    try:
        # Track startup time for uptime calculation
        app.state.start_time = datetime.utcnow()
        
        # Load all models (output suppressed in loader)
        models = load_all_models()
        
        # Connect to MongoDB
        mongo_url = os.getenv(
            'MONGODB_URI',
            os.getenv('DB', 'mongodb://admin:password@localhost:27017')
        )
        # Get database name from env or extract from URL
        db_name = os.getenv('DATABASE_NAME') or os.getenv('MONGODB_DB')
        
        if not db_name:
            # Extract database name from connection string
            if 'mongodb+srv://' in mongo_url or 'mongodb://' in mongo_url:
                try:
                    db_name_from_url = mongo_url.split('/')[-1].split('?')[0]
                    db_name = db_name_from_url if db_name_from_url else 'aura'
                except:
                    db_name = 'aura'
            else:
                db_name = 'aura'
        
        logger.info(f"Connecting to MongoDB: {mongo_url[:50]}...")
        logger.info(f"Using database: {db_name}")
        db_client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
        db = db_client[db_name]
        
        # Test connection
        db.command('ping')
        logger.info(f"✓ Connected to MongoDB: {db_name}")
        
        # Create indexes
        logger.info("Creating MongoDB indexes...")
        documents = db['documents']
        documents.create_index('status')
        documents.create_index('created_at')
        # Vector search index (if using Atlas)
        logger.info("✓ Indexes created")
        
        logger.info("✓ Service started successfully")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down AI Service Tier 1...")
    try:
        if db_client:
            db_client.close()
            logger.info("✓ MongoDB connection closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# ========================
# FastAPI Application
# ========================

app = FastAPI(
    title="AI Service Tier 1",
    description="Lightweight document processing, classification, search, and Q&A",
    version="1.0.0",
    lifespan=lifespan
)

# ========================
# Request Logging Middleware
# ========================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    logger.info(f"🌐 {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"📤 Response status: {response.status_code}")
    return response

# ========================
# Health & Status Endpoints
# ========================
# (Main health check defined below after CORS configuration)

# ========================
# CORS Configuration
# ========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # Allow all origins
        "http://localhost:3000",  # Control Panel Frontend
        "http://localhost:4000",  # Control Panel Backend
        "http://localhost:5173",  # Aura Frontend
        "http://localhost:8000",  # Aura Backend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================
# Include Config Router
# ========================

from app.api.config_endpoints import config_router
app.include_router(config_router)
logger.info("✅ Configuration router registered at /api/v1/config")


# ========================
# Endpoints
# ========================

@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint for Control Panel
    """
    # Check if GPU is forced or actually available
    force_gpu = os.getenv('FORCE_GPU', 'true').lower() == 'true'
    gpu_available = torch.cuda.is_available() or force_gpu
    
    return HealthResponse(
        status="healthy" if models_ready() else "degraded",
        timestamp=datetime.utcnow(),
        models_loaded=models_ready(),
        gpu_available=gpu_available,
        message="All models loaded and ready" if models_ready() else "Some models still loading"
    )


@app.get("/api/v1/status")
async def get_detailed_status():
    """
    Detailed status endpoint for Control Panel integration
    Provides comprehensive service health information
    """
    try:
        models = get_models()
        models_loaded = [name for name, model in models.items() if model is not None]
        
        # Get runtime config
        from app.api.config_endpoints import get_runtime_config
        runtime_config = get_runtime_config()
        
        # GPU info
        gpu_info = {
            "available": torch.cuda.is_available(),
            "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        }
        
        if torch.cuda.is_available():
            try:
                gpu_info["device_name"] = torch.cuda.get_device_name(0)
                gpu_info["memory_allocated_mb"] = torch.cuda.memory_allocated(0) / (1024 * 1024)
                gpu_info["memory_reserved_mb"] = torch.cuda.memory_reserved(0) / (1024 * 1024)
            except Exception:
                pass
        
        return {
            "status": "running",
            "service": "AI Service Tier 1",
            "version": "1.0.0",
            "models_loaded": models_loaded,
            "models_ready": models_ready(),
            "gpu": gpu_info,
            "database": {
                "connected": db is not None,
                "name": db.name if db is not None else None
            },
            "config": runtime_config,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": int((datetime.utcnow() - app.state.start_time).total_seconds()) if hasattr(app.state, 'start_time') else 0
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@app.get("/system/hardware")
async def get_hardware_stats() -> Dict[str, Any]:
    """
    Get real-time hardware statistics (CPU, GPU, RAM)
    """
    try:
        import psutil
        import platform
        
        hardware_info = {
            'timestamp': datetime.utcnow().isoformat(),
            'system': {},
            'cpu': {},
            'gpu': {}
        }
        
        # System Info
        hardware_info['system'] = {
            'platform': platform.system(),
            'platform_release': platform.release(),
            'platform_version': platform.version(),
            'architecture': platform.machine(),
            'hostname': platform.node(),
            'processor': platform.processor()
        }
        
        # RAM Info
        ram = psutil.virtual_memory()
        hardware_info['system']['ram_total'] = round(ram.total / (1024 ** 3), 2)  # GB
        hardware_info['system']['ram_used'] = round(ram.used / (1024 ** 3), 2)
        hardware_info['system']['ram_available'] = round(ram.available / (1024 ** 3), 2)
        hardware_info['system']['ram_percent'] = round(ram.percent, 1)
        
        # CPU Info
        cpu_freq = psutil.cpu_freq()
        hardware_info['cpu'] = {
            'cores': psutil.cpu_count(logical=False),
            'threads': psutil.cpu_count(logical=True),
            'usage': psutil.cpu_percent(interval=0.5),
            'frequency_mhz': round(cpu_freq.current, 2) if cpu_freq else None,
            'frequency_max_mhz': round(cpu_freq.max, 2) if cpu_freq else None,
        }
        
        # CPU Temperature (Windows/Linux)
        try:
            if hasattr(psutil, 'sensors_temperatures'):
                temps = psutil.sensors_temperatures()  # type: ignore
                if temps:
                    # Try common sensor names
                    for sensor_name in ['coretemp', 'cpu_thermal', 'k10temp']:
                        if sensor_name in temps:
                            cpu_temps = [t.current for t in temps[sensor_name] if t.current]
                            if cpu_temps:
                                hardware_info['cpu']['temperature'] = round(sum(cpu_temps) / len(cpu_temps), 1)
                                break
        except Exception as e:
            logger.debug(f"Could not get CPU temperature: {e}")
            hardware_info['cpu']['temperature'] = None
        
        # CPU Model
        try:
            hardware_info['cpu']['model'] = platform.processor()
        except:
            hardware_info['cpu']['model'] = 'Unknown'
        
        # GPU Info (NVIDIA only via torch)
        if torch.cuda.is_available():
            try:
                gpu_id = 0
                gpu_props = torch.cuda.get_device_properties(gpu_id)
                
                hardware_info['gpu'] = {
                    'available': True,
                    'name': gpu_props.name,
                    'cuda_version': getattr(torch.version, 'cuda', 'N/A') if hasattr(torch, 'version') else 'N/A',  # type: ignore
                    'memory': {
                        'total': round(gpu_props.total_memory / (1024 ** 3), 2),  # GB
                        'allocated': round(torch.cuda.memory_allocated(gpu_id) / (1024 ** 3), 2),
                        'reserved': round(torch.cuda.memory_reserved(gpu_id) / (1024 ** 3), 2),
                        'free': round((gpu_props.total_memory - torch.cuda.memory_allocated(gpu_id)) / (1024 ** 3), 2)
                    }
                }
                
                # GPU Memory Usage Percentage
                memory_used = torch.cuda.memory_allocated(gpu_id)
                memory_total = gpu_props.total_memory
                hardware_info['gpu']['memory']['used'] = round(memory_used / (1024 ** 3), 2)
                hardware_info['gpu']['memory']['percent'] = round((memory_used / memory_total) * 100, 2)
                
                # Try to get GPU utilization using nvidia-smi
                try:
                    import subprocess
                    result = subprocess.run(
                        ['nvidia-smi', '--query-gpu=utilization.gpu,temperature.gpu', '--format=csv,noheader,nounits'],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0:
                        gpu_util, gpu_temp = result.stdout.strip().split(',')
                        hardware_info['gpu']['usage'] = float(gpu_util.strip())
                        hardware_info['gpu']['temperature'] = float(gpu_temp.strip())
                except Exception as e:
                    logger.debug(f"Could not get GPU stats from nvidia-smi: {e}")
                    # Estimate GPU usage from memory usage as fallback
                    hardware_info['gpu']['usage'] = round((memory_used / memory_total) * 100, 2)
                    hardware_info['gpu']['temperature'] = None
                
            except Exception as e:
                logger.error(f"Error getting GPU stats: {e}")
                hardware_info['gpu'] = {
                    'available': True,
                    'error': str(e)
                }
        else:
            hardware_info['gpu'] = {
                'available': False,
                'message': 'No CUDA GPU detected'
            }
        
        return hardware_info
        
    except Exception as e:
        logger.error(f"Error collecting hardware stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Hardware monitoring error: {str(e)}"
        )


@app.post("/api/v1/process", response_model=ProcessResponse)
async def process_document(
    request: ProcessRequest,
    background_tasks: BackgroundTasks,
    config_override: Optional[Dict[str, Any]] = None
) -> ProcessResponse:
    """
    Queue document for AI processing
    
    Fire-and-forget: Accepts document, queues for background processing,
    returns immediately. Client polls MongoDB for status updates.
    
    Args:
        request: ProcessRequest with doc_id and pdf_file_path
        background_tasks: FastAPI background tasks
        config_override: Optional config overrides (tier/company-specific settings)
        
    Returns:
        ProcessResponse confirming document queued
    
    Config Priority:
        1. config_override (highest) - Tier/company-specific settings from Control Panel
        2. RUNTIME_CONFIG (medium) - AI Service configuration
        3. Environment defaults (lowest) - .env file settings
    """
    try:
        doc_id = request.doc_id
        pdf_path = validate_file_path(request.pdf_file_path)
        
        # Validate file exists
        if not os.path.exists(pdf_path):
            raise HTTPException(
                status_code=400,
                detail=f"PDF file not found: {pdf_path}"
            )
        
        logger.info(f"Received process request for {doc_id}: {pdf_path}")
        
        # Create document record in MongoDB
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        documents = db['documents']
        documents.insert_one({
            '_id': doc_id,
            'status': 'PENDING',
            'created_at': datetime.utcnow(),
            'processing_started': None,
            'processing_completed': None,
            'pdf_path': str(pdf_path),  # Convert Path to string for MongoDB
            'processed_data': [],
            'error': None
        })
        
        # Validate models are ready before queueing
        models = get_models()
        if not models or not models.get('paddleocr') or not models.get('sentence_transformer_search'):
            raise HTTPException(
                status_code=503,
                detail="AI models are still loading. Please try again in a few moments."
            )
        
        # Queue background task with optional config override
        background_tasks.add_task(
            run_full_ai_pipeline,
            doc_id,
            pdf_path,
            db,
            models,
            config_override
        )
        
        logger.info(f"✓ Document {doc_id} queued for processing (config_override: {'Yes' if config_override else 'No'})")
        
        return ProcessResponse(
            doc_id=doc_id,
            status="QUEUED",
            message=f"Document {doc_id} queued for processing",
            timestamp=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error queuing document: {str(e)}"
        )


@app.post("/api/v1/upload", response_model=ProcessResponse)
async def upload_and_process_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    doc_id: Optional[str] = Form(None),
    config_override: Optional[str] = Form(None)
) -> ProcessResponse:
    """
    Upload document directly from frontend/scanner and queue for AI processing
    
    This endpoint accepts file uploads directly (e.g., from scanner, frontend upload)
    and automatically processes them through the AI pipeline.
    
    Args:
        file: PDF file from scanner/frontend (multipart/form-data)
        background_tasks: FastAPI background tasks
        doc_id: Optional backend document ID to use (if not provided, generates UUID)
        config_override: Optional JSON string of config overrides (tier/company-specific)
        
    Returns:
        ProcessResponse with doc_id and status
        
    Config Priority:
        1. config_override (highest) - Tier/company-specific settings from Control Panel
        2. RUNTIME_CONFIG (medium) - AI Service configuration
        3. Environment defaults (lowest) - .env file settings
    """
    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported"
            )
        
        # Use provided doc_id or generate new one
        if not doc_id:
            import uuid
            doc_id = str(uuid.uuid4())
        
        # Use configured uploads directory
        upload_dir = UPLOADS_DIR
        
        # Save uploaded file
        file_path = upload_dir / f"{doc_id}_{file.filename}"
        
        logger.info(f"Receiving upload: {file.filename} → {doc_id}")
        
        # Write file to disk
        with open(str(file_path), "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        logger.info(f"✓ Saved file: {file_path} ({len(content)} bytes)")
        
        # Update or create document record in MongoDB
        from bson import ObjectId
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        documents = db['documents']
        documents.update_one(
            {'_id': safe_doc_id(doc_id)},
            {
                '$set': {
                    'status': 'PENDING',
                    'created_at': datetime.utcnow(),
                    'processing_started': None,
                    'processing_completed': None,
                    'pdf_path': str(file_path),
                    'original_filename': file.filename,
                    'file_size': len(content),
                    'processed_data': [],
                    'error': None
                }
            },
            upsert=True
        )
        
        # Validate models are ready before queueing
        models = get_models()
        if not models or not models.get('paddleocr') or not models.get('sentence_transformer_search'):
            raise HTTPException(
                status_code=503,
                detail="AI models are still loading. Please try again in a few moments."
            )
        
        # Parse config_override if provided
        config_dict = None
        if config_override:
            try:
                import json
                config_dict = json.loads(config_override)
                logger.info(f"Using config override for {doc_id}: {list(config_dict.keys())}")
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid config_override JSON: {e}. Using default config.")
        
        # Queue background task for processing
        if background_tasks:
            background_tasks.add_task(
                run_full_ai_pipeline,
                doc_id,
                str(file_path),
                db,
                models,
                config_dict
            )
        
        logger.info(f"✓ Document {doc_id} queued for processing (config_override: {'Yes' if config_dict else 'No'})")
        
        return ProcessResponse(
            doc_id=doc_id,
            status="QUEUED",
            message=f"Document uploaded and queued for processing",
            timestamp=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading document: {str(e)}"
        )


@app.get("/api/v1/documents/{doc_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(doc_id: str) -> DocumentStatusResponse:
    """
    Get processing status of a specific document
    Checks documents collection for both upload and scan
    
    Args:
        doc_id: Document ID to check
        
    Returns:
        DocumentStatusResponse with current status and processing details
    """
    try:
        from bson import ObjectId
        
        # Convert string ID to ObjectId (try both formats for backward compatibility)
        doc_obj_id = safe_doc_id(doc_id)
        
        # Check documents collection
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        documents = db['documents']
        doc = documents.find_one({'_id': doc_obj_id})
        
        # Fallback: try raw string if ObjectId lookup failed
        if not doc and isinstance(doc_obj_id, ObjectId):
            doc = documents.find_one({'_id': doc_id})
        
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document {doc_id} not found"
            )
        
        return DocumentStatusResponse(
            doc_id=doc_id,
            status=doc.get('status', 'UNKNOWN'),
            processing_started=doc.get('processing_started'),
            processing_completed=doc.get('processing_completed'),
            document_count=doc.get('document_count'),
            error=doc.get('error'),
            processed_data=doc.get('processed_data') if doc.get('status') == 'COMPLETE' else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching document status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching status: {str(e)}"
        )


@app.post("/api/v1/search")
async def vector_search(request: SearchRequest) -> Dict[str, Any]:
    """
    Vector search across document embeddings
    
    Uses all-MiniLM-L6-v2 embeddings stored in MongoDB for similarity search
    
    Args:
        request: SearchRequest with query text and optional doc_id filter
        
    Returns:
        List of search results with similarity scores
    """
    try:
        models = get_models()
        sentence_transformer = models['sentence_transformer_search']
        
        # Embed query
        query_embedding = sentence_transformer.encode(
            request.query,
            convert_to_tensor=False
        ).tolist()
        
        logger.info(f"Vector search for: {request.query}")
        
        # Search in MongoDB
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        documents = db['documents']
        
        # Build query filter
        search_filter = {}
        if request.doc_id:
            search_filter['_id'] = request.doc_id
        
        # Perform search (requires MongoDB Atlas vector search)
        # Fallback: simple cosine similarity on pulled documents
        try:
            # Try Atlas vector search first
            pipeline = [
                {
                    '$search': {
                        'cosmosSearch': True,
                        'vector': query_embedding,
                        'k': request.top_k
                    }
                },
                {
                    '$project': {
                        'similarity_score': {'$meta': 'searchScore'},
                        'document': '$$ROOT'
                    }
                }
            ]
            
            if request.doc_id:
                pipeline.append({
                    '$match': {'document._id': request.doc_id}
                })
            
            results = list(documents.aggregate(pipeline))
            
        except Exception as e:
            # Fallback: FAISS-based local similarity search
            logger.info(f"Atlas search unavailable, using FAISS fallback: {e}")
            
            from app.utils.vector_index import search as faiss_search
            results = faiss_search(
                query_embedding=query_embedding,
                db=db,
                top_k=request.top_k,
                doc_id_filter=request.doc_id,
                query_text=request.query,
            )
        
        # Format results - Convert ObjectId to string for JSON serialization
        formatted_results = [
            {
                'document_id': str(r['document']['_id']),  # Convert ObjectId to string
                'score': r['similarity_score'],
                'text_excerpt': r['document']['text'][:200] + "...",
                'page_range': r['document'].get('page_range', 'N/A')
            }
            for r in results
        ]
        
        logger.info(f"✓ Found {len(formatted_results)} results")
        
        return {
            'query': request.query,
            'results': formatted_results,
            'count': len(formatted_results)
        }
        
    except Exception as e:
        logger.error(f"Error in vector search: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Search error: {str(e)}"
        )




@app.post("/api/v1/summarize")
async def summarize_document_endpoint(request: Request):
    """
    Generate a summary of a document using dynamic prompts from Control Panel
    
    Expects JSON body with:
    - doc_id: Document ID to summarize
    - question: Optional custom summarization prompt
    - context_size: Optional context window size
    
    Returns:
    - summary: Generated summary
    - doc_id: Document ID
    - timestamp: When summary was generated
    """
    try:
        data = await request.json()
        doc_id = data.get("doc_id")
        
        if not doc_id:
            raise HTTPException(status_code=400, detail="doc_id is required")
        
        # Get document from MongoDB
        from bson import ObjectId
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        documents = db['documents']
        
        # Try as ObjectId first, then as string
        try:
            doc = documents.find_one({'_id': ObjectId(doc_id)})
        except Exception:
            doc = documents.find_one({'_id': doc_id})
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
        
        # Get document metadata
        company_id = doc.get('companyId')
        tier = doc.get('tier', 'tier1')
        doc_type = "unknown"
        
        # Check if we already have summaries
        if doc.get('processed_data'):
            summaries = []
            for processed_doc in doc['processed_data']:
                if processed_doc.get('summary'):
                    summaries.append(processed_doc['summary'])
                # Get document type from classification
                if processed_doc.get('classification'):
                    doc_type = processed_doc['classification'].get('label', 'unknown')
            
            if summaries and not data.get('force_regenerate'):
                combined_summary = " ".join(summaries)
                return {
                    'doc_id': doc_id,
                    'summary': combined_summary,
                    'prompt_used': 'cached',
                    'timestamp': datetime.utcnow().isoformat()
                }
        
        # Get document text
        doc_text = ""
        if doc.get('processed_data'):
            for processed_doc in doc['processed_data']:
                if processed_doc.get('text'):
                    doc_text += processed_doc['text'] + "\n\n"
        
        if not doc_text:
            raise HTTPException(
                status_code=400,
                detail="Document has no extracted text to summarize"
            )
        
        # Try to get dynamic prompt from Control Panel
        from app.utils.prompt_manager import get_prompt_for_task, get_fallback_prompt
        
        summary_question = data.get('question', '')
        
        prompt_data = await get_prompt_for_task(
            ai_capability='summarization',
            document_type=doc_type,
            company_id=company_id,
            tier=tier,
            variables={
                'document_text': doc_text[:2000],
                'question': summary_question
            }
        )
        
        if not prompt_data:
            logger.warning("No dynamic summarization prompt found, using fallback")
            prompt_data = get_fallback_prompt(
                'summarization',
                variables={
                    'document_text': doc_text[:2000],
                    'question': summary_question
                }
            )
        
        logger.info(f"Generating summary using prompt: {prompt_data['metadata']['name']}")
        
        # Generate summary using LLaMA with dynamic prompt
        try:
            models = get_models()
            llama = models.get('llama')
            if llama is None:
                from app.models.loader import load_llama_model
                llama = load_llama_model()
                models['llama'] = llama
            
            if llama:
                llm_config = prompt_data.get('llm_config', {})
                response = llama(
                    prompt_data['prompt'],
                    max_tokens=llm_config.get('maxTokens', 300),
                    temperature=llm_config.get('temperature', 0.5),
                    top_p=llm_config.get('topP', 0.9),
                    top_k=llm_config.get('topK', 40),
                    stop=llm_config.get('stopSequences', []),
                    echo=False
                )
                summary = response.get('choices', [{}])[0].get('text', '').strip()
            else:
                summary = doc_text[:200] + "..."
                
        except Exception as llama_error:
            logger.warning(f"LLaMA summary failed: {llama_error}")
            # Fallback: Return first 200 chars as summary
            summary = doc_text[:200] + "..."
        
        return {
            'doc_id': doc_id,
            'summary': summary,
            'prompt_used': prompt_data['metadata']['name'],
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Summary error: {str(e)}"
        )


@app.post("/api/v1/extract")
async def extract_structured_fields(request: QueryRequest) -> Dict[str, Any]:
    """
    Extract structured data from document based on document type
    Uses dynamic prompts from Control Panel with fallback to hardcoded logic

    Args:
        request: QueryRequest with doc_id and optional fields list

    Returns:
        Extracted structured data (invoice fields, contract terms, etc.)
    """
    try:
        if not request.doc_id:
            raise HTTPException(
                status_code=400,
                detail="doc_id is required"
            )

        models = get_models()
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        documents = db['documents']
        doc = documents.find_one({'_id': request.doc_id})

        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document {request.doc_id} not found"
            )

        doc_status = doc.get('status', 'UNKNOWN')
        if doc_status != 'COMPLETE':
            raise HTTPException(
                status_code=400,
                detail=f"Document still processing (status: {doc_status})"
            )

        # Get document text, classification, company, and tier
        doc_text = ""
        doc_type = "unknown"
        company_id = doc.get('companyId')
        tier = doc.get('tier', 'tier1')

        for processed_doc in doc.get('processed_data', []):
            doc_text += processed_doc.get('text', '')
            classification = processed_doc.get('classification', {})
            doc_type = classification.get('label', 'unknown')

        logger.info(f"Extracting structured data from {request.doc_id} (type: {doc_type}, company: {company_id}, tier: {tier})")

        # Try to get dynamic prompt from Control Panel
        from app.utils.prompt_manager import get_prompt_for_task, get_fallback_prompt
        
        prompt_data = await get_prompt_for_task(
            ai_capability='ner_extraction',
            document_type=doc_type,
            company_id=company_id,
            tier=tier,
            variables={'document_text': doc_text[:1500]}
        )
        
        if prompt_data:
            logger.info(f"✓ Using dynamic prompt: {prompt_data['metadata']['name']} (priority={prompt_data['metadata']['priority']})")
            # Use prompt-based extraction with dynamic LLM config
            from app.utils.extraction import extract_with_prompt
            extraction_result = await extract_with_prompt(doc_text, doc_type, models, prompt_data)
        else:
            logger.warning(f"No dynamic prompt found, falling back to hardcoded extraction")
            # Fallback to original hardcoded extraction
            from app.utils.extraction import extract_structured_data
            extraction_result = await extract_structured_data(doc_text, doc_type, models)

        return {
            'doc_id': request.doc_id,
            'document_type': doc_type,
            'extraction': extraction_result,
            'prompt_used': prompt_data['metadata']['name'] if prompt_data else 'fallback',
            'timestamp': datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting structured data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Extraction error: {str(e)}"
        )


@app.post("/api/v1/entities")
async def extract_document_entities(request: QueryRequest) -> Dict[str, Any]:
    """
    Extract named entities from document

    Args:
        request: QueryRequest with doc_id

    Returns:
        Dictionary with entity types and lists of found entities
    """
    try:
        if not request.doc_id:
            raise HTTPException(
                status_code=400,
                detail="doc_id is required"
            )

        models = get_models()
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        documents = db['documents']
        doc = documents.find_one({'_id': request.doc_id})

        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document {request.doc_id} not found"
            )

        doc_status = doc.get('status', 'UNKNOWN')
        if doc_status != 'COMPLETE':
            raise HTTPException(
                status_code=400,
                detail=f"Document still processing (status: {doc_status})"
            )

        # Get document text
        doc_text = ""
        for processed_doc in doc.get('processed_data', []):
            doc_text += processed_doc.get('text', '') + " "

        logger.info(f"Extracting entities from {request.doc_id}")

        # Extract entities
        from app.utils.extraction import extract_entities
        entities = await extract_entities(doc_text, models)

        return {
            'doc_id': request.doc_id,
            'entities': entities,
            'total_entities': sum(len(v) for v in entities.values()),
            'timestamp': datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Entity extraction error: {str(e)}"
        )


@app.post("/api/v1/validate-ocr")
async def validate_document_ocr(request: QueryRequest) -> Dict[str, Any]:
    """
    Validate and improve OCR quality for a document

    Args:
        request: QueryRequest with doc_id

    Returns:
        OCR validation results with corrected text
    """
    try:
        if not request.doc_id:
            raise HTTPException(
                status_code=400,
                detail="doc_id is required"
            )

        models = get_models()
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        documents = db['documents']
        doc = documents.find_one({'_id': request.doc_id})

        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document {request.doc_id} not found"
            )

        doc_status = doc.get('status', 'UNKNOWN')
        if doc_status != 'COMPLETE':
            raise HTTPException(
                status_code=400,
                detail=f"Document still processing (status: {doc_status})"
            )

        # Get document text
        doc_text = ""
        for processed_doc in doc.get('processed_data', []):
            doc_text += processed_doc.get('text', '') + "\n\n"

        logger.info(f"Validating OCR quality for {request.doc_id}")

        # Validate OCR
        from app.services.ocr_validation import validate_ocr_quality
        validation_result = await validate_ocr_quality(doc_text, models)

        return {
            'doc_id': request.doc_id,
            'validation': validation_result,
            'timestamp': datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating OCR: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"OCR validation error: {str(e)}"
        )


# ========================
# Scanner Endpoints
# ========================

@app.get("/api/v1/scanners")
async def list_scanners():
    """
    List all available physical scanners
    """
    try:
        from app.scanner.scanner_service import get_scanner_service
        
        scanner_service = get_scanner_service()
        scanners = scanner_service.list_scanners()
        
        return {
            'status': 'success',
            'scanners': scanners,
            'count': len(scanners),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listing scanners: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Scanner listing error: {str(e)}"
        )


@app.post("/api/v1/scan")
async def scan_document(
    background_tasks: BackgroundTasks,
    scan_request: ScanRequest
):
    """
    Scan document from physical scanner and process through AI pipeline
    """
    try:
        from app.scanner.scanner_service import get_scanner_service
        import uuid
        
        if db is None:
            raise HTTPException(status_code=503, detail="Database not connected")
        
        # Parse config_override if provided
        config_dict = scan_request.config_override
        if config_dict:
            logger.info(f"Using config override for scan {scan_request.doc_id}: {list(config_dict.keys())}")
        
        logger.info(f"\ud83d\udda8\ufe0f Scanning document (scanner={scan_request.scanner_name or 'default'}, mode={scan_request.color_mode}, dpi={scan_request.dpi})")
        
        # Get scanner service
        scanner_service = get_scanner_service()
        
        # Scan pages
        scanned_images = scanner_service.scan_document(
            scanner_name=scan_request.scanner_name,
            color_mode=scan_request.color_mode,
            dpi=scan_request.dpi,
            scan_mode=scan_request.scan_mode
        )
        
        if not scanned_images:
            raise HTTPException(status_code=400, detail="No pages scanned")
        
        logger.info(f"\u2713 Scanned {len(scanned_images)} page(s)")
        
        # Save as temporary PDF
        scan_id = str(uuid.uuid4())
        temp_pdf_path = os.path.join(TEMP_DIR, f"scan_{scan_id}.pdf")
        
        # Convert images to PDF
        if len(scanned_images) == 1:
            scanned_images[0].save(temp_pdf_path, 'PDF', resolution=scan_request.dpi)
        else:
            scanned_images[0].save(
                temp_pdf_path,
                'PDF',
                save_all=True,
                append_images=scanned_images[1:],
                resolution=scan_request.dpi
            )
        
        logger.info(f"\u2713 Saved scanned PDF: {temp_pdf_path}")
        
        # Use global db connection (no new MongoClient needed)
        from bson import ObjectId
        
        doc_id = scan_request.doc_id
        
        # Update the existing backend document with scan info
        db['documents'].update_one(
            {'_id': ObjectId(doc_id)},
            {
                '$set': {
                    'status': 'SCANNING',
                    'scan_pages': len(scanned_images),
                    'scan_timestamp': datetime.utcnow(),
                    'file_path': temp_pdf_path,
                    'document_count': 0,
                    'processed_data': []
                }
            },
            upsert=True
        )
        
        # Validate models are ready before queueing background task
        models = get_models()
        if not models or not models.get('paddleocr') or not models.get('sentence_transformer_search'):
            raise HTTPException(
                status_code=503,
                detail="AI models are still loading. Please try again in a few moments."
            )
        
        # Process through AI pipeline in background using the SAME document ID with config override
        background_tasks.add_task(
            run_full_ai_pipeline,
            doc_id,
            temp_pdf_path,
            db,
            models,
            config_dict
        )
        
        logger.info(f"✓ Scanned document {doc_id} queued for processing (config_override: {'Yes' if config_dict else 'No'})")
        
        return {
            'status': 'success',
            'message': 'Document scanned and queued for processing',
            'doc_id': doc_id,
            'pages_scanned': len(scanned_images),
            'scan_id': scan_id,
            'config_applied': bool(config_dict),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scanner error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Scanning error: {str(e)}"
        )


# ========================
# Q&A and Search Endpoints
# ========================

# Debug/test endpoints — only available when ENABLE_DEBUG_ENDPOINTS=true
_debug_endpoints_enabled = os.getenv('ENABLE_DEBUG_ENDPOINTS', 'false').lower() == 'true'

@app.get("/api/v1/test-code-version")
async def test_code_version():
    """Test endpoint to verify code has reloaded"""
    if not _debug_endpoints_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    return {"version": "v2_with_processed_data_fix", "timestamp": "2025-11-29_00:40"}

@app.get("/api/v1/test-db-connection")
async def test_db_connection():
    """Test MongoDB connection and show document count"""
    if not _debug_endpoints_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        if db is None:
            return {"error": "Database not initialized"}
        
        documents = db['documents']
        count = documents.count_documents({})
        
        # Get first 5 document IDs
        sample_docs = list(documents.find({}, {'_id': 1, 'filename': 1}).limit(5))
        doc_ids = [str(d['_id']) for d in sample_docs]
        
        return {
            "status": "connected",
            "database": db.name,
            "total_documents": count,
            "sample_ids": doc_ids
        }
    except Exception as e:
        return {"error": str(e), "db_status": "failed"}

@app.get("/api/v1/test-document/{doc_id}")
async def test_document(doc_id: str):
    """Test if a specific document can be found"""
    if not _debug_endpoints_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    global db
    try:
        if db is None:
            return {"error": "Database not initialized"}
        
        from bson import ObjectId
        documents = db['documents']
        
        # Try to find the document
        try:
            doc = documents.find_one({'_id': ObjectId(doc_id)})
        except Exception as e:
            return {"error": f"Invalid ObjectId: {str(e)}", "doc_id": doc_id}
        
        if not doc:
            # List all available IDs for comparison
            all_ids = [str(d['_id']) for d in documents.find({}, {'_id': 1}).limit(10)]
            return {
                "found": False,
                "doc_id": doc_id,
                "available_ids": all_ids,
                "message": "Document not found in database"
            }
        
        # Document found - check for text
        has_processed_data = bool(doc.get('processed_data'))
        has_text = False
        text_location = None
        
        processed_data = doc.get('processed_data', [])
        if has_processed_data and isinstance(processed_data, list):
            for item in processed_data:
                if isinstance(item, dict) and (item.get('text') or item.get('full_text')):
                    has_text = True
                    text_location = 'processed_data'
                    break
        
        return {
            "found": True,
            "doc_id": doc_id,
            "filename": doc.get('filename'),
            "has_processed_data": has_processed_data,
            "has_text": has_text,
            "text_location": text_location,
            "keys": list(doc.keys())
        }
    except Exception as e:
        return {"error": str(e), "traceback": str(e.__traceback__)}

@app.post("/api/v1/qa", response_model=QueryResponse)
@app.post("/api/v1/query", response_model=QueryResponse)
async def query_document(request: QueryRequest) -> QueryResponse:
    """
    Question answering over a document using Llamafile
    """
    # DEBUG: Log FIRST before anything else
    logger.info(f"🔵 Q&A REQUEST RECEIVED:")
    logger.info(f"   • request.doc_id = '{request.doc_id}'")
    logger.info(f"   • type = {type(request.doc_id)}")
    logger.info(f"   • length = {len(request.doc_id) if request.doc_id else 0}")
    logger.info(f"   • repr = {repr(request.doc_id)}")
    logger.info(f"   • question = '{request.question}'")
    
    global db
    
    try:
        
        if not request.doc_id:
            raise HTTPException(status_code=400, detail="doc_id is required")
        
        if db is None:
            raise HTTPException(status_code=500, detail="Database not initialized")
        
        # Verify database connection is alive
        try:
            db.command('ping')
            logger.info(f"✅ Database connection verified for Q&A request (doc_id: {request.doc_id})")
            logger.info(f"✅ Database name: {db.name}")
            logger.info(f"✅ Database client: {type(db).__name__}")
        except Exception as ping_error:
            logger.error(f"❌ Database connection lost: {ping_error}")
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        from bson import ObjectId
        import requests
        
        # Get document from MongoDB
        documents = db['documents']
        logger.info(f"✅ Collection reference created: {type(documents).__name__}")
        
        # Log the exact query before execution
        logger.info(f"🔍 About to query document: {request.doc_id}")
        
        try:
            obj_id = safe_doc_id(request.doc_id)
            logger.info(f"✅ Document ID resolved: {obj_id}")
            doc = documents.find_one({'_id': obj_id})
            # Fallback: try raw string if ObjectId lookup failed
            if not doc and isinstance(obj_id, ObjectId):
                doc = documents.find_one({'_id': request.doc_id})
            logger.info(f"🔍 Query executed. Result: {'FOUND' if doc else 'NOT FOUND'}")
        except Exception as e:
            logger.error(f"❌ Error resolving doc_id: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid doc_id format: {request.doc_id}")
        
        if not doc:
            logger.error(f"❌ Document not found in database: {request.doc_id}")
            # List similar documents for debugging
            all_docs = list(documents.find({}, {'_id': 1, 'filename': 1}).limit(10))
            logger.error(f"❌ Available documents: {[str(d['_id']) for d in all_docs]}")
            logger.error(f"❌ Total documents in collection: {documents.count_documents({})}")
            raise HTTPException(status_code=404, detail=f"Document {request.doc_id} not found in database")
        
        logger.info(f"Found document: {doc.get('filename', 'unknown')} (_id: {request.doc_id})")
        
        # Get extracted text from document
        extracted_text = ""
        
        # Try processed_data first (new AI pipeline format)
        processed_data = doc.get('processed_data', [])
        if processed_data and isinstance(processed_data, list):
            for proc in processed_data:
                if isinstance(proc, dict):
                    # Try full_text first, then text
                    text = proc.get('full_text') or proc.get('text')
                    if text:
                        extracted_text += text + '\n\n'
            if extracted_text:
                logger.info(f"Using text from processed_data ({len(extracted_text)} chars)")
        # Try extractedMetadata.ocr_text
        elif doc.get('extractedMetadata', {}).get('ocr_text'):
            extracted_text = doc['extractedMetadata']['ocr_text']
            logger.info(f"Using text from extractedMetadata.ocr_text ({len(extracted_text)} chars)")
        # Try extractedMetadata.pages
        elif doc.get('extractedMetadata', {}).get('pages'):
            pages = doc['extractedMetadata']['pages']
            if isinstance(pages, list):
                extracted_text = '\n\n'.join([page.get('text', '') for page in pages if isinstance(page, dict)])
                logger.info(f"Using text from extractedMetadata.pages ({len(extracted_text)} chars)")
        # Try adaptiveData
        elif doc.get('adaptiveData'):
            if isinstance(doc['adaptiveData'], dict):
                extracted_text = doc['adaptiveData'].get('extracted_text', '')
            elif isinstance(doc['adaptiveData'], list):
                extracted_text = ' '.join([item.get('text', '') for item in doc['adaptiveData'] if isinstance(item, dict)])
            logger.info(f"Using text from adaptiveData ({len(extracted_text)} chars)")
        
        if not extracted_text:
            logger.error(f"No text found in document {request.doc_id}. Available fields: {list(doc.keys())}")
            raise HTTPException(
                status_code=400,
                detail="No extracted text found in document. Please process the document first."
            )
        
        # Truncate context if too long
        context = extracted_text[:request.context_size]
        
        logger.info(f"🤖 Querying document {request.doc_id}: {request.question}")
        logger.info(f"📄 Context size: {len(context)} chars")
        
        prompt = f"""Based on the following document content, answer the question concisely and accurately.

Document Content:
{context}

Question: {request.question}

Answer:"""
        
        # Call LLaMA via wrapper
        models = get_models()
        llama = models.get('llama') if models else None
        
        try:
            if llama is None:
                raise HTTPException(
                    status_code=503,
                    detail="Llamafile service is not available."
                )
            
            result = llama(
                prompt,
                max_tokens=300,
                temperature=0.7,
                stop=['\n\n', 'Question:', 'Document:']
            )
            
            answer = ''
            if result and result.get('choices'):
                answer = result['choices'][0].get('text', '').strip()
            
            if not answer:
                answer = "I couldn't generate an answer. Please try rephrasing your question."
            
            logger.info(f"✓ Generated answer: {answer[:100]}...")
            
            return QueryResponse(
                doc_id=request.doc_id,
                question=request.question,
                answer=answer,
                confidence=0.8,
                timestamp=datetime.utcnow()
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"Llamafile service error: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying document: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Query error: {str(e)}"
        )


@app.post("/api/v1/conversational-search")
async def conversational_search(request: SearchRequest) -> Dict[str, Any]:
    """
    Conversational search with Q&A capabilities
    """
    try:
        from bson import ObjectId
        import requests
        
        # Search for relevant documents in MongoDB
        if db is None:
            raise HTTPException(
                status_code=503,
                detail="Database connection not available"
            )
        documents = db['documents']
        
        # If doc_id specified, search only that document
        if request.doc_id:
            try:
                doc = documents.find_one({'_id': ObjectId(request.doc_id)})
                docs_to_search = [doc] if doc else []
            except:
                docs_to_search = []
        else:
            # Search all documents with extracted text
            docs_to_search = list(documents.find({
                '$or': [
                    {'extractedMetadata.ocr_text': {'$exists': True, '$ne': ''}},
                    {'adaptiveData': {'$exists': True, '$ne': []}}
                ]
            }).limit(10))
        
        if not docs_to_search:
            return {
                'query': request.query,
                'answer': 'No documents found with extracted text.',
                'source_documents': [],
                'total_documents': 0
            }
        
        # Build context from documents
        context_parts = []
        source_docs = []
        
        for doc in docs_to_search:
            doc_text = ""
            if doc.get('extractedMetadata', {}).get('ocr_text'):
                doc_text = doc['extractedMetadata']['ocr_text']
            elif doc.get('adaptiveData'):
                if isinstance(doc['adaptiveData'], dict):
                    doc_text = doc['adaptiveData'].get('extracted_text', '')
                elif isinstance(doc['adaptiveData'], list):
                    doc_text = ' '.join([item.get('text', '') for item in doc['adaptiveData'] if isinstance(item, dict)])
            
            if doc_text:
                context_parts.append(f"[Document: {doc.get('filename', 'Unknown')}]\n{doc_text[:1000]}")
                source_docs.append({
                    'document_id': str(doc['_id']),
                    'filename': doc.get('filename', 'Unknown'),
                    'score': 0.85,
                    'text_excerpt': doc_text[:300]
                })
        
        combined_context = '\n\n'.join(context_parts)[:4000]
        
        # Call LLaMA via wrapper for answer
        models = get_models()
        llama = models.get('llama') if models else None
        
        prompt = f"""Based on the following documents, answer the question.

Documents:
{combined_context}

Question: {request.query}

Answer:"""
        
        try:
            if llama:
                result = llama(
                    prompt,
                    max_tokens=400,
                    temperature=0.7,
                    stop=['\n\n', 'Question:', 'Documents:']
                )
                answer = ''
                if result and result.get('choices'):
                    answer = result['choices'][0].get('text', '').strip()
                if not answer:
                    answer = "I couldn't generate an answer at this time."
            else:
                answer = "Llamafile service unavailable. Showing document matches only."
        except:
            answer = "Llamafile service unavailable. Showing document matches only."
        
        return {
            'query': request.query,
            'answer': answer,
            'source_documents': source_docs[:request.top_k],
            'total_documents': len(source_docs)
        }
        
    except Exception as e:
        logger.error(f"Error in conversational search: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search error: {str(e)}"
        )


@app.post("/api/v1/extract-tables")
async def extract_tables(
    file: UploadFile = File(...),
    doc_id: Optional[str] = Form(None)
) -> Dict[str, Any]:
    """
    Extract tables from uploaded document
    
    Args:
        file: PDF or image file
        doc_id: Optional document ID to update in MongoDB
        
    Returns:
        Extracted tables with structure and data
    """
    try:
        import tempfile
        import shutil
        from app.services.table_extraction import extract_tables_from_image
        from pdf2image import convert_from_path
        
        # Save uploaded file temporarily
        file_ext = os.path.splitext(file.filename)[1] if file.filename else '.tmp'
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            tmp_path = tmp_file.name
        
        try:
            all_tables = []
            
            # Check if PDF or image
            if file.filename and file.filename.lower().endswith('.pdf'):
                # Convert PDF pages to images
                logger.info(f"Converting PDF to images for table extraction: {file.filename}")
                # Read OCR DPI from Control Panel config
                from app.api.config_endpoints import get_runtime_config
                runtime_config = get_runtime_config()
                ocr_dpi = runtime_config.get('OCR_DPI', 300)
                images = convert_from_path(tmp_path, dpi=ocr_dpi)
                
                for page_num, img in enumerate(images, start=1):
                    # Save page as temp image
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as page_tmp:
                        img.save(page_tmp.name, 'PNG')
                        page_tmp_path = page_tmp.name
                    
                    try:
                        # Extract tables from page
                        page_tables = extract_tables_from_image(page_tmp_path)
                        
                        # Add page number to each table
                        for table in page_tables:
                            table['page'] = page_num
                            all_tables.append(table)
                    finally:
                        os.unlink(page_tmp_path)
            else:
                # Single image file
                logger.info(f"Extracting tables from image: {file.filename}")
                all_tables = extract_tables_from_image(tmp_path)
                for table in all_tables:
                    table['page'] = 1
            
            # Update MongoDB if doc_id provided
            if doc_id and db is not None:
                from bson import ObjectId
                documents_collection = db['documents']
                
                documents_collection.update_one(
                    {'_id': ObjectId(doc_id)},
                    {
                        '$set': {
                            'extractedMetadata.tables': all_tables,
                            'extractedMetadata.tableCount': len(all_tables),
                            'extractedMetadata.tablesExtractedAt': datetime.utcnow()
                        }
                    }
                )
                logger.info(f"✓ Updated document {doc_id} with {len(all_tables)} tables")
            
            return {
                'success': True,
                'filename': file.filename,
                'tables': all_tables,
                'table_count': len(all_tables),
                'doc_id': doc_id,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        finally:
            # Cleanup temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
    except Exception as e:
        logger.error(f"Error extracting tables: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Table extraction error: {str(e)}"
        )


# ========================
# API Catalog Endpoints (Tier-Based System)
# ========================

class OCRExtractRequest(BaseModel):
    """OCR extraction request"""
    file_path: str = Field(..., description="Path to image file")
    engine: Optional[str] = Field("paddleocr", description="OCR engine: paddleocr or trocr")


class OCRValidateRequest(BaseModel):
    """OCR validation request"""
    text: str = Field(..., description="OCR text to validate")
    ground_truth: Optional[str] = Field(None, description="Ground truth text for comparison")


class ClassifyRequest(BaseModel):
    """Document classification request"""
    text: str = Field(..., description="Document text to classify")
    doc_id: Optional[str] = Field(None, description="Document ID (optional)")


class StructuredExtractionRequest(BaseModel):
    """Structured data extraction request"""
    text: str = Field(..., description="Document text")
    doc_type: Optional[str] = Field(None, description="Document type hint")


class EntityExtractionRequest(BaseModel):
    """Entity extraction request"""
    text: str = Field(..., description="Text to extract entities from")


class EmbeddingRequest(BaseModel):
    """Embedding generation request"""
    texts: List[str] = Field(..., description="List of text chunks to embed")
    model: Optional[str] = Field("all-MiniLM-L6-v2", description="Embedding model")


def _ocr_extract_sync(file_path: str, engine: str, models: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous OCR extraction - runs in ThreadPoolExecutor
    This prevents blocking the async event loop during CPU-intensive OCR.
    Supports both PaddleOCR and TrOCR engines.
    """
    from PIL import Image
    import numpy as np
    
    if engine == "trocr":
        trocr = models.get('trocr')
        if not trocr:
            raise ValueError("TrOCR model not available")
        
        processor = trocr['processor']
        model = trocr['model']
        device = trocr.get('device', 'cpu')
        
        img = Image.open(file_path).convert("RGB")
        inputs = processor(images=img, return_tensors="pt")
        pixel_values = inputs["pixel_values"].to(device)
        
        import torch
        with torch.no_grad():
            generated_ids = model.generate(
                pixel_values=pixel_values,
                max_new_tokens=256,
                num_beams=1,
                do_sample=False,
                early_stopping=True
            )
        text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        
        return {
            'text': text.strip(),
            'confidence': 0.0,  # TrOCR doesn't provide per-line confidence
            'line_count': len(text.strip().splitlines()) if text.strip() else 0
        }
    
    # Default: PaddleOCR
    ocr_model = models.get('ocr')
    if not ocr_model:
        raise ValueError("PaddleOCR model not available")
    
    img = Image.open(file_path)
    img_array = np.array(img)
    
    # PaddleOCR inference (CPU-bound operation)
    result = ocr_model.ocr(img_array, cls=True)
    
    # Parse results
    extracted_text = ""
    confidence_scores = []
    
    if result and len(result) > 0:
        for line in result[0]:
            if line:
                text = line[1][0]
                confidence = line[1][1]
                extracted_text += text + "\n"
                confidence_scores.append(confidence)
    
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
    
    return {
        'text': extracted_text.strip(),
        'confidence': avg_confidence,
        'line_count': len(confidence_scores)
    }


@app.post("/ocr/extract")
async def ocr_extract_text(request: OCRExtractRequest) -> Dict[str, Any]:
    """
    Extract text from document images using PaddleOCR or TrOCR
    
    ASYNC OPTIMIZED: Offloads CPU-bound OCR to thread pool for 3-4x throughput
    
    Args:
        request: OCR extraction request with file path
        
    Returns:
        Extracted text and confidence scores
    """
    try:
        validated_path = validate_file_path(request.file_path)
        if not os.path.exists(validated_path):
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {request.file_path}"
            )
        
        models = get_models()
        if not models or not models_ready():
            raise HTTPException(
                status_code=503,
                detail="Models not loaded yet"
            )
        
        # Validate engine parameter
        engine = request.engine or "paddleocr"
        if engine not in ("paddleocr", "trocr"):
            raise HTTPException(status_code=400, detail="engine must be 'paddleocr' or 'trocr'")
        
        if engine == "paddleocr" and not models.get('ocr'):
            raise HTTPException(status_code=503, detail="PaddleOCR model not available")
        if engine == "trocr" and not models.get('trocr'):
            raise HTTPException(status_code=503, detail="TrOCR model not available")
        
        logger.info(f"[ASYNC] Extracting text from {validated_path} using {engine}")
        
        # Run CPU-bound OCR in thread pool (non-blocking)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            _ocr_extract_sync,
            validated_path,
            engine,
            models
        )
        
        return {
            'success': True,
            'text': result['text'],
            'confidence': result['confidence'],
            'line_count': result['line_count'],
            'engine': engine,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR extraction error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"OCR extraction failed: {str(e)}"
        )


@app.post("/ocr/validate")
async def ocr_validate_quality(request: OCRValidateRequest) -> Dict[str, Any]:
    """
    Validate OCR results against ground truth or using heuristics
    
    Args:
        request: OCR validation request
        
    Returns:
        Validation results with quality metrics
    """
    try:
        logger.info(f"Validating OCR quality for {len(request.text)} characters")
        
        # Heuristic-based quality checks
        quality_score = 100.0
        issues = []
        
        # Check 1: Character ratio (alphanumeric vs special)
        alphanumeric = sum(c.isalnum() for c in request.text)
        total_chars = len(request.text.replace(' ', '').replace('\n', ''))
        if total_chars > 0:
            alphanum_ratio = alphanumeric / total_chars
            if alphanum_ratio < 0.7:
                quality_score -= 20
                issues.append(f"Low alphanumeric ratio: {alphanum_ratio:.2%}")
        
        # Check 2: Word length distribution
        words = request.text.split()
        if words:
            avg_word_len = sum(len(w) for w in words) / len(words)
            if avg_word_len < 2 or avg_word_len > 15:
                quality_score -= 15
                issues.append(f"Unusual average word length: {avg_word_len:.1f}")
        
        # Check 3: Repeated characters (OCR artifacts)
        import re
        repeated_chars = len(re.findall(r'(.)\1{3,}', request.text))
        if repeated_chars > 5:
            quality_score -= 10
            issues.append(f"Found {repeated_chars} repeated character sequences")
        
        # Check 4: Ground truth comparison (if provided)
        accuracy = None
        if request.ground_truth:
            from difflib import SequenceMatcher
            accuracy = SequenceMatcher(None, request.text, request.ground_truth).ratio()
            if accuracy < 0.8:
                quality_score -= 30
                issues.append(f"Low accuracy vs ground truth: {accuracy:.2%}")
        
        is_valid = quality_score >= 70
        
        return {
            'valid': is_valid,
            'quality_score': max(0, quality_score),
            'accuracy': accuracy,
            'issues': issues,
            'character_count': len(request.text),
            'word_count': len(words) if words else 0,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"OCR validation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"OCR validation failed: {str(e)}"
        )


class BatchOCRRequest(BaseModel):
    """Batch OCR extraction request"""
    file_paths: List[str] = Field(..., description="List of image file paths")
    engine: Optional[str] = Field("paddleocr", description="OCR engine: paddleocr or trocr")


@app.post("/ocr/extract/batch")
async def ocr_extract_batch(request: BatchOCRRequest) -> Dict[str, Any]:
    """
    Extract text from multiple document images concurrently
    
    ASYNC OPTIMIZED: Processes 4-8 images concurrently for maximum throughput
    
    Args:
        request: Batch OCR request with multiple file paths
        
    Returns:
        List of extracted texts with confidence scores
    """
    try:
        models = get_models()
        if not models or not models_ready():
            raise HTTPException(
                status_code=503,
                detail="Models not loaded yet"
            )
        
        ocr_model = models.get('ocr')
        if not ocr_model:
            raise HTTPException(status_code=503, detail="OCR model not available")
        
        logger.info(f"[ASYNC BATCH] Processing {len(request.file_paths)} images concurrently")
        
        # Validate all file paths are within allowed directories
        validated_paths = [validate_file_path(fp) for fp in request.file_paths]
        
        # Validate all files exist
        missing_files = [fp for fp in validated_paths if not os.path.exists(fp)]
        if missing_files:
            raise HTTPException(
                status_code=404,
                detail=f"Files not found: {', '.join(missing_files[:3])}"
            )
        
        # Process all images concurrently using asyncio.gather
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                executor,
                _ocr_extract_sync,
                file_path,
                request.engine,
                ocr_model
            )
            for file_path in validated_paths
        ]
        
        # Wait for all OCR operations to complete (runs in parallel)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful = []
        failed = []
        
        for idx, result in enumerate(results):
            file_path = validated_paths[idx]
            if isinstance(result, Exception):
                failed.append({
                    'file_path': file_path,
                    'error': str(result)
                })
            else:
                successful.append({
                    'file_path': file_path,
                    'text': result['text'],
                    'confidence': result['confidence'],
                    'line_count': result['line_count']
                })
        
        return {
            'success': len(failed) == 0,
            'total_files': len(request.file_paths),
            'successful': len(successful),
            'failed': len(failed),
            'results': successful,
            'errors': failed,
            'engine': request.engine,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch OCR error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Batch OCR failed: {str(e)}"
        )


@app.post("/classify")
async def classify_document(request: ClassifyRequest) -> Dict[str, Any]:
    """
    Classify document type using ML models and dynamic prompts from Control Panel
    
    Args:
        request: Classification request with document text, optional company_id and tier
        
    Returns:
        Document classification with confidence score
    """
    try:
        models = get_models()
        if not models or not models_ready():
            raise HTTPException(
                status_code=503,
                detail="Models not loaded yet"
            )
        
        company_id = getattr(request, 'company_id', None)
        tier = getattr(request, 'tier', 'tier1')
        
        logger.info(f"Classifying document (text length: {len(request.text)} chars, company: {company_id}, tier: {tier})")
        
        # Try to get dynamic classification prompt from Control Panel
        from app.utils.prompt_manager import get_prompt_for_task, get_fallback_prompt
        
        prompt_data = await get_prompt_for_task(
            ai_capability='classification',
            document_type=None,  # We don't know the type yet
            company_id=company_id,
            tier=tier,
            variables={'document_text': request.text[:1000]}
        )
        
        if prompt_data:
            logger.info(f"✓ Using dynamic classification prompt: {prompt_data['metadata']['name']}")
            
            # Use LLM with dynamic prompt for classification
            llama = models.get('llama')
            if llama is None:
                from app.models.loader import load_llama_model
                llama = load_llama_model()
                models['llama'] = llama
            
            if llama:
                llm_config = prompt_data.get('llm_config', {})
                response = llama(
                    prompt_data['prompt'],
                    max_tokens=llm_config.get('maxTokens', 100),
                    temperature=llm_config.get('temperature', 0.3),
                    top_p=llm_config.get('topP', 0.9),
                    top_k=llm_config.get('topK', 40),
                    stop=llm_config.get('stopSequences', []),
                    echo=False
                )
                
                classification_text = response.get('choices', [{}])[0].get('text', '').strip()
                
                return {
                    'success': True,
                    'doc_id': request.doc_id,
                    'classification': classification_text,
                    'confidence': 0.85,  # High confidence when using custom prompt
                    'categories': [classification_text],
                    'reasoning': f'Classified using dynamic prompt: {prompt_data["metadata"]["name"]}',
                    'prompt_used': prompt_data['metadata']['name'],
                    'timestamp': datetime.utcnow().isoformat()
                }
        
        # Fallback to ML model classification
        logger.info("No dynamic prompt found or failed, using ML model classification")
        from app.core.classifier import classify_with_reasoning
        
        classification_result = await classify_with_reasoning(request.text, models)
        
        return {
            'success': True,
            'doc_id': request.doc_id,
            'classification': classification_result.get('label', 'unknown'),
            'confidence': classification_result.get('confidence', 0.0),
            'categories': classification_result.get('categories', []),
            'reasoning': classification_result.get('reasoning', ''),
            'prompt_used': 'ml_model_fallback',
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Classification error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {str(e)}"
        )


@app.post("/extraction/structured")
async def extract_structured_data(request: StructuredExtractionRequest) -> Dict[str, Any]:
    """
    Extract structured data (tables, forms, key-values) from documents
    
    Args:
        request: Structured extraction request
        
    Returns:
        Extracted structured data
    """
    try:
        models = get_models()
        if not models or not models_ready():
            raise HTTPException(
                status_code=503,
                detail="Models not loaded yet"
            )
        
        logger.info(f"Extracting structured data (doc_type: {request.doc_type or 'auto'})")
        
        # Import extraction utility
        from app.utils.extraction import extract_structured_data as extract_util
        
        # Determine document type if not provided
        doc_type = request.doc_type or "unknown"
        
        extraction_result = await extract_util(request.text, doc_type, models)
        
        return {
            'success': True,
            'doc_type': doc_type,
            'extracted_data': extraction_result,
            'field_count': len(extraction_result) if isinstance(extraction_result, dict) else 0,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Structured extraction error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Structured extraction failed: {str(e)}"
        )


@app.post("/extraction/entities")
async def extract_entities(request: EntityExtractionRequest) -> Dict[str, Any]:
    """
    Extract named entities (dates, amounts, names) from text
    
    Args:
        request: Entity extraction request
        
    Returns:
        Extracted entities by type
    """
    try:
        models = get_models()
        if not models or not models_ready():
            raise HTTPException(
                status_code=503,
                detail="Models not loaded yet"
            )
        
        logger.info(f"Extracting entities from text ({len(request.text)} chars)")
        
        # Import entity extraction utility
        from app.utils.entity_extraction import extract_entities as extract_util
        
        entities = await extract_util(request.text, models)
        
        return {
            'success': True,
            'entities': entities,
            'entity_count': sum(len(v) for v in entities.values()) if isinstance(entities, dict) else 0,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Entity extraction error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Entity extraction failed: {str(e)}"
        )


@app.post("/embeddings/generate")
async def generate_embeddings(request: EmbeddingRequest) -> Dict[str, Any]:
    """
    Generate vector embeddings for text chunks
    
    Args:
        request: Embedding generation request with text list
        
    Returns:
        Generated embeddings
    """
    try:
        models = get_models()
        if not models or not models_ready():
            raise HTTPException(
                status_code=503,
                detail="Models not loaded yet"
            )
        
        logger.info(f"Generating embeddings for {len(request.texts)} text chunks")
        
        # Get embedding model
        embedding_model = models.get('embedding')
        if not embedding_model:
            raise HTTPException(
                status_code=503,
                detail="Embedding model not available"
            )
        
        # Generate embeddings
        embeddings = embedding_model.encode(request.texts, convert_to_numpy=True)
        embeddings_list = embeddings.tolist()
        
        return {
            'success': True,
            'embeddings': embeddings_list,
            'count': len(embeddings_list),
            'dimension': len(embeddings_list[0]) if embeddings_list else 0,
            'model': request.model,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Embedding generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Embedding generation failed: {str(e)}"
        )


# ========================
# Error Handlers
# ========================

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc)
        }
    )


# ========================
# Startup Message
# ========================

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8080))
    
    logger.info(f"Starting Uvicorn on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level='info'
    )
