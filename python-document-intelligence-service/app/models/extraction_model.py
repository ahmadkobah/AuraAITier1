"""
Entity Extraction Model
=======================

Advanced named entity recognition (NER) and information extraction system
for documents using multiple approaches including rule-based patterns,
statistical models, and transformer-based models.

Features:
- Multi-entity type extraction (person, organization, date, amount, etc.)
- Custom pattern-based extraction
- Statistical and transformer-based NER
- Confidence scoring and validation
- Custom entity type definitions
- Batch processing capabilities
"""

import asyncio
import logging
import json
import pickle
import re
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime, date
from pathlib import Path
import os

# Core libraries
import numpy as np
import pandas as pd

# NLP libraries
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.chunk import ne_chunk
from nltk.tag import pos_tag

# Download required NLTK data on import
def ensure_nltk_data():
    """Ensure required NLTK data is available"""
    try:
        # Test if punkt tokenizer is available
        word_tokenize("test")
    except LookupError:
        nltk.download('punkt')
    
    try:
        # Test if averaged_perceptron_tagger is available
        pos_tag([('test', 'NN')])
    except LookupError:
        nltk.download('averaged_perceptron_tagger')

# Ensure NLTK data is available when module is imported
ensure_nltk_data()

import spacy
from spacy import displacy

# Transformer models
from transformers import AutoTokenizer, AutoModelForTokenClassification
from transformers import pipeline
import torch

# Pattern matching
import dateutil.parser
from dateutil import parser as date_parser
import phonenumbers
from email_validator import validate_email, EmailNotValidError

# Machine learning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
import joblib

logger = logging.getLogger(__name__)

