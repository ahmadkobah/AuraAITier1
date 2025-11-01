# Multi-Method Upload Implementation Guide

## Overview
This document outlines how to implement three upload methods for the adaptive document processing system:
1. ✅ **Direct Upload** (Already Working)
2. ⚠️ **Scanner Integration** (Needs Implementation)
3. ❌ **Email Import** (Needs Implementation)

---

## Method 1: Direct File Upload ✅ WORKING

### Current Implementation
Already available in `python-document-intelligence-service/main.py`:

```python
@app.post("/upload/analyze")
async def analyze_uploaded_file(
    file: UploadFile = File(...),
    analysis_type: str = Form("full"),
    confidence_threshold: float = Form(0.8)
):
    """Upload and analyze document file."""
    # Already processes:
    # - PDF files
    # - Images (JPG, PNG, TIFF)
    # - Scanned documents
```

### Supported Formats
- ✅ PDF documents
- ✅ Images: JPG, PNG, TIFF, BMP
- ✅ Scanned documents
- ✅ Multi-page PDFs
- ✅ Handwritten documents

### Usage from Projectena
```javascript
// Frontend React component
const uploadFile = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('analysis_type', 'full');
  formData.append('confidence_threshold', '0.8');
  
  const response = await fetch('http://localhost:8003/upload/analyze', {
    method: 'POST',
    body: formData
  });
  
  return await response.json();
};
```

**Status:** ✅ No changes needed

---

## Method 2: Scanner Integration ⚠️ NEEDS IMPLEMENTATION

### Overview
Support direct scanning from network scanners or TWAIN-compatible devices.

### Implementation Time: 2-3 hours

### A. Network Scanner Endpoint

**File:** `python-document-intelligence-service/main.py`

Add new endpoint:

```python
@app.post("/upload/scan")
async def receive_from_scanner(
    file: UploadFile = File(...),
    scanner_id: str = Form(...),
    scan_settings: Optional[str] = Form(None),  # JSON string
    company_id: Optional[str] = Form(None),
    department_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None)
):
    """
    Receive scanned documents from network scanners.
    
    Supported scanner types:
    - Network scanners (Canon, HP, Xerox, etc.)
    - MFPs (Multi-Function Printers)
    - Document scanners with network capability
    
    Scanner Configuration:
    Configure your scanner to POST to: http://<server>:8003/upload/scan
    """
    try:
        # Parse scan settings
        settings = {}
        if scan_settings:
            settings = json.loads(scan_settings)
        
        # Read scanned file
        content = await file.read()
        
        # Log scanner activity
        logger.info(f"Document received from scanner: {scanner_id}")
        logger.info(f"File: {file.filename}, Size: {len(content)} bytes")
        logger.info(f"Settings: {settings}")
        
        # Process with enhanced metadata
        extraction_result = await extract_text_from_file(
            content,
            file.filename or f"scan_{scanner_id}_{datetime.utcnow().timestamp()}.pdf",
            file.content_type or "application/pdf"
        )
        
        # Create document with scanner metadata
        document = DocumentInput(
            content=extraction_result.get("text", ""),
            filename=file.filename,
            metadata={
                "source": "scanner",
                "scanner_id": scanner_id,
                "scan_settings": settings,
                "content_type": file.content_type,
                "file_size": len(content),
                "scan_timestamp": datetime.utcnow().isoformat(),
                "company_id": company_id,
                "department_id": department_id,
                "user_id": user_id,
                "extraction_metadata": extraction_result.get("metadata", {})
            }
        )
        
        # Analyze document
        result = await analyze_document_intelligence(document)
        
        # Add scanner-specific info to response
        result["scanner_info"] = {
            "scanner_id": scanner_id,
            "scan_settings": settings,
            "scan_timestamp": document.metadata["scan_timestamp"]
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Scanner upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scanner upload failed: {str(e)}")
```

### B. Scanner Configuration Examples

#### Canon imageRUNNER
```
Scanner Settings → Scan and Send → Network
Destination Type: HTTP
URL: http://192.168.1.100:8003/upload/scan
Method: POST
Format: PDF or JPEG
```

#### HP Enterprise MFP
```
Scan Settings → Network Folder
Protocol: HTTP POST
Server: 192.168.1.100
Port: 8003
Path: /upload/scan
Authentication: None (or add if needed)
```

#### Xerox WorkCentre
```
Scan to Network → HTTP/HTTPS
Destination URL: http://192.168.1.100:8003/upload/scan
Method: POST
File Format: PDF (Searchable) or JPEG
```

