# 🔄 Complete System Flow: Projectena + Adaptive Document Processing

## Overview

This document maps the **complete end-to-end flow** from user login in Projectena to document processing and final storage, integrating both systems.

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         PROJECTENA SYSTEM                            │
│                   (Node.js + Express + MongoDB)                      │
│                         Port: 5000 (Backend)                         │
│                         Port: 5173 (React Frontend)                  │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ HTTP REST API
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│              ADAPTIVE DOCUMENT PROCESSING SYSTEM                     │
│                      (Python FastAPI Services)                       │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐       │
│  │  OCR Service   │  │  ICR Service   │  │  NLP Service   │       │
│  │   Port: 8000   │  │   Port: 8002   │  │   Port: 8001   │       │
│  │  (DeepSeek)    │  │  (TrOCR+ICR)   │  │  (spaCy+NER)   │       │
│  └────────────────┘  └────────────────┘  └────────────────┘       │
│           │                   │                   │                 │
│           └───────────────────┴───────────────────┘                 │
│                              │                                      │
│                    ┌─────────▼─────────┐                           │
│                    │ Intelligence API  │                           │
│                    │   Port: 8003      │                           │
│                    └───────────────────┘                           │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Complete User Flow (Login → Document → Exit)

### Phase 1: Authentication & Login

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: USER LOGIN                                                  │
└─────────────────────────────────────────────────────────────────────┘

