"""
Structure-Aware Entity Extraction

Enhanced entity recognition that leverages document structure from DeepSeek OCR.
Uses section context (headers, tables) to improve entity classification and extraction.

Example:
    In an invoice:
    - "Microsoft" under "Vendor" section → Organization (Vendor)
    - "Microsoft" under "Items" table → Product name
    - "$1,234.56" in "Total" section → Invoice total
    - "$45.00" in "Items" table row → Line item price
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from .markdown_parser import StructuredDocument, SectionType, TableStructure


class EntityType(str, Enum):
    """Types of entities to extract"""
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    DATE = "DATE"
    MONEY = "MONEY"
    PRODUCT = "PRODUCT"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    ADDRESS = "ADDRESS"
    INVOICE_NUMBER = "INVOICE_NUMBER"
    ORDER_NUMBER = "ORDER_NUMBER"
    TAX_ID = "TAX_ID"
    ACCOUNT_NUMBER = "ACCOUNT_NUMBER"


@dataclass
class StructuredEntity:
    """
    An entity with structure context.
    
    Attributes:
        text: The entity text
        type: Entity type
        confidence: Confidence score (0-1)
        section_context: Section where entity was found
        table_context: Table and row/column if in a table
        role: Semantic role (e.g., "vendor", "customer", "total")
        metadata: Additional context information
    """
    text: str
    type: EntityType
    confidence: float
    section_context: Optional[str] = None
    table_context: Optional[Dict[str, Any]] = None
    role: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "type": self.type.value,
            "confidence": self.confidence,
            "section_context": self.section_context,
            "table_context": self.table_context,
            "role": self.role,
            "metadata": self.metadata
        }


class StructureAwareExtractor:
    """
    Extract entities with awareness of document structure.
    
    Uses section headers and table context to improve entity classification
    and assign semantic roles.
    """
    
    def __init__(self):
        # Semantic role patterns for common document sections
        self.section_roles = {
            "vendor": ["vendor", "supplier", "from", "seller", "bill from"],
            "customer": ["customer", "client", "to", "buyer", "bill to", "ship to"],
            "items": ["items", "products", "services", "description", "line items"],
            "totals": ["total", "subtotal", "amount", "sum", "payment"],
            "dates": ["date", "due date", "invoice date", "order date"],
            "shipping": ["shipping", "delivery", "ship to", "delivery address"],
            "billing": ["billing", "bill to", "billing address"],
        }
        
        # Column name patterns for table-based extraction
        self.column_roles = {
            "quantity": ["qty", "quantity", "amount", "count", "units"],
            "price": ["price", "unit price", "rate", "cost", "amount"],
            "total": ["total", "subtotal", "amount", "sum"],
            "description": ["description", "item", "product", "service", "details"],
            "date": ["date", "due", "invoice date", "order date"],
        }
    
    def extract_entities(
        self,
        structured_doc: StructuredDocument,
        base_entities: List[Dict[str, Any]]
    ) -> List[StructuredEntity]:
        """
        Extract entities with structure awareness.
        
        Args:
            structured_doc: Parsed document structure
            base_entities: Entities from base NER model
            
        Returns:
            List of StructuredEntity with enhanced context
        """
        enhanced_entities = []
        
        # Process each base entity
        for entity in base_entities:
            text = entity.get("text", "")
            entity_type = entity.get("label", "")
            confidence = entity.get("score", 0.0)
            
            # Get section context
            section_context = structured_doc.get_context_for_text(text)
            
            # Determine semantic role based on context
            role = self._determine_role(text, section_context, entity_type)
            
            # Check if entity is in a table
            table_context = self._get_table_context(text, structured_doc)
            
            # Enhance entity type based on context
            enhanced_type = self._enhance_entity_type(
                entity_type, role, section_context, table_context
            )
            
            enhanced_entities.append(StructuredEntity(
                text=text,
                type=enhanced_type,
                confidence=confidence,
                section_context=section_context,
                table_context=table_context,
                role=role,
                metadata={
                    "original_type": entity_type,
                    "section_title": section_context
                }
            ))
        
        # Extract table-specific entities
        table_entities = self._extract_table_entities(structured_doc)
        enhanced_entities.extend(table_entities)
        
        # Remove duplicates and merge
        enhanced_entities = self._deduplicate_entities(enhanced_entities)
        
        return enhanced_entities
    
    def _determine_role(
        self,
        text: str,
        section_context: Optional[str],
        entity_type: str
    ) -> Optional[str]:
        """Determine the semantic role of an entity"""
        if not section_context:
            return None
        
        section_lower = section_context.lower()
        
        # Check for role patterns
        for role, patterns in self.section_roles.items():
            if any(pattern in section_lower for pattern in patterns):
                return role
        
        return None
    
    def _get_table_context(
        self,
        text: str,
        structured_doc: StructuredDocument
    ) -> Optional[Dict[str, Any]]:
        """Get table context for an entity"""
        for table in structured_doc.tables:
            # Check if text is in table
            if text in table.raw_text:
                # Find which row and column
                for row_idx, row in enumerate(table.rows):
                    for col_idx, cell in enumerate(row):
                        if text in cell:
                            return {
                                "table_headers": table.headers,
                                "row_index": row_idx,
                                "column_index": col_idx,
                                "column_name": table.headers[col_idx] if col_idx < len(table.headers) else None,
                                "row_data": dict(zip(table.headers, row))
                            }
        return None
    
    def _enhance_entity_type(
        self,
        base_type: str,
        role: Optional[str],
        section_context: Optional[str],
        table_context: Optional[Dict[str, Any]]
    ) -> EntityType:
        """Enhance entity type based on context"""
        # Map base NER types to EntityType
        type_mapping = {
            "PER": EntityType.PERSON,
            "PERSON": EntityType.PERSON,
            "ORG": EntityType.ORGANIZATION,
            "ORGANIZATION": EntityType.ORGANIZATION,
            "LOC": EntityType.LOCATION,
            "LOCATION": EntityType.LOCATION,
            "DATE": EntityType.DATE,
            "MONEY": EntityType.MONEY,
        }
        
        # Get base entity type
        entity_type = type_mapping.get(base_type.upper(), EntityType.ORGANIZATION)
        
        # Enhance based on table context
        if table_context:
            column_name = table_context.get("column_name", "").lower()
            
            if any(p in column_name for p in self.column_roles.get("price", [])):
                entity_type = EntityType.MONEY
            elif any(p in column_name for p in self.column_roles.get("description", [])):
                entity_type = EntityType.PRODUCT
            elif any(p in column_name for p in self.column_roles.get("date", [])):
                entity_type = EntityType.DATE
        
        return entity_type
    
    def _extract_table_entities(
        self,
        structured_doc: StructuredDocument
    ) -> List[StructuredEntity]:
        """Extract entities from table structure"""
        entities = []
        
        for table in structured_doc.tables:
            # Extract from each cell
            for row_idx, row in enumerate(table.rows):
                for col_idx, cell_text in enumerate(row):
                    if not cell_text.strip():
                        continue
                    
                    column_name = table.headers[col_idx] if col_idx < len(table.headers) else ""
                    
                    # Determine entity type from column name
                    entity_type = self._infer_type_from_column(column_name, cell_text)
                    
                    if entity_type:
                        role = self._get_role_from_column(column_name)
                        
                        entities.append(StructuredEntity(
                            text=cell_text,
                            type=entity_type,
                            confidence=0.85,  # High confidence for structured data
                            section_context=f"Table column: {column_name}",
                            table_context={
                                "table_headers": table.headers,
                                "row_index": row_idx,
                                "column_index": col_idx,
                                "column_name": column_name,
                                "row_data": dict(zip(table.headers, row))
                            },
                            role=role,
                            metadata={"source": "table_extraction"}
                        ))
        
        return entities
    
    def _infer_type_from_column(self, column_name: str, cell_text: str) -> Optional[EntityType]:
        """Infer entity type from column name"""
        column_lower = column_name.lower()
        
        # Money/Price columns
        if any(p in column_lower for p in ["price", "amount", "total", "cost", "fee", "charge"]):
            if any(c in cell_text for c in ["$", "€", "£", "¥"]) or cell_text.replace(".", "").replace(",", "").isdigit():
                return EntityType.MONEY
        
        # Date columns
        if any(p in column_lower for p in ["date", "due", "invoice date", "order date"]):
            return EntityType.DATE
        
        # Product/Item columns
        if any(p in column_lower for p in ["item", "product", "description", "service"]):
            return EntityType.PRODUCT
        
        # Quantity columns (skip - just numbers)
        if any(p in column_lower for p in ["qty", "quantity", "count"]):
            return None
        
        return None
    
    def _get_role_from_column(self, column_name: str) -> Optional[str]:
        """Get semantic role from column name"""
        column_lower = column_name.lower()
        
        for role, patterns in self.column_roles.items():
            if any(p in column_lower for pattern in patterns for p in [pattern]):
                return role
        
        return None
    
    def _deduplicate_entities(self, entities: List[StructuredEntity]) -> List[StructuredEntity]:
        """Remove duplicate entities, keeping the one with most context"""
        seen = {}
        
        for entity in entities:
            key = (entity.text, entity.type)
            
            if key not in seen:
                seen[key] = entity
            else:
                # Keep entity with more context
                existing = seen[key]
                if entity.table_context and not existing.table_context:
                    seen[key] = entity
                elif entity.role and not existing.role:
                    seen[key] = entity
                elif entity.confidence > existing.confidence:
                    seen[key] = entity
        
        return list(seen.values())


def extract_structured_entities(
    structured_doc: StructuredDocument,
    base_entities: List[Dict[str, Any]]
) -> List[StructuredEntity]:
    """
    Convenience function for structure-aware entity extraction.
    
    Args:
        structured_doc: Parsed document with structure
        base_entities: Base NER entities
        
    Returns:
        List of enhanced entities with context
    """
    extractor = StructureAwareExtractor()
    return extractor.extract_entities(structured_doc, base_entities)
