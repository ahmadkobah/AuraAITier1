# PDF Annotation Feature Guide

## Overview

The document processing system now automatically creates **annotated PDF copies** of your processed documents. These annotated PDFs visually show:

- **Extracted text** overlaid at original positions (blue highlighting)
- **Signature regions** highlighted with red boxes
- **Handwritten text** displayed as margin comments (green)
- **Auto-generated filenames** based on document titles
- **Both original and annotated** versions saved in the same directory

## How It Works

### Automatic Creation

By default, when you process a document through OCR or ICR services, an annotated PDF is automatically created:

```python
# OCR Service Example
import requests

with open("invoice.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/ocr/process",
        files={"file": f}
    )

result = response.json()
print(f"Original: invoice.pdf")
print(f"Annotated: {result['annotated_pdf']}")
# Output: Annotated: C:\path\to\Invoice_12345_annotated.pdf
```

```python
# ICR Service Example (Hybrid Processing)
with open("mixed_document.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8002/hybrid/process",
        files={"file": f}
    )

result = response.json()
print(f"Annotated PDF: {result['annotated_pdf']}")
# Output shows signatures, handwriting, and printed text
```

### Disable Annotation

If you don't want annotated PDFs:

```python
response = requests.post(
    "http://localhost:8000/ocr/process",
    files={"file": f},
    data={"create_annotated_pdf": "false"}
)
```

## Annotation Features

### 1. Text Overlay
- **Printed text** extracted by OCR is overlaid at the **exact original position**
- Light **blue highlighting** (0, 100, 255) with semi-transparent background
- Original document remains visible underneath

### 2. Signature Detection
- Signature boxes highlighted with **red borders** (255, 0, 0)
- Semi-transparent red fill (10% opacity)
- Label: "SIGNATURE" in red text
- Box positioned exactly where signature was detected

### 3. Handwritten Comments
- Handwritten text appears in **200px right margin**
- Green color coding (0, 180, 0)
- Doesn't obscure original document
- Vertical separator line between document and margin
- Each handwritten region listed separately

### 4. Document Title Header
- Auto-detected title at top of page
- Timestamp showing when processed
- Format: `Title: {detected_title} | Processed: {timestamp}`

### 5. Auto-Generated Filenames
- Title extracted from document content:
  * **H1 headers** (markdown documents)
  * **Invoice patterns**: "Invoice #12345", "Document #ABC", "Receipt #999"
  * **First line** if above fail
  * **Timestamp** as fallback
- Sanitized for filesystem (no special chars)
- Unique numbering if file exists: `Invoice_12345_annotated_2.pdf`

## File Organization

```
/path/to/documents/
├── invoice_original.pdf        # Your original file
└── Invoice_12345_annotated.pdf # Auto-generated annotated version
```

Both files are kept so you can:
- Compare original vs. extracted
- Verify detection accuracy
- Use annotated version for reports/audits
- Keep original pristine

## Color Coding Reference

| Element | Color | RGB | Purpose |
|---------|-------|-----|---------|
| Printed Text | Blue | (0, 100, 255) | OCR extracted text |
| Signatures | Red | (255, 0, 0) | Signature region boxes |
| Handwriting | Green | (0, 180, 0) | ICR extracted handwriting |

## Title Detection Examples

The system automatically detects document titles from:

1. **Markdown Headers**:
   ```
   # Monthly Report
   → Filename: Monthly_Report_annotated.pdf
   ```

2. **Invoice Patterns**:
   ```
   Invoice #12345
   → Filename: Invoice_12345_annotated.pdf
   ```

3. **Document Numbers**:
   ```
   Document #ABC-2024-001
   → Filename: Document_ABC-2024-001_annotated.pdf
   ```

4. **First Line**:
   ```
   Client Proposal for XYZ Corp
   → Filename: Client_Proposal_for_XYZ_Corp_annotated.pdf
   ```

5. **Fallback**:
   ```
   (no clear title)
   → Filename: Processed_20240115_143022_annotated.pdf
   ```

## API Response Format

### OCR Service Response

