"""
NLP Service - Natural Language Processing

This service provides advanced text analysis capabilities including sentiment analysis,
entity recognition, keyword extraction, text summarization, and more.

Features:
- Sentiment analysis using RoBERTa
- Named Entity Recognition (NER) using BERT
- Text summarization using BART
- Keyword extraction
- Language detection
- Multi-task processing
- GPU acceleration support

Training Status:
- ✅ Pre-trained models ready to use (RoBERTa, BERT, BART)
- ⚠️ Optional: Fine-tune on domain-specific data if needed
- 📊 Training pipeline available in app/training/

Why Separate NLP Service?
- Heavy ML dependencies (spaCy, transformers, NLTK)
- Independent scaling requirements
- Isolated computational resources
- Different deployment cycles from OCR/ICR
"""

import sys
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import asyncio
import logging
from typing import Any, Dict, List, Optional, Union, Tuple, TYPE_CHECKING, cast
from datetime import datetime
import os
from pathlib import Path
from pydantic import BaseModel, Field
from enum import Enum
from dataclasses import dataclass

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

try:
    from shared.schemas import (
        NlpClassificationRequest as _SharedNlpClassificationRequest,
        NlpClassificationResult as _SharedNlpClassificationResult,
    )
except ImportError:  # pragma: no cover - fallback for standalone usage
    _SharedNlpClassificationRequest = None
    _SharedNlpClassificationResult = None

if _SharedNlpClassificationRequest is None:
    class NlpClassificationRequest(BaseModel):  # type: ignore[misc, assignment]
        document_id: str
        raw_text: str
        metadata: Dict[str, Any] = {}
else:  # pragma: no cover
    NlpClassificationRequest = _SharedNlpClassificationRequest  # type: ignore[misc, assignment]

if _SharedNlpClassificationResult is None:
    class NlpClassificationResult(BaseModel):  # type: ignore[misc, assignment]
        document_id: str
        job_id: str
        suggested_title: Optional[str] = None
        suggested_tags: List[str] = []
        entities: List[Dict[str, Any]] = []
        confidence: float = 0.0
else:  # pragma: no cover
    NlpClassificationResult = _SharedNlpClassificationResult  # type: ignore[misc, assignment]

# Local imports
try:
    from app.models.multitask_nlp_model import MultiTaskNLPModel
    from app.processing.text_processor import TextPreprocessor, PreprocessingConfig
    from app.models.base_nlp_model import NLPTaskType, LanguageCode, NLPResult
    from app.utils.config import get_config, setup_environment_config
    from app.processing.markdown_parser import parse_markdown, StructuredDocument
    from app.processing.structure_aware_extraction import extract_structured_entities
except ImportError as e:  # pragma: no cover
    print(f"Warning: Some imports failed: {e}")

    class _FallbackNLPTaskType(str, Enum):
        SENTIMENT_ANALYSIS = "sentiment_analysis"
        ENTITY_RECOGNITION = "entity_recognition"
        KEYWORD_EXTRACTION = "keyword_extraction"
        TEXT_SUMMARIZATION = "text_summarization"
        LANGUAGE_DETECTION = "language_detection"
        TEXT_CLASSIFICATION = "text_classification"
        SEMANTIC_SIMILARITY = "semantic_similarity"

    class _FallbackLanguageCode(str, Enum):
        ENGLISH = "en"
        AUTO_DETECT = "auto"

    @dataclass
    class NLPResult:  # type: ignore[override]
        task_type: Any = None
        text: str = ""
        language: Optional[str] = None
        sentiment: Optional[Any] = None
        entities: Optional[List[Any]] = None
        keywords: Optional[List[Any]] = None
        summary: Optional[Any] = None
        language_detection: Optional[Any] = None
        classification: Optional[Any] = None
        similarity: Optional[Any] = None
        confidence: float = 0.0
        processing_time: float = 0.0
        model_version: str = "fallback"
        metadata: Optional[Dict[str, Any]] = None

    class _FallbackMultiTaskNLPModel:
        def __init__(self, config=None): pass
        def load_model(self): return True
        async def predict(self, *args, **kwargs):
            return NLPResult()
        def get_model_info(self):
            return {"model": "fallback", "status": "loaded"}

    class _FallbackTextPreprocessor:
        def __init__(self, config=None): pass

    @dataclass
    class _FallbackPreprocessingConfig:
        lowercase: bool = True

    class _FallbackConfig:
        def get(self, key, default=None):
            return default
        def get_model_config(self):
            return {}
        def get_max_text_length(self):
            return 10000
        def get_supported_languages(self):
            return ["en", "es", "fr", "de", "it", "pt", "ru", "zh"]
        def is_cache_enabled(self):
            return True

    def _fallback_get_config():
        return _FallbackConfig()

    def _fallback_setup_environment_config():
        return None

    MultiTaskNLPModel = _FallbackMultiTaskNLPModel  # type: ignore[assignment]
    TextPreprocessor = _FallbackTextPreprocessor  # type: ignore[assignment]
    PreprocessingConfig = _FallbackPreprocessingConfig  # type: ignore[assignment]
    NLPTaskType = _FallbackNLPTaskType  # type: ignore[assignment]
    LanguageCode = _FallbackLanguageCode  # type: ignore[assignment]
    get_config = _fallback_get_config  # type: ignore[assignment]
    setup_environment_config = _fallback_setup_environment_config  # type: ignore[assignment]

