"""
Mixed Document Detector for ICR Service

Detects documents containing both printed and handwritten text.
Routes printed regions to OCR (preferably DeepSeek) and handwritten regions to ICR.
Combines results into a unified output.

Use Cases:
- Forms with printed labels + handwritten answers
- Invoices with printed items + handwritten notes
- Contracts with printed text + handwritten signatures/amendments
- Partially filled forms
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import httpx
import asyncio


class RegionType(str, Enum):
    """Type of text region"""
    PRINTED = "printed"
    HANDWRITTEN = "handwritten"
    MIXED = "mixed"
    SIGNATURE = "signature"
    UNKNOWN = "unknown"


@dataclass
class TextRegion:
    """A region of text in the document"""
    type: RegionType
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    confidence: float
    image_crop: Optional[np.ndarray] = None
    text: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "bbox": {"x": self.bbox[0], "y": self.bbox[1], "width": self.bbox[2], "height": self.bbox[3]},
            "confidence": self.confidence,
            "text": self.text,
            "metadata": self.metadata
        }


@dataclass
class MixedDocumentAnalysis:
    """Analysis result for mixed documents"""
    is_mixed: bool
    printed_regions: List[TextRegion]
    handwritten_regions: List[TextRegion]
    signature_regions: List[TextRegion]
    overall_confidence: float
    processing_strategy: str  # "ocr_only", "icr_only", "hybrid"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_mixed": self.is_mixed,
            "printed_count": len(self.printed_regions),
            "handwritten_count": len(self.handwritten_regions),
            "signature_count": len(self.signature_regions),
            "total_regions": len(self.printed_regions) + len(self.handwritten_regions) + len(self.signature_regions),
            "overall_confidence": self.overall_confidence,
            "processing_strategy": self.processing_strategy,
            "printed_regions": [r.to_dict() for r in self.printed_regions],
            "handwritten_regions": [r.to_dict() for r in self.handwritten_regions],
            "signature_regions": [r.to_dict() for r in self.signature_regions],
        }


class MixedDocumentDetector:
    """
    Detect and classify text regions as printed or handwritten.
    
    Uses computer vision techniques:
    - Edge analysis (printed = sharp, handwritten = varied)
    - Stroke width analysis (printed = uniform, handwritten = varied)
    - Text line straightness (printed = straight, handwritten = curved)
    - Character spacing (printed = consistent, handwritten = irregular)
    """
    
    def __init__(
        self,
        min_region_size: int = 20,
        handwriting_threshold: float = 0.6
    ):
        """
        Initialize detector.
        
        Args:
            min_region_size: Minimum size for a valid region
            handwriting_threshold: Score above this = handwritten
        """
        self.min_region_size = min_region_size
        self.handwriting_threshold = handwriting_threshold
    
    def analyze(self, image: np.ndarray) -> MixedDocumentAnalysis:
        """
        Analyze image for mixed content.
        
        Args:
            image: Input document image (BGR format)
            
        Returns:
            MixedDocumentAnalysis with detected regions
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Find text regions
        text_regions = self._find_text_regions(gray)
        
        # Classify each region
        printed_regions = []
        handwritten_regions = []
        signature_regions = []
        
        for region in text_regions:
            x, y, w, h = region
            
            # Extract region
            roi = gray[y:y+h, x:x+w]
            
            # Classify region
            region_type, confidence = self._classify_region(roi)
            
            text_region = TextRegion(
                type=region_type,
                bbox=(x, y, w, h),
                confidence=confidence,
                image_crop=roi
            )
            
            if region_type == RegionType.PRINTED:
                printed_regions.append(text_region)
            elif region_type == RegionType.HANDWRITTEN:
                handwritten_regions.append(text_region)
            elif region_type == RegionType.SIGNATURE:
                signature_regions.append(text_region)
        
        # Determine if mixed
        is_mixed = (
            len(printed_regions) > 0 and 
            (len(handwritten_regions) > 0 or len(signature_regions) > 0)
        )
        
        # Determine processing strategy
        if is_mixed:
            strategy = "hybrid"
        elif len(printed_regions) > 0:
            strategy = "ocr_only"
        elif len(handwritten_regions) > 0 or len(signature_regions) > 0:
            strategy = "icr_only"
        else:
            strategy = "ocr_only"  # Default
        
        # Calculate overall confidence
        all_confidences = (
            [r.confidence for r in printed_regions] +
            [r.confidence for r in handwritten_regions] +
            [r.confidence for r in signature_regions]
        )
        overall_confidence = np.mean(all_confidences) if all_confidences else 0.0
        
        return MixedDocumentAnalysis(
            is_mixed=is_mixed,
            printed_regions=printed_regions,
            handwritten_regions=handwritten_regions,
            signature_regions=signature_regions,
            overall_confidence=float(overall_confidence),
            processing_strategy=strategy
        )
    
    def _find_text_regions(self, gray: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Find potential text regions using contours"""
        # Threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Morphological operations to group text
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
        dilated = cv2.morphologyEx(binary, cv2.MORPH_DILATE, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter and return bounding boxes
        regions = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter small regions
            if w >= self.min_region_size and h >= self.min_region_size:
                # Filter regions that are too wide/short (likely not text)
                aspect_ratio = w / h
                if 0.1 < aspect_ratio < 50:
                    regions.append((x, y, w, h))
        
        return regions
    
    def _classify_region(self, roi: np.ndarray) -> Tuple[RegionType, float]:
        """
        Classify a region as printed or handwritten.
        
        Args:
            roi: Region of interest (grayscale)
            
        Returns:
            Tuple of (RegionType, confidence)
        """
        # Extract features
        edge_variance = self._calculate_edge_variance(roi)
        stroke_variance = self._calculate_stroke_variance(roi)
        straightness = self._calculate_text_straightness(roi)
        aspect_ratio = roi.shape[1] / roi.shape[0]
        
        # Handwriting characteristics:
        # - Higher edge variance (irregular edges)
        # - Higher stroke width variance
        # - Lower straightness (curved lines)
        # - Often smaller aspect ratio for signatures
        
        handwriting_score = 0.0
        
        # Edge variance (0-0.3)
        if edge_variance > 30:
            handwriting_score += 0.3
        elif edge_variance > 20:
            handwriting_score += 0.15
        
        # Stroke variance (0-0.3)
        if stroke_variance > 5:
            handwriting_score += 0.3
        elif stroke_variance > 3:
            handwriting_score += 0.15
        
        # Straightness (0-0.2)
        if straightness < 0.7:
            handwriting_score += 0.2
        elif straightness < 0.85:
            handwriting_score += 0.1
        
        # Aspect ratio for signature detection (0-0.2)
        if 1.5 < aspect_ratio < 5 and handwriting_score > 0.4:
            # Likely signature
            handwriting_score += 0.2
            is_signature = True
        else:
            is_signature = False
        
        # Classify
        if handwriting_score >= self.handwriting_threshold:
            if is_signature:
                region_type = RegionType.SIGNATURE
            else:
                region_type = RegionType.HANDWRITTEN
            confidence = handwriting_score
        else:
            region_type = RegionType.PRINTED
            confidence = 1.0 - handwriting_score
        
        return region_type, confidence
    
    def _calculate_edge_variance(self, roi: np.ndarray) -> float:
        """Calculate edge variance (higher = more irregular = handwritten)"""
        edges = cv2.Canny(roi, 50, 150)
        edge_pixels = edges[edges > 0]
        
        if len(edge_pixels) == 0:
            return 0.0
        
        # Calculate variance of edge positions
        edge_positions = np.where(edges > 0)
        variance = np.var(edge_positions[1]) if len(edge_positions[1]) > 0 else 0.0
        
        return float(variance)
    
    def _calculate_stroke_variance(self, roi: np.ndarray) -> float:
        """Calculate stroke width variance (higher = handwritten)"""
        # Distance transform to get stroke widths
        _, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        dist_transform = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
        
        # Get stroke widths (distance from edge)
        stroke_widths = dist_transform[dist_transform > 0]
        
        if len(stroke_widths) == 0:
            return 0.0
        
        variance = np.var(stroke_widths)
        return float(variance)
    
    def _calculate_text_straightness(self, roi: np.ndarray) -> float:
        """Calculate text line straightness (lower = curved = handwritten)"""
        # Find horizontal projection
        _, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        horizontal_proj = np.sum(binary, axis=1)
        
        # Find peaks (text lines)
        mean_proj = np.mean(horizontal_proj)
        peaks = horizontal_proj > (mean_proj * 1.5)
        
        if not np.any(peaks):
            return 1.0  # No text found, assume straight
        
        # Calculate standard deviation of peak positions
        peak_indices = np.where(peaks)[0]
        if len(peak_indices) < 2:
            return 1.0
        
        # Fit line to peaks
        x = np.arange(len(horizontal_proj))
        y = horizontal_proj
        
        # Calculate deviation from fitted line
        coeffs = np.polyfit(peak_indices, horizontal_proj[peak_indices], 1)
        fitted_line = coeffs[0] * x + coeffs[1]
        deviation = np.mean(np.abs(y - fitted_line))
        
        # Normalize (0 = very curved, 1 = perfectly straight)
        straightness = 1.0 / (1.0 + deviation / 100)
        
        return float(straightness)


async def process_mixed_document(
    image: np.ndarray,
    ocr_service_url: str = "http://127.0.0.1:8000",
    icr_service_url: str = "http://127.0.0.1:8002"
) -> Dict[str, Any]:
    """
    Process a mixed document using both OCR and ICR services.
    
    Args:
        image: Document image
        ocr_service_url: URL of OCR service
        icr_service_url: URL of ICR service
        
    Returns:
        Combined results from both services
    """
    detector = MixedDocumentDetector()
    analysis = detector.analyze(image)
    
    results = {
        "analysis": analysis.to_dict(),
        "text": "",
        "regions": []
    }
    
    # Process printed regions with OCR if any
    if analysis.printed_regions:
        # For now, send whole image to OCR service
        # In production, could send individual regions
        pass  # OCR integration would go here
    
    # Process handwritten regions with ICR
    if analysis.handwritten_regions or analysis.signature_regions:
        # Process with ICR
        pass  # ICR integration would go here
    
    return results


def detect_mixed_document(image_path: Path) -> MixedDocumentAnalysis:
    """
    Convenience function to detect mixed documents.
    
    Args:
        image_path: Path to document image
        
    Returns:
        MixedDocumentAnalysis
    """
    import cv2
    image = cv2.imread(str(image_path))
    detector = MixedDocumentDetector()
    return detector.analyze(image)
