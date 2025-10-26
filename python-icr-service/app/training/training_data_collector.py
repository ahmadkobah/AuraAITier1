"""
Training Data Collector for ICR Service

Handles collection, validation, and management of training data for
handwriting recognition models.
"""

import os
import json
import cv2
import numpy as np
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import logging
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class TrainingSample:
    """Represents a training sample."""
    sample_id: str
    image_path: str
    ground_truth: str
    category: str
    metadata: Dict[str, Any]
    created_at: str
    image_hash: str
    preprocessing_applied: bool = False
    validation_status: str = "pending"  # pending, valid, invalid


@dataclass
class DatasetStats:
    """Dataset statistics."""
    total_samples: int
    categories: Dict[str, int]
    avg_text_length: float
    unique_characters: int
    character_frequency: Dict[str, int]
    samples_by_date: Dict[str, int]
    validation_status: Dict[str, int]


class TrainingDataCollector:
    """Manages collection and organization of training data."""
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.images_dir = self.data_dir / "images"
        self.metadata_dir = self.data_dir / "metadata"
        self.index_file = self.data_dir / "training_index.json"
        
        # Create directories
        self.data_dir.mkdir(exist_ok=True)
        self.images_dir.mkdir(exist_ok=True)
        self.metadata_dir.mkdir(exist_ok=True)
        
        # Load existing index
        self.training_index = self._load_training_index()
        
        logger.info(f"Training data collector initialized at {data_dir}")
    
    def _load_training_index(self) -> Dict[str, TrainingSample]:
        """Load the training data index."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Convert dict back to TrainingSample objects
                index = {}
                for sample_id, sample_data in data.items():
                    index[sample_id] = TrainingSample(**sample_data)
                
                return index
                
            except Exception as e:
                logger.error(f"Failed to load training index: {e}")
                return {}
        
        return {}
    
    def _save_training_index(self):
        """Save the training data index."""
        try:
            # Convert TrainingSample objects to dicts
            data = {}
            for sample_id, sample in self.training_index.items():
                data[sample_id] = asdict(sample)
            
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Failed to save training index: {e}")
            raise
    
    def _calculate_image_hash(self, image: np.ndarray) -> str:
        """Calculate hash of image for duplicate detection."""
        # Convert image to bytes and calculate hash
        image_bytes = cv2.imencode('.png', image)[1].tobytes()
        return hashlib.md5(image_bytes).hexdigest()
    
    def _validate_sample(self, image: np.ndarray, ground_truth: str) -> Tuple[bool, str]:
        """Validate a training sample."""
        try:
            # Check image validity
            if image is None or image.size == 0:
                return False, "Invalid image"
            
            # Check image dimensions
            if len(image.shape) not in [2, 3]:
                return False, "Invalid image dimensions"
            
            # Check if image is too small
            height, width = image.shape[:2]
            if height < 10 or width < 10:
                return False, "Image too small"
            
            # Check ground truth
            if not ground_truth or not ground_truth.strip():
                return False, "Empty ground truth"
            
            # Check for reasonable text length
            if len(ground_truth) > 1000:
                return False, "Ground truth too long"
            
            # Check for non-printable characters (except common whitespace)
            import string
            allowed_chars = string.printable
            if not all(c in allowed_chars for c in ground_truth):
                return False, "Invalid characters in ground truth"
            
            return True, "Valid"
            
        except Exception as e:
            return False, f"Validation error: {e}"
    
    async def add_training_sample(
        self,
        image: np.ndarray,
        ground_truth: str,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a new training sample to the dataset."""
        try:
            # Validate sample
            is_valid, validation_message = self._validate_sample(image, ground_truth)
            if not is_valid:
                raise ValueError(f"Invalid training sample: {validation_message}")
            
            # Calculate image hash for duplicate detection
            image_hash = self._calculate_image_hash(image)
            
            # Check for duplicates
            for existing_sample in self.training_index.values():
                if existing_sample.image_hash == image_hash:
                    logger.warning(f"Duplicate image detected, skipping")
                    return existing_sample.sample_id
            
            # Generate unique sample ID
            sample_id = str(uuid.uuid4())
            
            # Save image
            image_filename = f"{sample_id}.png"
            image_path = self.images_dir / image_filename
            cv2.imwrite(str(image_path), image)
            
            # Create training sample
            sample = TrainingSample(
                sample_id=sample_id,
                image_path=str(image_path),
                ground_truth=ground_truth,
                category=category,
                metadata=metadata or {},
                created_at=datetime.utcnow().isoformat(),
                image_hash=image_hash,
                validation_status="valid"
            )
            
            # Add to index
            self.training_index[sample_id] = sample
            
            # Save metadata
            metadata_file = self.metadata_dir / f"{sample_id}.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(sample), f, indent=2, ensure_ascii=False)
            
            # Save updated index
            self._save_training_index()
            
            logger.info(f"Added training sample {sample_id} in category {category}")
            return sample_id
            
        except Exception as e:
            logger.error(f"Failed to add training sample: {e}")
            raise
    
    async def get_training_sample(self, sample_id: str) -> Optional[TrainingSample]:
        """Get a training sample by ID."""
        return self.training_index.get(sample_id)
    
    async def remove_training_sample(self, sample_id: str) -> bool:
        """Remove a training sample from the dataset."""
        try:
            if sample_id not in self.training_index:
                return False
            
            sample = self.training_index[sample_id]
            
            # Remove image file
            if os.path.exists(sample.image_path):
                os.remove(sample.image_path)
            
            # Remove metadata file
            metadata_file = self.metadata_dir / f"{sample_id}.json"
            if metadata_file.exists():
                metadata_file.unlink()
            
            # Remove from index
            del self.training_index[sample_id]
            
            # Save updated index
            self._save_training_index()
            
            logger.info(f"Removed training sample {sample_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove training sample {sample_id}: {e}")
            return False
    
    async def list_samples(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[TrainingSample]:
        """List training samples with optional filtering."""
        samples = list(self.training_index.values())
        
        # Filter by category
        if category:
            samples = [s for s in samples if s.category == category]
        
        # Sort by creation date (newest first)
        samples.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply offset and limit
        if limit:
            samples = samples[offset:offset + limit]
        else:
            samples = samples[offset:]
        
        return samples
    
    async def get_dataset_stats(self) -> DatasetStats:
        """Get comprehensive dataset statistics."""
        try:
            samples = list(self.training_index.values())
            total_samples = len(samples)
            
            if total_samples == 0:
                return DatasetStats(
                    total_samples=0,
                    categories={},
                    avg_text_length=0.0,
                    unique_characters=0,
                    character_frequency={},
                    samples_by_date={},
                    validation_status={}
                )
            
            # Category distribution
            categories = {}
            for sample in samples:
                categories[sample.category] = categories.get(sample.category, 0) + 1
            
            # Text length statistics
            text_lengths = [len(sample.ground_truth) for sample in samples]
            avg_text_length = sum(text_lengths) / len(text_lengths)
            
            # Character frequency analysis
            character_frequency = {}
            all_text = "".join([sample.ground_truth for sample in samples])
            for char in all_text:
                character_frequency[char] = character_frequency.get(char, 0) + 1
            
            unique_characters = len(character_frequency)
            
            # Samples by date
            samples_by_date = {}
            for sample in samples:
                date = sample.created_at[:10]  # Extract date part
                samples_by_date[date] = samples_by_date.get(date, 0) + 1
            
            # Validation status
            validation_status = {}
            for sample in samples:
                status = sample.validation_status
                validation_status[status] = validation_status.get(status, 0) + 1
            
            return DatasetStats(
                total_samples=total_samples,
                categories=categories,
                avg_text_length=avg_text_length,
                unique_characters=unique_characters,
                character_frequency=character_frequency,
                samples_by_date=samples_by_date,
                validation_status=validation_status
            )
            
        except Exception as e:
            logger.error(f"Failed to calculate dataset stats: {e}")
            raise
    
    async def export_dataset(
        self,
        export_format: str = "coco",
        output_path: str = "dataset_export",
        category: Optional[str] = None
    ) -> str:
        """Export dataset in specified format."""
        try:
            export_dir = Path(output_path)
            export_dir.mkdir(exist_ok=True)
            
            # Get samples to export
            samples = await self.list_samples(category=category)
            
            if export_format == "coco":
                return await self._export_coco_format(samples, export_dir)
            elif export_format == "simple":
                return await self._export_simple_format(samples, export_dir)
            else:
                raise ValueError(f"Unsupported export format: {export_format}")
                
        except Exception as e:
            logger.error(f"Failed to export dataset: {e}")
            raise
    
    async def _export_coco_format(self, samples: List[TrainingSample], export_dir: Path) -> str:
        """Export in COCO-like format for text recognition."""
        # Create COCO-style annotation
        coco_data = {
            "info": {
                "description": "SmartDockAI ICR Training Dataset",
                "version": "1.0",
                "year": datetime.now().year,
                "contributor": "SmartDockAI",
                "date_created": datetime.utcnow().isoformat()
            },
            "images": [],
            "annotations": [],
            "categories": [
                {
                    "id": 1,
                    "name": "text",
                    "supercategory": "text"
                }
            ]
        }
        
        # Create images directory
        images_dir = export_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        for i, sample in enumerate(samples):
            # Copy image
            src_image_path = Path(sample.image_path)
            dst_image_path = images_dir / f"{sample.sample_id}.png"
            
            import shutil
            shutil.copy2(src_image_path, dst_image_path)
            
            # Add image info
            coco_data["images"].append({
                "id": i,
                "file_name": f"{sample.sample_id}.png",
                "width": 0,  # Would need to read image to get actual dimensions
                "height": 0,
                "category": sample.category
            })
            
            # Add annotation
            coco_data["annotations"].append({
                "id": i,
                "image_id": i,
                "category_id": 1,
                "text": sample.ground_truth,
                "area": 0,
                "bbox": [0, 0, 0, 0],  # Would need actual bounding box
                "iscrowd": 0
            })
        
        # Save annotations
        annotations_file = export_dir / "annotations.json"
        with open(annotations_file, 'w', encoding='utf-8') as f:
            json.dump(coco_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported {len(samples)} samples to COCO format at {export_dir}")
        return str(export_dir)
    
    async def _export_simple_format(self, samples: List[TrainingSample], export_dir: Path) -> str:
        """Export in simple format (image + text file)."""
        # Create images directory
        images_dir = export_dir / "images"
        labels_dir = export_dir / "labels"
        images_dir.mkdir(exist_ok=True)
        labels_dir.mkdir(exist_ok=True)
        
        # Create manifest
        manifest = []
        
        for sample in samples:
            # Copy image
            src_image_path = Path(sample.image_path)
            dst_image_path = images_dir / f"{sample.sample_id}.png"
            
            import shutil
            shutil.copy2(src_image_path, dst_image_path)
            
            # Create label file
            label_file = labels_dir / f"{sample.sample_id}.txt"
            with open(label_file, 'w', encoding='utf-8') as f:
                f.write(sample.ground_truth)
            
            # Add to manifest
            manifest.append({
                "sample_id": sample.sample_id,
                "image_path": f"images/{sample.sample_id}.png",
                "label_path": f"labels/{sample.sample_id}.txt",
                "category": sample.category,
                "ground_truth": sample.ground_truth,
                "metadata": sample.metadata
            })
        
        # Save manifest
        manifest_file = export_dir / "manifest.json"
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported {len(samples)} samples to simple format at {export_dir}")
        return str(export_dir)
    
    async def validate_dataset(self) -> Dict[str, Any]:
        """Validate the entire dataset."""
        try:
            samples = list(self.training_index.values())
            validation_results = {
                "total_samples": len(samples),
                "valid_samples": 0,
                "invalid_samples": 0,
                "errors": []
            }
            
            for sample in samples:
                try:
                    # Check if image file exists
                    if not os.path.exists(sample.image_path):
                        validation_results["errors"].append({
                            "sample_id": sample.sample_id,
                            "error": "Image file missing"
                        })
                        continue
                    
                    # Load and validate image
                    image = cv2.imread(sample.image_path)
                    if image is None:
                        validation_results["errors"].append({
                            "sample_id": sample.sample_id,
                            "error": "Could not load image"
                        })
                        continue
                    
                    is_valid, message = self._validate_sample(image, sample.ground_truth)
                    
                    if is_valid:
                        validation_results["valid_samples"] += 1
                    else:
                        validation_results["invalid_samples"] += 1
                        validation_results["errors"].append({
                            "sample_id": sample.sample_id,
                            "error": message
                        })
                
                except Exception as e:
                    validation_results["invalid_samples"] += 1
                    validation_results["errors"].append({
                        "sample_id": sample.sample_id,
                        "error": f"Validation exception: {e}"
                    })
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Dataset validation failed: {e}")
            raise