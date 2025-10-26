"""
Base ICR Model Interface

Abstract interface for Intelligent Character Recognition models that handle
handwriting recognition, signature verification, and character-level analysis.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
import numpy as np
from enum import Enum


class ICRTaskType(Enum):
    """Types of ICR tasks supported."""
    HANDWRITING_RECOGNITION = "handwriting_recognition"
    SIGNATURE_VERIFICATION = "signature_verification"
    CHARACTER_CLASSIFICATION = "character_classification"
    LINE_DETECTION = "line_detection"
    WORD_SEGMENTATION = "word_segmentation"


@dataclass
class CharacterPrediction:
    """Individual character prediction with confidence."""
    character: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    alternatives: Optional[List[Tuple[str, float]]] = None  # Alternative predictions


@dataclass
class WordPrediction:
    """Word-level prediction from handwriting."""
    text: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    characters: List[CharacterPrediction]
    word_type: str = "handwritten"  # handwritten, printed, mixed


@dataclass
class LinePrediction:
    """Line-level prediction from handwriting."""
    text: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    words: List[WordPrediction]
    line_angle: float = 0.0  # Rotation angle in degrees


@dataclass
class SignatureVerification:
    """Signature verification result."""
    is_genuine: bool
    confidence: float
    similarity_score: float
    verification_model: str
    features_extracted: Dict[str, Any]


@dataclass
class ICRResult:
    """Complete ICR processing result."""
    task_type: ICRTaskType
    text: str
    confidence: float
    characters: List[CharacterPrediction]
    words: List[WordPrediction]
    lines: List[LinePrediction]
    signature_verification: Optional[SignatureVerification]
    processing_time: float
    model_version: str
    metadata: Dict[str, Any]


@dataclass
class TrainingData:
    """ICR training data structure."""
    image_path: str
    ground_truth: Union[str, Dict[str, Any]]  # Text or structured labels
    task_type: ICRTaskType
    character_annotations: Optional[List[Dict[str, Any]]] = None
    word_annotations: Optional[List[Dict[str, Any]]] = None
    line_annotations: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


class ICRModelInterface(ABC):
    """Abstract base class for ICR models."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the ICR model with configuration."""
        self.config = config or {}
        self.is_loaded = False
        self.model_name = "base_icr_model"
        self.version = "1.0.0"
        self.supported_tasks = [ICRTaskType.HANDWRITING_RECOGNITION]
    
    @abstractmethod
    async def load_model(self) -> bool:
        """Load the ICR model and its dependencies."""
        pass
    
    @abstractmethod
    async def predict(
        self, 
        image: np.ndarray,
        task_type: ICRTaskType = ICRTaskType.HANDWRITING_RECOGNITION,
        options: Dict[str, Any] = None
    ) -> ICRResult:
        """
        Perform ICR prediction on an image.
        
        Args:
            image: Input image as numpy array
            task_type: Type of ICR task to perform
            options: Additional processing options
            
        Returns:
            ICRResult containing predictions and metadata
        """
        pass
    
    @abstractmethod
    async def batch_predict(
        self, 
        images: List[np.ndarray],
        task_type: ICRTaskType = ICRTaskType.HANDWRITING_RECOGNITION,
        options: Dict[str, Any] = None
    ) -> List[ICRResult]:
        """
        Perform batch ICR prediction on multiple images.
        
        Args:
            images: List of input images as numpy arrays
            task_type: Type of ICR task to perform
            options: Additional processing options
            
        Returns:
            List of ICRResult objects
        """
        pass
    
    @abstractmethod
    async def train(
        self,
        training_data: List[TrainingData],
        validation_data: List[TrainingData] = None,
        training_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Train the ICR model with provided data.
        
        Args:
            training_data: Training dataset
            validation_data: Validation dataset
            training_config: Training configuration
            
        Returns:
            Training results and metrics
        """
        pass
    
    @abstractmethod
    async def evaluate(
        self,
        test_data: List[TrainingData],
        metrics: List[str] = None
    ) -> Dict[str, float]:
        """
        Evaluate model performance on test data.
        
        Args:
            test_data: Test dataset
            metrics: List of metrics to compute
            
        Returns:
            Evaluation metrics
        """
        pass
    
    @abstractmethod
    async def save_model(self, save_path: str) -> bool:
        """Save the trained model to disk."""
        pass
    
    @abstractmethod
    async def load_pretrained(self, model_path: str) -> bool:
        """Load a pre-trained model from disk."""
        pass
    
    def get_supported_tasks(self) -> List[ICRTaskType]:
        """Get list of supported ICR tasks."""
        return self.supported_tasks.copy()
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information and configuration."""
        return {
            "name": self.model_name,
            "version": self.version,
            "loaded": self.is_loaded,
            "supported_tasks": [task.value for task in self.supported_tasks],
            "config": self.config
        }
    
    async def preprocess_image(
        self, 
        image: np.ndarray,
        task_type: ICRTaskType = ICRTaskType.HANDWRITING_RECOGNITION
    ) -> np.ndarray:
        """
        Preprocess image for ICR tasks.
        Default implementation - can be overridden.
        """
        # Basic preprocessing
        if len(image.shape) == 3:
            # Convert to grayscale
            import cv2
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Normalize
        image = image.astype(np.float32) / 255.0
        
        return image
    
    async def postprocess_predictions(
        self,
        raw_predictions: Any,
        image_shape: Tuple[int, ...],
        task_type: ICRTaskType
    ) -> ICRResult:
        """
        Post-process raw model predictions into ICRResult format.
        Must be implemented by specific model classes.
        """
        raise NotImplementedError("Subclasses must implement postprocess_predictions")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the ICR model."""
        return {
            "status": "healthy" if self.is_loaded else "not_loaded",
            "model": self.model_name,
            "version": self.version,
            "supported_tasks": [task.value for task in self.supported_tasks]
        }


class ICRModelRegistry:
    """Registry for managing multiple ICR models."""
    
    def __init__(self):
        self.models: Dict[str, ICRModelInterface] = {}
        self.default_model = None
    
    def register_model(self, name: str, model: ICRModelInterface, is_default: bool = False):
        """Register an ICR model."""
        self.models[name] = model
        if is_default or self.default_model is None:
            self.default_model = name
    
    def get_model(self, name: str = None) -> Optional[ICRModelInterface]:
        """Get an ICR model by name or default."""
        if name is None:
            name = self.default_model
        return self.models.get(name)
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List all registered models."""
        return [
            {
                "name": name,
                "info": model.get_model_info(),
                "is_default": name == self.default_model
            }
            for name, model in self.models.items()
        ]
    
    async def load_all_models(self) -> Dict[str, bool]:
        """Load all registered models."""
        results = {}
        for name, model in self.models.items():
            try:
                results[name] = await model.load_model()
            except Exception as e:
                results[name] = False
                print(f"Failed to load model {name}: {e}")
        return results