# 🔗 Projectena Integration Guide

**Integrating Adaptive Document Processing with Projectena**  
**Version:** 1.0.0  
**Date:** November 1, 2025

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Integration Steps](#integration-steps)
5. [API Reference](#api-reference)
6. [Frontend Integration](#frontend-integration)
7. [Backend Integration](#backend-integration)
8. [Scanner Integration](#scanner-integration)
9. [Testing](#testing)
10. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

This guide explains how to integrate the Adaptive Document Processing System with your existing **Projectena** system (Node.js + Express + MongoDB + React).

### What This Integration Provides

- ✅ **Automatic OCR**: Extract text from scanned/uploaded documents
- ✅ **Handwriting Recognition**: Process handwritten forms and signatures
- ✅ **Signature Detection**: Identify signed documents automatically
- ✅ **Smart Classification**: Auto-categorize documents by type
- ✅ **Entity Extraction**: Extract invoice numbers, dates, amounts, etc.
- ✅ **Smart Routing**: Auto-organize documents into folders by company/department
- ✅ **Scanner Support**: Accept uploads directly from network scanners

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────┐
│              Projectena System                      │
│  ┌──────────────┐         ┌─────────────────────┐ │
│  │ React Frontend│────────▶│ Express Backend     │ │
│  │  (Aura App)  │         │ (Node.js + MongoDB) │ │
│  └──────────────┘         └──────┬──────────────┘ │
└───────────────────────────────────┼────────────────┘
                                    │
                                    │ HTTP POST
                                    │
                    ┌───────────────▼──────────────┐
                    │ Adaptive Document Processing │
                    │  Document Intelligence API   │
                    │    (Python FastAPI)          │
                    │      Port 8003               │
                    └───────────────┬──────────────┘
                                    │
                    ┌───────────────┴──────────────┐
                    │   OCR + ICR + NLP Services   │
                    │       (Ports 8000-8002)      │
                    └──────────────────────────────┘
```

### Data Flow

1. **User uploads document** in Projectena's Aura app
2. **Projectena saves file** to storage (local/cloud)
3. **Projectena calls** Adaptive API with file
4. **Adaptive processes** document (OCR/ICR/NLP)
5. **Returns metadata** in Projectena-compatible format
6. **Projectena saves** to MongoDB with extracted data

---

## ✅ Prerequisites

### Adaptive System
- ✅ All services running (ports 8000-8003)
- ✅ Health checks passing
- ✅ Network accessible from Projectena server

### Projectena System
- ✅ Express backend running
- ✅ MongoDB connected
- ✅ Document upload routes configured
- ✅ Network access to Adaptive services

---

## 🚀 Integration Steps

### Step 1: Start Adaptive Services

```bash
cd adaptive-Dokumentenverarbeitung

# Windows
.\start_services.ps1

# Linux/Mac
bash start_services.sh
```

Verify all services:
```bash
curl http://localhost:8003/health
```

### Step 2: Update Projectena Backend

Add Adaptive API client to your Projectena backend.

**File: `projectena/backend/services/documentProcessingService.js`**

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

// Adaptive API configuration
const ADAPTIVE_API_URL = process.env.ADAPTIVE_API_URL || 'http://localhost:8003';

/**
 * Process document using Adaptive Document Processing System
 * @param {Object} options - Processing options
 * @param {string} options.filePath - Path to uploaded file
 * @param {string} options.companyId - Company identifier
 * @param {string} options.departmentId - Department identifier  
 * @param {string} options.uploadedBy - User ID who uploaded
 * @param {string[]} options.tags - Optional tags
 * @returns {Promise<Object>} Processed document metadata
 */
async function processDocument(options) {
    const {
        filePath,
        companyId,
        departmentId,
        uploadedBy,
        tags = []
    } = options;

    try {
        // Create form data
        const formData = new FormData();
        formData.append('file', fs.createReadStream(filePath));
        formData.append('companyId', companyId);
        formData.append('departmentId', departmentId);
        formData.append('uploadedBy', uploadedBy);
        
        // Add tags if provided
        tags.forEach(tag => {
            formData.append('tags', tag);
        });

        // Call Adaptive API
        const response = await axios.post(
            `${ADAPTIVE_API_URL}/upload/analyze/projectena`,
            formData,
            {
                headers: formData.getHeaders(),
                timeout: 60000, // 60 second timeout
                maxBodyLength: Infinity,
                maxContentLength: Infinity
            }
        );

        return response.data;
    } catch (error) {
        console.error('Document processing error:', error.message);
        throw new Error(`Failed to process document: ${error.message}`);
    }
}

module.exports = {
    processDocument
};
```

### Step 3: Update Document Upload Route

**File: `projectena/backend/routes/documents.js`**

```javascript
const express = require('express');
const router = express.Router();
const multer = require('multer');
const path = require('path');
const Document = require('../models/Document');
const { processDocument } = require('../services/documentProcessingService');

// Configure multer for file uploads
const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        cb(null, 'uploads/');
    },
    filename: function (req, file, cb) {
        const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
        cb(null, uniqueSuffix + path.extname(file.originalname));
    }
});

const upload = multer({ 
    storage: storage,
    limits: { fileSize: 50 * 1024 * 1024 } // 50MB max
});

/**
 * POST /api/documents/upload
 * Upload and process a document
 */
router.post('/upload', upload.single('file'), async (req, res) => {
    try {
        const { companyId, departmentId, folderId, tags } = req.body;
        const user = req.user; // Assuming auth middleware sets req.user

        if (!req.file) {
            return res.status(400).json({ error: 'No file uploaded' });
        }

        // Process document with Adaptive system
        const processingResult = await processDocument({
            filePath: req.file.path,
            companyId: companyId || user.companyId,
            departmentId: departmentId || user.departmentId,
            uploadedBy: user._id.toString(),
            tags: tags ? tags.split(',') : []
        });

        // Create document in MongoDB
        const document = new Document({
            filename: processingResult.filename,
            originalName: processingResult.originalName,
            filePath: req.file.path,
            size: processingResult.size,
            contentType: processingResult.contentType,
            uploadedBy: user._id,
            companyId: processingResult.companyId,
            departmentId: processingResult.departmentId,
            folderId: folderId || null,
            docType: processingResult.docType,
            tags: processingResult.tags,
            ocrStatus: processingResult.ocrStatus,
            extractedMetadata: processingResult.extractedMetadata,
            confidenceScore: processingResult.confidenceScore,
            signed: processingResult.signed,
            suggestedPath: processingResult.suggestedPath,
            processedAt: new Date(processingResult.processedAt)
        });

        await document.save();

        res.status(201).json({
            success: true,
            document: document,
            processing: {
                confidence: processingResult.confidenceScore,
                processingTime: processingResult.processingTime,
                signed: processingResult.signed,
                suggestedPath: processingResult.suggestedPath
            }
        });

    } catch (error) {
        console.error('Upload error:', error);
        res.status(500).json({ 
            error: 'Failed to process document',
            details: error.message 
        });
    }
});

module.exports = router;
```

### Step 4: Update MongoDB Document Model

**File: `projectena/backend/models/Document.js`**

```javascript
const mongoose = require('mongoose');

const documentSchema = new mongoose.Schema({
    // Basic file information
    filename: { type: String, required: true },
    originalName: { type: String, required: true },
    filePath: { type: String, required: true },
    size: { type: Number, required: true },
    contentType: { type: String, required: true },
    
    // User and organization
    uploadedBy: { 
        type: mongoose.Schema.Types.ObjectId, 
        ref: 'User', 
        required: true 
    },
    companyId: { type: String, required: true },
    departmentId: { type: String, required: true },
    folderId: { 
        type: mongoose.Schema.Types.ObjectId, 
        ref: 'Folder',
        default: null
    },
    
    // Document classification
    docType: { type: String, default: 'unknown' },
    tags: [String],
    
    // OCR/Processing status
    ocrStatus: { 
        type: String, 
        enum: ['pending', 'processing', 'completed', 'failed'],
        default: 'pending'
    },
    
    // Extracted data from Adaptive system
    extractedMetadata: {
        ocr_text: String,
        ocr_confidence: Number,
        document_type: String,
        classification_confidence: Number,
        entities: mongoose.Schema.Types.Mixed,
        signature_info: {
            signed: Boolean,
            signature_count: Number,
            confidence: Number
        },
        folder_paths: {
            base_path: String,
            dated_path: String,
            full_path: String
        }
    },
    
    // Processing metrics
    confidenceScore: { type: Number, default: 0 },
    processingTime: Number,
    signed: { type: Boolean, default: false },  // Quick access to signature status
    suggestedPath: String,  // Auto-generated folder path
    processedAt: Date,
    
    // Standard timestamps
    createdAt: { type: Date, default: Date.now },
    updatedAt: { type: Date, default: Date.now }
}, {
    timestamps: true
});

// Indexes for performance
documentSchema.index({ companyId: 1, departmentId: 1 });
documentSchema.index({ uploadedBy: 1 });
documentSchema.index({ docType: 1 });
documentSchema.index({ signed: 1 });
documentSchema.index({ 'extractedMetadata.document_type': 1 });

module.exports = mongoose.model('Document', documentSchema);
```

### Step 5: Update React Frontend

**File: `projectena/frontend/src/components/DocumentUpload.jsx`**

```javascript
import React, { useState } from 'react';
import axios from 'axios';

const DocumentUpload = ({ user, onUploadComplete }) => {
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    const handleFileChange = (e) => {
        setFile(e.target.files[0]);
        setError(null);
    };

    const handleUpload = async (e) => {
        e.preventDefault();
        
        if (!file) {
            setError('Please select a file');
            return;
        }

        setUploading(true);
        setError(null);
        setResult(null);

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('companyId', user.companyId);
            formData.append('departmentId', user.departmentId);

            const response = await axios.post('/api/documents/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                },
                onUploadProgress: (progressEvent) => {
                    const percentCompleted = Math.round(
                        (progressEvent.loaded * 100) / progressEvent.total
                    );
                    console.log(`Upload progress: ${percentCompleted}%`);
                }
            });

            setResult(response.data);
            
            if (onUploadComplete) {
                onUploadComplete(response.data.document);
            }

            // Reset form
            setFile(null);
            e.target.reset();

        } catch (err) {
            setError(err.response?.data?.details || 'Upload failed');
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="document-upload">
            <h2>Upload Document</h2>
            
            <form onSubmit={handleUpload}>
                <div className="form-group">
                    <label htmlFor="file">Select Document:</label>
                    <input
                        type="file"
                        id="file"
                        onChange={handleFileChange}
                        accept=".pdf,.jpg,.jpeg,.png,.tiff,.bmp"
                        disabled={uploading}
                    />
                </div>

                <button 
                    type="submit" 
                    disabled={!file || uploading}
                    className="btn btn-primary"
                >
                    {uploading ? 'Processing...' : 'Upload & Process'}
                </button>
            </form>

            {error && (
                <div className="alert alert-error">
                    {error}
                </div>
            )}

            {result && (
                <div className="alert alert-success">
                    <h3>✅ Document Processed Successfully!</h3>
                    <ul>
                        <li><strong>Type:</strong> {result.document.docType}</li>
                        <li><strong>Signed:</strong> {result.processing.signed ? 'Yes ✓' : 'No'}</li>
                        <li><strong>Confidence:</strong> {(result.processing.confidence * 100).toFixed(1)}%</li>
                        <li><strong>Suggested Path:</strong> {result.processing.suggestedPath}</li>
                        <li><strong>Processing Time:</strong> {result.processing.processingTime.toFixed(2)}s</li>
                    </ul>
                </div>
            )}
        </div>
    );
};

export default DocumentUpload;
```

---

## 📡 API Reference

### Endpoint: POST /upload/analyze/projectena

**URL:** `http://localhost:8003/upload/analyze/projectena`

**Method:** `POST`

**Content-Type:** `multipart/form-data`

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | File | Yes | Document file (PDF, JPG, PNG, etc.) |
| `companyId` | String | Yes | Company identifier |
| `departmentId` | String | Yes | Department identifier |
| `uploadedBy` | String | Yes | User ID who uploaded |
| `folderId` | String | No | Optional folder ID |
| `tags` | String[] | No | Optional tags array |

**Response:**

```json
{
  "filename": "20251101_120000_document.pdf",
  "originalName": "document.pdf",
  "size": 102400,
  "contentType": "application/pdf",
  "uploadedBy": "user_123",
  "companyId": "acme_corp",
  "departmentId": "finance",
  "folderId": null,
  "docType": "invoice",
  "tags": ["invoice", "finance", "2025"],
  "ocrStatus": "completed",
  "extractedMetadata": {
    "ocr_text": "Full extracted text...",
    "ocr_confidence": 0.92,
    "document_type": "invoice",
    "classification_confidence": 0.88,
    "entities": {
      "invoice_number": "INV-2025-001",
      "total_amount": "$1,234.56",
      "due_date": "2025-12-01"
    },
    "signature_info": {
      "signed": true,
      "signature_count": 1,
      "confidence": 0.95
    },
    "folder_paths": {
      "base_path": "/acme_corp/finance/invoice",
      "dated_path": "/acme_corp/finance/invoice/2025/11",
      "full_path": "/acme_corp/finance/invoice/2025/11/01"
    }
  },
  "processingTime": 2.5,
  "confidenceScore": 0.88,
  "signed": true,
  "suggestedPath": "/acme_corp/finance/invoice/2025/11/01",
  "status": "processed",
  "processedAt": "2025-11-01T12:00:00.000Z"
}
```

---

## 📱 Scanner Integration

### Configure Network Scanner

Many network scanners (Canon, HP, Epson) support "Scan to HTTP" or "Scan to Web".

**Scanner Settings:**

```
Name: Adaptive Document Processing
URL: http://YOUR_SERVER_IP:8003/upload/scan
Method: POST
Format: Multipart/form-data

Parameters:
  scanner_id: canon_mfp_01
  company_id: your_company
  department_id: finance
```

**Example Scanner POST:**

```http
POST /upload/scan HTTP/1.1
Host: YOUR_SERVER_IP:8003
Content-Type: multipart/form-data; boundary=----boundary

------boundary
Content-Disposition: form-data; name="file"; filename="scan.pdf"
Content-Type: application/pdf

<binary PDF data>
------boundary
Content-Disposition: form-data; name="scanner_id"

canon_mfp_01
------boundary
Content-Disposition: form-data; name="company_id"

acme_corp
------boundary
Content-Disposition: form-data; name="department_id"

finance
------boundary--
```

---

## 🧪 Testing

### Test 1: Manual cURL Test

```bash
# Create test document
echo "Invoice #12345, Amount: \$1500.00, Due Date: December 1, 2025" > test.txt

# Upload to Adaptive API
curl -X POST http://localhost:8003/upload/analyze/projectena \
  -F "file=@test.txt" \
  -F "companyId=test_company" \
  -F "departmentId=test_dept" \
  -F "uploadedBy=test_user" \
  | python -m json.tool
```

### Test 2: Projectena Integration Test

```javascript
// test/documentProcessing.test.js
const { processDocument } = require('../services/documentProcessingService');

describe('Document Processing Integration', () => {
    it('should process document and return metadata', async () => {
        const result = await processDocument({
            filePath: './test/fixtures/sample_invoice.pdf',
            companyId: 'test_company',
            departmentId: 'finance',
            uploadedBy: 'user_123',
            tags: ['test', 'invoice']
        });

        expect(result).toHaveProperty('filename');
        expect(result).toHaveProperty('docType');
        expect(result).toHaveProperty('signed');
        expect(result.ocrStatus).toBe('completed');
        expect(result.confidenceScore).toBeGreaterThan(0);
    });
});
```

### Test 3: End-to-End Test

1. Start all Adaptive services
2. Start Projectena backend
3. Open Projectena frontend
4. Upload a test document
5. Verify:
   - Document appears in MongoDB
   - Metadata is extracted correctly
   - Signed field is set correctly
   - Folder path is generated

---

## 🐛 Troubleshooting

### Issue: Connection Refused

**Symptom:** `ECONNREFUSED` error from Projectena

**Solution:**
```bash
# Check if Adaptive services are running
curl http://localhost:8003/health

# Check firewall settings
# Windows: Allow port 8003 in Windows Firewall
# Linux: sudo ufw allow 8003
```

### Issue: Timeout Errors

**Symptom:** Request timeout after 60 seconds

**Solution:**
```javascript
// Increase timeout in Projectena
const response = await axios.post(url, formData, {
    timeout: 120000  // 2 minutes
});
```

### Issue: Low Confidence Scores

**Symptom:** `confidenceScore` < 0.5

**Solution:**
- Check document quality (resolution, clarity)
- Ensure documents are properly scanned (not skewed/blurry)
- Consider fine-tuning models for domain-specific documents

### Issue: Missing Entities

**Symptom:** `entities` object is empty

**Solution:**
- NLP service may need domain-specific training
- Check if document text is clear and readable
- Verify NLP service is running (`curl http://localhost:8002/health`)

---

## 📊 Monitoring Integration

### Log Processing Metrics

```javascript
// Add to Projectena backend
router.post('/upload', upload.single('file'), async (req, res) => {
    const startTime = Date.now();
    
    try {
        const result = await processDocument({...});
        
        // Log metrics
        console.log({
            event: 'document_processed',
            duration: Date.now() - startTime,
            confidence: result.confidenceScore,
            signed: result.signed,
            docType: result.docType,
            fileSize: result.size
        });
        
        // ... rest of code
    } catch (error) {
        console.error({
            event: 'document_processing_failed',
            duration: Date.now() - startTime,
            error: error.message
        });
        throw error;
    }
});
```

---

## ✅ Integration Checklist

- [ ] Adaptive services running and healthy
- [ ] Projectena can reach Adaptive API
- [ ] `documentProcessingService.js` created
- [ ] Document upload route updated
- [ ] MongoDB Document model updated
- [ ] React frontend updated with upload component
- [ ] Test documents processed successfully
- [ ] Metadata saved correctly in MongoDB
- [ ] Signed field working correctly
- [ ] Folder paths generated correctly
- [ ] Scanner integration configured (if needed)
- [ ] Error handling implemented
- [ ] Logging configured
- [ ] Performance monitoring in place

---

**🎉 Integration Complete! Your Projectena system now has AI-powered document processing!**

For deployment to production, see [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