```json
{
  "text": "Extracted text content...",
  "confidence": 0.92,
  "metadata": {
    "engine_used": "deepseek",
    "routing_decision": {...}
  },
  "processing_time": 2.34,
  "engine": "deepseek",
  "annotated_pdf": "C:\\path\\to\\Invoice_12345_annotated.pdf"
}
```

### ICR Hybrid Service Response

```json
{
  "regions": [
    {
      "type": "printed",
      "bbox": [100, 200, 500, 250],
      "text": "Invoice #12345",
      "confidence": 0.95
    },
    {
      "type": "signature",
      "bbox": [100, 800, 300, 900],
      "confidence": 0.88
    },
    {
      "type": "handwritten",
      "bbox": [400, 850, 600, 900],
      "text": "Approved by John",
      "confidence": 0.82
    }
  ],
  "annotated_pdf": "C:\\path\\to\\Invoice_12345_annotated.pdf",
  "processing_time": 3.45
}
```

## Error Handling

If PDF annotation fails, processing continues and error is returned:

```json
{
  "text": "...",
  "annotated_pdf": null,
  "annotated_pdf_error": "PyMuPDF not installed"
}
```

## Requirements

PDF annotation requires **PyMuPDF** (already in requirements.txt):

```bash
pip install PyMuPDF>=1.23.0
```

## Image Input

For **image files** (PNG, JPG), the system:
1. Converts image to temporary PDF
2. Processes with OCR/ICR
3. Creates annotated PDF with results
4. Returns path to annotated PDF

Original image is preserved, annotated PDF is created alongside.

## Use Cases

### 1. Quality Assurance
- Visually verify extraction accuracy
- Check if signatures were detected
- Ensure handwriting was recognized

### 2. Client Deliverables
- Provide annotated documents showing what was extracted
- Highlight important regions (signatures, handwriting)
- Professional presentation of results

### 3. Training Data Review
- Review detection quality
- Identify areas for model improvement
- Annotate edge cases

### 4. Debugging
- Visualize where detection failed
- Compare original vs. extracted positions
- Understand routing decisions (OCR vs ICR)

## Tips

1. **Large Documents**: Annotation adds 2-5 seconds to processing time
2. **Disable for Batch**: Set `create_annotated_pdf=false` for high-volume processing
3. **Storage**: Annotated PDFs are ~10-30% larger than originals
4. **Cleanup**: Delete annotated PDFs when no longer needed
5. **Title Detection**: For best auto-naming, include clear titles in documents

## Integration Example

```python
import requests
from pathlib import Path

def process_and_annotate(file_path: str):
    """Process document and create annotated PDF"""
    
    with open(file_path, "rb") as f:
        response = requests.post(
            "http://localhost:8002/hybrid/process",
            files={"file": f},
            data={"create_annotated_pdf": "true"}
        )
    
    result = response.json()
    
    if result.get("annotated_pdf"):
        print(f"✅ Original: {file_path}")
        print(f"✅ Annotated: {result['annotated_pdf']}")
        
        # Check what was detected
        for region in result["regions"]:
            print(f"  - {region['type']}: {region.get('text', 'N/A')}")
    
    return result

# Process mixed document
result = process_and_annotate("contract_with_signature.pdf")
```

## Troubleshooting

### No Annotated PDF Created
- Check `annotated_pdf_error` in response
- Verify PyMuPDF is installed: `pip list | grep PyMuPDF`
- Ensure `create_annotated_pdf=true` in request

### Wrong Filename
- Title detection uses first clear title found
- Check document has clear H1 or invoice number
- Fallback uses timestamp if no title detected

### Text Not Aligned
- OCR provides bbox coordinates
- Text overlaid at exact coordinates
- Some PDFs have non-standard coordinate systems

### Missing Handwriting
- Handwriting only detected in hybrid/ICR mode
- Pure OCR mode doesn't detect handwriting regions
- Use `/hybrid/process` endpoint for handwriting

## Future Enhancements

Planned features:
- [ ] Confidence score visualization (color-coded by confidence)
- [ ] Interactive PDF with clickable regions
- [ ] Diff view between original and corrected text
- [ ] Custom color schemes
- [ ] Annotation templates