### C. TWAIN Support (Optional - Windows Only)

For local scanner integration via TWAIN:

**File:** `python-document-intelligence-service/app/scanner/__init__.py`

```python
"""
Scanner integration module.
Requires: pip install python-twain
Windows only - TWAIN scanner support
"""

try:
    import twain
    TWAIN_AVAILABLE = True
except ImportError:
    TWAIN_AVAILABLE = False

class TWAINScanner:
    """Interface for TWAIN-compatible scanners."""
    
    def __init__(self):
        if not TWAIN_AVAILABLE:
            raise RuntimeError("TWAIN not available - install python-twain")
        self.sm = twain.SourceManager(0)
        
    def list_scanners(self):
        """List available TWAIN scanners."""
        return self.sm.GetSourceList()
    
    def scan_document(self, scanner_name=None, **kwargs):
        """
        Scan document from TWAIN scanner.
        
        Args:
            scanner_name: Specific scanner name, or None for default
            **kwargs: Scanner settings (resolution, color mode, etc.)
        
        Returns:
            PIL.Image: Scanned image
        """
        if scanner_name:
            self.sm.SelectSource(scanner_name)
        
        ss = self.sm.OpenSource()
        
        # Configure scanning settings
        if 'resolution' in kwargs:
            ss.SetResolution(kwargs['resolution'])
        if 'color_mode' in kwargs:
            ss.SetPixelType(kwargs['color_mode'])
            
        # Perform scan
        ss.RequestAcquire(0, 0)
        images = []
        
        try:
            while True:
                rv = ss.XferImageNatively()
                if rv:
                    images.append(rv)
                else:
                    break
        except twain.excTWCC_SEQERROR:
            pass  # Expected at end of scan
            
        return images
```

Add endpoint:

```python
@app.post("/upload/scan/twain")
async def scan_with_twain(
    scanner_name: Optional[str] = Form(None),
    resolution: int = Form(300),
    color_mode: str = Form("color"),  # "color", "gray", "bw"
    company_id: Optional[str] = Form(None),
    department_id: Optional[str] = Form(None)
):
    """
    Scan document using TWAIN scanner (Windows only).
    Requires scanner connected to server.
    """
    try:
        from app.scanner import TWAINScanner, TWAIN_AVAILABLE
        
        if not TWAIN_AVAILABLE:
            raise HTTPException(
                status_code=501,
                detail="TWAIN not available on this server"
            )
        
        scanner = TWAINScanner()
        
        # Scan document
        images = scanner.scan_document(
            scanner_name=scanner_name,
            resolution=resolution,
            color_mode=color_mode
        )
        
        if not images:
            raise HTTPException(status_code=400, detail="No image scanned")
        
        # Convert first image to bytes (PDF or JPEG)
        import io
        img_bytes = io.BytesIO()
        images[0].save(img_bytes, format='PDF')
        content = img_bytes.getvalue()
        
        # Process scanned document
        filename = f"twain_scan_{datetime.utcnow().timestamp()}.pdf"
        extraction_result = await extract_text_from_file(
            content,
            filename,
            "application/pdf"
        )
        
        # Analyze
        document = DocumentInput(
            content=extraction_result.get("text", ""),
            filename=filename,
            metadata={
                "source": "twain_scanner",
                "scanner_name": scanner_name or "default",
                "resolution": resolution,
                "color_mode": color_mode,
                "company_id": company_id,
                "department_id": department_id
            }
        )
        
        return await analyze_document_intelligence(document)
        
    except Exception as e:
        logger.error(f"TWAIN scan error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"TWAIN scan failed: {str(e)}")

@app.get("/scanners/list")
async def list_available_scanners():
    """List TWAIN scanners connected to server."""
    try:
        from app.scanner import TWAINScanner, TWAIN_AVAILABLE
        
        if not TWAIN_AVAILABLE:
            return {"scanners": [], "twain_available": False}
        
        scanner = TWAINScanner()
        scanners = scanner.list_scanners()
        
        return {
            "scanners": scanners,
            "twain_available": True,
            "count": len(scanners)
        }
    except Exception as e:
        return {"scanners": [], "error": str(e)}
```

### D. Requirements

Add to `requirements.txt`:

```
# Scanner support
python-twain==2.2.0; platform_system=="Windows"  # TWAIN scanner support (Windows only)
```

---

