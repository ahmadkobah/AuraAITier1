"""
Document Classifier
==================

High-level document classification service that coordinates multiple
classification models and provides intelligent document type detection.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..models.classification_model import DocumentClassificationModel

logger = logging.getLogger(__name__)

class DocumentClassifier:
    """
    High-level document classification service.
    """
    
    def __init__(self):
        self.classification_model = DocumentClassificationModel()
        self.is_initialized = False
    
    async def initialize(self):
        """Initialize the document classifier."""
        try:
            logger.info("Initializing Document Classifier...")
            await self.classification_model.initialize()
            self.is_initialized = True
            logger.info("Document Classifier initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Document Classifier: {str(e)}")
            raise
    
    async def classify_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        confidence_threshold: float = 0.8,
        return_all: bool = False
    ) -> Dict[str, Any]:
        """
        Classify document using the classification model.
        
        Args:
            content: Document text content
            metadata: Additional document metadata
            confidence_threshold: Minimum confidence threshold
            return_all: Return all predictions or just the top one
            
        Returns:
            Classification result with confidence scores
        """
        if not self.is_initialized:
            raise RuntimeError("Document Classifier not initialized")
        
        return await self.classification_model.classify_document(
            content=content,
            metadata=metadata,
            confidence_threshold=confidence_threshold,
            return_all=return_all
        )
    
    async def train_classifier(self, training_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Train the classification model with new data."""
        if not self.is_initialized:
            raise RuntimeError("Document Classifier not initialized")
        
        return await self.classification_model.train_models(training_data)
    
    async def get_classifier_info(self) -> Dict[str, Any]:
        """Get information about the classifier."""
        if not self.is_initialized:
            return {"status": "not_initialized"}
        
        return await self.classification_model.get_model_info()