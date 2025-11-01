"""
Document Intelligence Service - Main Orchestrator

This service coordinates all document processing capabilities, integrating OCR, ICR,
and NLP services to provide comprehensive document understanding.

Features:
- Multi-service orchestration (OCR + ICR + NLP)
- Document classification and routing
- Entity extraction and validation
- Template matching
- Signature detection integration
- Company/department-based organization
- Projectena-compatible output format
- Network scanner integration

Integration Points:
- OCR Service (port 8000): Text extraction from printed documents
- ICR Service (port 8001): Handwriting and signature detection
- NLP Service (port 8002): Text analysis and entity recognition
- Projectena Backend: Document management system

Endpoints:
- POST /upload/analyze: General document upload
- POST /upload/analyze/projectena: Projectena-compatible format
- POST /upload/scan: Network scanner integration
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
import uvicorn
import logging
import asyncio
import json
import os
import httpx
from datetime import datetime, timedelta
import hashlib
import tempfile
import shutil

# Internal imports
from app.models.classification_model import DocumentClassificationModel
from app.models.extraction_model import EntityExtractionModel
from app.models.template_model import TemplateMatchingModel
from app.classification.document_classifier import DocumentClassifier
from app.extraction.entity_extractor import EntityExtractor
from app.templates.template_manager import TemplateManager
from app.validation.document_validator import DocumentValidator
from app.routing.document_router import DocumentRouter

# Initialize FastAPI app
app = FastAPI(
    title="SmartDockAI Document Intelligence Service",
    description="Advanced ML-based document understanding and intelligence platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('document_intelligence.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Service URLs for integration
OCR_SERVICE_URL = os.getenv("OCR_SERVICE_URL", "http://localhost:8000")
ICR_SERVICE_URL = os.getenv("ICR_SERVICE_URL", "http://localhost:8001")
NLP_SERVICE_URL = os.getenv("NLP_SERVICE_URL", "http://localhost:8002")


def _combine_handwriting_text(handwriting: Dict[str, Any]) -> str:
    """Return the best text representation from an ICR handwriting payload."""
    if not handwriting:
        return ""
    text = handwriting.get("text") or ""
    if text:
        return text.strip()
    lines = handwriting.get("lines") or []
    combined = "\n".join(
        (line.get("text") or "").strip()
        for line in lines
        if isinstance(line, dict) and line.get("text")
    ).strip()
    return combined


def _parse_icr_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize the new ICR service response into the legacy text/confidence shape."""
    handwriting = payload.get("handwriting") or {}
    text = _combine_handwriting_text(handwriting)
    confidence = handwriting.get("confidence")
    processing_time = handwriting.get("processing_time") or 0.0
    metadata = {
        "handwriting": handwriting,
        "signatures": payload.get("signatures", []),
        "icr_timestamp": payload.get("timestamp"),
        "matched_fields": handwriting.get("matched_fields", []),
    }
    return {
        "text": text,
        "confidence": confidence if isinstance(confidence, (int, float)) else 0.8,
        "metadata": metadata,
        "processing_time": processing_time,
    }

# HTTP Client functions for service integration
async def extract_text_with_ocr(content: bytes, filename: str, content_type: str) -> Dict[str, Any]:
    """Extract text using OCR service for image/PDF files."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"file": (filename, content, content_type)}
            response = await client.post(f"{OCR_SERVICE_URL}/ocr/process", files=files)
            
            if response.status_code == 200:
                result = response.json()
                metadata = result.get("metadata", {}) or {}
                metadata["extraction_method"] = "ocr_deepseek"
                return {
                    "text": result.get("text", ""),
                    "confidence": result.get("confidence", 0.0),
                    "metadata": metadata,
                    "processing_time": result.get("processing_time", 0.0)
                }
            else:
                logger.error(f"OCR service error: {response.status_code} - {response.text}")
                return {"text": "", "confidence": 0.0, "metadata": {}, "error": "OCR processing failed"}
    except Exception as e:
        logger.error(f"OCR service connection error: {str(e)}")
        return {"text": "", "confidence": 0.0, "metadata": {}, "error": str(e)}

async def extract_text_with_icr(content: bytes, filename: str, content_type: str) -> Dict[str, Any]:
    """Extract text using ICR service for handwritten documents."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"file": (filename, content, content_type)}
            response = await client.post(f"{ICR_SERVICE_URL}/icr/process", files=files)
            
            if response.status_code == 200:
                result = _parse_icr_response(response.json())
                result["metadata"]["extraction_method"] = "icr_handwriting"
                return result
            else:
                logger.error(f"ICR service error: {response.status_code} - {response.text}")
                return {"text": "", "confidence": 0.0, "metadata": {}, "error": "ICR processing failed"}
    except Exception as e:
        logger.error(f"ICR service connection error: {str(e)}")
        return {"text": "", "confidence": 0.0, "metadata": {}, "error": str(e)}