class EntityExtractionModel:
    """
    Advanced entity extraction model with multiple extraction approaches.
    """
    
    def __init__(self, model_dir: str = "trained_models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        
        # Model components
        self.nlp = None  # spaCy model
        self.ner_pipeline = None  # Transformer NER pipeline
        self.custom_models = {}  # Custom trained models
        
        # Pattern definitions
        self.patterns = self._initialize_patterns()
        
        # Entity type configurations
        self.entity_types = {
            "PERSON": {
                "description": "Person names and titles",
                "patterns": [
                    r"\b(?:Mr|Mrs|Ms|Dr|Prof|Sir|Madam)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*",
                    r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b"
                ],
                "validation": self._validate_person,
                "confidence_boost": 1.2
            },
            "ORGANIZATION": {
                "description": "Company and organization names",
                "patterns": [
                    r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Inc|Corp|LLC|Ltd|Co|Company|Corporation|Limited)\b",
                    r"\b(?:Microsoft|Google|Apple|Amazon|IBM|Oracle|Intel)\b"
                ],
                "validation": self._validate_organization,
                "confidence_boost": 1.1
            },
            "DATE": {
                "description": "Dates in various formats",
                "patterns": [
                    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
                    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
                    r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\b"
                ],
                "validation": self._validate_date,
                "confidence_boost": 1.3
            },
            "MONEY": {
                "description": "Monetary amounts and currency",
                "patterns": [
                    r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?",
                    r"\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP|dollars?|euros?|pounds?)\b",
                    r"\b(?:USD|EUR|GBP|\$)\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b"
                ],
                "validation": self._validate_money,
                "confidence_boost": 1.4
            },
            "EMAIL": {
                "description": "Email addresses",
                "patterns": [
                    r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
                ],
                "validation": self._validate_email,
                "confidence_boost": 1.5
            },
            "PHONE": {
                "description": "Phone numbers",
                "patterns": [
                    r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
                    r"\(\d{3}\)\s*\d{3}[-.]?\d{4}\b",
                    r"\+\d{1,3}\s*\d{3,4}\s*\d{3,4}\s*\d{3,4}\b"
                ],
                "validation": self._validate_phone,
                "confidence_boost": 1.3
            },
            "ADDRESS": {
                "description": "Physical addresses",
                "patterns": [
                    r"\b\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)\b",
                    r"\b\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:St|Ave|Rd|Dr|Ln|Blvd)\.?\s*,?\s*[A-Z][a-z]+\s*,?\s*[A-Z]{2}\s+\d{5}\b"
                ],
                "validation": self._validate_address,
                "confidence_boost": 1.1
            },
            "SSN": {
                "description": "Social Security Numbers",
                "patterns": [
                    r"\b\d{3}-\d{2}-\d{4}\b",
                    r"\b\d{9}\b"
                ],
                "validation": self._validate_ssn,
                "confidence_boost": 1.6
            },
            "ACCOUNT_NUMBER": {
                "description": "Account numbers and IDs",
                "patterns": [
                    r"\b(?:Account|Acct|ID|Number|No)\.?\s*:?\s*\d{6,20}\b",
                    r"\b[A-Z]{2,4}\d{6,15}\b"
                ],
                "validation": self._validate_account_number,
                "confidence_boost": 1.2
            },
            "TAX_ID": {
                "description": "Tax identification numbers",
                "patterns": [
                    r"\b\d{2}-\d{7}\b",  # EIN format
                    r"\b\d{3}-\d{2}-\d{4}\b"  # SSN format (also used for tax ID)
                ],
                "validation": self._validate_tax_id,
                "confidence_boost": 1.4
            }
        }
        
        # Extraction statistics
        self.stats = {
            "total_extractions": 0,
            "entity_counts": {},
            "confidence_distribution": {},
            "processing_times": [],
            "last_updated": None
        }
    
    def _initialize_patterns(self) -> Dict[str, List[str]]:
        """Initialize regex patterns for entity extraction."""
        return {
            "invoice_number": [
                r"invoice\s*#?\s*:?\s*([A-Z0-9\-]{3,20})",
                r"inv\s*#?\s*:?\s*([A-Z0-9\-]{3,20})",
                r"bill\s*#?\s*:?\s*([A-Z0-9\-]{3,20})"
            ],
            "contract_number": [
                r"contract\s*#?\s*:?\s*([A-Z0-9\-]{3,20})",
                r"agreement\s*#?\s*:?\s*([A-Z0-9\-]{3,20})"
            ],
            "po_number": [
                r"(?:purchase\s*order|po)\s*#?\s*:?\s*([A-Z0-9\-]{3,20})"
            ],
            "due_date": [
                r"due\s*(?:date|on)?\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                r"payment\s*due\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
            ],
            "total_amount": [
                r"total\s*:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
                r"amount\s*due\s*:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
                r"balance\s*:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)"
            ]
        }
    
    async def initialize(self):
        """Initialize the entity extraction model."""
        try:
            logger.info("Initializing Entity Extraction Model...")
            
            # Initialize spaCy model
            try:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("spaCy model loaded successfully")
            except OSError:
                logger.warning("spaCy model not found, using basic NER")
                self.nlp = None
            
            # Initialize transformer NER pipeline
            await self._initialize_transformer_ner()
            
            # Load custom trained models
            await self._load_custom_models()
            
            logger.info("Entity Extraction Model initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize entity extraction model: {str(e)}")
            raise
    
    async def _initialize_transformer_ner(self):
        """Initialize transformer-based NER pipeline."""
        try:
            # Use a pre-trained NER model
            self.ner_pipeline = pipeline(
                "ner",
                model="dbmdz/bert-large-cased-finetuned-conll03-english",
                aggregation_strategy="simple",
                device=0 if torch.cuda.is_available() else -1
            )
            logger.info("Transformer NER pipeline initialized")
            
        except Exception as e:
            logger.warning(f"Failed to initialize transformer NER: {str(e)}")
            self.ner_pipeline = None
    
    async def _load_custom_models(self):
        """Load custom trained extraction models."""
        try:
            models_path = self.model_dir / "extraction_models.pkl"
            if models_path.exists():
                with open(models_path, 'rb') as f:
                    self.custom_models = pickle.load(f)
                logger.info("Custom extraction models loaded")
            
        except Exception as e:
            logger.warning(f"Failed to load custom models: {str(e)}")
    
    async def extract_entities(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        extraction_types: Optional[List[str]] = None,
        custom_patterns: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Extract entities from document content using multiple approaches.
        
        Args:
            content: Document text content
            metadata: Additional document metadata
            extraction_types: Specific entity types to extract
            custom_patterns: Custom regex patterns for extraction
            
        Returns:
            Extraction results with entities and confidence scores
        """
        start_time = datetime.utcnow()
        
        try:
            logger.info("Starting entity extraction...")
            
            # Initialize results
            entities = {}
            confidence_scores = {}
            extraction_metadata = {
                "content_length": len(content),
                "extraction_timestamp": start_time.isoformat(),
                "methods_used": []
            }
            
            # Determine which entity types to extract
            target_types = extraction_types or list(self.entity_types.keys())
            
            # Pattern-based extraction
            pattern_entities = await self._pattern_based_extraction(content, target_types, custom_patterns)
            entities.update(pattern_entities["entities"])
            confidence_scores.update(pattern_entities["confidence_scores"])
            extraction_metadata["methods_used"].append("pattern_based")
            
            # spaCy NER extraction
            if self.nlp:
                spacy_entities = await self._spacy_extraction(content, target_types)
                entities = self._merge_entities(entities, spacy_entities["entities"])
                confidence_scores.update(spacy_entities["confidence_scores"])
                extraction_metadata["methods_used"].append("spacy")
            
            # Transformer NER extraction
            if self.ner_pipeline:
                transformer_entities = await self._transformer_extraction(content, target_types)
                entities = self._merge_entities(entities, transformer_entities["entities"])
                confidence_scores.update(transformer_entities["confidence_scores"])
                extraction_metadata["methods_used"].append("transformer")
            
            # Custom model extraction
            if self.custom_models:
                custom_entities = await self._custom_model_extraction(content, target_types)
                entities = self._merge_entities(entities, custom_entities["entities"])
                confidence_scores.update(custom_entities["confidence_scores"])
                extraction_metadata["methods_used"].append("custom_models")
            
            # Validate and filter entities
            validated_entities = await self._validate_entities(entities, confidence_scores)
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Update statistics
            await self._update_stats(validated_entities, processing_time)
            
            result = {
                "entities": validated_entities["entities"],
                "confidence_scores": validated_entities["confidence_scores"],
                "processing_time": processing_time,
                "extraction_metadata": extraction_metadata
            }
            
            logger.info(f"Entity extraction completed in {processing_time:.2f} seconds")
            logger.info(f"Extracted {sum(len(v) for v in validated_entities['entities'].values())} entities")
            
            return result
            
        except Exception as e:
            logger.error(f"Entity extraction error: {str(e)}")
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            return {
                "entities": {},
                "confidence_scores": {},
                "processing_time": processing_time,
                "extraction_metadata": {"error": str(e)}
            }
    
    async def _pattern_based_extraction(
        self,
        content: str,
        target_types: List[str],
        custom_patterns: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Extract entities using regex patterns."""
        try:
            entities = {}
            confidence_scores = {}
            
            # Use custom patterns if provided
            all_patterns = {**self.patterns}
            if custom_patterns:
                all_patterns.update(custom_patterns)
            
            # Extract using defined patterns for each entity type
            for entity_type in target_types:
                if entity_type not in self.entity_types:
                    continue
                
                type_entities = []
                type_confidences = {}
                
                # Use patterns defined for this entity type
                patterns = self.entity_types[entity_type].get("patterns", [])
                
                for pattern in patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        entity_text = match.group().strip()
                        if entity_text and len(entity_text) > 1:
                            # Calculate confidence based on pattern match quality
                            confidence = self._calculate_pattern_confidence(entity_text, entity_type)
                            
                            type_entities.append({
                                "text": entity_text,
                                "start": match.start(),
                                "end": match.end(),
                                "method": "pattern",
                                "pattern": pattern
                            })
                            type_confidences[entity_text] = confidence
                
                if type_entities:
                    entities[entity_type] = type_entities
                    confidence_scores.update(type_confidences)
            
            # Extract using document-specific patterns
            for pattern_name, patterns in all_patterns.items():
                if pattern_name not in target_types:
                    continue
                
                pattern_entities = []
                for pattern in patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if match.groups():
                            entity_text = match.group(1).strip()
                        else:
                            entity_text = match.group().strip()
                        
                        if entity_text:
                            pattern_entities.append({
                                "text": entity_text,
                                "start": match.start(),
                                "end": match.end(),
                                "method": "document_pattern",
                                "pattern_name": pattern_name
                            })
                            confidence_scores[entity_text] = 0.9  # High confidence for specific patterns
                
                if pattern_entities:
                    # Map pattern names to entity types
                    mapped_type = self._map_pattern_to_entity_type(pattern_name)
                    if mapped_type not in entities:
                        entities[mapped_type] = []
                    entities[mapped_type].extend(pattern_entities)
            
            return {
                "entities": entities,
                "confidence_scores": confidence_scores
            }
            
        except Exception as e:
            logger.error(f"Pattern-based extraction error: {str(e)}")
            return {"entities": {}, "confidence_scores": {}}
    
    async def _spacy_extraction(self, content: str, target_types: List[str]) -> Dict[str, Any]:
        """Extract entities using spaCy NER."""
        try:
            if not self.nlp:
                return {"entities": {}, "confidence_scores": {}}
            
            doc = self.nlp(content)
            entities = {}
            confidence_scores = {}
            
            # Map spaCy entity types to our entity types
            spacy_mapping = {
                "PERSON": "PERSON",
                "ORG": "ORGANIZATION",
                "DATE": "DATE",
                "MONEY": "MONEY",
                "GPE": "LOCATION",  # Geopolitical entity
                "LOC": "LOCATION"
            }
            
            for ent in doc.ents:
                mapped_type = spacy_mapping.get(ent.label_)
                if mapped_type and mapped_type in target_types:
                    if mapped_type not in entities:
                        entities[mapped_type] = []
                    
                    # Calculate confidence based on spaCy's confidence (if available)
                    confidence = getattr(ent, 'prob', 0.8)  # Default confidence
                    
                    entities[mapped_type].append({
                        "text": ent.text,
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "method": "spacy",
                        "label": ent.label_
                    })
                    confidence_scores[ent.text] = confidence
            
            return {
                "entities": entities,
                "confidence_scores": confidence_scores
            }
            
        except Exception as e:
            logger.error(f"spaCy extraction error: {str(e)}")
            return {"entities": {}, "confidence_scores": {}}
    
    async def _transformer_extraction(self, content: str, target_types: List[str]) -> Dict[str, Any]:
        """Extract entities using transformer-based NER."""
        try:
            if not self.ner_pipeline:
                return {"entities": {}, "confidence_scores": {}}
            
            # Truncate content if too long
            max_length = 512
            if len(content) > max_length:
                content = content[:max_length]
            
            # Get NER predictions
            ner_results = self.ner_pipeline(content)
            
            entities = {}
            confidence_scores = {}
            
            # Map transformer entity types to our entity types
            transformer_mapping = {
                "PER": "PERSON",
                "ORG": "ORGANIZATION",
                "LOC": "LOCATION",
                "MISC": "MISCELLANEOUS"
            }
            
            for result in ner_results:
                entity_type = transformer_mapping.get(result["entity_group"])
                if entity_type and entity_type in target_types:
                    if entity_type not in entities:
                        entities[entity_type] = []
                    
                    entities[entity_type].append({
                        "text": result["word"],
                        "start": result["start"],
                        "end": result["end"],
                        "method": "transformer",
                        "score": result["score"]
                    })
                    confidence_scores[result["word"]] = result["score"]
            
            return {
                "entities": entities,
                "confidence_scores": confidence_scores
            }
            
        except Exception as e:
            logger.error(f"Transformer extraction error: {str(e)}")
            return {"entities": {}, "confidence_scores": {}}
    
    async def _custom_model_extraction(self, content: str, target_types: List[str]) -> Dict[str, Any]:
        """Extract entities using custom trained models."""
        try:
            # Placeholder for custom model extraction
            # In production, this would use custom trained models
            return {"entities": {}, "confidence_scores": {}}
            
        except Exception as e:
            logger.error(f"Custom model extraction error: {str(e)}")
            return {"entities": {}, "confidence_scores": {}}
    
    def _merge_entities(self, entities1: Dict[str, List], entities2: Dict[str, List]) -> Dict[str, List]:
        """Merge entities from different extraction methods."""
        merged = entities1.copy()
        
        for entity_type, entity_list in entities2.items():
            if entity_type not in merged:
                merged[entity_type] = []
            
            # Add entities that don't already exist (based on text and position)
            existing_entities = {(e["text"], e.get("start", 0)) for e in merged[entity_type]}
            
            for entity in entity_list:
                entity_key = (entity["text"], entity.get("start", 0))
                if entity_key not in existing_entities:
                    merged[entity_type].append(entity)
        
        return merged
    
    async def _validate_entities(self, entities: Dict[str, List], confidence_scores: Dict[str, float]) -> Dict[str, Any]:
        """Validate extracted entities and filter by confidence."""
        try:
            validated_entities = {}
            validated_confidence = {}
            
            for entity_type, entity_list in entities.items():
                if entity_type not in self.entity_types:
                    continue
                
                valid_entities = []
                validation_func = self.entity_types[entity_type].get("validation")
                confidence_boost = self.entity_types[entity_type].get("confidence_boost", 1.0)
                
                for entity in entity_list:
                    entity_text = entity["text"]
                    base_confidence = confidence_scores.get(entity_text, 0.5)
                    
                    # Apply validation if available
                    is_valid = True
                    if validation_func:
                        is_valid = await validation_func(entity_text)
                    
                    if is_valid:
                        # Apply confidence boost for valid entities
                        final_confidence = min(base_confidence * confidence_boost, 1.0)
                        
                        # Filter by minimum confidence threshold
                        if final_confidence >= 0.3:  # Minimum threshold
                            valid_entities.append(entity)
                            validated_confidence[entity_text] = final_confidence
                
                if valid_entities:
                    validated_entities[entity_type] = valid_entities
            
            return {
                "entities": validated_entities,
                "confidence_scores": validated_confidence
            }
            
        except Exception as e:
            logger.error(f"Entity validation error: {str(e)}")
            return {"entities": entities, "confidence_scores": confidence_scores}
    
    def _calculate_pattern_confidence(self, entity_text: str, entity_type: str) -> float:
        """Calculate confidence score for pattern-matched entities."""
        try:
            base_confidence = 0.7
            
            # Boost confidence based on entity characteristics
            if entity_type == "EMAIL" and "@" in entity_text and "." in entity_text:
                base_confidence = 0.95
            elif entity_type == "PHONE" and re.match(r"^\+?[\d\s\-\(\)]{10,}$", entity_text):
                base_confidence = 0.9
            elif entity_type == "MONEY" and "$" in entity_text:
                base_confidence = 0.85
            elif entity_type == "DATE":
                base_confidence = 0.8
            
            return base_confidence
            
        except Exception:
            return 0.5
    
    def _map_pattern_to_entity_type(self, pattern_name: str) -> str:
        """Map pattern names to entity types."""
        mapping = {
            "invoice_number": "DOCUMENT_NUMBER",
            "contract_number": "DOCUMENT_NUMBER",
            "po_number": "DOCUMENT_NUMBER",
            "due_date": "DATE",
            "total_amount": "MONEY"
        }
        return mapping.get(pattern_name, "MISCELLANEOUS")
    
    # Validation functions
    async def _validate_person(self, text: str) -> bool:
        """Validate person name."""
        try:
            # Basic validation - should contain at least 2 words with proper capitalization
            words = text.split()
            return len(words) >= 2 and all(word[0].isupper() for word in words if word)
        except Exception:
            return False
    
    async def _validate_organization(self, text: str) -> bool:
        """Validate organization name."""
        try:
            # Should contain organization indicators or be properly capitalized
            org_indicators = ["inc", "corp", "llc", "ltd", "co", "company", "corporation"]
            return any(indicator in text.lower() for indicator in org_indicators) or text[0].isupper()
        except Exception:
            return False
    
    async def _validate_date(self, text: str) -> bool:
        """Validate date format."""
        try:
            date_parser.parse(text)
            return True
        except Exception:
            return False
    
    async def _validate_money(self, text: str) -> bool:
        """Validate monetary amount."""
        try:
            # Remove currency symbols and validate numeric part
            cleaned = re.sub(r'[^\d\.\,]', '', text)
            float(cleaned.replace(',', ''))
            return True
        except Exception:
            return False
    
    async def _validate_email(self, text: str) -> bool:
        """Validate email address."""
        try:
            validate_email(text)
            return True
        except (EmailNotValidError, Exception):
            return False
    
    async def _validate_phone(self, text: str) -> bool:
        """Validate phone number."""
        try:
            # Basic phone number validation
            cleaned = re.sub(r'[^\d]', '', text)
            return len(cleaned) >= 10
        except Exception:
            return False
    
    async def _validate_address(self, text: str) -> bool:
        """Validate address format."""
        try:
            # Basic address validation - should contain number and street indicators
            return re.search(r'\d+.*(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln)', text, re.IGNORECASE) is not None
        except Exception:
            return False
    
    async def _validate_ssn(self, text: str) -> bool:
        """Validate Social Security Number."""
        try:
            # Basic SSN format validation
            cleaned = re.sub(r'[^\d]', '', text)
            return len(cleaned) == 9
        except Exception:
            return False
    
    async def _validate_account_number(self, text: str) -> bool:
        """Validate account number."""
        try:
            # Should be alphanumeric with reasonable length
            cleaned = re.sub(r'[^\w]', '', text)
            return 6 <= len(cleaned) <= 20
        except Exception:
            return False
    
    async def _validate_tax_id(self, text: str) -> bool:
        """Validate tax ID."""
        try:
            # Basic tax ID validation (EIN or SSN format)
            cleaned = re.sub(r'[^\d]', '', text)
            return len(cleaned) == 9
        except Exception:
            return False
    
    async def _update_stats(self, entities: Dict[str, List], processing_time: float):
        """Update extraction statistics."""
        try:
            self.stats["total_extractions"] += 1
            self.stats["processing_times"].append(processing_time)
            self.stats["last_updated"] = datetime.utcnow().isoformat()
            
            # Update entity counts
            for entity_type, entity_list in entities.get("entities", {}).items():
                if entity_type not in self.stats["entity_counts"]:
                    self.stats["entity_counts"][entity_type] = 0
                self.stats["entity_counts"][entity_type] += len(entity_list)
            
            # Keep only last 1000 processing times
            if len(self.stats["processing_times"]) > 1000:
                self.stats["processing_times"] = self.stats["processing_times"][-1000:]
                
        except Exception as e:
            logger.warning(f"Failed to update stats: {str(e)}")
    
    async def get_extraction_stats(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        try:
            avg_processing_time = np.mean(self.stats["processing_times"]) if self.stats["processing_times"] else 0
            
            return {
                "total_extractions": self.stats["total_extractions"],
                "entity_counts": self.stats["entity_counts"],
                "average_processing_time": avg_processing_time,
                "supported_entity_types": list(self.entity_types.keys()),
                "last_updated": self.stats["last_updated"],
                "model_info": {
                    "spacy_available": self.nlp is not None,
                    "transformer_available": self.ner_pipeline is not None,
                    "custom_models": list(self.custom_models.keys())
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get extraction stats: {str(e)}")
            return {"error": str(e)}