## Method 3: Email Import ❌ NEEDS IMPLEMENTATION

### Overview
Monitor email inbox and automatically import attachments for processing.

### Implementation Time: 4-6 hours

### A. Email Service Architecture

```
┌─────────────────────────────────────────────────────┐
│              Email Server (IMAP/POP3)               │
│            (Gmail, Outlook, Exchange)               │
└────────────────────┬────────────────────────────────┘
                     │
                     │ Check every 60s
                     ▼
┌─────────────────────────────────────────────────────┐
│         Email Monitoring Service (New)              │
│         Port: 8005                                  │
│                                                     │
│  - Connect to IMAP/POP3                            │
│  - Check for new emails                            │
│  - Download attachments                            │
│  - Extract metadata from email body                │
└────────────────────┬────────────────────────────────┘
                     │
                     │ Forward attachments
                     ▼
┌─────────────────────────────────────────────────────┐
│      Document Intelligence Service                  │
│      POST /upload/analyze                           │
│                                                     │
│  - Process document                                 │
│  - Include email metadata                          │
│  - Return results                                  │
└─────────────────────────────────────────────────────┘
```

### B. Create Email Service

**File:** `python-email-import-service/main.py`

```python
"""
Email Import Service
Monitors email inbox and imports document attachments for processing.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
import imaplib
import email
from email.header import decode_header
import httpx
import asyncio
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import os
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Email Import Service",
    description="Monitor email inbox and import document attachments",
    version="1.0.0"
)

# Configuration
class EmailConfig(BaseModel):
    imap_server: str
    imap_port: int = 993
    email_address: EmailStr
    password: str
    folder: str = "INBOX"
    check_interval: int = 60  # seconds
    allowed_senders: Optional[List[str]] = None
    allowed_extensions: List[str] = [".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".docx"]

# Global configuration
email_configs: Dict[str, EmailConfig] = {}
monitoring_tasks: Dict[str, bool] = {}

class EmailImportService:
    """Service to monitor email and import attachments."""
    
    def __init__(self, config: EmailConfig):
        self.config = config
        self.doc_intelligence_url = "http://localhost:8003/upload/analyze"
        
    async def connect_imap(self):
        """Connect to IMAP server."""
        try:
            mail = imaplib.IMAP4_SSL(self.config.imap_server, self.config.imap_port)
            mail.login(self.config.email_address, self.config.password)
            mail.select(self.config.folder)
            logger.info(f"Connected to {self.config.email_address}")
            return mail
        except Exception as e:
            logger.error(f"IMAP connection failed: {str(e)}")
            raise
    
    def decode_str(self, s):
        """Decode email header string."""
        if isinstance(s, bytes):
            s = s.decode()
        value, encoding = decode_header(s)[0]
        if isinstance(value, bytes):
            value = value.decode(encoding or 'utf-8')
        return value
    
    async def process_email(self, mail, email_id):
        """Process single email and extract attachments."""
        try:
            # Fetch email
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Get email metadata
                    subject = self.decode_str(msg.get("Subject", ""))
                    from_addr = self.decode_str(msg.get("From", ""))
                    date = msg.get("Date", "")
                    
                    logger.info(f"Processing email: {subject} from {from_addr}")
                    
                    # Check allowed senders
                    if self.config.allowed_senders:
                        sender_email = email.utils.parseaddr(from_addr)[1]
                        if sender_email not in self.config.allowed_senders:
                            logger.info(f"Skipping email from unauthorized sender: {sender_email}")
                            return
                    
                    # Extract email body text
                    email_body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                email_body = part.get_payload(decode=True).decode()
                                break
                    else:
                        email_body = msg.get_payload(decode=True).decode()
                    
                    # Process attachments
                    attachments_processed = 0
                    
                    if msg.is_multipart():
                        for part in msg.walk():
                            # Check if part is attachment
                            if part.get_content_maintype() == 'multipart':
                                continue
                            if part.get('Content-Disposition') is None:
                                continue
                            
                            filename = part.get_filename()
                            if filename:
                                filename = self.decode_str(filename)
                                
                                # Check file extension
                                ext = os.path.splitext(filename)[1].lower()
                                if ext not in self.config.allowed_extensions:
                                    logger.info(f"Skipping file with extension {ext}: {filename}")
                                    continue
                                
                                # Get file content
                                file_data = part.get_payload(decode=True)
                                
                                # Parse email body for metadata hints
                                metadata = self.extract_metadata_from_email(
                                    subject, email_body, from_addr
                                )
                                
                                # Send to document intelligence service
                                await self.process_attachment(
                                    filename,
                                    file_data,
                                    {
                                        "email_subject": subject,
                                        "email_from": from_addr,
                                        "email_date": date,
                                        "email_body_preview": email_body[:500],
                                        **metadata
                                    }
                                )
                                
                                attachments_processed += 1
                    
                    if attachments_processed > 0:
                        logger.info(f"Processed {attachments_processed} attachments from: {subject}")
                        # Mark email as seen/processed (optional)
                        # mail.store(email_id, '+FLAGS', '\\Seen')
                    
        except Exception as e:
            logger.error(f"Email processing error: {str(e)}")
    
    def extract_metadata_from_email(self, subject: str, body: str, from_addr: str) -> Dict[str, Any]:
        """Extract metadata hints from email subject and body."""
        metadata = {}
        
        subject_lower = subject.lower()
        body_lower = body.lower()
        
        # Try to identify company from email domain
        sender_domain = email.utils.parseaddr(from_addr)[1].split('@')[1] if '@' in from_addr else ""
        metadata["sender_domain"] = sender_domain
        
        # Detect department hints
        if any(word in subject_lower or word in body_lower for word in ['invoice', 'payment', 'billing']):
            metadata["suggested_department"] = "finance"
        elif any(word in subject_lower or word in body_lower for word in ['contract', 'legal', 'agreement']):
            metadata["suggested_department"] = "legal"
        elif any(word in subject_lower or word in body_lower for word in ['hr', 'employee', 'resume']):
            metadata["suggested_department"] = "hr"
        
        # Extract urgency
        if any(word in subject_lower for word in ['urgent', 'asap', 'important']):
            metadata["priority"] = "high"
        
        return metadata
    
    async def process_attachment(self, filename: str, file_data: bytes, email_metadata: Dict[str, Any]):
        """Send attachment to document intelligence service."""
        try:
            # Prepare multipart form data
            files = {
                'file': (filename, file_data, 'application/octet-stream')
            }
            data = {
                'analysis_type': 'full',
                'confidence_threshold': '0.8'
            }
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    self.doc_intelligence_url,
                    files=files,
                    data=data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Add email metadata to result
                    result["source_metadata"] = {
                        "source": "email_import",
                        **email_metadata
                    }
                    
                    logger.info(f"✅ Processed: {filename}")
                    logger.info(f"   Document Type: {result.get('classification', {}).get('document_type', 'unknown')}")
                    logger.info(f"   Department: {result.get('routing', {}).get('department', 'unknown')}")
                    
                    # TODO: Save result to database or forward to Projectena
                    # await save_to_projectena(result)
                    
                    return result
                else:
                    logger.error(f"❌ Processing failed for {filename}: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Attachment processing error for {filename}: {str(e)}")
    
    async def check_new_emails(self):
        """Check for new emails and process them."""
        try:
            mail = await self.connect_imap()
            
            # Search for unread emails
            status, messages = mail.search(None, 'UNSEEN')
            
            if status == "OK":
                email_ids = messages[0].split()
                
                if email_ids:
                    logger.info(f"Found {len(email_ids)} new emails")
                    
                    for email_id in email_ids:
                        await self.process_email(mail, email_id)
                else:
                    logger.debug("No new emails")
            
            mail.close()
            mail.logout()
            
        except Exception as e:
            logger.error(f"Email check error: {str(e)}")

# API Endpoints

@app.post("/email/configure")
async def configure_email_monitoring(config: EmailConfig, background_tasks: BackgroundTasks):
    """Configure email monitoring for an account."""
    account_id = config.email_address
    
    # Store configuration
    email_configs[account_id] = config
    
    # Start monitoring in background
    if account_id not in monitoring_tasks or not monitoring_tasks[account_id]:
        monitoring_tasks[account_id] = True
        background_tasks.add_task(monitor_email_account, account_id)
    
    return {
        "status": "configured",
        "email": config.email_address,
        "folder": config.folder,
        "check_interval": config.check_interval,
        "monitoring": True
    }

@app.post("/email/stop/{email_address}")
async def stop_email_monitoring(email_address: str):
    """Stop monitoring an email account."""
    if email_address in monitoring_tasks:
        monitoring_tasks[email_address] = False
        return {"status": "stopped", "email": email_address}
    else:
        raise HTTPException(status_code=404, detail="Email account not configured")

@app.get("/email/status")
async def get_monitoring_status():
    """Get status of all monitored email accounts."""
    status = []
    for email_addr, config in email_configs.items():
        status.append({
            "email": email_addr,
            "monitoring": monitoring_tasks.get(email_addr, False),
            "folder": config.folder,
            "check_interval": config.check_interval
        })
    return {"accounts": status, "count": len(status)}

async def monitor_email_account(account_id: str):
    """Background task to monitor email account."""
    logger.info(f"Started monitoring: {account_id}")
    
    config = email_configs[account_id]
    service = EmailImportService(config)
    
    while monitoring_tasks.get(account_id, False):
        try:
            await service.check_new_emails()
        except Exception as e:
            logger.error(f"Monitoring error for {account_id}: {str(e)}")
        
        # Wait before next check
        await asyncio.sleep(config.check_interval)
    
    logger.info(f"Stopped monitoring: {account_id}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "email-import",
        "monitored_accounts": len(email_configs)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
```

