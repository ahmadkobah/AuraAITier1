"""
Minimal Document Intelligence Service for Testing
Fast startup without heavy ML model loading
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from typing import Optional
import uvicorn
from datetime import datetime
import hashlib
import re

app = FastAPI(
    title="Document Intelligence Service (Test Mode)",
    description="Minimal version for testing Projectena integration",
    version="1.0.0-test"
)

@app.get("/")
async def root():
    return {
        "service": "Document Intelligence Service",
        "version": "1.0.0-test",
        "status": "running",
        "mode": "test",
        "endpoints": [
            "/upload/analyze",
            "/upload/analyze/projectena",
            "/upload/scan",
            "/health"
        ]
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "mode": "test"
    }

@app.post("/upload/analyze")
async def analyze_uploaded_file(
    file: UploadFile = File(...),
    analysis_type: str = Form("full"),
    confidence_threshold: float = Form(0.8),
    company_id: Optional[str] = Form(None),
    department_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None)
):
    """Upload and analyze document file (test mode)."""
    try:
        # Read file
        content = await file.read()
        
        # Simulate processing
        return {
            "document_id": hashlib.md5(content).hexdigest()[:12],
            "filename": file.filename,
            "file_size": len(content),
            "content_type": file.content_type,
            "company_id": company_id,
            "department_id": department_id,
            "user_id": user_id,
            "status": "processed",
            "mode": "test",
            "classification": {
                "document_type": "invoice",
                "confidence": 0.85
            },
            "extraction": {
                "text_content": "[Test Mode] Text would be extracted here",
                "entities": {}
            },
            "routing": {
                "department": department_id or "finance",
                "folder_paths": {
                    "base_path": f"/{company_id}/{department_id}/invoice" if company_id and department_id else "/documents/general",
                    "dated_path": f"/{company_id}/{department_id}/invoice/2025/11" if company_id and department_id else "/documents/general/2025/11",
                    "full_path": f"/{company_id}/{department_id}/invoice/2025/11/01" if company_id and department_id else "/documents/general/2025/11/01"
                }
            },
            "overall_processing_time": 0.1,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload/analyze/projectena")
async def analyze_for_projectena(
    file: UploadFile = File(...),
    companyId: str = Form(...),
    departmentId: str = Form(...),
    uploadedBy: str = Form(...),
    folderId: Optional[str] = Form(None),
    tags: Optional[str] = Form(None)
):
    """Projectena-compatible endpoint (test mode)."""
    try:
        import json
        
        # Read file
        content = await file.read()
        file_size = len(content)
        
        # Parse tags
        tag_list = []
        if tags:
            try:
                tag_list = json.loads(tags) if isinstance(tags, str) else tags
            except:
                tag_list = []
        
        # Auto-generate some test tags
        auto_tags = tag_list + ["invoice", "finance", "test"]
        
        # Generate filename
        safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', file.filename or "document")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{safe_filename}"
        
        # Build Projectena response
        return {
            # Core fields
            "filename": unique_filename,
            "originalName": file.filename,
            "size": file_size,
            "contentType": file.content_type,
            
            # Ownership
            "uploadedBy": uploadedBy,
            "companyId": companyId,
            "departmentId": departmentId,
            "folderId": folderId,
            
            # Classification
            "docType": "invoice",
            "tags": auto_tags[:10],
            
            # OCR status
            "ocrStatus": "completed",
            
            # Extracted metadata
            "extractedMetadata": {
                "ocr_text": "[Test Mode] Full text would be extracted here using DeepSeek-OCR",
                "ocr_confidence": 0.92,
                "document_type": "invoice",
                "classification_confidence": 0.88,
                "entities": {
                    "invoice_number": "TEST-2024-001",
                    "total_amount": "$1,234.56",
                    "due_date": "2024-12-01"
                },
                "signature_info": {
                    "signed": True,
                    "signature_count": 1,
                    "confidence": 0.90
                },
                "folder_paths": {
                    "base_path": f"/{companyId}/{departmentId}/invoice",
                    "dated_path": f"/{companyId}/{departmentId}/invoice/2025/11",
                    "full_path": f"/{companyId}/{departmentId}/invoice/2025/11/01"
                }
            },
            
            # Additional fields
            "processingTime": 0.15,
            "confidenceScore": 0.88,
            "signed": True,
            "suggestedPath": f"/{companyId}/{departmentId}/invoice/2025/11/01",
            "status": "processed",
            "processedAt": datetime.utcnow().isoformat(),
            "mode": "test"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload/scan")
async def receive_from_scanner(
    file: UploadFile = File(...),
    scanner_id: str = Form(...),
    scan_settings: Optional[str] = Form(None),
    company_id: Optional[str] = Form(None),
    department_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None)
):
    """Scanner integration endpoint (test mode)."""
    try:
        import json
        
        # Read file
        content = await file.read()
        
        # Parse settings
        settings = {}
        if scan_settings:
            try:
                settings = json.loads(scan_settings)
            except:
                pass
        
        return {
            "document_id": hashlib.md5(content).hexdigest()[:12],
            "filename": file.filename,
            "file_size": len(content),
            "source": "scanner",
            "scanner_info": {
                "scanner_id": scanner_id,
                "scan_settings": settings,
                "scan_timestamp": datetime.utcnow().isoformat()
            },
            "company_id": company_id,
            "department_id": department_id,
            "user_id": user_id,
            "status": "processed",
            "mode": "test",
            "classification": {
                "document_type": "scanned_document",
                "confidence": 0.82
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 Starting Document Intelligence Service (TEST MODE)")
    print("=" * 70)
    print("\nEndpoints available:")
    print("  • http://localhost:8003/")
    print("  • http://localhost:8003/health")
    print("  • http://localhost:8003/upload/analyze")
    print("  • http://localhost:8003/upload/analyze/projectena")
    print("  • http://localhost:8003/upload/scan")
    print("\n" + "=" * 70)
    print("⚡ Fast startup mode - no ML models loaded")
    print("🧪 For testing API structure and integration")
    print("=" * 70 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8003)
