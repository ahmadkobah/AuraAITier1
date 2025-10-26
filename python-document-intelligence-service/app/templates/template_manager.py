"""
Template Manager
===============

High-level template management service that handles document templates,
matching, and template lifecycle management.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..models.template_model import TemplateMatchingModel

logger = logging.getLogger(__name__)

class TemplateManager:
    """
    High-level template management service.
    """
    
    def __init__(self):
        self.template_model = TemplateMatchingModel()
        self.is_initialized = False
    
    async def initialize(self):
        """Initialize the template manager."""
        try:
            logger.info("Initializing Template Manager...")
            await self.template_model.initialize()
            self.is_initialized = True
            logger.info("Template Manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Template Manager: {str(e)}")
            raise
    
    async def match_templates(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        template_ids: Optional[List[str]] = None,
        similarity_threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Match document content against available templates.
        
        Args:
            content: Document text content
            metadata: Additional document metadata
            template_ids: Specific template IDs to match against
            similarity_threshold: Minimum similarity threshold
            
        Returns:
            Template matching results with similarity scores
        """
        if not self.is_initialized:
            raise RuntimeError("Template Manager not initialized")
        
        return await self.template_model.match_templates(
            content=content,
            metadata=metadata,
            template_ids=template_ids,
            similarity_threshold=similarity_threshold
        )
    
    async def add_template(self, template_id: str, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new template to the system."""
        if not self.is_initialized:
            raise RuntimeError("Template Manager not initialized")
        
        return await self.template_model.add_template(template_id, template_data)
    
    async def get_template_info(self) -> Dict[str, Any]:
        """Get information about available templates."""
        if not self.is_initialized:
            return {"status": "not_initialized"}
        
        return await self.template_model.get_template_info()
    
    async def get_available_templates(self) -> List[str]:
        """Get list of available template IDs."""
        if not self.is_initialized:
            return []
        
        return list(self.template_model.templates.keys())
    
    async def get_template_categories(self) -> List[str]:
        """Get list of template categories."""
        if not self.is_initialized:
            return []
        
        return list(self.template_model.template_categories.keys())