### C. Email Service Requirements

**File:** `python-email-import-service/requirements.txt`

```txt
fastapi==0.104.1
uvicorn==0.24.0
httpx==0.25.1
python-multipart==0.0.6
pydantic[email]==2.5.0
```

### D. Configuration Examples

#### Gmail Setup

```python
# Configure Gmail monitoring
config = {
    "imap_server": "imap.gmail.com",
    "imap_port": 993,
    "email_address": "documents@yourcompany.com",
    "password": "app_specific_password",  # Use App Password, not account password
    "folder": "INBOX",
    "check_interval": 60,
    "allowed_senders": [
        "scanner@yourcompany.com",
        "accounting@partner.com"
    ],
    "allowed_extensions": [".pdf", ".jpg", ".png"]
}

# Enable Gmail IMAP:
# 1. Gmail Settings → Forwarding and POP/IMAP
# 2. Enable IMAP
# 3. Create App Password: Google Account → Security → App Passwords
```

#### Outlook/Office 365

```python
config = {
    "imap_server": "outlook.office365.com",
    "imap_port": 993,
    "email_address": "documents@yourcompany.com",
    "password": "your_password",
    "folder": "INBOX",
    "check_interval": 60
}
```

#### Exchange Server

```python
config = {
    "imap_server": "mail.yourcompany.com",
    "imap_port": 993,
    "email_address": "documents@yourcompany.com",
    "password": "your_password",
    "folder": "INBOX/Documents",  # Can specify subfolder
    "check_interval": 30
}
```