1. User opens Projectena React app (http://localhost:5173)
2. Navigates to /login page

┌─────────────────────────────────────────────────────────────────────┐
│ REACT FRONTEND (Login.jsx)                                          │
└─────────────────────────────────────────────────────────────────────┘
   │
   │ User enters: email + password
   │
   ▼
POST http://localhost:5000/users/login
{
  "email": "user@company.com",
  "password": "********"
}

┌─────────────────────────────────────────────────────────────────────┐
│ EXPRESS BACKEND (UserController.js)                                 │
└─────────────────────────────────────────────────────────────────────┘
   │
   ├─► Validate credentials (bcrypt.compare)
   ├─► Check isVerified = true
   ├─► Generate JWT tokens:
   │     - Access Token (15 min expiry)
   │     - Refresh Token (7 days expiry)
   │
   ▼
RESPONSE:
{
  "user": {
    "userId": "507f1f77bcf86cd799439011",
    "email": "user@company.com",
    "firstName": "John",
    "lastName": "Doe",
    "role": "user",
    "companyId": "507f1f77bcf86cd799439012",
    "departmentId": "507f1f77bcf86cd799439013",
    "isSuperAdmin": false,
    "isVerified": true
  },
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}

┌─────────────────────────────────────────────────────────────────────┐
│ REACT FRONTEND (AuthContext.jsx)                                    │
└─────────────────────────────────────────────────────────────────────┘
   │
   ├─► Store in localStorage:
   │     - user object
   │     - token
   │     - refreshToken
   │
   ├─► Update AuthContext state
   │
   ├─► Setup axios interceptors (auto-inject token)
   │
   ▼
Redirect to: /dashboard
```

---

### Phase 2: Document Upload

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: USER NAVIGATES TO DOCUMENT UPLOAD                          │
└─────────────────────────────────────────────────────────────────────┘

User on Dashboard → Clicks "Upload Document"

┌─────────────────────────────────────────────────────────────────────┐
│ REACT FRONTEND (DocumentUpload.jsx or Documents.jsx)                │
└─────────────────────────────────────────────────────────────────────┘
   │
   │ User actions:
   │  1. Selects file (PDF, PNG, JPG, etc.)
   │  2. Optionally selects:
   │     - Folder (optional)
   │     - Tags (optional)
   │  3. Clicks "Upload"
   │
   ▼

┌─────────────────────────────────────────────────────────────────────┐
│ FRONTEND: Prepare Upload Request                                    │
└─────────────────────────────────────────────────────────────────────┘

const formData = new FormData();
formData.append('file', selectedFile);
formData.append('companyId', user.companyId);      // From AuthContext
formData.append('departmentId', user.departmentId); // From AuthContext
formData.append('uploadedBy', user.userId);         // From AuthContext
formData.append('folderId', selectedFolder || '');  // Optional
formData.append('tags', JSON.stringify(tags));      // Optional

   │
   │ Option A: Direct to Projectena Backend
   │ Option B: Direct to Adaptive System (recommended)
   │
   ▼
```

---

### Phase 3: Document Processing (Adaptive System)

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: ADAPTIVE SYSTEM PROCESSES DOCUMENT                         │
└─────────────────────────────────────────────────────────────────────┘

POST http://localhost:8003/upload/analyze/projectena
Headers: { Authorization: Bearer <token> }  # Optional
FormData:
  - file: <binary data>
  - companyId: "507f1f77bcf86cd799439012"
  - departmentId: "507f1f77bcf86cd799439013"
  - uploadedBy: "507f1f77bcf86cd799439011"
  - folderId: "507f1f77bcf86cd799439014" (optional)
  - tags: '["invoice","urgent"]' (optional)

┌─────────────────────────────────────────────────────────────────────┐
│ DOCUMENT INTELLIGENCE SERVICE (Port 8003)                           │
│ File: python-document-intelligence-service/main.py                  │
│ Endpoint: /upload/analyze/projectena                                │
└─────────────────────────────────────────────────────────────────────┘
   │
   ├─► Step 3.1: Save uploaded file to temp location
   │
   ├─► Step 3.2: Document Complexity Analysis
   │     ├─ Analyze layout complexity
   │     ├─ Detect document type (invoice, contract, form, etc.)
   │     └─ Determine processing strategy
   │
   ├─► Step 3.3: Parallel Processing
   │     │
   │     ├─► OCR Service (Port 8000)
   │     │   POST /ocr/process
   │     │   ├─ Complexity routing:
   │     │   │  - Simple docs → TrOCR
   │     │   │  - Complex docs → DeepSeek OCR
   │     │   ├─ Extract printed text
   │     │   ├─ Get bounding boxes
   │     │   └─ Generate annotated PDF (NEW!)
   │     │
   │     ├─► ICR Service (Port 8002)
   │     │   POST /hybrid/process
   │     │   ├─ Detect handwritten regions
   │     │   ├─ Extract handwritten text (TrOCR)
   │     │   ├─ Detect signatures
   │     │   ├─ Mixed document analysis
   │     │   └─ Generate annotated PDF (NEW!)
   │     │
   │     └─► NLP Service (Port 8001)
   │         POST /nlp/analyze
   │         ├─ Parse markdown structure
   │         ├─ Structure-aware NER
   │         ├─ Entity extraction
   │         ├─ Date/amount/reference parsing
   │         └─ Generate metadata
   │
   ├─► Step 3.4: Signature Detection
   │     ├─ Check ICR results for signatures
   │     ├─ Count signature regions
   │     └─ Calculate confidence scores
   │
   ├─► Step 3.5: Folder Path Suggestion
   │     ├─ Based on document type
   │     ├─ Company/department hierarchy
   │     ├─ New structure: department/year/month/documentType
   │     └─ Example: /Finance/2025/November/Invoices/
   │
   ├─► Step 3.6: Create Annotated PDF (NEW!)
   │     ├─ Copy original PDF
   │     ├─ Overlay extracted text (blue)
   │     ├─ Highlight signatures (red boxes)
   │     ├─ Add handwritten comments (green margin)
   │     ├─ Auto-generate filename from title
   │     └─ Save in same directory as original
   │
   ▼

RESPONSE (Projectena-Compatible Format):
{
  // Document Metadata
  "filename": "invoice_12345_20251101.pdf",
  "originalName": "Scan001.pdf",
  "size": 245678,
  "contentType": "application/pdf",
  "checksum": "abc123def456...",
  
  // Ownership & Organization
  "companyId": "507f1f77bcf86cd799439012",
  "departmentId": "507f1f77bcf86cd799439013",
  "uploadedBy": "507f1f77bcf86cd799439011",
  "folderId": "507f1f77bcf86cd799439014",
  "tags": ["invoice", "urgent"],
  
  // Document Classification
  "documentType": "invoice",
  "category": "financial",
  "classification": {
    "type": "invoice",
    "confidence": 0.95,
    "subtype": "service_invoice"
  },
  
  // Extracted Content
  "extractedText": "Invoice #12345\nDate: November 1, 2025\nAmount: $1,234.56...",
  "extractedEntities": {
    "invoice_number": "12345",
    "date": "2025-11-01",
    "amount": 1234.56,
    "currency": "USD",
    "vendor": "ABC Company",
    "customer": "XYZ Corp"
  },
  
  // Signature Detection (NEW!)
  "signed": true,
  "signatureCount": 2,
  "signatureConfidence": 0.91,
  "signatures": [
    {
      "bbox": [100, 800, 300, 900],
      "confidence": 0.93,
      "page": 1
    },
    {
      "bbox": [400, 850, 600, 920],
      "confidence": 0.89,
      "page": 1
    }
  ],
  
  // Handwriting Detection
  "hasHandwriting": true,
  "handwrittenText": "Approved by John Doe",
  "handwritingConfidence": 0.82,
  
  // Processing Quality
  "confidence": 0.94,
  "ocrConfidence": 0.96,
  "nlpConfidence": 0.92,
  
  // Folder Organization
  "suggestedFolder": "507f1f77bcf86cd799439015",
  "suggestedPath": "/Finance/2025/November/Invoices/",
  
  // Annotated PDF (NEW!)
  "annotatedPdf": "C:\\Users\\Ahmad\\Documents\\Uploads\\Invoice_12345_annotated.pdf",
  
  // Status
  "status": "processed",
  "processedAt": "2025-11-01T12:34:56.789Z",
  
  // Metadata
  "metadata": {
    "processingTime": 4.56,
    "engines": {
      "ocr": "deepseek",
      "icr": "trocr",
      "nlp": "spacy"
    },
    "complexity": "complex",
    "pageCount": 1
  }
}
```

---

### Phase 4: Save to Projectena Database

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: PROJECTENA BACKEND SAVES TO MONGODB                        │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ OPTION A: Frontend calls Adaptive directly (current)                │
└─────────────────────────────────────────────────────────────────────┘

React → Adaptive API → React gets response
   │
   └─► React calls: POST /documents (Projectena backend)
       Body: { ...adaptive_response }

┌─────────────────────────────────────────────────────────────────────┐
│ OPTION B: Backend proxy (recommended)                               │
└─────────────────────────────────────────────────────────────────────┘

React → Projectena Backend → Adaptive API → Backend saves → Response
   │
   └─► More secure (backend handles file storage + DB)

┌─────────────────────────────────────────────────────────────────────┐
│ EXPRESS BACKEND (DokumentController.js)                             │
│ POST /documents or POST /documents/upload                           │
└─────────────────────────────────────────────────────────────────────┘
   │
   ├─► Step 4.1: Validate user permissions
   │     - Check user has access to company/department
   │     - Check upload permissions
   │
   ├─► Step 4.2: Save file to storage
   │     - Local: ./uploads/companyId/departmentId/
   │     - Cloud: S3/GCS bucket
   │     - Get file URL
   │
   ├─► Step 4.3: Create MongoDB document
   │
   ▼

const document = new Document({
  // File Info
  filename: "invoice_12345_20251101.pdf",
  originalName: "Scan001.pdf",
  filePath: "/uploads/companyA/finance/invoice_12345_20251101.pdf",
  size: 245678,
  contentType: "application/pdf",
  
  // Organization
  companyId: ObjectId("507f1f77bcf86cd799439012"),
  departmentId: ObjectId("507f1f77bcf86cd799439013"),
  folderId: ObjectId("507f1f77bcf86cd799439014"),
  uploadedBy: ObjectId("507f1f77bcf86cd799439011"),
  
  // Classification
  documentType: "invoice",
  category: "financial",
  tags: ["invoice", "urgent"],
  
  // Extracted Data (from Adaptive)
  extractedText: "Invoice #12345...",
  extractedEntities: {
    invoice_number: "12345",
    date: "2025-11-01",
    amount: 1234.56,
    vendor: "ABC Company"
  },
  
  // Signature Info (NEW!)
  signed: true,
  signatureCount: 2,
  signatureConfidence: 0.91,
  
  // Annotated PDF (NEW!)
  annotatedPdfPath: "/uploads/companyA/finance/Invoice_12345_annotated.pdf",
  
  // Quality Metrics
  confidence: 0.94,
  ocrConfidence: 0.96,
  
  // Status
  status: "processed",
  processedAt: new Date("2025-11-01T12:34:56.789Z"),
  
  // Timestamps
  createdAt: new Date(),
  updatedAt: new Date()
});

await document.save();

   │
   ▼

RESPONSE to Frontend:
{
  "success": true,
  "document": {
    "_id": "507f1f77bcf86cd799439020",
    "filename": "invoice_12345_20251101.pdf",
    "documentType": "invoice",
    "signed": true,
    "extractedEntities": { ... },
    "annotatedPdfPath": "/uploads/.../Invoice_12345_annotated.pdf",
    // ... all fields
  }
}
```

---

### Phase 5: Display in Dashboard

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 5: USER VIEWS DOCUMENT IN DASHBOARD                           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ REACT FRONTEND (Dashboard.jsx or Documents.jsx)                     │
└─────────────────────────────────────────────────────────────────────┘
   │
   ├─► Upload success notification shown
   │
   ├─► Documents list refreshes
   │
   ▼

GET http://localhost:5000/documents?companyId=xxx&departmentId=xxx
Headers: { Authorization: Bearer <token> }

┌─────────────────────────────────────────────────────────────────────┐
│ EXPRESS BACKEND (DokumentController.js)                             │
└─────────────────────────────────────────────────────────────────────┘
   │
   ├─► Query MongoDB:
   │     - Filter by user's company/department
   │     - Apply user's folder permissions
   │     - Sort by createdAt (descending)
   │
   ▼

RESPONSE:
{
  "documents": [
    {
      "_id": "507f1f77bcf86cd799439020",
      "filename": "invoice_12345_20251101.pdf",
      "documentType": "invoice",
      "signed": true,
      "signatureCount": 2,
      "extractedEntities": {
        "invoice_number": "12345",
        "amount": 1234.56,
        "date": "2025-11-01"
      },
      "annotatedPdfPath": "/uploads/.../Invoice_12345_annotated.pdf",
      "processedAt": "2025-11-01T12:34:56.789Z",
      "uploadedBy": {
        "firstName": "John",
        "lastName": "Doe"
      }
    },
    // ... more documents
  ],
  "total": 42,
  "page": 1,
  "pageSize": 20
}

┌─────────────────────────────────────────────────────────────────────┐
│ REACT FRONTEND: Display Documents Table                             │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Documents                                                        │
├──────────────────────────────────────────────────────────────────┤
│ Filename                │ Type    │ Signed │ Amount   │ Date    │
├─────────────────────────┼─────────┼────────┼──────────┼─────────┤
│ invoice_12345_...pdf    │ Invoice │ ✅ (2) │ $1,234.56│ Nov 1   │
│ contract_abc.pdf        │ Contract│ ✅ (1) │ -        │ Oct 31  │
│ receipt_999.jpg         │ Receipt │ ❌     │ $45.00   │ Oct 30  │
└─────────────────────────┴─────────┴────────┴──────────┴─────────┘

   │
   │ User clicks on document
   │
   ▼
```

---

### Phase 6: View Document Details

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 6: VIEW DOCUMENT DETAILS & ANNOTATED PDF                      │
└─────────────────────────────────────────────────────────────────────┘

User clicks: "invoice_12345_20251101.pdf"

┌─────────────────────────────────────────────────────────────────────┐
│ REACT FRONTEND (DocumentViewer.jsx or DocumentDetails.jsx)          │
└─────────────────────────────────────────────────────────────────────┘
   │
   ▼

GET http://localhost:5000/documents/507f1f77bcf86cd799439020

RESPONSE:
{
  "document": {
    "_id": "507f1f77bcf86cd799439020",
    "filename": "invoice_12345_20251101.pdf",
    "filePath": "/uploads/companyA/finance/invoice_12345_20251101.pdf",
    
    // Annotated PDF (NEW!)
    "annotatedPdfPath": "/uploads/companyA/finance/Invoice_12345_annotated.pdf",
    
    "documentType": "invoice",
    "signed": true,
    "signatureCount": 2,
    "signatures": [
      { "bbox": [100, 800, 300, 900], "confidence": 0.93, "page": 1 },
      { "bbox": [400, 850, 600, 920], "confidence": 0.89, "page": 1 }
    ],
    
    "extractedText": "Invoice #12345\nDate: November 1, 2025...",
    "extractedEntities": {
      "invoice_number": "12345",
      "date": "2025-11-01",
      "amount": 1234.56,
      "currency": "USD",
      "vendor": "ABC Company",
      "customer": "XYZ Corp"
    },
    
    "confidence": 0.94,
    "processedAt": "2025-11-01T12:34:56.789Z",
    "uploadedBy": { ... },
    "metadata": { ... }
  }
}

┌─────────────────────────────────────────────────────────────────────┐
│ FRONTEND: Document Details View                                     │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Invoice #12345                                          [Download]│
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│ ┌──────────────────┐  ┌──────────────────────────────────────┐ │
│ │  Original PDF    │  │  Annotated PDF (NEW!)               │ │
│ │                  │  │                                      │ │
│ │  [PDF Viewer]    │  │  [Shows overlays, signatures,       │ │
│ │                  │  │   handwritten comments]             │ │
│ └──────────────────┘  └──────────────────────────────────────┘ │
│                                                                  │
│ Details:                                                         │
│ ├─ Invoice Number: 12345                                        │
│ ├─ Date: November 1, 2025                                       │
│ ├─ Amount: $1,234.56 USD                                        │
│ ├─ Vendor: ABC Company                                          │
│ ├─ Customer: XYZ Corp                                           │
│ ├─ Signatures: ✅ 2 detected (93% confidence)                  │
│ ├─ Handwriting: "Approved by John Doe"                          │
│ └─ Processed: Nov 1, 2025 12:34 PM                              │
│                                                                  │
│ Extracted Text:                                                  │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ Invoice #12345                                             │ │
│ │ Date: November 1, 2025                                     │ │
│ │ Amount: $1,234.56                                          │ │
│ │ ...                                                         │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ [View Original] [View Annotated] [Download] [Edit] [Delete]    │
└──────────────────────────────────────────────────────────────────┘
```

---

### Phase 7: Download Documents

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 7: DOWNLOAD ORIGINAL OR ANNOTATED PDF                         │
└─────────────────────────────────────────────────────────────────────┘

User clicks: "Download Original" or "Download Annotated"

┌─────────────────────────────────────────────────────────────────────┐
│ Option 1: Download Original                                         │
└─────────────────────────────────────────────────────────────────────┘

GET http://localhost:5000/documents/507f1f77bcf86cd799439020/download

   ├─► Backend validates permissions
   ├─► Reads file from storage
   ├─► Sets headers:
   │     Content-Type: application/pdf
   │     Content-Disposition: attachment; filename="invoice_12345.pdf"
   └─► Streams file to browser

┌─────────────────────────────────────────────────────────────────────┐
│ Option 2: Download Annotated PDF (NEW!)                            │
└─────────────────────────────────────────────────────────────────────┘

GET http://localhost:5000/documents/507f1f77bcf86cd799439020/download/annotated

   ├─► Backend validates permissions
   ├─► Reads annotated PDF from storage
   ├─► Sets headers:
   │     Content-Type: application/pdf
   │     Content-Disposition: attachment; filename="Invoice_12345_annotated.pdf"
   └─► Streams file to browser

Browser downloads file to user's Downloads folder
```

---

### Phase 8: Logout / Exit

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 8: USER LOGOUT                                                │
└─────────────────────────────────────────────────────────────────────┘

User clicks: "Logout" in navbar

┌─────────────────────────────────────────────────────────────────────┐
│ REACT FRONTEND (AuthContext.jsx)                                    │
└─────────────────────────────────────────────────────────────────────┘
   │
   ├─► POST http://localhost:5000/users/logout
   │     Headers: { Authorization: Bearer <token> }
   │
   ▼

┌─────────────────────────────────────────────────────────────────────┐
│ EXPRESS BACKEND (UserController.js)                                 │
└─────────────────────────────────────────────────────────────────────┘
   │
   ├─► Invalidate refresh token in DB
   ├─► Add access token to blacklist (if using)
   │
   ▼

RESPONSE: { success: true }

┌─────────────────────────────────────────────────────────────────────┐
│ REACT FRONTEND                                                       │
└─────────────────────────────────────────────────────────────────────┘
   │
   ├─► Clear localStorage:
   │     - Remove user
   │     - Remove token
   │     - Remove refreshToken
   │
   ├─► Clear AuthContext state
   │
   ├─► Redirect to /login
   │
   ▼

User is logged out → Back to login page
```

---

## 🔄 Alternative Upload Methods

### Method 1: Web Upload (Standard)
**Flow:** User → React → Adaptive → Projectena Backend → MongoDB

### Method 2: Network Scanner Upload
**Flow:** Scanner → POST /upload/scan → Adaptive → Projectena Backend → MongoDB

```
POST http://localhost:8003/upload/scan
FormData:
  - file: <scanned image>
  - scannerId: "scanner_001"
  - companyId: "507f1f77bcf86cd799439012"
  - departmentId: "507f1f77bcf86cd799439013"
  - scanDate: "2025-11-01T12:34:56Z"
```

### Method 3: Email Import (Planned)
**Flow:** Email Server → IMAP Monitor → Extract Attachments → Adaptive → MongoDB

```
Email arrives → Python IMAP service polls
  → Extracts PDF attachments
  → Calls /upload/analyze/projectena
  → Saves to MongoDB with email metadata
```

---

## 🎯 Data Flow Summary

```
┌─────────────┐
│ Login Form  │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ JWT Token       │ ◄───────────┐
│ (15 min expiry) │             │
└──────┬──────────┘             │
       │                        │
       ▼                        │ Auto-refresh
┌─────────────────┐             │ on 401
│ Upload Document │             │
└──────┬──────────┘             │
       │                        │
       ▼                        │
┌──────────────────────────┐    │
│ Adaptive Processing:     │    │
│ ├─ OCR (text + annotate) │    │
│ ├─ ICR (signatures)      │    │
│ ├─ NLP (entities)        │    │
│ └─ Annotated PDF (NEW!)  │    │
└──────┬───────────────────┘    │
       │                        │
       ▼                        │
┌─────────────────────┐         │
│ Projectena Backend  │         │
│ ├─ Save file        │         │
│ ├─ Save to MongoDB  │         │
│ └─ Return response  │         │
└──────┬──────────────┘         │
       │                        │
       ▼                        │
┌─────────────────────┐         │
│ React Dashboard     │         │
│ ├─ Display docs     │         │
│ ├─ View annotated   │         │
│ └─ Download         │         │
└──────┬──────────────┘         │
       │                        │
       │ (loop back on actions) │
       └────────────────────────┘
```

---

## 🔐 Security Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ AUTHENTICATION & AUTHORIZATION AT EACH STEP                        │
└─────────────────────────────────────────────────────────────────────┘

1. LOGIN
   ├─ Credentials validated
   ├─ Email verification checked
   └─ JWT tokens generated

2. EVERY API REQUEST
   ├─ axios interceptor adds: Authorization: Bearer <token>
   ├─ Express middleware validates JWT
   ├─ Extracts user context (userId, companyId, departmentId, role)
   └─ Checks permissions for resource

3. DOCUMENT UPLOAD
   ├─ Validate user has upload permission
   ├─ Validate user belongs to company/department
   └─ Associate document with user's context

4. DOCUMENT ACCESS
   ├─ Validate user has read permission
   ├─ Check document belongs to user's company/department
   └─ Check folder-level permissions

5. TOKEN REFRESH
   ├─ Access token expires (15 min)
   ├─ Axios interceptor detects 401
   ├─ Calls /users/token/refresh with refresh token
   ├─ Gets new access token
   └─ Retries original request

6. LOGOUT
   ├─ Invalidate refresh token in DB
   ├─ Clear client-side storage
   └─ User must re-login
```

---

## 🗂️ File Storage Structure

```
/uploads/
├── company_507f1f77bcf86cd799439012/
│   ├── department_507f1f77bcf86cd799439013/  (Finance)
│   │   ├── 2025/
│   │   │   ├── November/
│   │   │   │   ├── Invoices/
│   │   │   │   │   ├── invoice_12345_20251101.pdf        ◄── Original
│   │   │   │   │   ├── Invoice_12345_annotated.pdf       ◄── Annotated (NEW!)
│   │   │   │   │   └── invoice_67890_20251102.pdf
│   │   │   │   ├── Contracts/
│   │   │   │   │   ├── contract_abc.pdf
│   │   │   │   │   └── Contract_ABC_annotated.pdf        ◄── Annotated (NEW!)
│   │   │   │   └── Receipts/
│   │   │   └── October/
│   │   │       └── Invoices/
│   │   └── 2024/
│   └── department_507f1f77bcf86cd799439014/  (Legal)
│       └── 2025/
│           └── November/
│               └── Contracts/
└── company_507f1f77bcf86cd799439015/
```

**Folder Hierarchy:**
```
Department → Year → Month → Document Type
Finance    → 2025 → November → Invoices
Finance    → 2025 → November → Contracts
Legal      → 2025 → November → Contracts
```

---

## 📊 MongoDB Collections

### Users Collection
```javascript
{
  _id: ObjectId("507f1f77bcf86cd799439011"),
  email: "user@company.com",
  passwordHash: "$2b$10$...",
  firstName: "John",
  lastName: "Doe",
  role: "user",
  companyId: ObjectId("507f1f77bcf86cd799439012"),
  departmentId: ObjectId("507f1f77bcf86cd799439013"),
  isVerified: true,
  refreshTokens: [{ tokenHash: "...", expiresAt: Date }],
  createdAt: ISODate("2025-01-01T00:00:00Z")
}
```

### Documents Collection
```javascript
{
  _id: ObjectId("507f1f77bcf86cd799439020"),
  filename: "invoice_12345_20251101.pdf",
  originalName: "Scan001.pdf",
  filePath: "/uploads/companyA/finance/invoice_12345_20251101.pdf",
  annotatedPdfPath: "/uploads/companyA/finance/Invoice_12345_annotated.pdf", // NEW!
  size: 245678,
  contentType: "application/pdf",
  
  companyId: ObjectId("507f1f77bcf86cd799439012"),
  departmentId: ObjectId("507f1f77bcf86cd799439013"),
  folderId: ObjectId("507f1f77bcf86cd799439014"),
  uploadedBy: ObjectId("507f1f77bcf86cd799439011"),
  
  documentType: "invoice",
  category: "financial",
  tags: ["invoice", "urgent"],
  
  extractedText: "Invoice #12345...",
  extractedEntities: {
    invoice_number: "12345",
    date: "2025-11-01",
    amount: 1234.56,
    vendor: "ABC Company"
  },
  
  signed: true,                    // NEW!
  signatureCount: 2,               // NEW!
  signatureConfidence: 0.91,       // NEW!
  signatures: [                    // NEW!
    { bbox: [100, 800, 300, 900], confidence: 0.93, page: 1 }
  ],
  
  confidence: 0.94,
  status: "processed",
  processedAt: ISODate("2025-11-01T12:34:56Z"),
  createdAt: ISODate("2025-11-01T12:34:56Z"),
  updatedAt: ISODate("2025-11-01T12:34:56Z")
}
```

---

## 🚀 Service Ports Reference

| Service | Port | Description |
|---------|------|-------------|
| Projectena Backend | 5000 | Express.js API (MongoDB) |
| Projectena Frontend | 5173 | React app (Vite dev server) |
| OCR Service | 8000 | DeepSeek OCR + TrOCR routing |
| NLP Service | 8001 | spaCy + structured NER |
| ICR Service | 8002 | Handwriting + signature detection |
| Intelligence API | 8003 | Main orchestrator (combines all) |

---

## 🎯 Key Features in Your Flow

### ✅ Implemented
1. **User Authentication** (JWT-based)
2. **Document Upload** (web + scanner)
3. **OCR Processing** (DeepSeek + TrOCR hybrid routing)
4. **ICR Processing** (handwriting + signature detection)
5. **NLP Analysis** (entity extraction, structured parsing)
6. **Document Classification** (invoice, contract, receipt, etc.)
7. **Folder Organization** (company/department hierarchy)
8. **Signature Detection** (count + confidence)
9. **Multi-tenancy** (company/department isolation)
10. **Annotated PDF Generation** (NEW! - overlays, highlights, comments)

### 🔄 In Progress
1. File storage implementation (local/cloud)
2. Download endpoints
3. Email import service

### 📋 Planned
1. Document versioning
2. Audit logging
3. Advanced search
4. Batch processing
5. Webhook notifications

---

## 💡 Summary

**Your complete flow is:**

1. **Login** → Get JWT token → Store in localStorage
2. **Upload Document** → Adaptive API processes (OCR/ICR/NLP)
3. **Adaptive Returns** → Extracted data + annotated PDF + signatures
4. **Projectena Saves** → MongoDB + file storage
5. **Dashboard Shows** → Documents list with metadata
6. **View Details** → Original PDF + Annotated PDF side-by-side
7. **Download** → Either original or annotated version
8. **Logout** → Clear tokens → Redirect to login

**New PDF Annotation Feature:**
- Every processed document gets an annotated PDF copy
- Shows extracted text overlaid on original
- Highlights signatures with red boxes
- Adds handwritten text as margin comments
- Auto-generates descriptive filename
- Both original and annotated saved for comparison

This is a **complete enterprise document management system** with advanced AI processing! 🎉
