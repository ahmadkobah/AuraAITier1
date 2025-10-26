"""
Base NLP Model Interface

Abstract base class for all NLP models in the SmartDockAI NLP service.
Provides standardized interfaces for different NLP tasks.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np


class NLPTaskType(Enum):
    """Types of NLP tasks supported."""
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    ENTITY_RECOGNITION = "entity_recognition"
    KEYWORD_EXTRACTION = "keyword_extraction"
    TEXT_SUMMARIZATION = "text_summarization"
    LANGUAGE_DETECTION = "language_detection"
    TEXT_CLASSIFICATION = "text_classification"
    TOPIC_MODELING = "topic_modeling"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    TEXT_GENERATION = "text_generation"
    INTENT_CLASSIFICATION = "intent_classification"


class LanguageCode(Enum):
    """Supported language codes."""
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    RUSSIAN = "ru"
    CHINESE = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    ARABIC = "ar"
    DUTCH = "nl"
    SWEDISH = "sv"
    NORWEGIAN = "no"
    DANISH = "da"
    AUTO_DETECT = "auto"


@dataclass
class Entity:
    """Named entity representation."""
    text: str
    label: str
    start: int
    end: int
    confidence: float
    metadata: Dict[str, Any]


@dataclass
class SentimentResult:
    """Sentiment analysis result."""
    label: str  # positive, negative, neutral
    score: float  # confidence score
    compound_score: float  # compound sentiment score
    details: Dict[str, float]  # individual sentiment scores


@dataclass
class KeywordResult:
    """Keyword extraction result."""
    keyword: str
    score: float
    frequency: int
    positions: List[int]
    context: List[str]


@dataclass
class SummaryResult:
    """Text summarization result."""
    summary: str
    original_length: int
    summary_length: int
    compression_ratio: float
    key_sentences: List[str]


@dataclass
class LanguageResult:
    """Language detection result."""
    language: str
    confidence: float
    iso_code: str
    alternatives: List[Tuple[str, float]]


@dataclass
class TopicResult:
    """Topic modeling result."""
    topic_id: int
    topic_words: List[Tuple[str, float]]
    topic_weight: float
    coherence_score: float


@dataclass
class ClassificationResult:
    """Text classification result."""
    label: str
    confidence: float
    probabilities: Dict[str, float]
    features: Dict[str, Any]


@dataclass
class SimilarityResult:
    """Semantic similarity result."""
    similarity_score: float
    embedding_1: Optional[np.ndarray]
    embedding_2: Optional[np.ndarray]
    method: str


@dataclass
class NLPResult:
    """Complete NLP processing result."""
    task_type: NLPTaskType
    text: str
    language: Optional[str]
    
    # Task-specific results
    sentiment: Optional[SentimentResult] = None
    entities: Optional[List[Entity]] = None
    keywords: Optional[List[KeywordResult]] = None
    summary: Optional[SummaryResult] = None
    language_detection: Optional[LanguageResult] = None
    classification: Optional[ClassificationResult] = None
    topics: Optional[List[TopicResult]] = None
    similarity: Optional[SimilarityResult] = None
    
    # Metadata
    processing_time: float = 0.0
    model_version: str = "unknown"
    confidence: float = 0.0
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TrainingData:
    """NLP training data structure."""
    text: str
    labels: Dict[str, Any]  # Task-specific labels
    task_type: NLPTaskType
    language: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TrainingConfig:
    """Training configuration for NLP models."""
    task_type: NLPTaskType
    model_name: str
    epochs: int = 10
    batch_size: int = 16
    learning_rate: float = 1e-5
    validation_split: float = 0.2
    early_stopping: bool = True
    save_best_only: bool = True
    metrics: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = ["accuracy", "f1"]


class NLPModelInterface(ABC):
    """Abstract base class for NLP models."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the NLP model with configuration."""
        self.config = config or {}
        self.model = None
        self.tokenizer = None
        self.model_name = "base_nlp_model"
        self.model_version = "1.0.0"
        self.supported_tasks = [NLPTaskType.TEXT_CLASSIFICATION]
        self.supported_languages = [LanguageCode.ENGLISH]
        self.is_loaded = False
    
    @abstractmethod
    def load_model(self) -> bool:
        """Load the NLP model and its dependencies."""
        pass
    
    @abstractmethod
    async def predict(
        self,
        text: Union[str, List[str]],
        task_type: NLPTaskType = NLPTaskType.TEXT_CLASSIFICATION,
        language: Optional[LanguageCode] = None,
        **kwargs
    ) -> Union[NLPResult, List[NLPResult]]:
        """
        Perform NLP prediction on text.
        
        Args:
            text: Input text or list of texts
            task_type: Type of NLP task to perform
            language: Language of the text (auto-detect if None)
            **kwargs: Additional task-specific parameters
            
        Returns:
            NLPResult or list of NLPResults containing predictions and metadata
        """
        pass
    
    @abstractmethod
    async def train(
        self,
        training_data: List[TrainingData],
        config: TrainingConfig
    ) -> Dict[str, Any]:
        """
        Train the NLP model with provided data.
        
        Args:
            training_data: List of training samples
            config: Training configuration
            
        Returns:
            Training results and metrics
        """
        pass
    
    @abstractmethod
    async def evaluate(
        self,
        test_data: List[TrainingData],
        metrics: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """
        Evaluate the model on test data.
        
        Args:
            test_data: List of test samples
            metrics: List of evaluation metrics
            
        Returns:
            Evaluation results
        """
        pass
    
    def save_model(self, path: str) -> bool:
        """Save the trained model to disk."""
        try:
            # Default implementation - override in subclasses
            import joblib
            import os
            
            os.makedirs(path, exist_ok=True)
            
            if self.model is not None:
                joblib.dump(self.model, os.path.join(path, "model.pkl"))
            
            if self.tokenizer is not None:
                self.tokenizer.save_pretrained(path)
            
            # Save configuration
            import json
            config_path = os.path.join(path, "config.json")
            with open(config_path, 'w') as f:
                json.dump({
                    "model_name": self.model_name,
                    "model_version": self.model_version,
                    "supported_tasks": [task.value for task in self.supported_tasks],
                    "supported_languages": [lang.value for lang in self.supported_languages],
                    "config": self.config
                }, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error saving model: {e}")
            return False
    
    def load_saved_model(self, path: str) -> bool:
        """Load a saved model from disk."""
        try:
            import joblib
            import json
            import os
            
            # Load configuration
            config_path = os.path.join(path, "config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    saved_config = json.load(f)
                    self.model_name = saved_config.get("model_name", self.model_name)
                    self.model_version = saved_config.get("model_version", self.model_version)
                    self.config.update(saved_config.get("config", {}))
            
            # Load model
            model_path = os.path.join(path, "model.pkl")
            if os.path.exists(model_path):
                self.model = joblib.load(model_path)
            
            # Load tokenizer if exists
            try:
                from transformers import AutoTokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(path)
            except:
                pass  # Tokenizer not found or not needed
            
            self.is_loaded = True
            return True
            
        except Exception as e:
            print(f"Error loading saved model: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "supported_tasks": [task.value for task in self.supported_tasks],
            "supported_languages": [lang.value for lang in self.supported_languages],
            "is_loaded": self.is_loaded,
            "config": self.config
        }
    
    def preprocess_text(self, text: str, language: Optional[LanguageCode] = None) -> str:
        """Preprocess text for the model."""
        # Basic preprocessing - override in subclasses for specific needs
        import re
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove special characters if needed
        if self.config.get("remove_special_chars", False):
            text = re.sub(r'[^\w\s]', '', text)
        
        return text
    
    def postprocess_result(self, result: NLPResult) -> NLPResult:
        """Postprocess model results."""
        # Add model metadata
        result.model_version = self.model_version
        
        # Calculate overall confidence if not set
        if result.confidence == 0.0:
            if result.sentiment and result.sentiment.score:
                result.confidence = result.sentiment.score
            elif result.classification and result.classification.confidence:
                result.confidence = result.classification.confidence
            elif result.entities:
                result.confidence = float(np.mean([e.confidence for e in result.entities]))
        
        return result