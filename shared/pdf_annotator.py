"""
PDF Annotator - Creates Enhanced PDF Copies

Creates annotated PDFs with:
- Extracted text overlaid in original positions
- Signature boxes highlighted and copied
- Handwritten regions shown as margin comments
- Auto-generated filename based on document title
- Saved alongside original for comparison
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import cv2
import numpy as np
from PIL import Image
from datetime import datetime
import re

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor, Color
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class PDFAnnotator:
    """
    Creates annotated PDF copies with OCR/ICR results overlaid.
    
    Features:
    - Overlays extracted text at original positions
    - Highlights signature regions with boxes
    - Adds handwritten text as right-margin comments
    - Generates title from document content
    - Saves alongside original with descriptive name
    """
    
    def __init__(self):
        self.signature_color = (255, 0, 0)  # Red for signatures
        self.handwritten_color = (0, 180, 0)  # Green for handwriting
        self.printed_color = (0, 100, 255)  # Blue for printed text
        self.comment_width = 200  # Width of right margin for comments
    
    def create_annotated_pdf(
        self,
        original_path: Path,
        ocr_text: str,
        regions: List[Dict[str, Any]],
        output_dir: Optional[Path] = None,
        title_override: Optional[str] = None
    ) -> Path:
        """
        Create annotated PDF copy.
        
        Args:
            original_path: Path to original PDF/image
            ocr_text: Extracted text from OCR
            regions: List of detected regions with text and bboxes
            output_dir: Output directory (defaults to same as original)
            title_override: Custom title (auto-detected if None)
            
        Returns:
            Path to created annotated PDF
        """
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF (fitz) required: pip install PyMuPDF")
        
        # Determine output directory
        if output_dir is None:
            output_dir = original_path.parent
        
        # Extract document title
        if title_override:
            title = title_override
        else:
            title = self._extract_title(ocr_text)
        
        # Generate output filename
        output_path = self._generate_output_path(original_path, title, output_dir)
        
        # Convert to PDF if image
        if original_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
            pdf_path = self._image_to_pdf(original_path)
            is_temp_pdf = True
        else:
            pdf_path = original_path
            is_temp_pdf = False
        
        # Open original PDF
        doc = fitz.open(pdf_path)
        
        try:
            # Process each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Add right margin for comments
                self._add_comment_margin(page)
                
                # Process regions
                self._annotate_regions(page, regions, page_num)
                
                # Add header with metadata
                self._add_header(page, title)
            
            # Save annotated PDF
            doc.save(str(output_path))
            doc.close()
            
            print(f"✅ Annotated PDF created: {output_path}")
            return output_path
            
        finally:
            # Cleanup temp PDF if created
            if is_temp_pdf and pdf_path.exists():
                pdf_path.unlink()
    
    def _extract_title(self, text: str) -> str:
        """
        Extract document title from OCR text.
        
        Looks for:
        - First H1 header (# Title)
        - First line if it looks like a title
        - "Invoice #12345" patterns
        - Default to timestamp if nothing found
        """
        lines = text.strip().split('\n')
        
        # Check for markdown H1
        for line in lines[:5]:
            if line.strip().startswith('# '):
                title = line.replace('#', '').strip()
                if title:
                    return self._sanitize_filename(title[:50])
        
        # Check for invoice/document number patterns
        invoice_patterns = [
            r'Invoice\s*[#:]?\s*(\w+)',
            r'Document\s*[#:]?\s*(\w+)',
            r'Receipt\s*[#:]?\s*(\w+)',
            r'Order\s*[#:]?\s*(\w+)',
            r'Bill\s*[#:]?\s*(\w+)',
        ]
        
        for pattern in invoice_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                doc_type = pattern.split(r'\s')[0].replace('\\', '')
                doc_num = match.group(1)
                return self._sanitize_filename(f"{doc_type}_{doc_num}")
        
        # Use first non-empty line if it's short (likely a title)
        for line in lines[:3]:
            cleaned = line.strip().replace('#', '').replace('|', '').strip()
            if cleaned and len(cleaned) < 60 and not cleaned.startswith('-'):
                return self._sanitize_filename(cleaned[:50])
        
        # Default: use timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"Document_{timestamp}"
    
    def _sanitize_filename(self, name: str) -> str:
        """Remove invalid filename characters"""
        # Remove invalid characters
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        # Replace spaces with underscores
        name = name.replace(' ', '_')
        # Remove multiple underscores
        name = re.sub(r'_+', '_', name)
        # Trim
        name = name.strip('_')
        return name or "Document"
    
    def _generate_output_path(
        self,
        original_path: Path,
        title: str,
        output_dir: Path
    ) -> Path:
        """Generate unique output path"""
        base_name = f"{title}_annotated"
        output_path = output_dir / f"{base_name}.pdf"
        
        # Ensure unique filename
        counter = 1
        while output_path.exists():
            output_path = output_dir / f"{base_name}_{counter}.pdf"
            counter += 1
        
        return output_path
    
    def _image_to_pdf(self, image_path: Path) -> Path:
        """Convert image to temporary PDF"""
        img = Image.open(image_path)
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Create temporary PDF
        temp_pdf = image_path.parent / f"{image_path.stem}_temp.pdf"
        img.save(temp_pdf, "PDF", resolution=100.0)
        
        return temp_pdf
    
    def _add_comment_margin(self, page: fitz.Page):
        """Add right margin area for handwritten comments"""
        rect = page.rect
        
        # Draw vertical line to separate comment area
        line_x = rect.width - self.comment_width
        page.draw_line(
            (line_x, 0),
            (line_x, rect.height),
            color=(0.7, 0.7, 0.7),
            width=1
        )
        
        # Add "Handwritten Notes" header in margin
        header_rect = fitz.Rect(
            line_x + 5,
            10,
            rect.width - 5,
            30
        )
        page.insert_textbox(
            header_rect,
            "Handwritten Notes",
            fontsize=10,
            color=(0.3, 0.3, 0.3),
            align=fitz.TEXT_ALIGN_CENTER
        )
    
    def _annotate_regions(
        self,
        page: fitz.Page,
        regions: List[Dict[str, Any]],
        page_num: int
    ):
        """Annotate page with detected regions"""
        page_rect = page.rect
        comment_x = page_rect.width - self.comment_width
        comment_y = 40  # Start below header
        
        for region in regions:
            region_type = region.get('type', 'unknown')
            text = region.get('text', '')
            bbox = region.get('bbox', {})
            confidence = region.get('confidence', 0.0)
            
            # Skip if no bbox or wrong page
            if not bbox or region.get('page', 0) != page_num:
                continue
            
            # Convert bbox to fitz.Rect
            x = bbox.get('x', 0)
            y = bbox.get('y', 0)
            w = bbox.get('width', 100)
            h = bbox.get('height', 20)
            rect = fitz.Rect(x, y, x + w, y + h)
            
            if region_type == 'signature':
                self._annotate_signature(page, rect, text, confidence)
            
            elif region_type == 'handwritten':
                # Draw box around handwritten region
                self._draw_region_box(page, rect, self.handwritten_color, "Handwriting")
                
                # Add as comment in right margin
                comment_y = self._add_margin_comment(
                    page, text, comment_x, comment_y, self.handwritten_color
                )
            
            elif region_type == 'printed':
                # Overlay text in original position
                self._overlay_text(page, rect, text, self.printed_color, confidence)
    
    def _annotate_signature(
        self,
        page: fitz.Page,
        rect: fitz.Rect,
        text: str,
        confidence: float
    ):
        """Highlight signature region"""
        # Draw red box around signature
        page.draw_rect(
            rect,
            color=self._color_to_fitz(self.signature_color),
            width=2
        )
        
        # Add semi-transparent red fill
        page.draw_rect(
            rect,
            color=self._color_to_fitz(self.signature_color),
            fill=self._color_to_fitz(self.signature_color),
            fill_opacity=0.1
        )
        
        # Add label above signature
        label_rect = fitz.Rect(
            rect.x0,
            rect.y0 - 15,
            rect.x1,
            rect.y0
        )
        page.insert_textbox(
            label_rect,
            f"SIGNATURE ({confidence:.0%})",
            fontsize=8,
            color=(1, 0, 0),
            align=fitz.TEXT_ALIGN_CENTER
        )
    
    def _draw_region_box(
        self,
        page: fitz.Page,
        rect: fitz.Rect,
        color: Tuple[int, int, int],
        label: str
    ):
        """Draw box around detected region"""
        fitz_color = self._color_to_fitz(color)
        
        page.draw_rect(
            rect,
            color=fitz_color,
            width=1.5
        )
        
        # Add semi-transparent fill
        page.draw_rect(
            rect,
            fill=fitz_color,
            fill_opacity=0.05
        )
    
    def _overlay_text(
        self,
        page: fitz.Page,
        rect: fitz.Rect,
        text: str,
        color: Tuple[int, int, int],
        confidence: float
    ):
        """Overlay extracted text at original position"""
        if not text.strip():
            return
        
        # Draw light background box
        page.draw_rect(
            rect,
            fill=(1, 1, 0.9),  # Light yellow
            fill_opacity=0.3
        )
        
        # Insert text
        fontsize = min(rect.height * 0.6, 12)
        page.insert_textbox(
            rect,
            text,
            fontsize=fontsize,
            color=self._color_to_fitz(color),
            align=fitz.TEXT_ALIGN_LEFT
        )
        
        # Add small confidence indicator
        if confidence > 0:
            conf_text = f"{confidence:.0%}"
            conf_rect = fitz.Rect(
                rect.x1 - 30,
                rect.y0,
                rect.x1,
                rect.y0 + 10
            )
            page.insert_textbox(
                conf_rect,
                conf_text,
                fontsize=6,
                color=(0.5, 0.5, 0.5),
                align=fitz.TEXT_ALIGN_RIGHT
            )
    
    def _add_margin_comment(
        self,
        page: fitz.Page,
        text: str,
        x: float,
        y: float,
        color: Tuple[int, int, int]
    ) -> float:
        """Add handwritten text as margin comment"""
        if not text.strip():
            return y
        
        page_rect = page.rect
        comment_rect = fitz.Rect(
            x + 5,
            y,
            page_rect.width - 5,
            y + 60  # Approximate height
        )
        
        # Draw comment box
        page.draw_rect(
            comment_rect,
            color=self._color_to_fitz(color),
            width=0.5
        )
        
        # Add text
        page.insert_textbox(
            comment_rect,
            text[:100],  # Truncate if too long
            fontsize=8,
            color=self._color_to_fitz(color),
            align=fitz.TEXT_ALIGN_LEFT
        )
        
        return y + 65  # Return new y position
    
    def _add_header(self, page: fitz.Page, title: str):
        """Add header with document info"""
        rect = page.rect
        
        # Add title at top
        title_rect = fitz.Rect(10, 5, rect.width - self.comment_width - 10, 25)
        page.insert_textbox(
            title_rect,
            title,
            fontsize=14,
            color=(0, 0, 0.5),
            align=fitz.TEXT_ALIGN_LEFT
        )
        
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        timestamp_rect = fitz.Rect(10, 25, rect.width - self.comment_width - 10, 35)
        page.insert_textbox(
            timestamp_rect,
            f"Annotated: {timestamp}",
            fontsize=8,
            color=(0.5, 0.5, 0.5),
            align=fitz.TEXT_ALIGN_LEFT
        )
    
    def _color_to_fitz(self, color: Tuple[int, int, int]) -> Tuple[float, float, float]:
        """Convert RGB (0-255) to PyMuPDF color (0-1)"""
        return (color[0] / 255, color[1] / 255, color[2] / 255)


def annotate_hybrid_result(
    original_path: Path,
    hybrid_result: Dict[str, Any],
    output_dir: Optional[Path] = None
) -> Path:
    """
    Create annotated PDF from hybrid OCR/ICR result.
    
    Args:
        original_path: Path to original document
        hybrid_result: Result from /hybrid/process endpoint
        output_dir: Output directory (optional)
        
    Returns:
        Path to annotated PDF
    """
    annotator = PDFAnnotator()
    
    # Extract data from hybrid result
    combined_text = hybrid_result.get('combined_text', '')
    regions = hybrid_result.get('regions', [])
    
    # Create annotated PDF
    return annotator.create_annotated_pdf(
        original_path=original_path,
        ocr_text=combined_text,
        regions=regions,
        output_dir=output_dir
    )


def annotate_ocr_result(
    original_path: Path,
    ocr_result: Dict[str, Any],
    output_dir: Optional[Path] = None
) -> Path:
    """
    Create annotated PDF from OCR result.
    
    Args:
        original_path: Path to original document
        ocr_result: Result from /ocr/process endpoint
        output_dir: Output directory (optional)
        
    Returns:
        Path to annotated PDF
    """
    annotator = PDFAnnotator()
    
    text = ocr_result.get('text', '')
    
    # Create simple region for full text
    regions = [{
        'type': 'printed',
        'text': text,
        'bbox': {'x': 50, 'y': 50, 'width': 500, 'height': 700},
        'confidence': ocr_result.get('confidence', 0.9)
    }]
    
    return annotator.create_annotated_pdf(
        original_path=original_path,
        ocr_text=text,
        regions=regions,
        output_dir=output_dir
    )
