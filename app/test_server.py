"""
Test Server - Runs on port 8001 for development/testing
Separate from main production app on port 8000
"""

import os
import logging
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch

from app.model_loader import load_all_models, get_models, models_ready

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_server")

# Create test app
test_app = FastAPI(
    title="AI Service Tier 1 - Test Server",
    description="Test and development endpoints",
    version="1.0.0"
)

# ========================
# Test Endpoints
# ========================

@test_app.get("/test/health")
async def test_health():
    """Test health endpoint"""
    return {
        "status": "healthy",
        "port": 8001,
        "models_ready": models_ready(),
        "gpu_available": torch.cuda.is_available()
    }


@test_app.get("/test/models")
async def test_models():
    """Test available models"""
    models = get_models()
    return {
        "loaded_models": [k for k, v in models.items() if v is not None],
        "total_models": len(models),
        "models_ready": models_ready(),
        "gpu": torch.cuda.is_available()
    }


@test_app.post("/test/simple-ocr")
async def test_simple_ocr(image_path: str):
    """
    Test PaddleOCR on a single image
    
    Args:
        image_path: Path to image file
        
    Returns:
        OCR results
    """
    try:
        if not os.path.exists(image_path):
            raise HTTPException(status_code=400, detail=f"Image not found: {image_path}")
        
        models = get_models()
        paddleocr = models['paddleocr']
        
        from PIL import Image
        import numpy as np
        
        image = Image.open(image_path)
        image_array = np.array(image)
        
        result = paddleocr.ocr(image_array, cls=True)
        
        text_lines = []
        if result:
            for line in result:
                if line:
                    for word_info in line:
                        if word_info and len(word_info) >= 2:
                            text_lines.append(word_info[1][0])
        
        return {
            "status": "success",
            "image_path": image_path,
            "text": " ".join(text_lines),
            "lines_extracted": len(text_lines)
        }
        
    except Exception as e:
        logger.error(f"Error in test OCR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@test_app.post("/test/embedding")
async def test_embedding(text: str):
    """
    Test text embedding with all-MiniLM-L6-v2
    
    Args:
        text: Text to embed
        
    Returns:
        Embedding vector
    """
    try:
        models = get_models()
        sentence_transformer = models['sentence_transformer_search']
        
        embedding = sentence_transformer.encode(text, convert_to_tensor=False)
        
        return {
            "status": "success",
            "text": text[:100] + "..." if len(text) > 100 else text,
            "embedding_dim": len(embedding),
            "embedding": embedding.tolist()[:10] + ["..."] # First 10 values + ellipsis
        }
        
    except Exception as e:
        logger.error(f"Error in test embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@test_app.post("/test/classification")
async def test_classification(text: str):
    """
    Test zero-shot classification with all-MiniLM-L12-v2
    
    Args:
        text: Text to classify
        
    Returns:
        Classification results
    """
    try:
        models = get_models()
        sentence_transformer = models['sentence_transformer_classify']
        
        candidate_labels = [
            'Invoice', 'Contract', 'Receipt', 'Report', 'Letter',
            'Form', 'Agreement', 'Statement', 'Certificate', 'Other'
        ]
        
        text_embedding = sentence_transformer.encode(text, convert_to_tensor=False)
        label_embeddings = sentence_transformer.encode(
            candidate_labels,
            convert_to_tensor=False
        )
        
        # Compute cosine similarities
        import numpy as np
        similarities = {}
        text_norm = np.linalg.norm(text_embedding)
        
        for label, label_embedding in zip(candidate_labels, label_embeddings):
            label_norm = np.linalg.norm(label_embedding)
            similarity = np.dot(text_embedding, label_embedding) / (
                text_norm * label_norm + 1e-8
            )
            similarities[label] = float(similarity)
        
        # Normalize to probabilities (softmax)
        max_sim = max(similarities.values())
        similarities_exp = {
            k: np.exp(v - max_sim) for k, v in similarities.items()
        }
        sum_exp = sum(similarities_exp.values())
        probabilities = {
            k: v / sum_exp for k, v in similarities_exp.items()
        }
        
        # Get top label
        top_label = max(probabilities, key=probabilities.get)
        
        return {
            "status": "success",
            "text": text[:100] + "..." if len(text) > 100 else text,
            "top_label": top_label,
            "confidence": probabilities[top_label],
            "all_labels": probabilities
        }
        
    except Exception as e:
        logger.error(f"Error in test classification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Test Server on port 8001")
    logger.info("Main app runs on port 8000")
    
    uvicorn.run(
        test_app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
