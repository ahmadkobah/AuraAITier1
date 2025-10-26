"""
Training Data Collector for NLP Service

Collects and manages training data for various NLP tasks including
sentiment analysis, entity recognition, text classification, etc.
"""

import json
import os
import csv
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
import asyncio
import logging
from dataclasses import dataclass, asdict
from enum import Enum
import sqlite3
import hashlib

# Setup logging
logger = logging.getLogger(__name__)

class TaskType(Enum):
    """NLP task types for training data collection."""
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    ENTITY_RECOGNITION = "entity_recognition"
    TEXT_CLASSIFICATION = "text_classification"
    KEYWORD_EXTRACTION = "keyword_extraction"
    TEXT_SUMMARIZATION = "text_summarization"
    LANGUAGE_DETECTION = "language_detection"
    SEMANTIC_SIMILARITY = "semantic_similarity"

class DataQuality(Enum):
    """Data quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNKNOWN = "unknown"

@dataclass
class TrainingSample:
    """Base class for training samples."""
    id: str
    text: str
    task_type: TaskType
    language: str
    created_at: datetime
    quality_score: float = 0.0
    quality_level: DataQuality = DataQuality.UNKNOWN
    source: str = "manual"
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)
        if isinstance(self.task_type, str):
            self.task_type = TaskType(self.task_type)
        if isinstance(self.quality_level, str):
            self.quality_level = DataQuality(self.quality_level)

@dataclass
class SentimentSample(TrainingSample):
    """Training sample for sentiment analysis."""
    sentiment_label: str = "neutral"  # positive, negative, neutral
    sentiment_score: float = 0.0  # -1.0 to 1.0
    confidence: float = 1.0
    
    def __post_init__(self):
        super().__post_init__()
        self.task_type = TaskType.SENTIMENT_ANALYSIS

@dataclass
class EntitySample(TrainingSample):
    """Training sample for entity recognition."""
    entities: Optional[List[Dict[str, Any]]] = None  # [{"text": "John", "label": "PERSON", "start": 0, "end": 4}]
    
    def __post_init__(self):
        super().__post_init__()
        self.task_type = TaskType.ENTITY_RECOGNITION
        if self.entities is None:
            self.entities = []

@dataclass
class ClassificationSample(TrainingSample):
    """Training sample for text classification."""
    category: str = "unknown"
    categories: Optional[List[str]] = None
    confidence: float = 1.0
    
    def __post_init__(self):
        super().__post_init__()
        self.task_type = TaskType.TEXT_CLASSIFICATION
        if self.categories is None:
            self.categories = []

@dataclass
class KeywordSample(TrainingSample):
    """Training sample for keyword extraction."""
    keywords: Optional[List[Dict[str, Any]]] = None  # [{"keyword": "AI", "score": 0.9, "frequency": 3}]
    
    def __post_init__(self):
        super().__post_init__()
        self.task_type = TaskType.KEYWORD_EXTRACTION
        if self.keywords is None:
            self.keywords = []

@dataclass
class SummarizationSample(TrainingSample):
    """Training sample for text summarization."""
    summary: str = ""
    compression_ratio: float = 0.0
    
    def __post_init__(self):
        super().__post_init__()
        self.task_type = TaskType.TEXT_SUMMARIZATION
        if self.compression_ratio == 0.0:
            self.compression_ratio = len(self.summary) / len(self.text) if self.text else 0.0

@dataclass
class LanguageSample(TrainingSample):
    """Training sample for language detection."""
    detected_language: str = "unknown"
    language_confidence: float = 1.0
    
    def __post_init__(self):
        super().__post_init__()
        self.task_type = TaskType.LANGUAGE_DETECTION

@dataclass
class SimilaritySample(TrainingSample):
    """Training sample for semantic similarity."""
    text2: str = ""
    similarity_score: float = 0.0  # 0.0 to 1.0
    method: str = "manual"
    
    def __post_init__(self):
        super().__post_init__()
        self.task_type = TaskType.SEMANTIC_SIMILARITY

class TrainingDataCollector:
    """Manages collection and storage of training data for NLP tasks."""
    
    def __init__(self, data_dir: str = "./training_data"):
        """Initialize the training data collector.
        
        Args:
            data_dir: Directory to store training data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self.db_path = self.data_dir / "training_data.db"
        self._init_database()
        
        # Task-specific directories
        self.task_dirs = {}
        for task in TaskType:
            task_dir = self.data_dir / task.value
            task_dir.mkdir(exist_ok=True)
            self.task_dirs[task] = task_dir
        
        logger.info(f"Training data collector initialized at {self.data_dir}")
    
    def _init_database(self):
        """Initialize SQLite database for training data management."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create main training samples table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS training_samples (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    language TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    quality_score REAL DEFAULT 0.0,
                    quality_level TEXT DEFAULT 'unknown',
                    source TEXT DEFAULT 'manual',
                    metadata TEXT,
                    task_data TEXT,
                    text_hash TEXT,
                    UNIQUE(text_hash, task_type)
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_type ON training_samples(task_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_language ON training_samples(language)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality ON training_samples(quality_score)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON training_samples(created_at)")
            
            conn.commit()
    
    def _generate_sample_id(self, text: str, task_type: TaskType) -> str:
        """Generate unique ID for a training sample."""
        content = f"{text}_{task_type.value}_{datetime.utcnow().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _generate_text_hash(self, text: str) -> str:
        """Generate hash for text to check for duplicates."""
        return hashlib.sha256(text.encode()).hexdigest()
    
    def add_sample(self, sample: TrainingSample) -> bool:
        """Add a training sample to the collection.
        
        Args:
            sample: Training sample to add
            
        Returns:
            bool: True if added successfully, False if duplicate
        """
        try:
            # Generate ID if not provided
            if not sample.id:
                sample.id = self._generate_sample_id(sample.text, sample.task_type)
            
            # Generate text hash for duplicate detection
            text_hash = self._generate_text_hash(sample.text)
            
            # Prepare task-specific data
            task_data = {}
            if isinstance(sample, SentimentSample):
                task_data = {
                    "sentiment_label": sample.sentiment_label,
                    "sentiment_score": sample.sentiment_score,
                    "confidence": sample.confidence
                }
            elif isinstance(sample, EntitySample):
                task_data = {"entities": sample.entities}
            elif isinstance(sample, ClassificationSample):
                task_data = {
                    "category": sample.category,
                    "categories": sample.categories,
                    "confidence": sample.confidence
                }
            elif isinstance(sample, KeywordSample):
                task_data = {"keywords": sample.keywords}
            elif isinstance(sample, SummarizationSample):
                task_data = {
                    "summary": sample.summary,
                    "compression_ratio": sample.compression_ratio
                }
            elif isinstance(sample, LanguageSample):
                task_data = {
                    "detected_language": sample.detected_language,
                    "language_confidence": sample.language_confidence
                }
            elif isinstance(sample, SimilaritySample):
                task_data = {
                    "text2": sample.text2,
                    "similarity_score": sample.similarity_score,
                    "method": sample.method
                }
            
            # Store in database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO training_samples 
                    (id, text, task_type, language, created_at, quality_score, 
                     quality_level, source, metadata, task_data, text_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sample.id,
                    sample.text,
                    sample.task_type.value,
                    sample.language,
                    sample.created_at.isoformat(),
                    sample.quality_score,
                    sample.quality_level.value,
                    sample.source,
                    json.dumps(sample.metadata),
                    json.dumps(task_data),
                    text_hash
                ))
                
                conn.commit()
            
            # Also save as JSON file
            self._save_sample_to_file(sample, task_data)
            
            logger.info(f"Added training sample {sample.id} for {sample.task_type.value}")
            return True
            
        except sqlite3.IntegrityError:
            text_hash = self._generate_text_hash(sample.text)
            logger.warning(f"Duplicate sample detected for text hash {text_hash}")
            return False
        except Exception as e:
            logger.error(f"Failed to add sample: {e}")
            return False
    
    def _save_sample_to_file(self, sample: TrainingSample, task_data: Dict[str, Any]):
        """Save sample to JSON file for backup."""
        task_dir = self.task_dirs[sample.task_type]
        filename = f"{sample.id}.json"
        filepath = task_dir / filename
        
        sample_dict = asdict(sample)
        sample_dict.update(task_data)
        sample_dict["created_at"] = sample.created_at.isoformat()
        sample_dict["task_type"] = sample.task_type.value
        sample_dict["quality_level"] = sample.quality_level.value
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(sample_dict, f, indent=2, ensure_ascii=False)
    
    def get_samples(
        self,
        task_type: Optional[TaskType] = None,
        language: Optional[str] = None,
        min_quality: float = 0.0,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[TrainingSample]:
        """Retrieve training samples with filtering.
        
        Args:
            task_type: Filter by task type
            language: Filter by language
            min_quality: Minimum quality score
            limit: Maximum number of samples to return
            offset: Number of samples to skip
            
        Returns:
            List of training samples
        """
        query = """
            SELECT id, text, task_type, language, created_at, quality_score,
                   quality_level, source, metadata, task_data
            FROM training_samples
            WHERE quality_score >= ?
        """
        params: List[Union[float, str]] = [min_quality]
        
        if task_type:
            query += " AND task_type = ?"
            params.append(task_type.value)
        
        if language:
            query += " AND language = ?"
            params.append(language)
        
        query += " ORDER BY created_at DESC"
        
        if limit:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        
        samples = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            for row in cursor.fetchall():
                sample_data = {
                    "id": row[0],
                    "text": row[1],
                    "task_type": row[2],
                    "language": row[3],
                    "created_at": row[4],
                    "quality_score": row[5],
                    "quality_level": row[6],
                    "source": row[7],
                    "metadata": json.loads(row[8]) if row[8] else {},
                }
                
                task_data = json.loads(row[9]) if row[9] else {}
                
                # Create appropriate sample type
                sample = self._create_sample_from_data(sample_data, task_data)
                if sample:
                    samples.append(sample)
        
        return samples
    
    def _create_sample_from_data(self, sample_data: Dict[str, Any], task_data: Dict[str, Any]) -> Optional[TrainingSample]:
        """Create appropriate sample type from database data."""
        try:
            task_type = TaskType(sample_data["task_type"])
            
            base_data = {
                "id": sample_data["id"],
                "text": sample_data["text"],
                "task_type": task_type,
                "language": sample_data["language"],
                "created_at": sample_data["created_at"],
                "quality_score": sample_data["quality_score"],
                "quality_level": sample_data["quality_level"],
                "source": sample_data["source"],
                "metadata": sample_data["metadata"]
            }
            
            if task_type == TaskType.SENTIMENT_ANALYSIS:
                return SentimentSample(
                    **base_data,
                    sentiment_label=task_data.get("sentiment_label", "neutral"),
                    sentiment_score=task_data.get("sentiment_score", 0.0),
                    confidence=task_data.get("confidence", 1.0)
                )
            elif task_type == TaskType.ENTITY_RECOGNITION:
                return EntitySample(
                    **base_data,
                    entities=task_data.get("entities", [])
                )
            elif task_type == TaskType.TEXT_CLASSIFICATION:
                return ClassificationSample(
                    **base_data,
                    category=task_data.get("category", "unknown"),
                    categories=task_data.get("categories", []),
                    confidence=task_data.get("confidence", 1.0)
                )
            elif task_type == TaskType.KEYWORD_EXTRACTION:
                return KeywordSample(
                    **base_data,
                    keywords=task_data.get("keywords", [])
                )
            elif task_type == TaskType.TEXT_SUMMARIZATION:
                return SummarizationSample(
                    **base_data,
                    summary=task_data.get("summary", ""),
                    compression_ratio=task_data.get("compression_ratio", 0.0)
                )
            elif task_type == TaskType.LANGUAGE_DETECTION:
                return LanguageSample(
                    **base_data,
                    detected_language=task_data.get("detected_language", "unknown"),
                    language_confidence=task_data.get("language_confidence", 1.0)
                )
            elif task_type == TaskType.SEMANTIC_SIMILARITY:
                return SimilaritySample(
                    **base_data,
                    text2=task_data.get("text2", ""),
                    similarity_score=task_data.get("similarity_score", 0.0),
                    method=task_data.get("method", "manual")
                )
            
        except Exception as e:
            logger.error(f"Failed to create sample from data: {e}")
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the training data collection."""
        stats = {
            "total_samples": 0,
            "by_task": {},
            "by_language": {},
            "by_quality": {},
            "by_source": {},
            "quality_distribution": {}
        }
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total samples
            cursor.execute("SELECT COUNT(*) FROM training_samples")
            stats["total_samples"] = cursor.fetchone()[0]
            
            # By task type
            cursor.execute("SELECT task_type, COUNT(*) FROM training_samples GROUP BY task_type")
            stats["by_task"] = dict(cursor.fetchall())
            
            # By language
            cursor.execute("SELECT language, COUNT(*) FROM training_samples GROUP BY language")
            stats["by_language"] = dict(cursor.fetchall())
            
            # By quality level
            cursor.execute("SELECT quality_level, COUNT(*) FROM training_samples GROUP BY quality_level")
            stats["by_quality"] = dict(cursor.fetchall())
            
            # By source
            cursor.execute("SELECT source, COUNT(*) FROM training_samples GROUP BY source")
            stats["by_source"] = dict(cursor.fetchall())
            
            # Quality score distribution
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN quality_score >= 0.8 THEN 'high'
                        WHEN quality_score >= 0.6 THEN 'medium'
                        WHEN quality_score >= 0.4 THEN 'low'
                        ELSE 'very_low'
                    END as quality_range,
                    COUNT(*)
                FROM training_samples 
                GROUP BY quality_range
            """)
            stats["quality_distribution"] = dict(cursor.fetchall())
        
        return stats
    
    def export_dataset(
        self,
        task_type: TaskType,
        format: str = "json",
        output_path: Optional[Union[str, Path]] = None,
        train_split: float = 0.8,
        val_split: float = 0.1,
        test_split: float = 0.1
    ) -> Dict[str, str]:
        """Export training dataset in specified format.
        
        Args:
            task_type: Type of task to export
            format: Export format ('json', 'csv', 'jsonl')
            output_path: Output directory path
            train_split: Training data split ratio
            val_split: Validation data split ratio
            test_split: Test data split ratio
            
        Returns:
            Dictionary with file paths for each split
        """
        if abs(train_split + val_split + test_split - 1.0) > 0.001:
            raise ValueError("Data splits must sum to 1.0")
        
        samples = self.get_samples(task_type=task_type)
        if not samples:
            raise ValueError(f"No samples found for task type {task_type.value}")
        
        # Shuffle samples
        import random
        random.shuffle(samples)
        
        # Calculate split indices
        total = len(samples)
        train_end = int(total * train_split)
        val_end = train_end + int(total * val_split)
        
        splits = {
            "train": samples[:train_end],
            "validation": samples[train_end:val_end],
            "test": samples[val_end:]
        }
        
        # Set output directory
        if not output_path:
            output_dir = self.task_dirs[task_type] / "export"
        else:
            output_dir = Path(output_path)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Export each split
        file_paths = {}
        for split_name, split_samples in splits.items():
            if not split_samples:
                continue
                
            filename = f"{task_type.value}_{split_name}.{format}"
            filepath = output_dir / filename
            
            if format == "json":
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump([asdict(sample) for sample in split_samples], f, indent=2, default=str)
            elif format == "jsonl":
                with open(filepath, 'w', encoding='utf-8') as f:
                    for sample in split_samples:
                        json.dump(asdict(sample), f, default=str)
                        f.write('\n')
            elif format == "csv":
                df = pd.DataFrame([asdict(sample) for sample in split_samples])
                df.to_csv(filepath, index=False)
            
            file_paths[split_name] = str(filepath)
        
        logger.info(f"Exported {task_type.value} dataset to {output_dir}")
        return file_paths
    
    def import_from_file(self, filepath_str: str, task_type: TaskType, language: str = "en") -> int:
        """Import training data from file.
        
        Args:
            filepath_str: Path to input file
            task_type: Task type for the samples
            language: Language of the samples
            
        Returns:
            Number of samples imported
        """
        filepath = Path(filepath_str)
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        imported_count = 0
        
        try:
            if filepath.suffix == ".json":
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            elif filepath.suffix == ".jsonl":
                data = []
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        data.append(json.loads(line.strip()))
            elif filepath.suffix == ".csv":
                df = pd.read_csv(filepath)
                data = df.to_dict('records')
            else:
                raise ValueError(f"Unsupported file format: {filepath.suffix}")
            
            for item in data:
                try:
                    # Create sample based on task type
                    sample_data = {
                        "id": item.get("id", ""),
                        "text": item["text"],
                        "task_type": task_type,
                        "language": item.get("language", language),
                        "created_at": datetime.utcnow(),
                        "quality_score": item.get("quality_score", 0.5),
                        "quality_level": DataQuality(item.get("quality_level", "unknown")),
                        "source": item.get("source", "import"),
                        "metadata": item.get("metadata", {})
                    }
                    
                    # Create task-specific sample
                    if task_type == TaskType.SENTIMENT_ANALYSIS:
                        sample = SentimentSample(
                            **sample_data,
                            sentiment_label=item["sentiment_label"],
                            sentiment_score=item.get("sentiment_score", 0.0),
                            confidence=item.get("confidence", 1.0)
                        )
                    elif task_type == TaskType.ENTITY_RECOGNITION:
                        sample = EntitySample(
                            **sample_data,
                            entities=item["entities"]
                        )
                    elif task_type == TaskType.TEXT_CLASSIFICATION:
                        sample = ClassificationSample(
                            **sample_data,
                            category=item["category"],
                            categories=item.get("categories", []),
                            confidence=item.get("confidence", 1.0)
                        )
                    # Add other task types as needed
                    else:
                        continue
                    
                    if self.add_sample(sample):
                        imported_count += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to import sample: {e}")
                    continue
            
            logger.info(f"Imported {imported_count} samples from {filepath}")
            return imported_count
            
        except Exception as e:
            logger.error(f"Failed to import from {filepath}: {e}")
            raise
    
    def validate_dataset(self, task_type: TaskType) -> Dict[str, Any]:
        """Validate dataset for a specific task type.
        
        Args:
            task_type: Task type to validate
            
        Returns:
            Validation results
        """
        samples = self.get_samples(task_type=task_type)
        
        validation_results = {
            "total_samples": len(samples),
            "valid_samples": 0,
            "invalid_samples": 0,
            "errors": [],
            "warnings": [],
            "quality_metrics": {
                "avg_quality_score": 0.0,
                "min_text_length": float('inf'),
                "max_text_length": 0,
                "avg_text_length": 0.0
            }
        }
        
        if not samples:
            validation_results["errors"].append("No samples found")
            return validation_results
        
        total_quality = 0
        total_length = 0
        
        for sample in samples:
            is_valid = True
            
            # Basic validation
            if not sample.text or len(sample.text.strip()) == 0:
                validation_results["errors"].append(f"Sample {sample.id}: Empty text")
                is_valid = False
            
            if len(sample.text) < 10:
                validation_results["warnings"].append(f"Sample {sample.id}: Very short text")
            
            # Task-specific validation
            if task_type == TaskType.SENTIMENT_ANALYSIS and isinstance(sample, SentimentSample):
                if sample.sentiment_label not in ["positive", "negative", "neutral"]:
                    validation_results["errors"].append(f"Sample {sample.id}: Invalid sentiment label")
                    is_valid = False
            
            elif task_type == TaskType.ENTITY_RECOGNITION and isinstance(sample, EntitySample):
                if not sample.entities:
                    validation_results["warnings"].append(f"Sample {sample.id}: No entities")
            
            # Update metrics
            text_len = len(sample.text)
            total_quality += sample.quality_score
            total_length += text_len
            
            validation_results["quality_metrics"]["min_text_length"] = min(
                validation_results["quality_metrics"]["min_text_length"], text_len
            )
            validation_results["quality_metrics"]["max_text_length"] = max(
                validation_results["quality_metrics"]["max_text_length"], text_len
            )
            
            if is_valid:
                validation_results["valid_samples"] += 1
            else:
                validation_results["invalid_samples"] += 1
        
        # Calculate averages
        if samples:
            validation_results["quality_metrics"]["avg_quality_score"] = total_quality / len(samples)
            validation_results["quality_metrics"]["avg_text_length"] = total_length / len(samples)
        
        return validation_results
    
    def cleanup_duplicates(self) -> int:
        """Remove duplicate samples based on text content.
        
        Returns:
            Number of duplicates removed
        """
        removed_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Find duplicates
            cursor.execute("""
                SELECT text_hash, task_type, COUNT(*), MIN(id)
                FROM training_samples
                GROUP BY text_hash, task_type
                HAVING COUNT(*) > 1
            """)
            
            duplicates = cursor.fetchall()
            
            for text_hash, task_type, count, keep_id in duplicates:
                # Delete all but the earliest one
                cursor.execute("""
                    DELETE FROM training_samples
                    WHERE text_hash = ? AND task_type = ? AND id != ?
                """, (text_hash, task_type, keep_id))
                
                removed_count += count - 1
            
            conn.commit()
        
        logger.info(f"Removed {removed_count} duplicate samples")
        return removed_count

# Example usage and testing
if __name__ == "__main__":
    # Initialize collector
    collector = TrainingDataCollector("./test_training_data")
    
    # Create sample data
    sentiment_sample = SentimentSample(
        id="",
        text="This is a great product! I love it.",
        task_type=TaskType.SENTIMENT_ANALYSIS,
        language="en",
        created_at=datetime.utcnow(),
        sentiment_label="positive",
        sentiment_score=0.8,
        confidence=0.9,
        quality_score=0.9,
        source="manual_annotation"
    )
    
    # Add sample
    collector.add_sample(sentiment_sample)
    
    # Get statistics
    stats = collector.get_statistics()
    print("Training Data Statistics:")
    print(json.dumps(stats, indent=2))
    
    # Validate dataset
    validation = collector.validate_dataset(TaskType.SENTIMENT_ANALYSIS)
    print("\nDataset Validation:")
    print(json.dumps(validation, indent=2))