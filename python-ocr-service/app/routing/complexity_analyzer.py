"""
Document Complexity Analyzer

Analyzes document images to determine complexity and route to appropriate OCR engine.
Routes simple documents to TrOCR (fast) and complex documents to DeepSeek (accurate).
"""

from pathlib import Path
from typing import Dict, Literal, Tuple
import cv2
import numpy as np
from PIL import Image
from dataclasses import dataclass


@dataclass
class ComplexityScore:
    """Document complexity assessment"""
    score: float  # 0-1, where 1 is most complex
    has_tables: bool
    has_multi_column: bool
    has_graphics: bool
    text_density: float
    recommended_engine: Literal["trocr", "deepseek"]
    confidence: float
    
    def to_dict(self) -> Dict:
        return {
            "complexity_score": self.score,
            "has_tables": self.has_tables,
            "has_multi_column": self.has_multi_column,
            "has_graphics": self.has_graphics,
            "text_density": self.text_density,
            "recommended_engine": self.recommended_engine,
            "confidence": self.confidence
        }


class DocumentComplexityAnalyzer:
    """
    Analyzes document images to determine routing strategy.
    
    Uses computer vision techniques to detect:
    - Tables and grids
    - Multi-column layouts
    - Graphics and images
    - Text density and distribution
    
    Complexity scoring:
    - 0.0-0.3: Simple (single column, plain text) → TrOCR
    - 0.3-0.7: Moderate (some structure) → DeepSeek if important
    - 0.7-1.0: Complex (tables, multi-column) → DeepSeek
    """
    
    def __init__(
        self,
        simple_threshold: float = 0.3,
        complex_threshold: float = 0.6
    ):
        """
        Initialize analyzer with thresholds.
        
        Args:
            simple_threshold: Below this = simple (use TrOCR)
            complex_threshold: Above this = complex (use DeepSeek)
        """
        self.simple_threshold = simple_threshold
        self.complex_threshold = complex_threshold
    
    def analyze(self, image_path: Path) -> ComplexityScore:
        """
        Analyze document and return complexity score.
        
        Args:
            image_path: Path to document image
            
        Returns:
            ComplexityScore with analysis results
        """
        # Load image
        image = Image.open(image_path).convert('RGB')
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        # Run detection algorithms
        has_tables, table_confidence = self._detect_tables(gray)
        has_multi_column, column_confidence = self._detect_columns(gray)
        has_graphics, graphics_confidence = self._detect_graphics(cv_image)
        text_density = self._calculate_text_density(gray)
        
        # Calculate overall complexity score
        complexity_score = self._calculate_complexity(
            has_tables=has_tables,
            has_multi_column=has_multi_column,
            has_graphics=has_graphics,
            text_density=text_density,
            table_conf=table_confidence,
            column_conf=column_confidence
        )
        
        # Determine recommended engine
        if complexity_score < self.simple_threshold:
            recommended_engine = "trocr"
            confidence = 1.0 - complexity_score
        elif complexity_score > self.complex_threshold:
            recommended_engine = "deepseek"
            confidence = complexity_score
        else:
            # Moderate complexity - prefer DeepSeek if tables detected
            if has_tables or has_multi_column:
                recommended_engine = "deepseek"
                confidence = 0.7
            else:
                recommended_engine = "trocr"
                confidence = 0.6
        
        return ComplexityScore(
            score=complexity_score,
            has_tables=has_tables,
            has_multi_column=has_multi_column,
            has_graphics=has_graphics,
            text_density=text_density,
            recommended_engine=recommended_engine,
            confidence=confidence
        )
    
    def _detect_tables(self, gray_image: np.ndarray) -> Tuple[bool, float]:
        """
        Detect presence of tables using line detection.
        
        Args:
            gray_image: Grayscale image
            
        Returns:
            Tuple of (has_tables, confidence)
        """
        # Detect horizontal and vertical lines
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        
        # Threshold
        _, binary = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Detect lines
        horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
        
        # Count line intersections (table grid)
        h_count = cv2.countNonZero(horizontal_lines)
        v_count = cv2.countNonZero(vertical_lines)
        
        # If significant horizontal AND vertical lines exist, likely a table
        h_ratio = h_count / (gray_image.shape[0] * gray_image.shape[1])
        v_ratio = v_count / (gray_image.shape[0] * gray_image.shape[1])
        
        # Table detection heuristic
        has_table = (h_ratio > 0.005 and v_ratio > 0.005)
        confidence = min((h_ratio + v_ratio) * 50, 1.0) if has_table else 0.0
        
        return has_table, confidence
    
    def _detect_columns(self, gray_image: np.ndarray) -> Tuple[bool, float]:
        """
        Detect multi-column layout using vertical projection.
        
        Args:
            gray_image: Grayscale image
            
        Returns:
            Tuple of (has_multi_column, confidence)
        """
        # Binarize
        _, binary = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Vertical projection (sum along columns)
        vertical_projection = np.sum(binary, axis=0)
        
        # Smooth projection
        kernel_size = max(3, len(vertical_projection) // 100)
        if kernel_size % 2 == 0:
            kernel_size += 1
        smoothed = cv2.GaussianBlur(vertical_projection.reshape(1, -1), (kernel_size, 1), 0).flatten()
        
        # Find valleys (column separators) - low values in projection
        mean_val = np.mean(smoothed)
        valleys = smoothed < (mean_val * 0.3)
        
        # Count significant valleys (potential column separators)
        valley_regions = self._find_regions(valleys, min_width=20)
        
        # Multi-column if we have clear separators
        has_multi_column = len(valley_regions) >= 1
        confidence = min(len(valley_regions) * 0.3, 1.0)
        
        return has_multi_column, confidence
    
    def _detect_graphics(self, color_image: np.ndarray) -> Tuple[bool, float]:
        """
        Detect presence of graphics/images (not text).
        
        Args:
            color_image: Color image
            
        Returns:
            Tuple of (has_graphics, confidence)
        """
        # Convert to grayscale
        gray = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)
        
        # Calculate color variance (graphics tend to have more color variation)
        color_std = np.std(color_image, axis=2).mean()
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        # High edge density with color variation suggests graphics
        has_graphics = (edge_density > 0.1 and color_std > 20)
        confidence = min((edge_density * 5 + color_std / 50) / 2, 1.0) if has_graphics else 0.0
        
        return has_graphics, confidence
    
    def _calculate_text_density(self, gray_image: np.ndarray) -> float:
        """
        Calculate text density (ratio of text pixels to total).
        
        Args:
            gray_image: Grayscale image
            
        Returns:
            Text density ratio (0-1)
        """
        # Binarize
        _, binary = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Text density
        text_pixels = np.sum(binary > 0)
        total_pixels = binary.size
        
        density = text_pixels / total_pixels
        return min(density, 1.0)
    
    def _find_regions(self, boolean_array: np.ndarray, min_width: int = 10) -> list:
        """
        Find continuous True regions in boolean array.
        
        Args:
            boolean_array: 1D boolean array
            min_width: Minimum region width to count
            
        Returns:
            List of (start, end) tuples for each region
        """
        regions = []
        in_region = False
        start = 0
        
        for i, val in enumerate(boolean_array):
            if val and not in_region:
                start = i
                in_region = True
            elif not val and in_region:
                if i - start >= min_width:
                    regions.append((start, i))
                in_region = False
        
        # Handle case where region extends to end
        if in_region and len(boolean_array) - start >= min_width:
            regions.append((start, len(boolean_array)))
        
        return regions
    
    def _calculate_complexity(
        self,
        has_tables: bool,
        has_multi_column: bool,
        has_graphics: bool,
        text_density: float,
        table_conf: float,
        column_conf: float
    ) -> float:
        """
        Calculate overall complexity score.
        
        Scoring weights:
        - Tables: 0.4 (most important for routing)
        - Multi-column: 0.3
        - Graphics: 0.1
        - Text density variance: 0.2
        
        Args:
            has_tables: Table detection result
            has_multi_column: Column detection result
            has_graphics: Graphics detection result
            text_density: Text density ratio
            table_conf: Table detection confidence
            column_conf: Column detection confidence
            
        Returns:
            Complexity score (0-1)
        """
        score = 0.0
        
        # Tables are strong indicator of complexity
        if has_tables:
            score += 0.4 * table_conf
        
        # Multi-column layouts need DeepSeek
        if has_multi_column:
            score += 0.3 * column_conf
        
        # Graphics add some complexity
        if has_graphics:
            score += 0.1
        
        # Very high or very low text density indicates complexity
        # Normal density is around 0.1-0.3 for typical documents
        if text_density < 0.05 or text_density > 0.4:
            score += 0.2
        
        return min(score, 1.0)


def analyze_document_complexity(image_path: Path) -> ComplexityScore:
    """
    Convenience function to analyze document complexity.
    
    Args:
        image_path: Path to document image
        
    Returns:
        ComplexityScore with routing recommendation
    """
    analyzer = DocumentComplexityAnalyzer()
    return analyzer.analyze(image_path)