### E. Usage from Projectena

**Add to Projectena Backend:**

```javascript
// services/emailImportService.js

const axios = require('axios');

const EMAIL_IMPORT_SERVICE = 'http://localhost:8005';

/**
 * Configure email monitoring for document imports
 */
async function configureEmailImport(emailConfig) {
  try {
    const response = await axios.post(
      `${EMAIL_IMPORT_SERVICE}/email/configure`,
      emailConfig
    );
    return response.data;
  } catch (error) {
    console.error('Email import configuration failed:', error.message);
    throw error;
  }
}

/**
 * Stop email monitoring
 */
async function stopEmailImport(emailAddress) {
  try {
    const response = await axios.post(
      `${EMAIL_IMPORT_SERVICE}/email/stop/${emailAddress}`
    );
    return response.data;
  } catch (error) {
    console.error('Failed to stop email monitoring:', error.message);
    throw error;
  }
}

/**
 * Get email monitoring status
 */
async function getEmailImportStatus() {
  try {
    const response = await axios.get(
      `${EMAIL_IMPORT_SERVICE}/email/status`
    );
    return response.data;
  } catch (error) {
    console.error('Failed to get email import status:', error.message);
    throw error;
  }
}

module.exports = {
  configureEmailImport,
  stopEmailImport,
  getEmailImportStatus
};
```

**Add API Endpoint in Projectena:**

```javascript
// Routes/emailImportRoutes.js

const express = require('express');
const router = express.Router();
const emailImportService = require('../services/emailImportService');
const { authenticate } = require('../middleware/auth');

// Configure email import (Admin only)
router.post('/configure', authenticate, async (req, res) => {
  try {
    // Only superadmin or company admin can configure
    if (req.user.role !== 'superadmin' && req.user.role !== 'admin') {
      return res.status(403).json({ message: 'Insufficient permissions' });
    }
    
    const result = await emailImportService.configureEmailImport(req.body);
    res.json(result);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

// Stop email monitoring
router.post('/stop/:email', authenticate, async (req, res) => {
  try {
    const result = await emailImportService.stopEmailImport(req.params.email);
    res.json(result);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

// Get status
router.get('/status', authenticate, async (req, res) => {
  try {
    const result = await emailImportService.getEmailImportStatus();
    res.json(result);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

module.exports = router;
```