async def analyze_text_with_nlp(text: str, analysis_types: Optional[List[str]] = None) -> Dict[str, Any]:
    """Analyze text using NLP service for sentiment, entities, etc."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            data = {
                "text": text,
                "analysis_types": analysis_types or ["sentiment", "entities", "summary"]
            }
            response = await client.post(f"{NLP_SERVICE_URL}/nlp/analyze", json=data)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"NLP service error: {response.status_code} - {response.text}")
                return {"error": "NLP analysis failed"}
    except Exception as e:
        logger.error(f"NLP service connection error: {str(e)}")
        return {"error": str(e)}

async def extract_text_from_file(content: bytes, filename: str, content_type: str) -> Dict[str, Any]:
    """Extract text from uploaded file using appropriate service."""
    if content_type.startswith('text/'):
        # Handle text files directly
        try:
            text = content.decode('utf-8')
            return {
                "text": text,
                "confidence": 1.0,
                "metadata": {"extraction_method": "direct_text"},
                "processing_time": 0.0
            }
        except UnicodeDecodeError:
            # Fallback to UTF-8 with error handling
            text = content.decode('utf-8', errors='replace')
            return {
                "text": text,
                "confidence": 0.9,
                "metadata": {"extraction_method": "text_with_fallback"},
                "processing_time": 0.0
            }
    elif content_type.startswith('image/') or content_type == 'application/pdf':
        # Check if it might be handwritten content
        lowercase_name = (filename or "").lower()
        if 'handwrit' in lowercase_name or 'scan' in lowercase_name or 'signature' in lowercase_name:
            return await extract_text_with_icr(content, filename, content_type)
        else:
            return await extract_text_with_ocr(content, filename, content_type)
    else:
        # Try OCR as fallback for unknown file types
        logger.warning(f"Unknown content type {content_type}, trying OCR")
        return await extract_text_with_ocr(content, filename, content_type)

# Global service instances
classifier: Optional[DocumentClassifier] = None
extractor: Optional[EntityExtractor] = None
template_manager: Optional[TemplateManager] = None
validator: Optional[DocumentValidator] = None
router: Optional[DocumentRouter] = None


def _require_classifier() -> DocumentClassifier:
    if classifier is None:
        raise HTTPException(status_code=503, detail="Classifier service not initialized")
    return classifier


def _require_extractor() -> EntityExtractor:
    if extractor is None:
        raise HTTPException(status_code=503, detail="Entity extractor not initialized")
    return extractor


def _require_template_manager() -> TemplateManager:
    if template_manager is None:
        raise HTTPException(status_code=503, detail="Template manager not initialized")
    return template_manager


def _require_validator() -> DocumentValidator:
    if validator is None:
        raise HTTPException(status_code=503, detail="Validator not initialized")
    return validator


def _require_router() -> DocumentRouter:
    if router is None:
        raise HTTPException(status_code=503, detail="Router not initialized")
    return router

# Pydantic models for API
class DocumentInput(BaseModel):
    content: str = Field(..., description="Document content text")
    filename: Optional[str] = Field(None, description="Original filename")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

class ClassificationRequest(BaseModel):
    document: DocumentInput
    confidence_threshold: Optional[float] = Field(0.8, description="Minimum confidence threshold")
    return_all_predictions: Optional[bool] = Field(False, description="Return all predictions or top one")

class ExtractionRequest(BaseModel):
    document: DocumentInput
    extraction_types: Optional[List[str]] = Field(None, description="Specific entity types to extract")
    custom_patterns: Optional[Dict[str, str]] = Field(None, description="Custom regex patterns")

class TemplateMatchRequest(BaseModel):
    document: DocumentInput
    template_ids: Optional[List[str]] = Field(None, description="Specific template IDs to match against")
    similarity_threshold: Optional[float] = Field(0.85, description="Minimum similarity threshold")

class ValidationRequest(BaseModel):
    document: DocumentInput
    document_type: Optional[str] = Field(None, description="Document type for validation")
    validation_rules: Optional[List[str]] = Field(None, description="Specific validation rules")

class RoutingRequest(BaseModel):
    document: DocumentInput
    classification_result: Optional[Dict[str, Any]] = Field(None, description="Pre-computed classification")
    routing_criteria: Optional[Dict[str, Any]] = Field(None, description="Custom routing criteria")

class BatchProcessingRequest(BaseModel):
    documents: List[DocumentInput]
    processing_options: Dict[str, Any] = Field(default_factory=dict)
    callback_url: Optional[str] = Field(None, description="Webhook URL for completion notification")

# Response models
class ClassificationResult(BaseModel):
    document_type: str
    confidence: float
    sub_categories: List[Dict[str, Any]]
    processing_time: float
    all_predictions: Optional[List[Dict[str, Any]]] = None

class ExtractionResult(BaseModel):
    entities: Dict[str, List[Dict[str, Any]]]
    confidence_scores: Dict[str, float]
    processing_time: float
    extraction_metadata: Dict[str, Any]

class TemplateMatchResult(BaseModel):
    matched_templates: List[Dict[str, Any]]
    best_match: Optional[Dict[str, Any]]
    similarity_scores: Dict[str, float]
    processing_time: float

class ValidationResult(BaseModel):
    is_valid: bool
    validation_score: float
    issues: List[Dict[str, Any]]
    recommendations: List[str]
    processing_time: float

class RoutingResult(BaseModel):
    recommended_actions: List[Dict[str, Any]]
    priority_level: str
    routing_destinations: List[str]
    workflow_suggestions: List[Dict[str, Any]]
    processing_time: float

class IntelligenceResult(BaseModel):
    classification: ClassificationResult
    extraction: ExtractionResult
    template_match: TemplateMatchResult
    validation: ValidationResult
    routing: RoutingResult
    overall_processing_time: float
    document_summary: Dict[str, Any]
    company_id: Optional[str] = None
    department_id: Optional[str] = None
    user_id: Optional[str] = None

# Application startup
@app.on_event("startup")
async def startup_event():
    """Initialize all document intelligence services."""
    global classifier, extractor, template_manager, validator, router
    
    logger.info("Starting Document Intelligence Service...")
    
    try:
        # Initialize models and services
        classifier = DocumentClassifier()
        extractor = EntityExtractor()
        template_manager = TemplateManager()
        validator = DocumentValidator()
        router = DocumentRouter()
        
        # Load pre-trained models
        await classifier.initialize()
        await extractor.initialize()
        await template_manager.initialize()
        await validator.initialize()
        await router.initialize()
        
        logger.info("Document Intelligence Service started successfully!")
        
    except Exception as e:
        logger.error(f"Failed to start Document Intelligence Service: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("Shutting down Document Intelligence Service...")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Document Intelligence Service",
        "version": "1.0.0"
    }

# Main intelligence endpoint
@app.post("/intelligence/analyze", response_model=IntelligenceResult)
async def analyze_document_intelligence(request: DocumentInput):
    """
    Comprehensive document intelligence analysis.
    Performs classification, extraction, template matching, validation, and routing.
    """
    start_time = datetime.utcnow()
    
    try:
        logger.info(f"Starting comprehensive analysis for document: {request.filename}")
        clf = _require_classifier()
        entity_extractor = _require_extractor()
        tmpl_manager = _require_template_manager()
        doc_validator = _require_validator()
        doc_router = _require_router()

        # Run all intelligence processes
        classification_task = asyncio.create_task(
            clf.classify_document(request.content, request.metadata)
        )
        extraction_task = asyncio.create_task(
            entity_extractor.extract_entities(request.content, request.metadata)
        )
        template_task = asyncio.create_task(
            tmpl_manager.match_templates(request.content, request.metadata)
        )
        
        # Wait for initial results
        classification_result, extraction_result, template_result = await asyncio.gather(
            classification_task, extraction_task, template_task
        )
        
        # Run validation and routing based on classification
        validation_result = await doc_validator.validate_document(
            request.content, classification_result.get('document_type'), request.metadata
        )
        routing_result = await doc_router.route_document(
            request.content, classification_result, request.metadata
        )
        
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        # Create comprehensive result
        result = IntelligenceResult(
            classification=classification_result,
            extraction=extraction_result,
            template_match=template_result,
            validation=validation_result,
            routing=routing_result,
            overall_processing_time=processing_time,
            document_summary={
                "filename": request.filename,
                "processing_timestamp": end_time.isoformat(),
                "content_length": len(request.content),
                "intelligence_score": calculate_intelligence_score(
                    classification_result, extraction_result, validation_result
                )
            }
        )
        
        logger.info(f"Completed intelligence analysis in {processing_time:.2f} seconds")
        return result
        
    except Exception as e:
        logger.error(f"Error in document intelligence analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

# Individual service endpoints
@app.post("/classification/classify", response_model=ClassificationResult)
async def classify_document(request: ClassificationRequest):
    """Classify document type and category."""
    try:
        clf = _require_classifier()
        confidence_threshold = (
            request.confidence_threshold
            if request.confidence_threshold is not None
            else 0.8
        )
        return_all = request.return_all_predictions if request.return_all_predictions is not None else False
        result = await clf.classify_document(
            request.document.content,
            request.document.metadata,
            confidence_threshold=confidence_threshold,
            return_all=return_all,
        )
        return result
    except Exception as e:
        logger.error(f"Classification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

@app.post("/extraction/extract", response_model=ExtractionResult)
async def extract_entities(request: ExtractionRequest):
    """Extract entities from document content."""
    try:
        entity_extractor = _require_extractor()
        result = await entity_extractor.extract_entities(
            request.document.content,
            request.document.metadata,
            extraction_types=request.extraction_types,
            custom_patterns=request.custom_patterns
        )
        return result
    except Exception as e:
        logger.error(f"Extraction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

@app.post("/templates/match", response_model=TemplateMatchResult)
async def match_templates(request: TemplateMatchRequest):
    """Match document against templates."""
    try:
        tmpl_manager = _require_template_manager()
        result = await tmpl_manager.match_templates(
            request.document.content,
            request.document.metadata,
            template_ids=request.template_ids,
            similarity_threshold=request.similarity_threshold
        )
        return result
    except Exception as e:
        logger.error(f"Template matching error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Template matching failed: {str(e)}")

@app.post("/validation/validate", response_model=ValidationResult)
async def validate_document(request: ValidationRequest):
    """Validate document against business rules."""
    try:
        doc_validator = _require_validator()
        result = await doc_validator.validate_document(
            request.document.content,
            request.document_type,
            request.document.metadata,
            validation_rules=request.validation_rules
        )
        return result
    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

@app.post("/routing/route", response_model=RoutingResult)
async def route_document(request: RoutingRequest):
    """Determine document routing and workflow actions."""
    try:
        doc_router = _require_router()
        result = await doc_router.route_document(
            request.document.content,
            request.classification_result,
            request.document.metadata,
            routing_criteria=request.routing_criteria
        )
        return result
    except Exception as e:
        logger.error(f"Routing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Routing failed: {str(e)}")

# Batch processing endpoints
@app.post("/batch/process")
async def process_batch(request: BatchProcessingRequest, background_tasks: BackgroundTasks):
    """Process multiple documents in batch."""
    try:
        batch_id = hashlib.md5(f"{datetime.utcnow().isoformat()}".encode()).hexdigest()[:8]
        
        # Add batch processing task to background
        background_tasks.add_task(
            process_document_batch,
            batch_id,
            request.documents,
            request.processing_options,
            request.callback_url
        )
        
        return {
            "batch_id": batch_id,
            "status": "processing",
            "document_count": len(request.documents),
            "estimated_completion": (datetime.utcnow() + timedelta(minutes=len(request.documents) * 2)).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Batch processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")

# File upload endpoint
@app.post("/upload/analyze")
async def analyze_uploaded_file(
    file: UploadFile = File(...),
    analysis_type: str = Form("full"),
    confidence_threshold: float = Form(0.8),
    company_id: Optional[str] = Form(None),
    department_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None)
):
    """Upload and analyze document file."""
    try:
        # Read file content
        content = await file.read()
        
        # Extract text using appropriate service
        extraction_result = await extract_text_from_file(
            content, 
            file.filename or "unknown", 
            file.content_type or "application/octet-stream"
        )
        
        # Get extracted text and metadata
        text_content = extraction_result.get("text", "")
        extraction_metadata = extraction_result.get("metadata", {})
        
        # Enhance with NLP analysis if text was extracted successfully
        nlp_analysis = {}
        if text_content and not extraction_result.get("error"):
            nlp_analysis = await analyze_text_with_nlp(text_content)
        
        # Create document input with enriched metadata
        document = DocumentInput(
            content=text_content,
            filename=file.filename,
            metadata={
                "content_type": file.content_type,
                "file_size": len(content),
                "upload_timestamp": datetime.utcnow().isoformat(),
                "extraction_confidence": extraction_result.get("confidence", 0.0),
                "extraction_method": extraction_metadata.get("extraction_method", "unknown"),
                "processing_time": extraction_result.get("processing_time", 0.0),
                "nlp_analysis": nlp_analysis,
                "extraction_error": extraction_result.get("error"),
                "company_id": company_id,
                "department_id": department_id,
                "user_id": user_id
            }
        )
        
        # Perform analysis based on type
        if analysis_type == "full":
            result = await analyze_document_intelligence(document)
            # Add IDs to Pydantic model
            result.company_id = company_id
            result.department_id = department_id
            result.user_id = user_id
            
            # Add folder workflow if company_id and department_id are provided
            if company_id and department_id:
                routing = result.routing if hasattr(result, 'routing') else {}
                if isinstance(routing, dict):
                    folder_paths = routing.get("folder_paths", {})
                else:
                    folder_paths = getattr(routing, 'folder_paths', {})
                
                classification = result.classification if hasattr(result, 'classification') else {}
                if isinstance(classification, dict):
                    document_type = classification.get("document_type", "unknown")
                else:
                    document_type = getattr(classification, 'document_type', 'unknown')
                
                # Convert result to dict to add folderWorkflow
                if hasattr(result, 'dict'):
                    result_dict = result.dict()
                elif isinstance(result, dict):
                    result_dict = result
                else:
                    result_dict = {}
                    
                result_dict["folderWorkflow"] = {
                    "createAfterProcessing": True,
                    "finalPath": folder_paths.get("full_path", f"/{str(company_id)}/{str(department_id)}/{str(document_type)}") if folder_paths else f"/{str(company_id)}/{str(department_id)}/{str(document_type)}",
                    "components": {
                        "year": folder_paths.get("year", datetime.utcnow().strftime("%Y")) if folder_paths else datetime.utcnow().strftime("%Y"),
                        "month": folder_paths.get("month", datetime.utcnow().strftime("%B")) if folder_paths else datetime.utcnow().strftime("%B"),
                        "docType": str(document_type)
                    },
                    "shouldAutoCreate": True,
                    "checkExistingFirst": True
                }
                return result_dict
            
            return result
        elif analysis_type == "classification":
            result = await classify_document(ClassificationRequest(
                document=document,
                confidence_threshold=confidence_threshold,
                return_all_predictions=False
            ))
            # Convert to dict for classification results
            result_dict = result if isinstance(result, dict) else result.dict()
            result_dict["company_id"] = company_id
            result_dict["department_id"] = department_id
            result_dict["user_id"] = user_id
            return result_dict
        else:
            raise HTTPException(status_code=400, detail="Invalid analysis type")
            
    except Exception as e:
        logger.error(f"File upload analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File analysis failed: {str(e)}")

# Projectena-compatible upload endpoint
@app.post("/upload/analyze/projectena")
async def analyze_for_projectena(
    file: UploadFile = File(...),
    companyId: str = Form(...),
    departmentId: str = Form(...),
    uploadedBy: str = Form(...),
    folderId: Optional[str] = Form(None),
    tags: Optional[str] = Form(None)  # JSON string array
):
    """
    Upload and analyze document file in Projectena-compatible format.
    
    This endpoint returns results formatted for Projectena's DocumentModel.
    It processes the document through OCR, ICR, NLP, and classification,
    then returns metadata compatible with MongoDB storage.
    """
    try:
        import json
        from datetime import datetime
        
        logger.info(f"Projectena upload - File: {file.filename}, Company: {companyId}, Dept: {departmentId}")
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Extract text using appropriate service
        extraction_result = await extract_text_from_file(
            content,
            file.filename or "unknown",
            file.content_type or "application/octet-stream"
        )
        
        # Get extracted text and metadata
        text_content = extraction_result.get("text", "")
        extraction_metadata = extraction_result.get("metadata", {})
        
        # Enhance with NLP analysis if text was extracted
        nlp_analysis = {}
        if text_content and not extraction_result.get("error"):
            nlp_analysis = await analyze_text_with_nlp(text_content)
        
        # Create document input with Projectena context
        document = DocumentInput(
            content=text_content,
            filename=file.filename,
            metadata={
                "content_type": file.content_type,
                "file_size": file_size,
                "upload_timestamp": datetime.utcnow().isoformat(),
                "extraction_confidence": extraction_result.get("confidence", 0.0),
                "extraction_method": extraction_metadata.get("extraction_method", "unknown"),
                "company_id": companyId,
                "department_id": departmentId,
                "user_id": uploadedBy,
                "folder_id": folderId
            }
        )
        
        # Run full intelligence analysis
        result = await analyze_document_intelligence(document)
        
        # Parse tags if provided
        tag_list = []
        if tags:
            try:
                tag_list = json.loads(tags) if isinstance(tags, str) else tags
            except:
                tag_list = []
        
        # Extract NLP keywords as additional tags
        nlp_keywords = nlp_analysis.get("keywords", []) if nlp_analysis else []
        auto_tags = tag_list + nlp_keywords[:5]  # Combine manual + auto tags (limit 5 auto)
        
        # Get ICR metadata for signature detection
        icr_metadata = extraction_result.get("metadata", {}).get("icr_result", {})
        signed = icr_metadata.get("signed", False)
        signature_info = {
            "signed": signed,
            "signature_count": icr_metadata.get("signature_count", 0),
            "confidence": icr_metadata.get("signature_confidence"),
            "signatures": icr_metadata.get("signatures", [])
        }
        
        # Get classification info
        classification = result.classification if hasattr(result, 'classification') else {}
        if isinstance(classification, dict):
            document_type = classification.get("document_type", "unknown")
            confidence_score = classification.get("confidence", 0.0)
        else:
            document_type = getattr(classification, 'document_type', 'unknown')
            confidence_score = getattr(classification, 'confidence', 0.0)
        
        # Get extraction entities
        extraction = result.extraction if hasattr(result, 'extraction') else {}
        if isinstance(extraction, dict):
            entities = extraction.get("entities", {})
        else:
            entities = getattr(extraction, 'entities', {})
        
        # Get routing info for folder paths
        routing = result.routing if hasattr(result, 'routing') else {}
        if isinstance(routing, dict):
            folder_paths = routing.get("folder_paths", {})
        else:
            folder_paths = getattr(routing, 'folder_paths', {})
        
        # Ensure folder_paths is a dict, not a list or other type
        if not isinstance(folder_paths, dict):
            logger.warning(f"folder_paths is not a dict: {type(folder_paths)} - {folder_paths}")
            folder_paths = {}
        
        # Generate safe filename
        import re
        safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', file.filename or "document")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{safe_filename}"
        
        # Build Projectena-compatible response
        projectena_response = {
            # Core document fields
            "filename": unique_filename,
            "originalName": file.filename,
            "size": file_size,
            "contentType": file.content_type,
            
            # Ownership & organization
            "uploadedBy": uploadedBy,
            "companyId": companyId,
            "departmentId": departmentId,
            "folderId": folderId,
            
            # Document classification
            "docType": document_type,
            "tags": auto_tags[:10],  # Limit to 10 tags
            
            # OCR processing status
            "ocrStatus": "completed" if text_content else "failed",
            
            # Extracted metadata (all processing results)
            "extractedMetadata": {
                # OCR text
                "ocr_text": text_content,
                "ocr_confidence": extraction_result.get("confidence", 0.0),
                "extraction_method": extraction_metadata.get("extraction_method", "unknown"),
                
                # Classification
                "document_type": document_type,
                "classification_confidence": confidence_score,
                "classification_details": classification if isinstance(classification, dict) else {},
                
                # Entity extraction
                "entities": entities,
                
                # NLP analysis
                "nlp_analysis": nlp_analysis,
                
                # Signature detection
                "signature_info": signature_info,
                
                # Folder paths
                "folder_paths": folder_paths,
                
                # Processing summary
                "processing_summary": {
                    "total_time": result.overall_processing_time if hasattr(result, 'overall_processing_time') else 0.0,
                    "timestamp": datetime.utcnow().isoformat(),
                    "services_used": ["ocr", "icr", "nlp", "classification", "routing"]
                }
            },
            
            # Additional fields for Projectena
            "processingTime": result.overall_processing_time if hasattr(result, 'overall_processing_time') else 0.0,
            "confidenceScore": confidence_score,
            "signed": signed,
            
            # Suggested folder path - ensure all components are strings
            "suggestedPath": folder_paths.get("full_path", f"/{str(companyId)}/{str(departmentId)}/{str(document_type)}") if folder_paths else f"/{str(companyId)}/{str(departmentId)}/{str(document_type)}",
            
            # Folder creation workflow (create AFTER processing completes)
            "folderWorkflow": {
                "createAfterProcessing": True,  # Don't create folder until processing is done
                "finalPath": folder_paths.get("full_path", f"/{str(companyId)}/{str(departmentId)}/{str(document_type)}") if folder_paths else f"/{str(companyId)}/{str(departmentId)}/{str(document_type)}",
                "components": {
                    "year": folder_paths.get("year", datetime.utcnow().strftime("%Y")) if folder_paths else datetime.utcnow().strftime("%Y"),
                    "month": folder_paths.get("month", datetime.utcnow().strftime("%B")) if folder_paths else datetime.utcnow().strftime("%B"),
                    "docType": str(document_type)
                },
                "shouldAutoCreate": True,  # Auto-create if folder doesn't exist
                "checkExistingFirst": True  # Check if folder already exists before creating
            },
            
            # Status
            "status": "processed",
            "processedAt": datetime.utcnow().isoformat()
        }
        
        logger.info(f"✅ Projectena processing complete - Type: {document_type}, Path: {folder_paths.get('full_path', 'N/A') if folder_paths else 'N/A'}, Signed: {signed}")
        
        return projectena_response
        
    except Exception as e:
        logger.error(f"Projectena upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Projectena upload failed: {str(e)}")

# Scanner integration endpoint
@app.post("/upload/scan")
async def receive_from_scanner(
    file: UploadFile = File(...),
    scanner_id: str = Form(...),
    scan_settings: Optional[str] = Form(None),  # JSON string
    company_id: Optional[str] = Form(None),
    department_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None)
):
    """
    Receive scanned documents from network scanners.
    
    Supported scanner types:
    - Network scanners (Canon, HP, Xerox, etc.)
    - MFPs (Multi-Function Printers)
    - Document scanners with network capability
    
    Scanner Configuration:
    Configure your scanner to POST to: http://<server>:8003/upload/scan
    """
    try:
        import json
        
        logger.info(f"Document received from scanner: {scanner_id}")
        
        # Parse scan settings if provided
        settings = {}
        if scan_settings:
            try:
                settings = json.loads(scan_settings)
            except:
                logger.warning(f"Failed to parse scan settings: {scan_settings}")
        
        # Read scanned file
        content = await file.read()
        
        logger.info(f"Scanner file - Name: {file.filename}, Size: {len(content)} bytes, Settings: {settings}")
        
        # Extract text using appropriate service
        extraction_result = await extract_text_from_file(
            content,
            file.filename or f"scan_{scanner_id}_{datetime.utcnow().timestamp()}.pdf",
            file.content_type or "application/pdf"
        )
        
        # Get extracted text
        text_content = extraction_result.get("text", "")
        extraction_metadata = extraction_result.get("metadata", {})
        
        # Enhance with NLP analysis
        nlp_analysis = {}
        if text_content and not extraction_result.get("error"):
            nlp_analysis = await analyze_text_with_nlp(text_content)
        
        # Create document input with scanner metadata
        document = DocumentInput(
            content=text_content,
            filename=file.filename,
            metadata={
                "source": "scanner",
                "scanner_id": scanner_id,
                "scan_settings": settings,
                "content_type": file.content_type,
                "file_size": len(content),
                "scan_timestamp": datetime.utcnow().isoformat(),
                "company_id": company_id,
                "department_id": department_id,
                "user_id": user_id,
                "extraction_metadata": extraction_metadata
            }
        )
        
        # Analyze document
        result = await analyze_document_intelligence(document)
        
        # Convert to dict properly
        if hasattr(result, 'dict'):
            result_dict = result.dict()
        elif isinstance(result, dict):
            result_dict = result
        else:
            result_dict = {}
        
        # Add scanner-specific info to response
        result_dict.update({
            "scanner_info": {
                "scanner_id": scanner_id,
                "scan_settings": settings,
                "scan_timestamp": datetime.utcnow().isoformat()
            },
            "source": "scanner",
            "company_id": company_id,
            "department_id": department_id,
            "user_id": user_id
        })
        
        # Add folder workflow if company_id and department_id are provided
        if company_id and department_id:
            routing = result_dict.get("routing", {})
            folder_paths = routing.get("folder_paths", {}) if isinstance(routing, dict) else {}
            
            classification = result_dict.get("classification", {})
            document_type = classification.get("document_type", "unknown") if isinstance(classification, dict) else "unknown"
            
            result_dict["folderWorkflow"] = {
                "createAfterProcessing": True,
                "finalPath": folder_paths.get("full_path", f"/{str(company_id)}/{str(department_id)}/{str(document_type)}") if folder_paths else f"/{str(company_id)}/{str(department_id)}/{str(document_type)}",
                "components": {
                    "year": folder_paths.get("year", datetime.utcnow().strftime("%Y")) if folder_paths else datetime.utcnow().strftime("%Y"),
                    "month": folder_paths.get("month", datetime.utcnow().strftime("%B")) if folder_paths else datetime.utcnow().strftime("%B"),
                    "docType": str(document_type)
                },
                "shouldAutoCreate": True,
                "checkExistingFirst": True
            }
        
        logger.info(f"✅ Scanner document processed - Scanner: {scanner_id}")
        
        return result_dict
        
    except Exception as e:
        logger.error(f"Scanner upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scanner upload failed: {str(e)}")

# Analytics endpoints
@app.get("/analytics/stats")
async def get_analytics_stats():
    """Get processing statistics and analytics."""
    try:
        stats = {
            "service_uptime": "Service uptime tracking not implemented",
            "total_documents_processed": "Document counter not implemented",
            "classification_accuracy": "Accuracy tracking not implemented",
            "average_processing_time": "Timing analytics not implemented",
            "most_common_document_types": "Document type analytics not implemented"
        }
        return stats
    except Exception as e:
        logger.error(f"Analytics error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analytics failed: {str(e)}")

# Utility functions
def calculate_intelligence_score(classification_result, extraction_result, validation_result):
    """Calculate overall intelligence score for document analysis."""
    try:
        classification_score = classification_result.get('confidence', 0)
        extraction_score = sum(extraction_result.get('confidence_scores', {}).values()) / max(
            len(extraction_result.get('confidence_scores', {})), 1
        )
        validation_score = validation_result.get('validation_score', 0)
        
        # Weighted average
        intelligence_score = (
            classification_score * 0.4 +
            extraction_score * 0.3 +
            validation_score * 0.3
        )
        
        return round(intelligence_score, 3)
    except Exception:
        return 0.0

async def process_document_batch(batch_id: str, documents: List[DocumentInput], options: Dict[str, Any], callback_url: Optional[str]):
    """Background task for batch document processing."""
    try:
        logger.info(f"Starting batch processing for batch_id: {batch_id}")
        
        results = []
        for i, document in enumerate(documents):
            try:
                result = await analyze_document_intelligence(document)
                results.append({
                    "index": i,
                    "filename": document.filename,
                    "status": "success",
                    "result": result.dict()
                })
            except Exception as e:
                results.append({
                    "index": i,
                    "filename": document.filename,
                    "status": "error",
                    "error": str(e)
                })
        
        # Save results (implement actual storage here)
        logger.info(f"Completed batch processing for batch_id: {batch_id}")
        
        # Send callback if provided
        if callback_url:
            # Implement webhook callback here
            pass
            
    except Exception as e:
        logger.error(f"Batch processing error for batch_id {batch_id}: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level="info"
    )
