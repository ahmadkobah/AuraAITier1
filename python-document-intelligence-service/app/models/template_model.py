"""
Template Matching Model
======================

Advanced document template matching and management system for identifying
document types based on layout, structure, and content patterns.

Features:
- Template creation and management
- Structural similarity matching
- Content-based template matching
- Layout analysis and comparison
- Template versioning and updates
- Confidence scoring for matches
"""

import asyncio
import logging
import json
import pickle
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import os
import hashlib

# Text processing
import re
from difflib import SequenceMatcher
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
import textdistance

# Image processing (for layout analysis)
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

logger = logging.getLogger(__name__)

class TemplateMatchingModel:
    """
    Advanced template matching model for document classification and analysis.
    """
    
    def __init__(self, model_dir: str = "trained_models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        
        # Template storage
        self.templates = {}
        self.template_metadata = {}
        
        # Matching algorithms
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 3),
            min_df=1,
            max_df=0.95
        )
        
        # Template categories
        self.template_categories = {
            "invoice": {
                "description": "Invoice and billing documents",
                "required_fields": ["invoice_number", "amount", "date"],
                "structural_patterns": [
                    "header_company_info",
                    "bill_to_section",
                    "line_items_table",
                    "total_section"
                ]
            },
            "contract": {
                "description": "Legal contracts and agreements",
                "required_fields": ["parties", "terms", "signatures"],
                "structural_patterns": [
                    "title_section",
                    "parties_section",
                    "terms_conditions",
                    "signature_section"
                ]
            },
            "receipt": {
                "description": "Purchase receipts and transaction records",
                "required_fields": ["transaction_id", "amount", "date"],
                "structural_patterns": [
                    "merchant_info",
                    "transaction_details",
                    "payment_method",
                    "total_amount"
                ]
            },
            "letter": {
                "description": "Business and personal letters",
                "required_fields": ["recipient", "sender", "date"],
                "structural_patterns": [
                    "letterhead",
                    "date_line",
                    "recipient_address",
                    "salutation",
                    "body",
                    "closing"
                ]
            },
            "form": {
                "description": "Application forms and surveys",
                "required_fields": ["form_title", "fields", "instructions"],
                "structural_patterns": [
                    "form_header",
                    "instruction_section",
                    "input_fields",
                    "submission_section"
                ]
            }
        }
        
        # Matching configuration
        self.config = {
            "similarity_threshold": 0.85,
            "content_weight": 0.4,
            "structure_weight": 0.3,
            "layout_weight": 0.2,
            "metadata_weight": 0.1,
            "min_template_length": 100,
            "max_templates_per_category": 50
        }
        
        # Performance tracking
        self.stats = {
            "total_matches": 0,
            "successful_matches": 0,
            "average_similarity": 0.0,
            "template_usage": {},
            "last_updated": None
        }
    
    async def initialize(self):
        """Initialize the template matching model."""
        try:
            logger.info("Initializing Template Matching Model...")
            
            # Load existing templates
            await self._load_templates()
            
            # Initialize default templates if none exist
            if not self.templates:
                await self._create_default_templates()
            
            logger.info(f"Template Matching Model initialized with {len(self.templates)} templates")
            
        except Exception as e:
            logger.error(f"Failed to initialize template matching model: {str(e)}")
            raise
    
    async def _load_templates(self):
        """Load templates from disk."""
        try:
            templates_path = self.model_dir / "templates.pkl"
            if templates_path.exists():
                with open(templates_path, 'rb') as f:
                    data = pickle.load(f)
                    self.templates = data.get('templates', {})
                    self.template_metadata = data.get('metadata', {})
                    self.stats = data.get('stats', self.stats)
                
                logger.info(f"Loaded {len(self.templates)} templates from disk")
            
        except Exception as e:
            logger.warning(f"Failed to load templates: {str(e)}")
    
    async def _create_default_templates(self):
        """Create default templates for common document types."""
        try:
            default_templates = {
                "invoice_standard": {
                    "category": "invoice",
                    "name": "Standard Invoice Template",
                    "description": "Common invoice layout with header, line items, and total",
                    "content_patterns": [
                        r"invoice\s*#?\s*\d+",
                        r"bill\s+to\s*:",
                        r"amount\s*due",
                        r"total\s*:\s*\$",
                        r"due\s+date"
                    ],
                    "structural_features": {
                        "has_header": True,
                        "has_table": True,
                        "has_total_section": True,
                        "sections": ["header", "billing_info", "line_items", "total"]
                    },
                    "layout_features": {
                        "text_density": 0.6,
                        "table_presence": True,
                        "header_position": "top"
                    }
                },
                "contract_basic": {
                    "category": "contract",
                    "name": "Basic Contract Template",
                    "description": "Standard contract with parties, terms, and signatures",
                    "content_patterns": [
                        r"this\s+agreement",
                        r"party\s+of\s+the\s+first\s+part",
                        r"terms\s+and\s+conditions",
                        r"signature\s*:",
                        r"effective\s+date"
                    ],
                    "structural_features": {
                        "has_title": True,
                        "has_parties": True,
                        "has_terms": True,
                        "has_signatures": True,
                        "sections": ["title", "parties", "recitals", "terms", "signatures"]
                    },
                    "layout_features": {
                        "text_density": 0.8,
                        "paragraph_structure": True,
                        "signature_lines": True
                    }
                },
                "receipt_retail": {
                    "category": "receipt",
                    "name": "Retail Receipt Template",
                    "description": "Standard retail receipt format",
                    "content_patterns": [
                        r"receipt\s*#?\s*\d+",
                        r"transaction\s+id",
                        r"thank\s+you",
                        r"subtotal\s*:",
                        r"tax\s*:"
                    ],
                    "structural_features": {
                        "has_merchant_info": True,
                        "has_items": True,
                        "has_payment_info": True,
                        "sections": ["merchant", "items", "payment", "footer"]
                    },
                    "layout_features": {
                        "text_density": 0.5,
                        "centered_text": True,
                        "narrow_format": True
                    }
                },
                "letter_business": {
                    "category": "letter",
                    "name": "Business Letter Template",
                    "description": "Formal business letter format",
                    "content_patterns": [
                        r"dear\s+(?:mr|mrs|ms|dr)\.?\s+\w+",
                        r"sincerely\s*,?",
                        r"yours\s+truly",
                        r"best\s+regards",
                        r"letterhead"
                    ],
                    "structural_features": {
                        "has_letterhead": True,
                        "has_date": True,
                        "has_address": True,
                        "has_salutation": True,
                        "has_body": True,
                        "has_closing": True,
                        "sections": ["letterhead", "date", "address", "salutation", "body", "closing"]
                    },
                    "layout_features": {
                        "text_density": 0.7,
                        "formal_spacing": True,
                        "aligned_text": True
                    }
                }
            }
            
            for template_id, template_data in default_templates.items():
                await self.add_template(template_id, template_data)
            
            logger.info(f"Created {len(default_templates)} default templates")
            
        except Exception as e:
            logger.error(f"Failed to create default templates: {str(e)}")
    
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
        start_time = datetime.utcnow()
        
        try:
            logger.info("Starting template matching...")
            
            # Determine which templates to match against
            target_templates = template_ids or list(self.templates.keys())
            threshold = similarity_threshold or self.config["similarity_threshold"]
            
            # Prepare document features
            doc_features = await self._extract_document_features(content, metadata)
            
            # Match against each template
            match_results = []
            
            for template_id in target_templates:
                if template_id not in self.templates:
                    continue
                
                template = self.templates[template_id]
                similarity_score = await self._calculate_template_similarity(
                    doc_features, template
                )
                
                if similarity_score >= threshold:
                    match_results.append({
                        "template_id": template_id,
                        "template_name": template.get("name", template_id),
                        "category": template.get("category", "unknown"),
                        "similarity": similarity_score,
                        "confidence": self._calculate_match_confidence(similarity_score, template),
                        "matched_features": self._get_matched_features(doc_features, template)
                    })
            
            # Sort by similarity score
            match_results.sort(key=lambda x: x["similarity"], reverse=True)
            
            # Determine best match
            best_match = match_results[0] if match_results else None
            
            # Calculate all similarity scores for reference
            all_similarities = {}
            for template_id in self.templates.keys():
                if template_id in target_templates:
                    template = self.templates[template_id]
                    similarity = await self._calculate_template_similarity(doc_features, template)
                    all_similarities[template_id] = similarity
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Update statistics
            await self._update_match_stats(match_results, processing_time)
            
            result = {
                "matched_templates": match_results,
                "best_match": best_match,
                "similarity_scores": all_similarities,
                "processing_time": processing_time,
                "document_features": doc_features,
                "matching_metadata": {
                    "threshold_used": threshold,
                    "templates_checked": len(target_templates),
                    "matches_found": len(match_results)
                }
            }
            
            logger.info(f"Template matching completed in {processing_time:.2f} seconds")
            logger.info(f"Found {len(match_results)} matching templates")
            
            return result
            
        except Exception as e:
            logger.error(f"Template matching error: {str(e)}")
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            return {
                "matched_templates": [],
                "best_match": None,
                "similarity_scores": {},
                "processing_time": processing_time,
                "error": str(e)
            }
    
    async def _extract_document_features(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract features from document for template matching."""
        try:
            features = {
                "content_length": len(content),
                "word_count": len(content.split()),
                "line_count": len(content.split('\n')),
                "metadata": metadata or {}
            }
            
            # Content patterns
            features["content_patterns"] = await self._extract_content_patterns(content)
            
            # Structural features
            features["structural_features"] = await self._extract_structural_features(content)
            
            # Layout features (basic text-based analysis)
            features["layout_features"] = await self._extract_layout_features(content)
            
            # Statistical features
            features["statistical_features"] = await self._extract_statistical_features(content)
            
            return features
            
        except Exception as e:
            logger.error(f"Feature extraction error: {str(e)}")
            return {"error": str(e)}
    
    async def _extract_content_patterns(self, content: str) -> List[str]:
        """Extract content patterns from document."""
        try:
            patterns = []
            
            # Common document patterns
            pattern_checks = [
                (r"invoice\s*#?\s*\d+", "invoice_number"),
                (r"contract\s*#?\s*\d+", "contract_number"),
                (r"receipt\s*#?\s*\d+", "receipt_number"),
                (r"dear\s+\w+", "salutation"),
                (r"sincerely\s*,?", "closing"),
                (r"total\s*:\s*\$", "total_amount"),
                (r"due\s+date", "due_date"),
                (r"bill\s+to", "billing_address"),
                (r"signature\s*:", "signature_line"),
                (r"terms\s+and\s+conditions", "terms"),
                (r"\$\d+\.?\d*", "currency_amount"),
                (r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", "date_format"),
                (r"@\w+\.\w+", "email_address"),
                (r"\(\d{3}\)\s*\d{3}-\d{4}", "phone_number")
            ]
            
            for pattern, pattern_name in pattern_checks:
                if re.search(pattern, content, re.IGNORECASE):
                    patterns.append(pattern_name)
            
            return patterns
            
        except Exception as e:
            logger.warning(f"Content pattern extraction error: {str(e)}")
            return []
    
    async def _extract_structural_features(self, content: str) -> Dict[str, Any]:
        """Extract structural features from document."""
        try:
            lines = content.split('\n')
            non_empty_lines = [line.strip() for line in lines if line.strip()]
            
            features = {
                "total_lines": len(lines),
                "non_empty_lines": len(non_empty_lines),
                "empty_line_ratio": (len(lines) - len(non_empty_lines)) / max(len(lines), 1),
                "has_tables": self._detect_tables(content),
                "has_headers": self._detect_headers(content),
                "has_signatures": self._detect_signatures(content),
                "paragraph_count": len(content.split('\n\n')),
                "section_count": len(re.findall(r'\n\s*[A-Z][A-Z\s]{2,}:?\s*\n', content))
            }
            
            return features
            
        except Exception as e:
            logger.warning(f"Structural feature extraction error: {str(e)}")
            return {}
    
    async def _extract_layout_features(self, content: str) -> Dict[str, Any]:
        """Extract layout-related features from text."""
        try:
            lines = content.split('\n')
            non_empty_lines = [line for line in lines if line.strip()]
            
            # Calculate text density
            total_chars = len(content)
            text_chars = len(content.replace(' ', '').replace('\n', '').replace('\t', ''))
            text_density = text_chars / max(total_chars, 1)
            
            # Calculate line characteristics
            line_lengths = [len(line) for line in non_empty_lines]
            avg_line_length = np.mean(line_lengths) if line_lengths else 0
            line_length_variance = np.var(line_lengths) if line_lengths else 0
            
            # Detect alignment patterns
            left_aligned = sum(1 for line in non_empty_lines if line.startswith(' ') == False)
            indented = sum(1 for line in non_empty_lines if line.startswith(' '))
            
            features = {
                "text_density": text_density,
                "average_line_length": avg_line_length,
                "line_length_variance": line_length_variance,
                "left_aligned_ratio": left_aligned / max(len(non_empty_lines), 1),
                "indented_ratio": indented / max(len(non_empty_lines), 1),
                "has_centered_text": self._detect_centered_text(lines),
                "has_justified_text": self._detect_justified_text(lines)
            }
            
            return features
            
        except Exception as e:
            logger.warning(f"Layout feature extraction error: {str(e)}")
            return {}
    
    async def _extract_statistical_features(self, content: str) -> Dict[str, Any]:
        """Extract statistical features from document text."""
        try:
            words = content.split()
            sentences = re.split(r'[.!?]+', content)
            
            # Word statistics
            word_lengths = [len(word) for word in words]
            avg_word_length = np.mean(word_lengths) if word_lengths else 0
            
            # Sentence statistics
            sentence_lengths = [len(sentence.split()) for sentence in sentences if sentence.strip()]
            avg_sentence_length = np.mean(sentence_lengths) if sentence_lengths else 0
            
            # Character statistics
            uppercase_count = sum(1 for char in content if char.isupper())
            lowercase_count = sum(1 for char in content if char.islower())
            digit_count = sum(1 for char in content if char.isdigit())
            punctuation_count = sum(1 for char in content if not char.isalnum() and not char.isspace())
            
            features = {
                "word_count": len(words),
                "sentence_count": len(sentence_lengths),
                "average_word_length": avg_word_length,
                "average_sentence_length": avg_sentence_length,
                "uppercase_ratio": uppercase_count / max(len(content), 1),
                "lowercase_ratio": lowercase_count / max(len(content), 1),
                "digit_ratio": digit_count / max(len(content), 1),
                "punctuation_ratio": punctuation_count / max(len(content), 1)
            }
            
            return features
            
        except Exception as e:
            logger.warning(f"Statistical feature extraction error: {str(e)}")
            return {}
    
    def _detect_tables(self, content: str) -> bool:
        """Detect if content contains table-like structures."""
        try:
            # Look for table indicators
            table_indicators = [
                r'\|.*\|.*\|',  # Pipe-separated
                r'\t.*\t.*\t',  # Tab-separated
                r'^\s*\w+\s+\w+\s+\w+\s*$',  # Multi-column alignment
            ]
            
            return any(re.search(pattern, content, re.MULTILINE) for pattern in table_indicators)
            
        except Exception:
            return False
    
    def _detect_headers(self, content: str) -> bool:
        """Detect if content has header-like structures."""
        try:
            # Look for header patterns
            header_patterns = [
                r'^[A-Z][A-Z\s]{10,}$',  # ALL CAPS headers
                r'^\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s*$',  # Title Case headers
                r'===+|---+|\*\*\*+',  # Underlined headers
            ]
            
            lines = content.split('\n')
            for line in lines[:5]:  # Check first few lines
                if any(re.search(pattern, line) for pattern in header_patterns):
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _detect_signatures(self, content: str) -> bool:
        """Detect signature-related content."""
        try:
            signature_patterns = [
                r'signature\s*:',
                r'signed\s*:',
                r'date\s*signed',
                r'print\s+name',
                r'__+\s*date',
                r'__+\s*signature'
            ]
            
            return any(re.search(pattern, content, re.IGNORECASE) for pattern in signature_patterns)
            
        except Exception:
            return False
    
    def _detect_centered_text(self, lines: List[str]) -> bool:
        """Detect if text appears to be centered."""
        try:
            centered_count = 0
            for line in lines:
                if line.strip():
                    # Simple heuristic: line starts and ends with significant whitespace
                    leading_spaces = len(line) - len(line.lstrip())
                    trailing_spaces = len(line) - len(line.rstrip())
                    if leading_spaces > 5 and trailing_spaces > 5:
                        centered_count += 1
            
            return centered_count > len([l for l in lines if l.strip()]) * 0.3
            
        except Exception:
            return False
    
    def _detect_justified_text(self, lines: List[str]) -> bool:
        """Detect if text appears to be justified."""
        try:
            # Simple heuristic: most lines have similar lengths
            line_lengths = [len(line.rstrip()) for line in lines if line.strip()]
            if len(line_lengths) < 3:
                return False
            
            avg_length = np.mean(line_lengths)
            length_variance = np.var(line_lengths)
            
            # Low variance suggests justified text
            return length_variance < avg_length * 0.1
            
        except Exception:
            return False
    
    async def _calculate_template_similarity(
        self,
        doc_features: Dict[str, Any],
        template: Dict[str, Any]
    ) -> float:
        """Calculate similarity between document features and template."""
        try:
            similarity_scores = []
            weights = []
            
            # Content pattern similarity
            content_sim = self._calculate_content_similarity(doc_features, template)
            similarity_scores.append(content_sim)
            weights.append(self.config["content_weight"])
            
            # Structural similarity
            structure_sim = self._calculate_structural_similarity(doc_features, template)
            similarity_scores.append(structure_sim)
            weights.append(self.config["structure_weight"])
            
            # Layout similarity
            layout_sim = self._calculate_layout_similarity(doc_features, template)
            similarity_scores.append(layout_sim)
            weights.append(self.config["layout_weight"])
            
            # Metadata similarity
            metadata_sim = self._calculate_metadata_similarity(doc_features, template)
            similarity_scores.append(metadata_sim)
            weights.append(self.config["metadata_weight"])
            
            # Weighted average
            total_weight = sum(weights)
            if total_weight > 0:
                weighted_similarity = sum(
                    score * weight for score, weight in zip(similarity_scores, weights)
                ) / total_weight
            else:
                weighted_similarity = 0.0
            
            return weighted_similarity
            
        except Exception as e:
            logger.error(f"Similarity calculation error: {str(e)}")
            return 0.0
    
    def _calculate_content_similarity(self, doc_features: Dict[str, Any], template: Dict[str, Any]) -> float:
        """Calculate content-based similarity."""
        try:
            doc_patterns = set(doc_features.get("content_patterns", []))
            template_patterns = set(template.get("content_patterns", []))
            
            if not template_patterns:
                return 0.5  # Neutral score if no template patterns
            
            # Jaccard similarity
            intersection = len(doc_patterns.intersection(template_patterns))
            union = len(doc_patterns.union(template_patterns))
            
            if union == 0:
                return 0.0
            
            return intersection / union
            
        except Exception:
            return 0.0
    
    def _calculate_structural_similarity(self, doc_features: Dict[str, Any], template: Dict[str, Any]) -> float:
        """Calculate structural similarity."""
        try:
            doc_structure = doc_features.get("structural_features", {})
            template_structure = template.get("structural_features", {})
            
            similarities = []
            
            # Compare boolean features
            bool_features = ["has_tables", "has_headers", "has_signatures"]
            for feature in bool_features:
                doc_val = doc_structure.get(feature, False)
                template_val = template_structure.get(feature, False)
                similarities.append(1.0 if doc_val == template_val else 0.0)
            
            # Compare numeric features
            numeric_features = ["paragraph_count", "section_count"]
            for feature in numeric_features:
                doc_val = doc_structure.get(feature, 0)
                template_val = template_structure.get(feature, 0)
                
                if template_val == 0:
                    similarities.append(1.0 if doc_val == 0 else 0.5)
                else:
                    # Normalized difference
                    diff = abs(doc_val - template_val) / max(template_val, 1)
                    similarity = max(0, 1 - diff)
                    similarities.append(similarity)
            
            return np.mean(similarities) if similarities else 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_layout_similarity(self, doc_features: Dict[str, Any], template: Dict[str, Any]) -> float:
        """Calculate layout-based similarity."""
        try:
            doc_layout = doc_features.get("layout_features", {})
            template_layout = template.get("layout_features", {})
            
            similarities = []
            
            # Compare numeric layout features
            numeric_features = ["text_density", "average_line_length"]
            for feature in numeric_features:
                doc_val = doc_layout.get(feature, 0)
                template_val = template_layout.get(feature, 0)
                
                if template_val == 0:
                    similarities.append(1.0 if doc_val == 0 else 0.5)
                else:
                    # Normalized difference
                    diff = abs(doc_val - template_val) / max(template_val, 1)
                    similarity = max(0, 1 - diff)
                    similarities.append(similarity)
            
            # Compare boolean layout features
            bool_features = ["has_centered_text", "has_justified_text"]
            for feature in bool_features:
                doc_val = doc_layout.get(feature, False)
                template_val = template_layout.get(feature, False)
                similarities.append(1.0 if doc_val == template_val else 0.0)
            
            return np.mean(similarities) if similarities else 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_metadata_similarity(self, doc_features: Dict[str, Any], template: Dict[str, Any]) -> float:
        """Calculate metadata-based similarity."""
        try:
            doc_metadata = doc_features.get("metadata", {})
            template_metadata = template.get("metadata", {})
            
            if not template_metadata:
                return 1.0  # No metadata requirements
            
            similarities = []
            for key, template_value in template_metadata.items():
                doc_value = doc_metadata.get(key)
                if doc_value is not None:
                    if isinstance(template_value, str) and isinstance(doc_value, str):
                        # String similarity
                        similarities.append(SequenceMatcher(None, doc_value, template_value).ratio())
                    elif doc_value == template_value:
                        similarities.append(1.0)
                    else:
                        similarities.append(0.0)
                else:
                    similarities.append(0.0)
            
            return np.mean(similarities) if similarities else 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_match_confidence(self, similarity: float, template: Dict[str, Any]) -> float:
        """Calculate confidence score for template match."""
        try:
            # Base confidence from similarity
            confidence = similarity
            
            # Boost confidence for well-defined templates
            if len(template.get("content_patterns", [])) > 3:
                confidence *= 1.1
            
            if template.get("structural_features", {}).get("sections"):
                confidence *= 1.05
            
            # Normalize to [0, 1]
            return min(confidence, 1.0)
            
        except Exception:
            return similarity
    
    def _get_matched_features(self, doc_features: Dict[str, Any], template: Dict[str, Any]) -> List[str]:
        """Get list of features that matched between document and template."""
        try:
            matched = []
            
            # Content pattern matches
            doc_patterns = set(doc_features.get("content_patterns", []))
            template_patterns = set(template.get("content_patterns", []))
            pattern_matches = doc_patterns.intersection(template_patterns)
            matched.extend([f"content_pattern:{p}" for p in pattern_matches])
            
            # Structural feature matches
            doc_structure = doc_features.get("structural_features", {})
            template_structure = template.get("structural_features", {})
            
            for feature in ["has_tables", "has_headers", "has_signatures"]:
                if (doc_structure.get(feature, False) == 
                    template_structure.get(feature, False) and 
                    template_structure.get(feature, False)):
                    matched.append(f"structural:{feature}")
            
            return matched
            
        except Exception:
            return []
    
    async def add_template(self, template_id: str, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new template to the system."""
        try:
            # Validate template data
            required_fields = ["category", "name", "description"]
            for field in required_fields:
                if field not in template_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Add metadata
            template_data["created_at"] = datetime.utcnow().isoformat()
            template_data["updated_at"] = datetime.utcnow().isoformat()
            template_data["version"] = "1.0.0"
            template_data["usage_count"] = 0
            
            # Store template
            self.templates[template_id] = template_data
            self.template_metadata[template_id] = {
                "created_at": template_data["created_at"],
                "last_used": None,
                "match_count": 0,
                "average_similarity": 0.0
            }
            
            # Save to disk
            await self._save_templates()
            
            logger.info(f"Added template: {template_id}")
            
            return {
                "status": "success",
                "template_id": template_id,
                "message": "Template added successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to add template {template_id}: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _save_templates(self):
        """Save templates to disk."""
        try:
            data = {
                "templates": self.templates,
                "metadata": self.template_metadata,
                "stats": self.stats,
                "config": self.config
            }
            
            templates_path = self.model_dir / "templates.pkl"
            with open(templates_path, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"Saved {len(self.templates)} templates to disk")
            
        except Exception as e:
            logger.error(f"Failed to save templates: {str(e)}")
    
    async def _update_match_stats(self, match_results: List[Dict[str, Any]], processing_time: float):
        """Update matching statistics."""
        try:
            self.stats["total_matches"] += 1
            if match_results:
                self.stats["successful_matches"] += 1
                
                # Update average similarity
                avg_sim = np.mean([result["similarity"] for result in match_results])
                current_avg = self.stats["average_similarity"]
                total_matches = self.stats["total_matches"]
                
                self.stats["average_similarity"] = (
                    (current_avg * (total_matches - 1) + avg_sim) / total_matches
                )
                
                # Update template usage
                for result in match_results:
                    template_id = result["template_id"]
                    if template_id not in self.stats["template_usage"]:
                        self.stats["template_usage"][template_id] = 0
                    self.stats["template_usage"][template_id] += 1
                    
                    # Update template metadata
                    if template_id in self.template_metadata:
                        meta = self.template_metadata[template_id]
                        meta["last_used"] = datetime.utcnow().isoformat()
                        meta["match_count"] += 1
                        
                        # Update average similarity for this template
                        current_sim = meta["average_similarity"]
                        match_count = meta["match_count"]
                        new_sim = result["similarity"]
                        
                        meta["average_similarity"] = (
                            (current_sim * (match_count - 1) + new_sim) / match_count
                        )
            
            self.stats["last_updated"] = datetime.utcnow().isoformat()
            
        except Exception as e:
            logger.warning(f"Failed to update match stats: {str(e)}")
    
    async def get_template_info(self) -> Dict[str, Any]:
        """Get information about available templates."""
        try:
            template_info = {}
            
            for template_id, template in self.templates.items():
                metadata = self.template_metadata.get(template_id, {})
                
                template_info[template_id] = {
                    "name": template.get("name", template_id),
                    "category": template.get("category", "unknown"),
                    "description": template.get("description", ""),
                    "created_at": template.get("created_at"),
                    "usage_count": metadata.get("match_count", 0),
                    "average_similarity": metadata.get("average_similarity", 0.0),
                    "last_used": metadata.get("last_used")
                }
            
            return {
                "templates": template_info,
                "total_templates": len(self.templates),
                "categories": list(self.template_categories.keys()),
                "stats": self.stats,
                "config": self.config
            }
            
        except Exception as e:
            logger.error(f"Failed to get template info: {str(e)}")
            return {"error": str(e)}