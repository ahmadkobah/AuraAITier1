"""
Document Classification Model
============================

Advanced ML-based document classification using multiple algorithms including
transformer models, traditional ML, and ensemble methods.

Features:
- Multi-class document classification
- Confidence scoring and uncertainty estimation
- Transfer learning with pre-trained transformers
- Custom document type definitions
- Real-time and batch classification
- Model performance monitoring
"""

import asyncio
import logging
import json
import pickle
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import os
from pathlib import Path

# ML Libraries
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import LabelEncoder
import joblib

# Deep Learning
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from transformers import pipeline
import torch

# Text Processing
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.stem import WordNetLemmatizer

# Download required NLTK data on import
def ensure_nltk_data():
    """Ensure required NLTK data is available"""
    try:
        # Test if stopwords are available
        stopwords.words('english')
    except LookupError:
        nltk.download('stopwords')
    
    try:
        # Test if punkt tokenizer is available
        word_tokenize("test")
    except LookupError:
        nltk.download('punkt')
    
    try:
        # Test if wordnet is available
        from nltk.corpus import wordnet
        list(wordnet.synsets('test'))
    except LookupError:
        nltk.download('wordnet')

# Ensure NLTK data is available when module is imported
ensure_nltk_data()
import spacy
import re

logger = logging.getLogger(__name__)