# Setup configuration
setup_environment_config()
config = get_config()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="SmartDockAI NLP Service - Enhanced with Structure Awareness",
    description="Natural Language Processing service with markdown parsing and context-aware entity extraction. Optimized for DeepSeek OCR structured output.",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for model instances and cached jobs
nlp_model: Optional[MultiTaskNLPModel] = None
text_processor: Optional[TextPreprocessor] = None
nlp_jobs: Dict[str, NlpClassificationResult] = {}
ANALYSIS_TASK_MAP = {
    "sentiment": NLPTaskType.SENTIMENT_ANALYSIS,
    "entities": NLPTaskType.ENTITY_RECOGNITION,
    "keywords": NLPTaskType.KEYWORD_EXTRACTION,
    "summary": NLPTaskType.TEXT_SUMMARIZATION,
    "language": NLPTaskType.LANGUAGE_DETECTION,
    "classification": NLPTaskType.TEXT_CLASSIFICATION,
}

# Configuration
try:
    NLP_CONFIG = {
        "model_path": config.get("models.base_path", "./models"),
        "training_data_path": config.get("training.data_path", "./training_data"),
        "cache_enabled": config.is_cache_enabled(),
        "max_text_length": config.get_max_text_length(),
        "supported_languages": config.get_supported_languages(),
        "models": config.get_model_config()
    }
except:
    NLP_CONFIG = {
        "model_path": os.getenv("NLP_MODEL_PATH", "./models"),
        "training_data_path": os.getenv("TRAINING_DATA_PATH", "./training_data"),
        "cache_enabled": os.getenv("CACHE_ENABLED", "true").lower() == "true",
        "max_text_length": int(os.getenv("MAX_TEXT_LENGTH", "10000")),
        "supported_languages": ["en", "es", "fr", "de", "it", "pt", "ru", "zh"],
        "models": {
            "sentiment_model": "cardiffnlp/twitter-roberta-base-sentiment-latest",
            "ner_model": "dbmdz/bert-large-cased-finetuned-conll03-english",
            "summarization_model": "facebook/bart-large-cnn",
            "sentence_model": "all-MiniLM-L6-v2",
            "spacy_model": "en_core_web_sm"
        }
    }

# Pydantic models for API
class TextInput(BaseModel):
    text: str = Field(..., description="Input text to process", max_length=10000)
    language: Optional[str] = Field(None, description="Language code (auto-detect if not specified)")
    
class SentimentRequest(TextInput):
    include_details: bool = Field(True, description="Include detailed sentiment scores")

class EntityRequest(TextInput):
    entity_types: Optional[List[str]] = Field(None, description="Filter by specific entity types")

class KeywordRequest(TextInput):
    max_keywords: int = Field(10, description="Maximum number of keywords to extract", ge=1, le=50)
    min_score: float = Field(0.1, description="Minimum keyword score threshold", ge=0.0, le=1.0)

class SummarizationRequest(TextInput):
    max_length: int = Field(150, description="Maximum summary length", ge=50, le=500)
    min_length: int = Field(50, description="Minimum summary length", ge=10, le=200)

class ClassificationRequest(TextInput):
    categories: Optional[List[str]] = Field(None, description="Custom categories for classification")

class SimilarityRequest(BaseModel):
    text1: str = Field(..., description="First text for comparison", max_length=5000)
    text2: str = Field(..., description="Second text for comparison", max_length=5000)
    language: Optional[str] = Field(None, description="Language code")

