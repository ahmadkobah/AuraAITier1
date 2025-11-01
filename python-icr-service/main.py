"""
ICR Service - Intelligent Character Recognition

This service provides handwriting recognition and signature detection using
Microsoft's TrOCR (Transformer-based OCR) pre-trained handwriting model.

Features:
- Handwriting text extraction using transformers
- Signature detection and verification
- Form field processing
- Training data collection for continuous improvement
- GPU acceleration support
- Pre-trained model (microsoft/trocr-base-handwritten) - production ready

Training Status:
- ✅ Pre-trained model ready to use
- ⚠️ Optional: Collect data from production for fine-tuning
- 📊 Training pipeline available in app/training/
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import numpy as np
import cv2
import io
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import os
import sys
import hashlib
import shutil
import tempfile
from pathlib import Path
import httpx
from uuid import uuid4
from pydantic import BaseModel
import traceback

# Local imports
from app.models.trocr_model import TrOCRHandwritingModel
from app.preprocessing.handwriting_processor import HandwritingPreprocessor
from app.training.training_data_collector import TrainingDataCollector

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

try:
    from shared.schemas import FileReference, IcrJobRequest, IcrJobResult
except ImportError:  # pragma: no cover - fallback definitions
    class FileReference(BaseModel):  # type: ignore
        uri: str
        checksum: Optional[str] = None

    class IcrJobRequest(BaseModel):  # type: ignore
        document_id: str
        source_file: FileReference
        fields_of_interest: List[str] = []

    class IcrJobResult(BaseModel):  # type: ignore
        document_id: str
        job_id: str
        status: str
        signed: bool = False
        signature_count: int = 0
        signature_confidence: Optional[float] = None
        signatures: List[Dict[str, Any]]
        handwriting: List[Dict[str, Any]]

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SmartDockAI ICR Service",
    description="Intelligent Character Recognition service for handwriting, signatures, and forms",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for model instances
icr_model: Optional[TrOCRHandwritingModel] = None
preprocessor: Optional[HandwritingPreprocessor] = None
training_collector: Optional[TrainingDataCollector] = None

# Configuration
ICR_CONFIG = {
    "model_path": os.getenv("ICR_MODEL_PATH", "./models"),
    "training_data_path": os.getenv("TRAINING_DATA_PATH", "./training_data"),
    "max_image_size": int(os.getenv("MAX_IMAGE_SIZE", "2048")),
    "supported_formats": ["png", "jpg", "jpeg", "tiff", "bmp"],
    "preprocessing": {
        "noise_reduction": "medium",
        "skew_detection": True,
        "min_line_height": 20,
        "max_line_height": 200
    }
}

icr_jobs: Dict[str, IcrJobResult] = {}


async def get_icr_model() -> TrOCRHandwritingModel:
    """Dependency to get ICR model instance."""
    global icr_model
    if icr_model is None:
        icr_model = TrOCRHandwritingModel()
        # Initialize model
        await icr_model.load_model()  # Use async load_model and correct variable name
        logger.info("ICR model initialized")
    return icr_model


async def get_preprocessor() -> HandwritingPreprocessor:
    """Dependency to get handwriting preprocessor instance."""
    global preprocessor
    if preprocessor is None:
        preprocessor = HandwritingPreprocessor(ICR_CONFIG["preprocessing"])
        logger.info("Handwriting preprocessor initialized")
    return preprocessor


async def get_training_collector() -> TrainingDataCollector:
    """Dependency to get training data collector instance."""
    global training_collector
    if training_collector is None:
        training_collector = TrainingDataCollector(
            data_dir=ICR_CONFIG["training_data_path"]
        )
        logger.info("Training data collector initialized")
    return training_collector


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting ICR Service...")
    
    # Create necessary directories
    os.makedirs(ICR_CONFIG["model_path"], exist_ok=True)
    os.makedirs(ICR_CONFIG["training_data_path"], exist_ok=True)
    
    # Initialize models
    await get_icr_model()
    await get_preprocessor()
    await get_training_collector()
    
    logger.info("ICR Service startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down ICR Service...")


def validate_image_file(file: UploadFile) -> bool:
    """Validate uploaded image file."""
    if not file.filename:
        return False
    
    file_extension = file.filename.split('.')[-1].lower()
    return file_extension in ICR_CONFIG["supported_formats"]


async def load_image_from_upload(file: UploadFile) -> np.ndarray:
    """Load image from uploaded file."""
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise ValueError("Failed to decode image")
        
        # Resize if too large
        height, width = image.shape[:2]
        max_size = ICR_CONFIG["max_image_size"]
        
        if max(height, width) > max_size:
            scale = max_size / max(height, width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        return image
        
    except Exception as e:
        logger.error(f"Error loading image: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid image file: {e}")


def parse_fields_param(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        values = raw
    else:
        values = [chunk.strip() for chunk in str(raw).split(",")]
    return [v for v in values if v]


def load_image_from_path(path: Path) -> np.ndarray:
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(f"Unable to read image at {path}")
    height, width = image.shape[:2]
    max_size = ICR_CONFIG["max_image_size"]
    if max(height, width) > max_size:
        scale = max_size / max(height, width)
        new_width = int(width * scale)
        new_height = int(height * scale)
        image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    return image


def resolve_file_reference(source: FileReference) -> Tuple[Path, Optional[Path]]:
    uri = source.uri
    if uri.startswith(("http://", "https://")):
        tmp_dir = Path(tempfile.mkdtemp())
        target = tmp_dir / Path(uri).name
        with httpx.stream("GET", uri, timeout=60.0) as response:
            response.raise_for_status()
            with target.open("wb") as fh:
                for chunk in response.iter_bytes():
                    fh.write(chunk)
        return target, tmp_dir
    path = Path(uri)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {uri}")
    return path, None


def serialize_character(char) -> Dict[str, Any]:
    return {
        "text": char.character,
        "confidence": float(char.confidence),
        "bbox": list(char.bbox),
        "alternatives": char.alternatives or [],
    }


def serialize_word(word) -> Dict[str, Any]:
    return {
        "text": word.text,
        "confidence": float(word.confidence),
        "bbox": list(word.bbox),
        "word_type": word.word_type,
        "characters": [serialize_character(c) for c in word.characters],
    }


def serialize_line(line) -> Dict[str, Any]:
    return {
        "text": line.text,
        "confidence": float(line.confidence),
        "bbox": list(line.bbox),
        "line_angle": line.line_angle,
        "words": [serialize_word(w) for w in line.words],
    }


def serialize_signature(signature) -> Dict[str, Any]:
    if not signature:
        return {}
    return {
        "is_genuine": signature.is_genuine,
        "confidence": float(signature.confidence),
        "similarity_score": float(signature.similarity_score),
        "verification_model": signature.verification_model,
        "features": signature.features_extracted,
    }


def collect_field_matches(text: str, lines: List[Dict[str, Any]], fields: List[str]) -> List[str]:
    if not fields:
        return []
    matches = set()
    lower_fields = [field.lower() for field in fields]
    def check(candidate: str):
        lower_candidate = candidate.lower()
        for field in lower_fields:
            if field and field in lower_candidate:
                matches.add(field)
    check(text)
    for line in lines:
        check(line["text"])
        for word in line.get("words", []):
            check(word["text"])
    return sorted(matches)


async def analyze_handwriting_image(
    image: np.ndarray,
    fields_of_interest: Optional[List[str]] = None
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    preprocessor = await get_preprocessor()
    model = await get_icr_model()

    try:
        preprocessing = await preprocessor.preprocess_handwriting(image, "line_recognition")
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        preprocessing = {"preprocessed_image": image, "metadata": {}}
    processed_image = preprocessing.get("preprocessed_image")
    if processed_image is None:
        processed_image = image

    try:
        icr_result = await model.predict(processed_image)
    except Exception as e:
        # Log full traceback to help diagnose ambiguous-array boolean errors
        logger.exception("Model prediction failed")
        logger.debug(traceback.format_exc())
        # Also persist traceback to a file for offline inspection
        try:
            with open("icr_tracebacks.log", "a", encoding="utf-8") as fh:
                fh.write(f"\n---[{datetime.utcnow().isoformat()}] Model prediction traceback---\n")
                fh.write(traceback.format_exc())
                fh.write("\n")
        except Exception:
            pass
        # Return a minimal result so the API stays available
        class MockResult:
            def __init__(self):
                self.text = ''
                self.confidence = 0.0
                self.lines = []
                self.words = []
                self.characters = []
                self.signature_verification = None
                self.processing_time = 0.0
                self.model_version = 'error'
                self.metadata = {}
        icr_result = MockResult()

    lines = [serialize_line(line) for line in icr_result.lines]
    handwriting_entry = {
        "text": icr_result.text,
        "confidence": float(icr_result.confidence),
        "processing_time": icr_result.processing_time,
        "model_version": icr_result.model_version,
        "lines": lines,
        "metadata": {
            **(icr_result.metadata or {}),
            "preprocessing": preprocessing.get("metadata", {}),
            "line_count": len(preprocessing.get("line_segments", [])),
        },
    }

    matches = collect_field_matches(icr_result.text, lines, fields_of_interest or [])
    if matches:
        handwriting_entry["matched_fields"] = matches

    signature_payload = serialize_signature(icr_result.signature_verification)
    signatures = [signature_payload] if signature_payload else []

    return handwriting_entry, signatures


def build_icr_job_result(
    document_id: str,
    job_id: str,
    status: str,
    handwriting: List[Dict[str, Any]],
    signatures: List[Dict[str, Any]],
) -> IcrJobResult:
    # Calculate signature boolean and statistics
    signed = False
    signature_count = len(signatures)
    signature_confidence = None
    
    if signatures:
        # Check if any signature is genuine
        signed = any(sig.get("is_genuine", False) for sig in signatures)
        
        # Calculate average confidence
        confidences = [sig.get("confidence", 0.0) for sig in signatures if "confidence" in sig]
        if confidences:
            signature_confidence = sum(confidences) / len(confidences)
    
    return IcrJobResult(
        document_id=document_id,
        job_id=job_id,
        status=status,
        signed=signed,
        signature_count=signature_count,
        signature_confidence=signature_confidence,
        handwriting=handwriting,
        signatures=signatures,
    )


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "SmartDockAI ICR Service",
        "version": "1.0.0",
        "status": "active",
        "capabilities": [
            "handwriting_recognition",
            "signature_verification", 
            "form_processing",
            "character_segmentation",
            "training_data_collection"
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        model = await get_icr_model()
        preprocessor = await get_preprocessor()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "icr_model": "ready" if model else "unavailable",
                "preprocessor": "ready" if preprocessor else "unavailable"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@app.post("/icr/process")
async def icr_process(
    file: UploadFile = File(...),
    fields: Optional[str] = None
):
    """Process handwritten uploads and return structured handwriting metadata."""
    if not validate_image_file(file):
        raise HTTPException(status_code=400, detail="Invalid image format")

    try:
        image = await load_image_from_upload(file)
        fields_of_interest = parse_fields_param(fields)
        handwriting_entry, signatures = await analyze_handwriting_image(image, fields_of_interest)
        return {
            "handwriting": handwriting_entry,
            "signatures": signatures,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        # Log full traceback for debugging
        logger.exception("ICR processing failed during request handling")
        logger.debug(traceback.format_exc())
        # Persist traceback to file
        try:
            with open("icr_tracebacks.log", "a", encoding="utf-8") as fh:
                fh.write(f"\n---[{datetime.utcnow().isoformat()}] Request handling traceback---\n")
                fh.write(traceback.format_exc())
                fh.write("\n")
        except Exception:
            pass
        # Return a default response instead of raising HTTP 500
        return {
            "handwriting": {
                "text": "",
                "confidence": 0.0,
                "processing_time": 0.0,
                "model_version": "error",
                "lines": [],
                "metadata": {}
            },
            "signatures": [],
            "timestamp": datetime.utcnow().isoformat(),
        }


async def _run_icr_job(job_id: str, payload: IcrJobRequest):
    cleanup_dir: Optional[Path] = None
    try:
        source_path, cleanup_dir = resolve_file_reference(payload.source_file)
        image = load_image_from_path(source_path)
        fields = payload.fields_of_interest or []
        handwriting_entry, signatures = await analyze_handwriting_image(image, fields)
        icr_jobs[job_id] = build_icr_job_result(
            document_id=payload.document_id,
            job_id=job_id,
            status="completed",
            handwriting=[handwriting_entry],
            signatures=signatures,
        )
    except Exception as exc:
        logger.error(f"ICR job {job_id} failed: {exc}")
        icr_jobs[job_id] = build_icr_job_result(
            document_id=payload.document_id,
            job_id=job_id,
            status="failed",
            handwriting=[],
            signatures=[],
        )
    finally:
        if cleanup_dir and cleanup_dir.exists():
            shutil.rmtree(cleanup_dir, ignore_errors=True)


@app.post("/jobs", response_model=IcrJobResult)
async def create_icr_job(req: IcrJobRequest):
    job_id = f"icr_{req.document_id}_{uuid4().hex[:6]}"
    icr_jobs[job_id] = build_icr_job_result(
        document_id=req.document_id,
        job_id=job_id,
        status="queued",
        handwriting=[],
        signatures=[],
    )
    asyncio.create_task(_run_icr_job(job_id, req))
    return icr_jobs[job_id]


@app.get("/jobs/{job_id}", response_model=IcrJobResult)
async def get_icr_job(job_id: str):
    if job_id not in icr_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return icr_jobs[job_id]


@app.post("/recognize")
async def recognize_handwriting(
    file: UploadFile = File(...),
    recognition_type: str = "full_text",
    preprocess: bool = True,
    model: TrOCRHandwritingModel = Depends(get_icr_model),
    preprocessor: HandwritingPreprocessor = Depends(get_preprocessor)
):
    """
    Recognize handwriting from uploaded image.
    
    Args:
        file: Image file containing handwriting
        recognition_type: Type of recognition (full_text, line_by_line, word_by_word)
        preprocess: Whether to apply preprocessing
    """
    if not validate_image_file(file):
        raise HTTPException(status_code=400, detail="Invalid image format")
    
    try:
        # Load image
        image = await load_image_from_upload(file)
        
        # Preprocess if requested
        preprocessed_image = image
        preprocessing_metadata = {}
        
        if preprocess:
            results = await preprocessor.preprocess_handwriting(image, "line_recognition")
            preprocessed_image = results["preprocessed_image"]
            preprocessing_metadata = results["metadata"]
        
        # Perform recognition based on type
        if recognition_type == "full_text":
            # Process entire image as one
            recognition_result = await model.predict(preprocessed_image)
            
            return {
                "recognized_text": recognition_result.text,
                "confidence": recognition_result.confidence,
                "recognition_type": recognition_type,
                "preprocessing_applied": preprocess,
                "preprocessing_metadata": preprocessing_metadata,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        elif recognition_type == "line_by_line":
            # Process each line separately
            if not preprocess:
                results = await preprocessor.preprocess_handwriting(image, "line_recognition")
            
            line_results = []
            for i, line_segment in enumerate(results["line_segments"]):
                line_recognition = await model.predict(line_segment.image)
                line_results.append({
                    "line_index": i,
                    "text": line_recognition.text,
                    "confidence": line_recognition.confidence,
                    "bbox": line_segment.bbox
                })
            
            return {
                "lines": line_results,
                "total_lines": len(line_results),
                "recognition_type": recognition_type,
                "preprocessing_applied": True,
                "preprocessing_metadata": preprocessing_metadata,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        elif recognition_type == "word_by_word":
            # Process each word separately
            if not preprocess:
                results = await preprocessor.preprocess_handwriting(image, "word_recognition")
            
            word_results = []
            for i, word_segment in enumerate(results["word_segments"]):
                word_recognition = await model.predict(word_segment.image)
                word_results.append({
                    "word_index": i,
                    "text": word_recognition.text,
                    "confidence": word_recognition.confidence,
                    "bbox": word_segment.bbox
                })
            
            return {
                "words": word_results,
                "total_words": len(word_results),
                "recognition_type": recognition_type,
                "preprocessing_applied": True,
                "preprocessing_metadata": preprocessing_metadata,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        else:
            raise HTTPException(status_code=400, detail="Invalid recognition_type")
            
    except Exception as e:
        logger.error(f"Recognition failed: {e}")
        raise HTTPException(status_code=500, detail=f"Recognition failed: {e}")


@app.post("/preprocess")
async def preprocess_image(
    file: UploadFile = File(...),
    task_type: str = "line_recognition",
    return_segments: bool = False,
    preprocessor: HandwritingPreprocessor = Depends(get_preprocessor)
):
    """
    Preprocess handwriting image without recognition.
    
    Args:
        file: Image file containing handwriting
        task_type: Type of preprocessing (line_recognition, word_recognition, character_recognition)
        return_segments: Whether to return segmented images
    """
    if not validate_image_file(file):
        raise HTTPException(status_code=400, detail="Invalid image format")
    
    try:
        # Load image
        image = await load_image_from_upload(file)
        
        # Preprocess
        results = await preprocessor.preprocess_handwriting(image, task_type)
        
        # Prepare response
        response = {
            "preprocessing_completed": True,
            "task_type": task_type,
            "metadata": results["metadata"],
            "segment_counts": {
                "lines": len(results["line_segments"]),
                "words": len(results["word_segments"]),
                "characters": len(results["character_segments"])
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if return_segments:
            # Convert images to base64 for JSON response
            import base64
            
            def image_to_base64(img):
                _, buffer = cv2.imencode('.png', img)
                return base64.b64encode(buffer).decode('utf-8')
            
            response["segments"] = {
                "lines": [
                    {
                        "index": i,
                        "bbox": seg.bbox,
                        "image_base64": image_to_base64(seg.image),
                        "confidence": seg.confidence
                    }
                    for i, seg in enumerate(results["line_segments"])
                ],
                "words": [
                    {
                        "index": i,
                        "bbox": seg.bbox,
                        "image_base64": image_to_base64(seg.image),
                        "confidence": seg.confidence
                    }
                    for i, seg in enumerate(results["word_segments"])
                ]
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Preprocessing failed: {e}")


@app.post("/training/add_sample")
async def add_training_sample(
    ground_truth: str,
    file: UploadFile = File(...),
    category: str = "general",
    metadata: Optional[str] = None,
    collector: TrainingDataCollector = Depends(get_training_collector)
):
    """
    Add a training sample to the dataset.
    
    Args:
        file: Image file containing handwriting
        ground_truth: Correct text transcription
        category: Category for the sample (general, signature, form, etc.)
        metadata: Additional metadata as JSON string
    """
    if not validate_image_file(file):
        raise HTTPException(status_code=400, detail="Invalid image format")
    
    try:
        # Load image
        image = await load_image_from_upload(file)
        
        # Parse metadata
        import json
        sample_metadata = {}
        if metadata:
            try:
                sample_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON")
        
        # Add sample to training data
        sample_id = await collector.add_training_sample(
            image=image,
            ground_truth=ground_truth,
            category=category,
            metadata=sample_metadata
        )
        
        return {
            "sample_added": True,
            "sample_id": sample_id,
            "category": category,
            "ground_truth_length": len(ground_truth),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to add training sample: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add training sample: {e}")


@app.get("/training/stats")
async def get_training_stats(
    collector: TrainingDataCollector = Depends(get_training_collector)
):
    """Get training dataset statistics."""
    try:
        stats = await collector.get_dataset_stats()
        return {
            "dataset_stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get training stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get training stats: {e}")


@app.post("/training/start")
async def start_training(
    background_tasks: BackgroundTasks,
    epochs: int = 5,
    batch_size: int = 8,
    learning_rate: float = 1e-5,
    model: TrOCRHandwritingModel = Depends(get_icr_model),
    collector: TrainingDataCollector = Depends(get_training_collector)
):
    """
    Start model training in the background.
    
    Args:
        epochs: Number of training epochs
        batch_size: Training batch size
        learning_rate: Learning rate for training
    """
    try:
        # Check if training data exists
        stats = await collector.get_dataset_stats()
        if stats["total_samples"] < 10:
            raise HTTPException(
                status_code=400, 
                detail="Insufficient training data. Need at least 10 samples."
            )
        
        # Start training in background
        training_config = {
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "data_dir": ICR_CONFIG["training_data_path"]
        }
        
        background_tasks.add_task(model.train, training_config)
        
        return {
            "training_started": True,
            "training_config": training_config,
            "dataset_stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to start training: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start training: {e}")


@app.get("/model/info")
async def get_model_info(
    model: TrOCRHandwritingModel = Depends(get_icr_model)
):
    """Get information about the current model."""
    try:
        info = model.get_model_info()  # Remove await since it's not async
        return {
            "model_info": info,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get model info: {e}")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,  # Different port from OCR service
        reload=True
    )
