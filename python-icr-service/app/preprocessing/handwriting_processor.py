"""
Handwriting-Specific Image Preprocessing

Specialized preprocessing for handwriting recognition including
line detection, word segmentation, character isolation, and enhancement.
"""

import cv2
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
import logging
from scipy import ndimage
import matplotlib.pyplot as plt


@dataclass
class HandwritingSegment:
    """Represents a segmented portion of handwriting."""
    image: np.ndarray
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    segment_type: str  # line, word, character
    confidence: float
    metadata: Dict[str, Any]


@dataclass
class LineSegmentation:
    """Results of line segmentation."""
    lines: List[HandwritingSegment]
    line_spacing: float
    skew_angle: float
    original_image: np.ndarray


@dataclass
class WordSegmentation:
    """Results of word segmentation."""
    words: List[HandwritingSegment]
    word_spacing: float
    line_segments: List[HandwritingSegment]


class HandwritingPreprocessor:
    """Specialized preprocessor for handwriting recognition."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Preprocessing parameters
        self.min_line_height = config.get("min_line_height", 20)
        self.max_line_height = config.get("max_line_height", 200)
        self.min_word_width = config.get("min_word_width", 10)
        self.skew_detection_enabled = config.get("skew_detection", True)
        self.noise_reduction_level = config.get("noise_reduction", "medium")
    
    async def preprocess_handwriting(
        self, 
        image: np.ndarray,
        task_type: str = "line_recognition"
    ) -> Dict[str, Any]:
        """
        Comprehensive handwriting preprocessing pipeline.
        
        Args:
            image: Input handwriting image
            task_type: Type of recognition (line_recognition, word_recognition, character_recognition)
            
        Returns:
            Dictionary with preprocessed images and metadata
        """
        results = {
            "original_image": image.copy(),
            "preprocessed_image": None,
            "line_segments": [],
            "word_segments": [],
            "character_segments": [],
            "metadata": {}
        }
        
        try:
            # Step 1: Basic preprocessing
            processed_image = await self._basic_preprocessing(image)
            
            # Step 2: Skew correction
            if self.skew_detection_enabled:
                processed_image, skew_angle = await self._correct_skew(processed_image)
                results["metadata"]["skew_angle"] = skew_angle
            
            # Step 3: Noise reduction
            processed_image = await self._reduce_noise(processed_image)
            
            # Step 4: Enhance contrast for handwriting
            processed_image = await self._enhance_handwriting_contrast(processed_image)
            
            # Step 5: Binarization
            binary_image = await self._binarize_handwriting(processed_image)
            
            results["preprocessed_image"] = binary_image
            
            # Step 6: Segmentation based on task type
            if task_type in ["line_recognition", "word_recognition", "character_recognition"]:
                line_segmentation = await self._segment_lines(binary_image)
                results["line_segments"] = line_segmentation.lines
                results["metadata"]["line_spacing"] = line_segmentation.line_spacing
                
                if task_type in ["word_recognition", "character_recognition"]:
                    word_segments = []
                    for line_segment in line_segmentation.lines:
                        word_seg = await self._segment_words(line_segment.image)
                        word_segments.extend(word_seg.words)
                    results["word_segments"] = word_segments
                    
                    if task_type == "character_recognition":
                        char_segments = []
                        for word_segment in word_segments:
                            char_seg = await self._segment_characters(word_segment.image)
                            char_segments.extend(char_seg)
                        results["character_segments"] = char_segments
            
            self.logger.info(f"Handwriting preprocessing completed for {task_type}")
            return results
            
        except Exception as e:
            self.logger.error(f"Handwriting preprocessing failed: {e}")
            raise
    
    async def _basic_preprocessing(self, image: np.ndarray) -> np.ndarray:
        """Basic image preprocessing steps."""
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Resize if too large (for performance)
        height, width = gray.shape
        if width > 2000:
            scale = 2000 / width
            new_width = int(width * scale)
            new_height = int(height * scale)
            gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        return gray
    
    async def _correct_skew(self, image: np.ndarray) -> Tuple[np.ndarray, float]:
        """Detect and correct skew in handwriting."""
        # Find edges
        edges = cv2.Canny(image, 50, 150, apertureSize=3)
        
        # Detect lines using Hough transform
        lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
        
        if lines is not None:
            # Calculate angles
            angles = []
            for rho, theta in lines[:, 0]:
                angle = np.degrees(theta) - 90
                if abs(angle) <= 45:  # Filter reasonable angles
                    angles.append(angle)
            
            if angles:
                # Use median angle to avoid outliers
                skew_angle = np.median(angles)
                
                # Rotate image to correct skew
                height, width = image.shape
                center = (width // 2, height // 2)
                rotation_matrix = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
                
                corrected = cv2.warpAffine(
                    image, rotation_matrix, (width, height),
                    flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
                )
                
                return corrected, skew_angle
        
        return image, 0.0
    
    async def _reduce_noise(self, image: np.ndarray) -> np.ndarray:
        """Apply noise reduction appropriate for handwriting."""
        if self.noise_reduction_level == "light":
            # Light Gaussian blur
            return cv2.GaussianBlur(image, (3, 3), 0.5)
        elif self.noise_reduction_level == "medium":
            # Bilateral filter to preserve edges
            return cv2.bilateralFilter(image, 9, 75, 75)
        elif self.noise_reduction_level == "heavy":
            # Non-local means denoising
            return cv2.fastNlMeansDenoising(image, h=10, templateWindowSize=7, searchWindowSize=21)
        else:
            return image
    
    async def _enhance_handwriting_contrast(self, image: np.ndarray) -> np.ndarray:
        """Enhance contrast specifically for handwriting."""
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(image)
        
        # Additional enhancement for handwriting
        # Sharpen the image slightly
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel * 0.5)
        
        # Blend original and sharpened
        result = cv2.addWeighted(enhanced, 0.7, sharpened, 0.3, 0)
        
        return result
    
    async def _binarize_handwriting(self, image: np.ndarray) -> np.ndarray:
        """Binarize image optimized for handwriting."""
        # Try multiple binarization methods and choose the best
        
        # Method 1: Adaptive threshold
        adaptive = cv2.adaptiveThreshold(
            image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10
        )
        
        # Method 2: Otsu's method
        _, otsu = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Method 3: Sauvola's method (approximation)
        mean = cv2.GaussianBlur(image, (15, 15), 0)
        sqr_mean = cv2.GaussianBlur(image**2, (15, 15), 0)
        std = np.sqrt(sqr_mean - mean**2)
        k = 0.2
        threshold = mean * (1 + k * ((std / 128) - 1))
        sauvola = (image > threshold).astype(np.uint8) * 255
        
        # Choose the best method based on image characteristics
        # For now, use adaptive thresholding as it works well for handwriting
        return adaptive
    
    async def _segment_lines(self, binary_image: np.ndarray) -> LineSegmentation:
        """Segment handwriting into lines."""
        # Calculate horizontal projection
        horizontal_projection = np.sum(binary_image == 0, axis=1)  # Count black pixels
        
        # Find line boundaries
        line_boundaries = []
        in_line = False
        start_y = 0
        
        for y, pixel_count in enumerate(horizontal_projection):
            if pixel_count > 5 and not in_line:  # Start of line
                start_y = y
                in_line = True
            elif pixel_count <= 5 and in_line:  # End of line
                if y - start_y >= self.min_line_height:  # Valid line height
                    line_boundaries.append((start_y, y))
                in_line = False
        
        # Handle case where last line goes to image bottom
        if in_line:
            line_boundaries.append((start_y, len(horizontal_projection) - 1))
        
        # Extract line segments
        lines = []
        for i, (y_start, y_end) in enumerate(line_boundaries):
            # Add some padding
            y_start = max(0, y_start - 5)
            y_end = min(binary_image.shape[0] - 1, y_end + 5)
            
            line_image = binary_image[y_start:y_end, :]
            
            # Remove empty columns at the sides
            vertical_projection = np.sum(line_image == 0, axis=0)
            non_empty_cols = np.where(vertical_projection > 0)[0]
            
            if len(non_empty_cols) > 0:
                x_start = non_empty_cols[0]
                x_end = non_empty_cols[-1] + 1
                line_image = line_image[:, x_start:x_end]
                
                lines.append(HandwritingSegment(
                    image=line_image,
                    bbox=(x_start, y_start, x_end - x_start, y_end - y_start),
                    segment_type="line",
                    confidence=0.9,
                    metadata={"line_index": i}
                ))
        
        # Calculate average line spacing
        line_spacing = 0.0
        if len(line_boundaries) > 1:
            spacings = []
            for i in range(len(line_boundaries) - 1):
                spacing = line_boundaries[i + 1][0] - line_boundaries[i][1]
                spacings.append(spacing)
            line_spacing = np.mean(spacings)
        
        return LineSegmentation(
            lines=lines,
            line_spacing=line_spacing,
            skew_angle=0.0,
            original_image=binary_image
        )
    
    async def _segment_words(self, line_image: np.ndarray) -> WordSegmentation:
        """Segment a line into words."""
        # Calculate vertical projection
        vertical_projection = np.sum(line_image == 0, axis=0)  # Count black pixels
        
        # Find word boundaries
        word_boundaries = []
        in_word = False
        start_x = 0
        
        for x, pixel_count in enumerate(vertical_projection):
            if pixel_count > 2 and not in_word:  # Start of word
                start_x = x
                in_word = True
            elif pixel_count <= 2 and in_word:  # End of word
                if x - start_x >= self.min_word_width:  # Valid word width
                    word_boundaries.append((start_x, x))
                in_word = False
        
        # Handle case where last word goes to image edge
        if in_word:
            word_boundaries.append((start_x, len(vertical_projection) - 1))
        
        # Extract word segments
        words = []
        for i, (x_start, x_end) in enumerate(word_boundaries):
            # Add some padding
            x_start = max(0, x_start - 2)
            x_end = min(line_image.shape[1] - 1, x_end + 2)
            
            word_image = line_image[:, x_start:x_end]
            
            words.append(HandwritingSegment(
                image=word_image,
                bbox=(x_start, 0, x_end - x_start, line_image.shape[0]),
                segment_type="word",
                confidence=0.8,
                metadata={"word_index": i}
            ))
        
        # Calculate average word spacing
        word_spacing = 0.0
        if len(word_boundaries) > 1:
            spacings = []
            for i in range(len(word_boundaries) - 1):
                spacing = word_boundaries[i + 1][0] - word_boundaries[i][1]
                spacings.append(spacing)
            word_spacing = np.mean(spacings)
        
        return WordSegmentation(
            words=words,
            word_spacing=word_spacing,
            line_segments=[]
        )
    
    async def _segment_characters(self, word_image: np.ndarray) -> List[HandwritingSegment]:
        """Segment a word into individual characters."""
        # This is a simplified character segmentation
        # In practice, you might use more sophisticated methods
        
        # Calculate vertical projection
        vertical_projection = np.sum(word_image == 0, axis=0)
        
        # Simple character segmentation based on projection minima
        chars = []
        
        # Find potential character boundaries
        boundaries = []
        min_char_width = 5
        
        # Use watershed or contour-based segmentation for better results
        contours, _ = cv2.findContours(word_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Sort contours by x-coordinate
        contours = sorted(contours, key=lambda c: cv2.boundingRect(c)[0])
        
        for i, contour in enumerate(contours):
            x, y, w, h = cv2.boundingRect(contour)
            
            if w >= min_char_width and h >= 5:  # Minimum character size
                char_image = word_image[y:y+h, x:x+w]
                
                chars.append(HandwritingSegment(
                    image=char_image,
                    bbox=(x, y, w, h),
                    segment_type="character",
                    confidence=0.7,
                    metadata={"character_index": i}
                ))
        
        return chars
    
    async def visualize_segmentation(
        self, 
        image: np.ndarray, 
        segments: List[HandwritingSegment],
        save_path: Optional[str] = None
    ) -> np.ndarray:
        """Visualize segmentation results."""
        # Create visualization
        vis_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR) if len(image.shape) == 2 else image.copy()
        
        # Draw bounding boxes for each segment
        colors = {
            "line": (0, 255, 0),      # Green for lines
            "word": (255, 0, 0),      # Blue for words
            "character": (0, 0, 255)   # Red for characters
        }
        
        for segment in segments:
            color = colors.get(segment.segment_type, (128, 128, 128))
            x, y, w, h = segment.bbox
            cv2.rectangle(vis_image, (x, y), (x + w, y + h), color, 2)
            
            # Add label
            label = f"{segment.segment_type}_{segment.metadata.get(f'{segment.segment_type}_index', 0)}"
            cv2.putText(vis_image, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        if save_path:
            cv2.imwrite(save_path, vis_image)
        
        return vis_image
    
    async def export_training_data(
        self,
        image: np.ndarray,
        ground_truth: str,
        output_dir: str,
        sample_id: str
    ) -> Dict[str, Any]:
        """Export preprocessed data for training."""
        import os
        import json
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Preprocess image
        results = await self.preprocess_handwriting(image, "line_recognition")
        
        # Save preprocessed image
        preprocessed_path = os.path.join(output_dir, f"{sample_id}_preprocessed.png")
        cv2.imwrite(preprocessed_path, results["preprocessed_image"])
        
        # Save line segments
        line_paths = []
        for i, line_segment in enumerate(results["line_segments"]):
            line_path = os.path.join(output_dir, f"{sample_id}_line_{i}.png")
            cv2.imwrite(line_path, line_segment.image)
            line_paths.append(line_path)
        
        # Save metadata
        metadata = {
            "sample_id": sample_id,
            "ground_truth": ground_truth,
            "preprocessed_image": preprocessed_path,
            "line_segments": line_paths,
            "preprocessing_metadata": results["metadata"],
            "config": self.config
        }
        
        metadata_path = os.path.join(output_dir, f"{sample_id}_metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "preprocessed_image": preprocessed_path,
            "line_segments": line_paths,
            "metadata_file": metadata_path,
            "line_count": len(results["line_segments"])
        }