class BatchRequest(BaseModel):
    texts: List[str] = Field(..., description="List of texts to process", max_length=100)
    task: str = Field(..., description="NLP task to perform")
    language: Optional[str] = Field(None, description="Language code")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Task-specific parameters")

class TrainingRequest(BaseModel):
    task_type: str = Field(..., description="Type of NLP task to train")
    training_data: List[Dict[str, Any]] = Field(..., description="Training data samples")
    epochs: int = Field(10, description="Number of training epochs", ge=1, le=100)
    batch_size: int = Field(16, description="Training batch size", ge=1, le=128)
    learning_rate: float = Field(1e-5, description="Learning rate", ge=1e-6, le=1e-2)

class NLPAnalyzeRequest(BaseModel):
    text: str = Field(..., description="Text content to analyze")
    analysis_types: Optional[List[str]] = Field(
        default_factory=lambda: ["sentiment", "entities", "summary"],
        description="List of analysis modules to run"
    )
    language: Optional[str] = Field(None, description="Preferred language (auto if omitted)")
    options: Dict[str, Any] = Field(default_factory=dict, description="Optional parameters per analysis type")

# Dependency functions
async def get_nlp_model() -> MultiTaskNLPModel:
    """Dependency to get NLP model instance."""
    global nlp_model
    if nlp_model is None:
        nlp_model = MultiTaskNLPModel(NLP_CONFIG["models"])
        if not nlp_model.load_model():
            raise HTTPException(status_code=503, detail="Failed to load NLP model")
        logger.info("NLP model initialized")
    return nlp_model

async def get_text_processor() -> TextPreprocessor:
    """Dependency to get text processor instance."""
    global text_processor
    if text_processor is None:
        text_processor = TextPreprocessor()
        logger.info("Text processor initialized")
    return text_processor

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting NLP Service...")
    
    # Create necessary directories
    os.makedirs(NLP_CONFIG["model_path"], exist_ok=True)
    os.makedirs(NLP_CONFIG["training_data_path"], exist_ok=True)
    
    # Initialize models
    try:
        await get_nlp_model()
        await get_text_processor()
        logger.info("NLP Service startup complete")
    except Exception as e:
        logger.error(f"Failed to initialize NLP service: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down NLP Service...")

# Utility functions
def validate_language(language: Optional[str]) -> str:
    """Validate and normalize language code."""
    if not language or language == "auto":
        return "auto"
    
    if language in NLP_CONFIG["supported_languages"]:
        return language
    
    # Try to map common variations
    lang_map = {
        "english": "en",
        "spanish": "es", 
        "french": "fr",
        "german": "de",
        "italian": "it",
        "portuguese": "pt",
        "russian": "ru",
        "chinese": "zh"
    }
    
    return lang_map.get(language.lower(), "en")