---

## Integration Summary

### Complete Upload Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     UPLOAD SOURCES                          │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         │                    │                    │
    User Upload         Scanner Device         Email Server
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Projectena │      │   Network   │      │    Email    │
│   Frontend  │      │   Scanner   │      │   Import    │
│  (React)    │      │  (HTTP)     │      │  Service    │
└──────┬──────┘      └──────┬──────┘      └──────┬──────┘
       │                    │                    │
       │ POST /upload/analyze                    │
       │                    │                    │
       └────────────────────┼────────────────────┘
                            ▼
              ┌──────────────────────────┐
              │  Document Intelligence   │
              │      Service (8003)      │
              │                          │
              │  - Receives file         │
              │  - OCR/ICR/NLP          │
              │  - Classification        │
              │  - Routing               │
              └────────────┬─────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │   Projectena Backend     │
              │                          │
              │  - Save to MongoDB       │
              │  - Store file            │
              │  - Create record         │
              └──────────────────────────┘
```

### Implementation Checklist

#### Phase 1: Direct Upload ✅ (Already Working)
- [x] File upload endpoint
- [x] Multi-format support (PDF, images)
- [x] OCR/ICR processing
- [x] Projectena integration

#### Phase 2: Scanner Integration ⚠️ (2-3 hours)
- [ ] Add `/upload/scan` endpoint
- [ ] Test with network scanner
- [ ] Document scanner configuration
- [ ] Optional: Add TWAIN support for local scanners

#### Phase 3: Email Import ❌ (4-6 hours)
- [ ] Create email import service
- [ ] IMAP/POP3 connection
- [ ] Attachment extraction
- [ ] Background monitoring
- [ ] Projectena integration
- [ ] Security: App passwords, allowed senders

### Security Considerations

1. **Scanner Upload:**
   - Configure scanner IP whitelist
   - Use HTTPS in production
   - Validate file types

2. **Email Import:**
   - Use app-specific passwords (not account passwords)
   - Whitelist allowed sender addresses
   - Validate attachment types
   - Scan for malware before processing
   - Use dedicated email account (not personal)

3. **All Methods:**
   - Add authentication tokens
   - Rate limiting
   - File size limits
   - Virus scanning

---

## Quick Start Guide

### 1. Test Direct Upload (Works Now)
```bash
# From Projectena frontend
curl -X POST http://localhost:8003/upload/analyze \
  -F "file=@document.pdf" \
  -F "analysis_type=full"
```

### 2. Add Scanner Support (2-3 hours)
```bash
# Add endpoint to main.py (see section 2.A above)
# Configure scanner to POST to: http://your-server:8003/upload/scan
```

### 3. Setup Email Import (4-6 hours)
```bash
# Create new service
cd adaptive-Dokumentenverarbeitung
mkdir python-email-import-service
cd python-email-import-service

# Copy code from section 3.B
# Install requirements
pip install -r requirements.txt

# Run service
python main.py  # Runs on port 8005

# Configure monitoring
curl -X POST http://localhost:8005/email/configure \
  -H "Content-Type: application/json" \
  -d '{
    "imap_server": "imap.gmail.com",
    "imap_port": 993,
    "email_address": "documents@yourcompany.com",
    "password": "app_password",
    "folder": "INBOX",
    "check_interval": 60
  }'
```

---

## Total Implementation Time

| Method | Status | Time Required |
|--------|--------|---------------|
| Direct Upload | ✅ Working | 0 hours |
| Scanner Integration | ⚠️ Needs Code | 2-3 hours |
| Email Import | ❌ New Service | 4-6 hours |
| **TOTAL** | | **6-9 hours** |

---

## Conclusion

**Yes, all three upload methods can be supported!**

1. ✅ **Direct Upload** - Already working
2. ⚠️ **Scanner** - Simple to add (2-3 hours)
3. ❌ **Email** - Requires new service (4-6 hours)

**Recommended Approach:**
1. Use direct upload immediately (works now)
2. Add scanner support first (easier, 2-3 hours)
3. Add email import if needed (4-6 hours)

Total time to support all three methods: **6-9 hours of development**
