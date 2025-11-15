"""
FastAPI Server - AI Service Tier 1
Main endpoints for document processing, search, and Q&A
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import torch

from app.model_loader import load_all_models, get_models, models_ready
from app.pipeline_worker import run_full_ai_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ai_service")

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
    doc_id: str = Field(..., description="Document to query")
    question: str = Field(..., description="Question to answer")
    context_size: int = Field(2000, description="Context window for answer generation")


class QueryResponse(BaseModel):
    """Question answering response"""
    doc_id: str
    question: str
    answer: str
    confidence: float
    timestamp: datetime


# ========================
# Global State
# ========================

db_client: MongoClient = None
db = None


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
    logger.info("🚀 Starting AI Service Tier 1...")
    
    try:
        # Load all models
        logger.info("Loading ML models...")
        models = load_all_models()
        logger.info(f"✓ Loaded {len([m for m in models.values() if m])} models")
        
        # Connect to MongoDB
        mongo_url = os.getenv(
            'DATABASE_URL',
            'mongodb://localhost:27017'
        )
        db_name = os.getenv('MAIN_DB_NAME', 'document_processing')
        
        logger.info(f"Connecting to MongoDB: {mongo_url}")
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
# Endpoints
# ========================

@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint
    """
    return HealthResponse(
        status="healthy" if models_ready() else "degraded",
        timestamp=datetime.utcnow(),
        models_loaded=models_ready(),
        gpu_available=torch.cuda.is_available(),
        message="All models loaded and ready" if models_ready() else "Some models still loading"
    )


@app.get("/api/v1/status", response_model=StatusResponse)
async def service_status() -> StatusResponse:
    """
    Detailed service status including loaded models
    """
    models = get_models()
    loaded_models = [
        name for name, model in models.items()
        if model is not None and name != 'llama'  # Llama is lazy-loaded
    ]
    
    return StatusResponse(
        status="ready" if models_ready() else "initializing",
        models_loaded=loaded_models,
        ready=models_ready(),
        gpu_available=torch.cuda.is_available(),
        available_models=len(loaded_models),
        timestamp=datetime.utcnow()
    )


@app.post("/api/v1/process", response_model=ProcessResponse)
async def process_document(
    request: ProcessRequest,
    background_tasks: BackgroundTasks
) -> ProcessResponse:
    """
    Queue document for AI processing
    
    Fire-and-forget: Accepts document, queues for background processing,
    returns immediately. Client polls MongoDB for status updates.
    
    Args:
        request: ProcessRequest with doc_id and pdf_file_path
        background_tasks: FastAPI background tasks
        
    Returns:
        ProcessResponse confirming document queued
    """
    try:
        doc_id = request.doc_id
        pdf_path = request.pdf_file_path
        
        # Validate file exists
        if not os.path.exists(pdf_path):
            raise HTTPException(
                status_code=400,
                detail=f"PDF file not found: {pdf_path}"
            )
        
        logger.info(f"Received process request for {doc_id}: {pdf_path}")
        
        # Create document record in MongoDB
        documents = db['documents']
        documents.insert_one({
            '_id': doc_id,
            'status': 'PENDING',
            'created_at': datetime.utcnow(),
            'processing_started': None,
            'processing_completed': None,
            'pdf_path': pdf_path,
            'processed_data': [],
            'error': None
        })
        
        # Queue background task
        background_tasks.add_task(
            run_full_ai_pipeline,
            doc_id,
            pdf_path,
            db,
            get_models()
        )
        
        logger.info(f"✓ Document {doc_id} queued for processing")
        
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
            # Fallback: manual similarity search
            logger.info(f"Atlas search unavailable, using fallback: {e}")
            
            all_docs = list(documents.find(search_filter))
            results = []
            
            for doc in all_docs:
                for processed_doc in doc.get('processed_data', []):
                    embedding = processed_doc.get('embedding', [])
                    if embedding:
                        # Cosine similarity
                        import numpy as np
                        sim = np.dot(query_embedding, embedding) / (
                            np.linalg.norm(query_embedding) * np.linalg.norm(embedding) + 1e-8
                        )
                        
                        if sim > 0.3:  # Threshold
                            results.append({
                                'similarity_score': float(sim),
                                'document': {
                                    '_id': doc['_id'],
                                    'logical_doc_num': processed_doc['logical_doc_num'],
                                    'text': processed_doc['text'],
                                    'page_range': processed_doc['page_range']
                                }
                            })
            
            # Sort by score
            results.sort(
                key=lambda x: x['similarity_score'],
                reverse=True
            )
            results = results[:request.top_k]
        
        # Format results
        formatted_results = [
            {
                'document_id': r['document']['_id'],
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


@app.post("/api/v1/query", response_model=QueryResponse)
async def query_document(request: QueryRequest) -> QueryResponse:
    """
    Question-answering over a document using Llama 3.2 3B
    
    Args:
        request: QueryRequest with doc_id and question
        
    Returns:
        QueryResponse with answer from Llama
    """
    try:
        models = get_models()
        
        # Get document from MongoDB
        documents = db['documents']
        doc = documents.find_one({'_id': request.doc_id})
        
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document {request.doc_id} not found"
            )
        
        if doc['status'] != 'COMPLETE':
            raise HTTPException(
                status_code=400,
                detail=f"Document still processing (status: {doc['status']})"
            )
        
        # Gather context from processed data
        context_texts = []
        for processed_doc in doc.get('processed_data', []):
            context_texts.append(processed_doc['text'])
        
        context = " ".join(context_texts)[:request.context_size]
        
        logger.info(f"Querying document {request.doc_id}: {request.question}")
        
        # Load Llama if needed
        if models.get('llama') is None:
            from app.model_loader import load_llama_model
            llama = load_llama_model()
            models['llama'] = llama
        else:
            llama = models['llama']
        
        if llama is None:
            # Fallback without Llama
            answer = "Llama model not available. Please check server logs."
            confidence = 0.0
        else:
            # Generate answer with Llama
            prompt = f"""Context:
{context}

Question: {request.question}

Answer:"""
            
            response = llama(
                prompt,
                max_tokens=300,
                temperature=0.7,
                top_p=0.9
            )
            
            answer = response['choices'][0]['text'].strip()
            confidence = 0.8  # Placeholder
        
        logger.info(f"✓ Generated answer ({len(answer)} chars)")
        
        return QueryResponse(
            doc_id=request.doc_id,
            question=request.question,
            answer=answer,
            confidence=confidence,
            timestamp=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying document: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Query error: {str(e)}"
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
    port = int(os.getenv('PORT', 8000))
    
    logger.info(f"Starting Uvicorn on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level='info'
    )