def validate_text_length(text: str) -> str:
    """Validate text length."""
    if len(text) > NLP_CONFIG["max_text_length"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Text too long. Maximum length is {NLP_CONFIG['max_text_length']} characters."
        )
    
    if len(text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    
    return text.strip()

def resolve_language_code(language: Optional[str]) -> LanguageCode:
    """Resolve a language string into LanguageCode enum."""
    if not language:
        return LanguageCode.AUTO_DETECT
    normalized = language.lower()
    if normalized == "auto":
        return LanguageCode.AUTO_DETECT
    for code in LanguageCode:
        value = getattr(code, "value", str(code))
        if isinstance(value, str) and value.lower() == normalized:
            return code
    return LanguageCode.ENGLISH

def language_code_to_str(code: Union[LanguageCode, str]) -> str:
    """Convert LanguageCode enum to string value."""
    if isinstance(code, str):
        return code
    value = getattr(code, "value", None)
    return value if isinstance(value, str) else str(code)

def _serialize_sentiment(result: Optional[NLPResult]) -> Dict[str, Any]:
    if not result or not result.sentiment:
        return {}
    sentiment = result.sentiment
    return {
        "label": sentiment.label,
        "score": float(sentiment.score),
        "compound": float(sentiment.compound_score),
        "details": sentiment.details,
        "confidence": float(result.confidence or sentiment.score),
    }

def _serialize_entities(result: Optional[NLPResult]) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    if result and result.entities:
        for entity in result.entities[:20]:
            serialized.append({
                "text": entity.text,
                "label": entity.label,
                "start": entity.start,
                "end": entity.end,
                "confidence": float(entity.confidence),
                "metadata": entity.metadata or {},
            })
    return serialized

def _serialize_keywords(result: Optional[NLPResult]) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    if result and result.keywords:
        for keyword in result.keywords[:15]:
            serialized.append({
                "keyword": keyword.keyword,
                "score": float(keyword.score),
                "frequency": keyword.frequency,
                "positions": keyword.positions,
            })
    return serialized

def _serialize_summary(result: Optional[NLPResult]) -> Dict[str, Any]:
    if not result or not result.summary:
        return {}
    summary = result.summary
    return {
        "summary": summary.summary,
        "original_length": summary.original_length,
        "summary_length": summary.summary_length,
        "compression_ratio": summary.compression_ratio,
        "key_sentences": summary.key_sentences,
        "confidence": float(result.confidence or 0.0),
    }

def _serialize_language(result: Optional[NLPResult], fallback: LanguageCode) -> Dict[str, Any]:
    detection = result.language_detection if result else None
    if detection:
        return {
            "language": detection.language,
            "confidence": detection.confidence,
            "iso_code": detection.iso_code,
            "alternatives": detection.alternatives,
        }
    return {"language": language_code_to_str(fallback), "confidence": 1.0}

def _serialize_classification(result: Optional[NLPResult]) -> Dict[str, Any]:
    if not result or not result.classification:
        return {}
    classification = result.classification
    return {
        "label": classification.label,
        "confidence": float(classification.confidence),
        "probabilities": classification.probabilities,
        "features": classification.features,
    }

def _collect_confidence(values: List[float]) -> float:
    valid = [float(v) for v in values if isinstance(v, (int, float))]
    if not valid:
        return 0.0
    return max(valid)

def _ensure_single_result(result: Union[NLPResult, List[NLPResult], None]) -> Optional[NLPResult]:
    if isinstance(result, list):
        return result[0] if result else None
    return result

async def _run_requested_analyses(
    text: str,
    analysis_types: List[str],
    language_hint: Optional[str],
    options: Dict[str, Any]
) -> Dict[str, Any]:
    """Run requested NLP analyses and serialize the responses."""
    model = await get_nlp_model()
    language_code = resolve_language_code(language_hint)
    tasks: Dict[str, asyncio.Task] = {}
    requested: List[str] = []

    for analysis in analysis_types:
        normalized = analysis.lower().strip()
        if normalized not in ANALYSIS_TASK_MAP:
            continue
        requested.append(normalized)
        kwargs: Dict[str, Any] = {}

        if normalized == "summary":
            summary_opts = options.get("summary", {})
            kwargs["max_length"] = summary_opts.get("max_length", 160)
            kwargs["min_length"] = summary_opts.get("min_length", 40)
        elif normalized == "keywords":
            keyword_opts = options.get("keywords", {})
            kwargs["max_keywords"] = keyword_opts.get("max_keywords", 10)

        tasks[normalized] = asyncio.create_task(
            model.predict(
                text=text,
                task_type=ANALYSIS_TASK_MAP[normalized],
                language=language_code,
                **kwargs,
            )
        )

    if not requested:
        raise HTTPException(status_code=400, detail="No supported analysis types requested.")

    serialized_results: Dict[str, Any] = {}
    confidence_values: List[float] = []

    for name, task in tasks.items():
        try:
            nlp_result_raw = await task
            nlp_result = _ensure_single_result(nlp_result_raw)
        except Exception as exc:
            logger.error(f"{name} analysis failed: {exc}")
            serialized_results[name] = {"error": str(exc)}
            continue

        if nlp_result and nlp_result.confidence:
            confidence_values.append(float(nlp_result.confidence))

        if name == "sentiment":
            serialized = _serialize_sentiment(nlp_result)
        elif name == "entities":
            serialized = _serialize_entities(nlp_result)
        elif name == "keywords":
            serialized = _serialize_keywords(nlp_result)
        elif name == "summary":
            serialized = _serialize_summary(nlp_result)
        elif name == "language":
            serialized = _serialize_language(nlp_result, language_code)
        elif name == "classification":
            serialized = _serialize_classification(nlp_result)
        else:
            serialized = nlp_result.__dict__ if nlp_result else {}

        if isinstance(serialized, dict) and "confidence" in serialized:
            confidence_values.append(float(serialized["confidence"]))

        serialized_results[name] = serialized

    overall_confidence = _collect_confidence(confidence_values)
    return {
        "requested": requested,
        "results": serialized_results,
        "language": language_code,
        "confidence": overall_confidence,
    }

async def _process_pipeline_job(job_id: str, request: NlpClassificationRequest) -> NlpClassificationResult:
    """Produce suggested title/tags/entities for downstream routing."""
    if NlpClassificationResult is None:
        raise HTTPException(status_code=503, detail="Shared schemas not available.")

    text = validate_text_length(request.raw_text)
    metadata = request.metadata or {}
    language_hint = metadata.get("language") if isinstance(metadata.get("language"), str) else None
    language_code = resolve_language_code(language_hint)
    model = await get_nlp_model()

    summary_task = asyncio.create_task(
        model.predict(
            text=text,
            task_type=NLPTaskType.TEXT_SUMMARIZATION,
            language=language_code,
            max_length=160,
            min_length=40,
        )
    )
    keywords_task = asyncio.create_task(
        model.predict(
            text=text,
            task_type=NLPTaskType.KEYWORD_EXTRACTION,
            language=language_code,
            max_keywords=8,
        )
    )
    entities_task = asyncio.create_task(
        model.predict(
            text=text,
            task_type=NLPTaskType.ENTITY_RECOGNITION,
            language=language_code,
        )
    )

    summary_result_raw, keywords_result_raw, entities_result_raw = await asyncio.gather(
        summary_task, keywords_task, entities_task
    )
    summary_result = _ensure_single_result(summary_result_raw)
    keywords_result = _ensure_single_result(keywords_result_raw)
    entities_result = _ensure_single_result(entities_result_raw)

    def derive_title() -> Optional[str]:
        if summary_result and summary_result.summary and summary_result.summary.summary:
            candidate = summary_result.summary.summary.strip()
        else:
            candidate = text.strip()
        if not candidate:
            return None
        return candidate.splitlines()[0][:120]

    def derive_tags() -> List[str]:
        tags: List[str] = []
        if keywords_result and keywords_result.keywords:
            for keyword in keywords_result.keywords[:8]:
                if keyword.keyword:
                    tags.append(keyword.keyword.strip())
        return tags

    def derive_entities() -> List[Dict[str, Any]]:
        entity_payload: List[Dict[str, Any]] = []
        if entities_result and entities_result.entities:
            for entity in entities_result.entities[:15]:
                entity_payload.append({
                    "type": entity.label,
                    "value": entity.text,
                    "confidence": float(entity.confidence),
                    "metadata": entity.metadata or {},
                })
        return entity_payload

    entities_payload = derive_entities()

    confidence_values: List[float] = []
    for result in (summary_result, keywords_result, entities_result):
        if result and result.confidence:
            confidence_values.append(float(result.confidence))
    entity_confidence = [
        e["confidence"] for e in entities_payload if isinstance(e.get("confidence"), (int, float))
    ]
    if entity_confidence:
        confidence_values.append(sum(entity_confidence) / len(entity_confidence))

    overall_confidence = _collect_confidence(confidence_values) or 0.8

    return NlpClassificationResult(
        document_id=request.document_id,
        job_id=job_id,
        suggested_title=derive_title(),
        suggested_tags=derive_tags(),
        entities=entities_payload,
        confidence=float(overall_confidence),
    )

# API Endpoints
@app.post("/nlp/analyze")
async def analyze_text_endpoint(request: NLPAnalyzeRequest):
    """Unified analysis endpoint used by the document intelligence pipeline."""
    text = validate_text_length(request.text)
    analysis_types = request.analysis_types or ["sentiment", "entities", "summary"]
    analysis_payload = await _run_requested_analyses(
        text=text,
        analysis_types=analysis_types,
        language_hint=request.language or request.options.get("language"),
        options=request.options or {},
    )
    language_str = language_code_to_str(analysis_payload["language"])
    response = {
        "language": language_str,
        "requested_types": analysis_payload["requested"],
        "confidence": analysis_payload["confidence"],
        "text_length": len(text),
        "timestamp": datetime.utcnow().isoformat(),
        "analysis": analysis_payload["results"],
    }
    response.update(analysis_payload["results"])
    return response


@app.post("/nlp/analyze-structured")
async def analyze_structured_text(request: NLPAnalyzeRequest):
    """
    Analyze markdown-formatted text with structure awareness.
    
    This endpoint parses markdown structure from DeepSeek OCR and uses
    section/table context to improve entity recognition and classification.
    
    Returns enhanced entities with context information.
    """
    try:
        text = validate_text_length(request.text)
        
        # Parse markdown structure
        structured_doc = parse_markdown(text)
        
        # Run base NLP analysis
        analysis_types = request.analysis_types or ["entities", "sentiment"]
        analysis_payload = await _run_requested_analyses(
            text=text,
            analysis_types=analysis_types,
            language_hint=request.language or request.options.get("language"),
            options=request.options or {},
        )
        
        # Extract base entities
        base_entities = []
        if "entities" in analysis_payload["results"]:
            entities_data = analysis_payload["results"]["entities"]
            if isinstance(entities_data, list):
                base_entities = entities_data
            elif isinstance(entities_data, dict) and "entities" in entities_data:
                base_entities = entities_data["entities"]
        
        # Enhance with structure awareness
        structured_entities = extract_structured_entities(structured_doc, base_entities)
        
        # Build response
        language_str = language_code_to_str(analysis_payload["language"])
        response = {
            "language": language_str,
            "text_length": len(text),
            "timestamp": datetime.utcnow().isoformat(),
            "structure": {
                "sections": len(structured_doc.sections),
                "tables": len(structured_doc.tables),
                "headers": len(structured_doc.headers),
                "has_tables": structured_doc.metadata.get("has_tables", False),
                "document_title": structured_doc.metadata.get("document_title"),
            },
            "entities": [e.to_dict() for e in structured_entities],
            "tables": [t.to_dict() for t in structured_doc.tables],
            "confidence": analysis_payload["confidence"],
            "analysis": analysis_payload["results"]
        }
        
        # Add semantic extraction from tables
        if structured_doc.tables:
            response["table_data"] = _extract_semantic_table_data(structured_doc.tables)
        
        return response
        
    except Exception as e:
        logger.error(f"Structured analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Structured analysis failed: {e}")


def _extract_semantic_table_data(tables: list) -> Dict[str, Any]:
    """Extract semantic information from tables"""
    table_data = {
        "totals": [],
        "line_items": [],
        "key_values": {}
    }
    
    for table in tables:
        headers_lower = [h.lower() for h in table.headers]
        
        # Detect invoice line items table
        if any(h in headers_lower for h in ["item", "description", "product"]):
            for row in table.rows:
                row_dict = dict(zip(table.headers, row))
                table_data["line_items"].append(row_dict)
        
        # Extract totals
        if any(h in headers_lower for h in ["total", "amount", "subtotal"]):
            for idx, header in enumerate(table.headers):
                if "total" in header.lower() or "amount" in header.lower():
                    values = [row[idx] for row in table.rows if idx < len(row)]
                    table_data["totals"].append({
                        "field": header,
                        "values": values
                    })
        
        # Extract key-value pairs (2-column tables)
        if len(table.headers) == 2:
            for row in table.rows:
                if len(row) >= 2:
                    table_data["key_values"][row[0]] = row[1]
    
    return table_data

@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "SmartDockAI NLP Service",
        "version": "2.0.0",
        "status": "active",
        "capabilities": [
            "sentiment_analysis",
            "entity_recognition", 
            "keyword_extraction",
            "text_summarization",
            "language_detection",
            "text_classification",
            "semantic_similarity",
            "batch_processing",
            "structured_text_analysis",  # NEW
            "markdown_parsing",  # NEW
            "context_aware_ner",  # NEW
            "table_extraction",  # NEW
        ],
        "supported_languages": NLP_CONFIG["supported_languages"],
        "features": {
            "structure_aware": True,
            "markdown_support": True,
            "table_parsing": True,
            "context_based_entities": True,
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        model = await get_nlp_model()
        processor = await get_text_processor()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "nlp_model": "ready" if model else "unavailable",
                "text_processor": "ready" if processor else "unavailable"
            },
            "config": {
                "max_text_length": NLP_CONFIG["max_text_length"],
                "cache_enabled": NLP_CONFIG["cache_enabled"]
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

@app.post("/analyze/sentiment")
async def analyze_sentiment(
    request: SentimentRequest,
    model: MultiTaskNLPModel = Depends(get_nlp_model)
):
    """Analyze sentiment of text."""
    try:
        text = validate_text_length(request.text)
        language = validate_language(request.language)
        language_code = resolve_language_code(language)
        
        result = await model.predict(
            text=text,
            task_type=NLPTaskType.SENTIMENT_ANALYSIS,
            language=language
        )
        
        response = {
            "sentiment": {
                "label": result.sentiment.label if result.sentiment else "neutral",
                "score": result.sentiment.score if result.sentiment else 0.5,
                "confidence": result.confidence
            },
            "text": text,
            "language": result.language,
            "processing_time": result.processing_time,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if request.include_details and result.sentiment:
            response["sentiment"]["details"] = result.sentiment.details
            response["sentiment"]["compound_score"] = result.sentiment.compound_score
        
        return response
        
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sentiment analysis failed: {e}")

@app.post("/analyze/entities")
async def extract_entities(
    request: EntityRequest,
    model: MultiTaskNLPModel = Depends(get_nlp_model)
):
    """Extract named entities from text."""
    try:
        text = validate_text_length(request.text)
        language = validate_language(request.language)
        
        result = await model.predict(
            text=text,
            task_type=NLPTaskType.ENTITY_RECOGNITION,
            language=language
        )
        
        entities = result.entities or []
        
        # Filter by entity types if specified
        if request.entity_types:
            entities = [
                entity for entity in entities 
                if entity.label.lower() in [t.lower() for t in request.entity_types]
            ]
        
        return {
            "entities": [
                {
                    "text": entity.text,
                    "label": entity.label,
                    "start": entity.start,
                    "end": entity.end,
                    "confidence": entity.confidence
                }
                for entity in entities
            ],
            "total_entities": len(entities),
            "text": text,
            "language": result.language,
            "processing_time": result.processing_time,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Entity extraction failed: {e}")

@app.post("/analyze/keywords")
async def extract_keywords(
    request: KeywordRequest,
    model: MultiTaskNLPModel = Depends(get_nlp_model)
):
    """Extract keywords from text."""
    try:
        text = validate_text_length(request.text)
        language = validate_language(request.language)
        
        result = await model.predict(
            text=text,
            task_type=NLPTaskType.KEYWORD_EXTRACTION,
            language=language,
            max_keywords=request.max_keywords,
            min_score=request.min_score
        )
        
        keywords = result.keywords or []
        
        return {
            "keywords": [
                {
                    "keyword": kw.keyword,
                    "score": kw.score,
                    "frequency": kw.frequency
                }
                for kw in keywords
            ],
            "total_keywords": len(keywords),
            "text": text,
            "language": result.language,
            "processing_time": result.processing_time,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Keyword extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Keyword extraction failed: {e}")

@app.post("/analyze/summarize")
async def summarize_text(
    request: SummarizationRequest,
    model: MultiTaskNLPModel = Depends(get_nlp_model)
):
    """Summarize text."""
    try:
        text = validate_text_length(request.text)
        language = validate_language(request.language)
        
        result = await model.predict(
            text=text,
            task_type=NLPTaskType.TEXT_SUMMARIZATION,
            language=language,
            max_length=request.max_length,
            min_length=request.min_length
        )
        
        summary = result.summary
        
        return {
            "summary": {
                "text": summary.summary if summary else text[:request.max_length],
                "original_length": summary.original_length if summary else len(text),
                "summary_length": summary.summary_length if summary else len(text[:request.max_length]),
                "compression_ratio": summary.compression_ratio if summary else 1.0
            },
            "original_text": text,
            "language": result.language,
            "processing_time": result.processing_time,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Text summarization failed: {e}")
        raise HTTPException(status_code=500, detail=f"Text summarization failed: {e}")

@app.post("/analyze/language")
async def detect_language(
    request: TextInput,
    model: MultiTaskNLPModel = Depends(get_nlp_model)
):
    """Detect language of text."""
    try:
        text = validate_text_length(request.text)
        
        result = await model.predict(
            text=text,
            task_type=NLPTaskType.LANGUAGE_DETECTION
        )
        
        lang_result = result.language_detection
        
        return {
            "language": {
                "detected": lang_result.language if lang_result else "English",
                "confidence": lang_result.confidence if lang_result else 0.5,
                "iso_code": lang_result.iso_code if lang_result else "en",
                "alternatives": lang_result.alternatives if lang_result else []
            },
            "text": text,
            "processing_time": result.processing_time,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Language detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Language detection failed: {e}")

@app.post("/analyze/classify")
async def classify_text(
    request: ClassificationRequest,
    model: MultiTaskNLPModel = Depends(get_nlp_model)
):
    """Classify text into categories."""
    try:
        text = validate_text_length(request.text)
        language = validate_language(request.language)
        
        result = await model.predict(
            text=text,
            task_type=NLPTaskType.TEXT_CLASSIFICATION,
            language=language,
            categories=request.categories
        )
        
        classification = result.classification
        
        return {
            "classification": {
                "label": classification.label if classification else "unknown",
                "confidence": classification.confidence if classification else 0.0,
                "probabilities": classification.probabilities if classification else {}
            },
            "text": text,
            "language": result.language,
            "processing_time": result.processing_time,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Text classification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Text classification failed: {e}")

@app.post("/analyze/similarity")
async def calculate_similarity(
    request: SimilarityRequest,
    model: MultiTaskNLPModel = Depends(get_nlp_model)
):
    """Calculate semantic similarity between two texts."""
    try:
        text1 = validate_text_length(request.text1)
        text2 = validate_text_length(request.text2)
        language = validate_language(request.language)
        
        result = await model.predict(
            text=text1,
            task_type=NLPTaskType.SEMANTIC_SIMILARITY,
            language=language,
            compare_text=text2
        )
        
        similarity = result.similarity
        
        return {
            "similarity": {
                "score": similarity.similarity_score if similarity else 0.0,
                "method": similarity.method if similarity else "unknown"
            },
            "text1": text1,
            "text2": text2,
            "language": result.language,
            "processing_time": result.processing_time,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Similarity calculation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Similarity calculation failed: {e}")

@app.post("/analyze/batch")
async def batch_analyze(
    request: BatchRequest,
    model: MultiTaskNLPModel = Depends(get_nlp_model)
):
    """Process multiple texts with the same task."""
    try:
        if len(request.texts) > 100:
            raise HTTPException(status_code=400, detail="Maximum 100 texts per batch")
        
        # Validate all texts
        validated_texts = [validate_text_length(text) for text in request.texts]
        language = validate_language(request.language)
        
        # Map task string to enum
        task_map = {
            "sentiment": NLPTaskType.SENTIMENT_ANALYSIS,
            "entities": NLPTaskType.ENTITY_RECOGNITION,
            "keywords": NLPTaskType.KEYWORD_EXTRACTION,
            "summarize": NLPTaskType.TEXT_SUMMARIZATION,
            "language": NLPTaskType.LANGUAGE_DETECTION,
            "classify": NLPTaskType.TEXT_CLASSIFICATION,
            "similarity": NLPTaskType.SEMANTIC_SIMILARITY
        }
        
        task_type = task_map.get(request.task)
        if not task_type:
            raise HTTPException(status_code=400, detail=f"Unsupported task: {request.task}")
        
        # Process all texts
        results = await model.predict(
            text=validated_texts,
            task_type=task_type,
            language=language_code,
            **(request.parameters or {})
        )
        
        return {
            "results": [
                {
                    "text": text,
                    "result": result.__dict__,
                    "index": i
                }
                for i, (text, result) in enumerate(zip(validated_texts, results))
            ],
            "total_processed": len(results),
            "task": request.task,
            "language": language_code_to_str(language_code),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {e}")

@app.post("/jobs", response_model=NlpClassificationResult)
async def create_nlp_job(request: NlpClassificationRequest):
    """Create an NLP enrichment job compatible with the shared pipeline schema."""
    if NlpClassificationRequest is None or NlpClassificationResult is None:
        raise HTTPException(status_code=503, detail="Shared schemas are unavailable in this environment.")
    job_id = f"nlp_{request.document_id}_{uuid4().hex[:8]}"
    result = await _process_pipeline_job(job_id, request)
    nlp_jobs[job_id] = result
    return result

@app.get("/jobs/{job_id}", response_model=NlpClassificationResult)
async def get_nlp_job(job_id: str):
    """Retrieve a previously computed NLP job."""
    if job_id not in nlp_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return nlp_jobs[job_id]

@app.get("/models/info")
async def get_model_info(
    model: MultiTaskNLPModel = Depends(get_nlp_model)
):
    """Get information about loaded models."""
    try:
        info = model.get_model_info()
        return {
            "model_info": info,
            "config": NLP_CONFIG["models"],
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get model info: {e}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,  # Different port from OCR (8000) and ICR (8001)
        reload=True
    )
