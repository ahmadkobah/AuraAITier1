"""
Entity Extractor
===============

High-level entity extraction service that coordinates multiple
extraction models and provides comprehensive entity recognition.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..models.extraction_model import EntityExtractionModel

logger = logging.getLogger(__name__)

class EntityExtractor:
    """
    High-level entity extraction service.
    """
    
    def __init__(self):
        self.extraction_model = EntityExtractionModel()
        self.is_initialized = False
    
    async def initialize(self):
        """Initialize the entity extractor."""
        try:
            logger.info("Initializing Entity Extractor...")
            await self.extraction_model.initialize()
            self.is_initialized = True
            logger.info("Entity Extractor initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Entity Extractor: {str(e)}")
            raise
    
    async def extract_entities(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        extraction_types: Optional[List[str]] = None,
        custom_patterns: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Extract entities from document content.
        
        Args:
            content: Document text content
            metadata: Additional document metadata
            extraction_types: Specific entity types to extract
            custom_patterns: Custom regex patterns for extraction
            
        Returns:
            Extraction results with entities and confidence scores
        """
        if not self.is_initialized:
            raise RuntimeError("Entity Extractor not initialized")
        
        return await self.extraction_model.extract_entities(
            content=content,
            metadata=metadata,
            extraction_types=extraction_types,
            custom_patterns=custom_patterns
        )
    
    async def get_extractor_stats(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        if not self.is_initialized:
            return {"status": "not_initialized"}
        
        return await self.extraction_model.get_extraction_stats()
    
    async def get_supported_entity_types(self) -> List[str]:
        """Get list of supported entity types."""
        if not self.is_initialized:
            return []
        
        return list(self.extraction_model.entity_types.keys())