class DocumentClassificationModel:
    """
    Advanced document classification model with multiple ML approaches.
    """
    
    def __init__(self, model_dir: str = "trained_models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        
        # Model components
        self.vectorizer = None
        self.label_encoder = None
        self.traditional_models = {}
        self.transformer_model = None
        self.transformer_tokenizer = None
        self.classifier_pipeline = None
        
        # Text processing
        self.nlp = None
        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(stopwords.words('english'))
        
        # Model configuration
        self.config = {
            "max_features": 10000,
            "ngram_range": (1, 3),
            "min_df": 2,
            "max_df": 0.95,
            "transformer_model": "microsoft/DialoGPT-medium",
            "max_length": 512,
            "confidence_threshold": 0.8,
            "ensemble_weights": {
                "transformer": 0.5,
                "random_forest": 0.2,
                "gradient_boosting": 0.15,
                "logistic_regression": 0.1,
                "svm": 0.05
            }
        }
        
        # Document type mappings
        self.document_types = {
            "invoice": {
                "keywords": ["invoice", "bill", "payment", "due", "amount", "total"],
                "patterns": [r"invoice\s*#?\s*\d+", r"due\s+date", r"amount\s+due"],
                "sub_categories": ["sales_invoice", "service_invoice", "proforma_invoice"]
            },
            "contract": {
                "keywords": ["agreement", "contract", "terms", "conditions", "party"],
                "patterns": [r"this\s+agreement", r"terms\s+and\s+conditions", r"effective\s+date"],
                "sub_categories": ["service_contract", "employment_contract", "vendor_contract"]
            },
            "receipt": {
                "keywords": ["receipt", "purchase", "transaction", "paid", "received"],
                "patterns": [r"receipt\s*#?\s*\d+", r"transaction\s+id", r"paid\s+on"],
                "sub_categories": ["sales_receipt", "payment_receipt", "expense_receipt"]
            },
            "letter": {
                "keywords": ["dear", "sincerely", "regards", "yours", "letter"],
                "patterns": [r"dear\s+\w+", r"sincerely\s*,", r"best\s+regards"],
                "sub_categories": ["business_letter", "personal_letter", "formal_letter"]
            },
            "report": {
                "keywords": ["report", "analysis", "summary", "findings", "conclusion"],
                "patterns": [r"executive\s+summary", r"table\s+of\s+contents", r"conclusions?"],
                "sub_categories": ["financial_report", "technical_report", "status_report"]
            },
            "form": {
                "keywords": ["form", "application", "submit", "complete", "field"],
                "patterns": [r"please\s+complete", r"form\s+\d+", r"signature\s+required"],
                "sub_categories": ["application_form", "registration_form", "survey_form"]
            },
            "email": {
                "keywords": ["from", "to", "subject", "sent", "email"],
                "patterns": [r"from:\s+.+@.+", r"to:\s+.+@.+", r"subject:"],
                "sub_categories": ["business_email", "notification_email", "marketing_email"]
            },
            "memo": {
                "keywords": ["memo", "memorandum", "notice", "announcement", "urgent"],
                "patterns": [r"memorandum", r"to:\s+all", r"urgent\s+notice"],
                "sub_categories": ["internal_memo", "policy_memo", "announcement_memo"]
            }
        }
        
        # Performance metrics
        self.metrics = {
            "accuracy": 0.0,
            "precision": {},
            "recall": {},
            "f1_score": {},
            "confusion_matrix": None,
            "last_trained": None,
            "model_version": "1.0.0"
        }
    
    async def initialize(self):
        """Initialize the classification model and load pre-trained components."""
        try:
            logger.info("Initializing Document Classification Model...")
            
            # Initialize spaCy
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy model not found, using basic processing")
                self.nlp = None
            
            # Load pre-trained models if available
            await self._load_trained_models()
            
            # Initialize transformer model
            await self._initialize_transformer()
            
            logger.info("Document Classification Model initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize classification model: {str(e)}")
            raise
    
    async def _initialize_transformer(self):
        """Initialize transformer-based classification model."""
        try:
            # Use a lightweight pre-trained model for document classification
            model_name = "microsoft/DialoGPT-medium"  # Replace with document classification model
            
            # For now, we'll use a general classification pipeline
            # In production, you'd use a model specifically trained for document classification
            self.classifier_pipeline = pipeline(
                "text-classification",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                return_all_scores=True
            )
            
            logger.info("Transformer model initialized")
            
        except Exception as e:
            logger.warning(f"Failed to initialize transformer model: {str(e)}")
            self.classifier_pipeline = None
    
    async def _load_trained_models(self):
        """Load pre-trained models from disk."""
        try:
            model_path = self.model_dir / "classification_models.pkl"
            if model_path.exists():
                with open(model_path, 'rb') as f:
                    saved_data = pickle.load(f)
                
                self.vectorizer = saved_data.get('vectorizer')
                self.label_encoder = saved_data.get('label_encoder')
                self.traditional_models = saved_data.get('traditional_models', {})
                self.metrics = saved_data.get('metrics', self.metrics)
                
                logger.info("Pre-trained models loaded successfully")
            else:
                logger.info("No pre-trained models found, will use rule-based classification")
                
        except Exception as e:
            logger.warning(f"Failed to load pre-trained models: {str(e)}")
    
    async def classify_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        confidence_threshold: float = 0.8,
        return_all: bool = False
    ) -> Dict[str, Any]:
        """
        Classify document content into predefined categories.
        
        Args:
            content: Document text content
            metadata: Additional document metadata
            confidence_threshold: Minimum confidence for classification
            return_all: Return all predictions or just the top one
            
        Returns:
            Classification result with confidence scores
        """
        start_time = datetime.utcnow()
        
        try:
            # Preprocess content
            processed_content = await self._preprocess_text(content)
            
            # Get predictions from different models
            predictions = {}
            
            # Rule-based classification (always available)
            rule_based_result = await self._rule_based_classification(content, processed_content)
            predictions['rule_based'] = rule_based_result
            
            # Traditional ML classification (if models are trained)
            if self.vectorizer and self.traditional_models:
                ml_result = await self._ml_classification(processed_content)
                predictions['traditional_ml'] = ml_result
            
            # Transformer-based classification (if available)
            if self.classifier_pipeline:
                transformer_result = await self._transformer_classification(content)
                predictions['transformer'] = transformer_result
            
            # Ensemble prediction
            final_result = await self._ensemble_prediction(predictions, return_all)
            
            # Add metadata
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            final_result.update({
                'processing_time': processing_time,
                'metadata': metadata or {},
                'content_length': len(content),
                'processing_timestamp': datetime.utcnow().isoformat()
            })
            
            logger.info(f"Document classified as {final_result.get('document_type')} with confidence {final_result.get('confidence'):.3f}")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Classification error: {str(e)}")
            # Return default classification on error
            return {
                'document_type': 'unknown',
                'confidence': 0.0,
                'sub_categories': [],
                'processing_time': (datetime.utcnow() - start_time).total_seconds(),
                'error': str(e)
            }
    
    async def _preprocess_text(self, text: str) -> str:
        """Preprocess text for classification."""
        try:
            # Basic cleaning
            text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
            text = re.sub(r'[^\w\s\-\.\,\:\;\!\?]', '', text)  # Remove special chars
            text = text.lower().strip()
            
            # Advanced preprocessing with spaCy if available
            if self.nlp:
                doc = self.nlp(text)
                # Extract meaningful tokens (exclude stop words, punctuation)
                tokens = [
                    token.lemma_ for token in doc
                    if not token.is_stop and not token.is_punct and len(token.text) > 2
                ]
                text = ' '.join(tokens)
            else:
                # Basic tokenization and lemmatization
                tokens = word_tokenize(text)
                tokens = [
                    self.lemmatizer.lemmatize(token) for token in tokens
                    if token not in self.stop_words and len(token) > 2
                ]
                text = ' '.join(tokens)
            
            return text
            
        except Exception as e:
            logger.warning(f"Text preprocessing error: {str(e)}")
            return text.lower().strip()
    
    async def _rule_based_classification(self, original_content: str, processed_content: str) -> Dict[str, Any]:
        """Rule-based document classification using keywords and patterns."""
        try:
            scores = {}
            pattern_matches = {}
            
            for doc_type, type_info in self.document_types.items():
                score = 0.0
                matches = []
                
                # Keyword matching
                keywords = type_info.get('keywords', [])
                for keyword in keywords:
                    if keyword in processed_content:
                        score += 1.0
                        matches.append(f"keyword: {keyword}")
                
                # Pattern matching
                patterns = type_info.get('patterns', [])
                for pattern in patterns:
                    if re.search(pattern, original_content, re.IGNORECASE):
                        score += 2.0  # Patterns get higher weight
                        matches.append(f"pattern: {pattern}")
                
                # Normalize score
                max_possible = len(keywords) + (len(patterns) * 2)
                if max_possible > 0:
                    score = score / max_possible
                
                scores[doc_type] = score
                pattern_matches[doc_type] = matches
            
            # Find best match
            best_type = max(scores.keys(), key=lambda k: scores[k])
            best_score = scores[best_type]
            
            # Determine sub-category
            sub_categories = self.document_types[best_type].get('sub_categories', [])
            
            return {
                'document_type': best_type,
                'confidence': best_score,
                'all_scores': scores,
                'matches': pattern_matches[best_type],
                'sub_categories': sub_categories
            }
            
        except Exception as e:
            logger.error(f"Rule-based classification error: {str(e)}")
            return {
                'document_type': 'unknown',
                'confidence': 0.0,
                'all_scores': {},
                'matches': [],
                'sub_categories': []
            }
    
    async def _ml_classification(self, processed_content: str) -> Dict[str, Any]:
        """Traditional ML-based classification."""
        try:
            if not self.vectorizer or not self.traditional_models:
                return {'error': 'Models not trained'}
            
            # Vectorize content
            features = self.vectorizer.transform([processed_content])
            
            # Get predictions from all models
            predictions = {}
            for model_name, model in self.traditional_models.items():
                try:
                    if hasattr(model, 'predict_proba'):
                        proba = model.predict_proba(features)[0]
                        classes = model.classes_
                        pred_dict = dict(zip(classes, proba))
                        predictions[model_name] = pred_dict
                    else:
                        pred = model.predict(features)[0]
                        predictions[model_name] = {pred: 1.0}
                except Exception as e:
                    logger.warning(f"Model {model_name} prediction failed: {str(e)}")
            
            return predictions
            
        except Exception as e:
            logger.error(f"ML classification error: {str(e)}")
            return {'error': str(e)}
    
    async def _transformer_classification(self, content: str) -> Dict[str, Any]:
        """Transformer-based classification."""
        try:
            if not self.classifier_pipeline:
                return {'error': 'Transformer model not available'}
            
            # Truncate content if too long
            max_length = self.config.get('max_length', 512)
            if len(content) > max_length:
                content = content[:max_length]
            
            # Get predictions
            results = self.classifier_pipeline(content)
            
            # Convert to our format
            predictions = {}
            for result in results:
                label = result['label']
                score = result['score']
                predictions[label] = score
            
            return predictions
            
        except Exception as e:
            logger.error(f"Transformer classification error: {str(e)}")
            return {'error': str(e)}
    
    async def _ensemble_prediction(self, predictions: Dict[str, Any], return_all: bool = False) -> Dict[str, Any]:
        """Combine predictions from different models using ensemble method."""
        try:
            # Initialize combined scores
            combined_scores = {}
            weights = self.config.get('ensemble_weights', {})
            
            # Rule-based predictions (always available)
            if 'rule_based' in predictions:
                rule_result = predictions['rule_based']
                if 'all_scores' in rule_result:
                    for doc_type, score in rule_result['all_scores'].items():
                        combined_scores[doc_type] = combined_scores.get(doc_type, 0) + score * 0.4
            
            # Traditional ML predictions
            if 'traditional_ml' in predictions and 'error' not in predictions['traditional_ml']:
                ml_predictions = predictions['traditional_ml']
                for model_name, model_preds in ml_predictions.items():
                    weight = weights.get(model_name, 0.1)
                    for doc_type, score in model_preds.items():
                        combined_scores[doc_type] = combined_scores.get(doc_type, 0) + score * weight
            
            # Transformer predictions
            if 'transformer' in predictions and 'error' not in predictions['transformer']:
                transformer_preds = predictions['transformer']
                weight = weights.get('transformer', 0.3)
                # Map transformer labels to our document types (simplified mapping)
                for label, score in transformer_preds.items():
                    # This is a simplified mapping - in production you'd have proper label mapping
                    mapped_type = self._map_transformer_label(label)
                    if mapped_type:
                        combined_scores[mapped_type] = combined_scores.get(mapped_type, 0) + score * weight
            
            # Normalize scores
            if combined_scores:
                max_score = max(combined_scores.values())
                if max_score > 0:
                    combined_scores = {k: v / max_score for k, v in combined_scores.items()}
            
            # Find best prediction
            if combined_scores:
                best_type = max(combined_scores.keys(), key=lambda k: combined_scores[k])
                best_confidence = combined_scores[best_type]
            else:
                best_type = 'unknown'
                best_confidence = 0.0
            
            # Get sub-categories
            sub_categories = []
            if best_type in self.document_types:
                sub_categories = self.document_types[best_type].get('sub_categories', [])
            
            result = {
                'document_type': best_type,
                'confidence': best_confidence,
                'sub_categories': sub_categories
            }
            
            if return_all:
                result['all_predictions'] = combined_scores
                result['individual_predictions'] = predictions
            
            return result
            
        except Exception as e:
            logger.error(f"Ensemble prediction error: {str(e)}")
            return {
                'document_type': 'unknown',
                'confidence': 0.0,
                'sub_categories': []
            }
    
    def _map_transformer_label(self, label: str) -> Optional[str]:
        """Map transformer model labels to our document types."""
        # This is a simplified mapping - in production you'd have a proper mapping
        label_mapping = {
            'POSITIVE': 'letter',  # Assuming positive sentiment = letter
            'NEGATIVE': 'report',  # Assuming negative sentiment = report
            # Add more mappings as needed
        }
        return label_mapping.get(label.upper())
    
    async def train_models(self, training_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Train classification models on provided data."""
        try:
            logger.info(f"Training classification models on {len(training_data)} documents")
            
            # Prepare training data
            texts = []
            labels = []
            
            for item in training_data:
                if 'content' in item and 'document_type' in item:
                    processed_text = await self._preprocess_text(item['content'])
                    texts.append(processed_text)
                    labels.append(item['document_type'])
            
            if len(texts) < 10:
                raise ValueError("Insufficient training data (minimum 10 documents required)")
            
            # Initialize vectorizer
            self.vectorizer = TfidfVectorizer(
                max_features=self.config['max_features'],
                ngram_range=self.config['ngram_range'],
                min_df=self.config['min_df'],
                max_df=self.config['max_df']
            )
            
            # Fit vectorizer and transform texts
            X = self.vectorizer.fit_transform(texts)
            
            # Encode labels
            self.label_encoder = LabelEncoder()
            y = self.label_encoder.fit_transform(labels)
            
            # Train multiple models
            models_to_train = {
                'random_forest': RandomForestClassifier(n_estimators=100, random_state=42),
                'gradient_boosting': GradientBoostingClassifier(random_state=42),
                'logistic_regression': LogisticRegression(random_state=42, max_iter=1000),
                'svm': SVC(probability=True, random_state=42),
                'naive_bayes': MultinomialNB()
            }
            
            training_results = {}
            
            for model_name, model in models_to_train.items():
                try:
                    # Train model
                    model.fit(X, y)
                    
                    # Evaluate with cross-validation
                    cv_scores = cross_val_score(model, X, y, cv=5)
                    
                    self.traditional_models[model_name] = model
                    training_results[model_name] = {
                        'accuracy': cv_scores.mean(),
                        'std': cv_scores.std()
                    }
                    
                    logger.info(f"{model_name} trained with accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
                    
                except Exception as e:
                    logger.warning(f"Failed to train {model_name}: {str(e)}")
            
            # Save models
            await self._save_models()
            
            # Update metrics
            self.metrics.update({
                'last_trained': datetime.utcnow().isoformat(),
                'training_data_size': len(training_data),
                'model_performance': training_results
            })
            
            return {
                'status': 'success',
                'models_trained': list(self.traditional_models.keys()),
                'performance': training_results,
                'training_data_size': len(training_data)
            }
            
        except Exception as e:
            logger.error(f"Model training error: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def _save_models(self):
        """Save trained models to disk."""
        try:
            model_data = {
                'vectorizer': self.vectorizer,
                'label_encoder': self.label_encoder,
                'traditional_models': self.traditional_models,
                'metrics': self.metrics,
                'config': self.config,
                'document_types': self.document_types
            }
            
            model_path = self.model_dir / "classification_models.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"Models saved to {model_path}")
            
        except Exception as e:
            logger.error(f"Failed to save models: {str(e)}")
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model state."""
        return {
            'available_models': list(self.traditional_models.keys()),
            'transformer_available': self.classifier_pipeline is not None,
            'vectorizer_features': self.vectorizer.get_feature_names_out().tolist() if self.vectorizer else [],
            'document_types': list(self.document_types.keys()),
            'metrics': self.metrics,
            'config': self.config
        }