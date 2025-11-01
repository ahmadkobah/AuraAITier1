# 📁 Automatic Folder Management Implementation

## Problem Statement

**Current Behavior:**
- Document Intelligence Service suggests folder path: `/Finance/2025/November/Invoices/`
- New structure: **department/year/month/documentType**
- Returns path in `suggestedPath` field
- **Does NOT check** if folder exists in Projectena
- **Does NOT create** folders automatically

**Desired Behavior:**
- Check if suggested folder exists
- Create folder hierarchy if missing (department → year → month → documentType)
- Return actual folder ID that was used/created
- Update document with correct folder association

---

## Solution: Two-Part Implementation

### Part 1: Projectena Backend Enhancement (RECOMMENDED)

The **Projectena backend** should handle folder creation because:
- It has access to MongoDB folders collection
- It knows folder permissions and hierarchy
- It maintains data consistency
- It handles user authentication

### Part 2: Intelligence Service Enhancement (OPTIONAL)

The **Intelligence Service** can optionally query Projectena to check/create folders via API.

---

## Implementation Guide

### Option A: Projectena Backend Handles It (RECOMMENDED)

#### Step 1: Add Folder Auto-Creation to Document Upload

**File: `projectena/backend/controllers/DokumentController.js`**

```javascript
const Folder = require('../models/Folder');
const Document = require('../models/Document');

/**
 * Create folder hierarchy if it doesn't exist
 * New structure: department/year/month/documentType
 * Example: /Finance/2025/November/Invoices/
 */
async function ensureFolderPath(companyId, departmentId, suggestedPath, userId) {
  try {
    // Parse suggested path: /Finance/2025/November/Invoices/
    const pathParts = suggestedPath.split('/').filter(p => p);
    
    // New structure: [company?, department, year, month, docType]
    // Extract parts (skip company if present)
    let startIndex = 0;
    if (pathParts[0] === companyId) {
      startIndex = 1; // Skip company ID
    }
    
    const [department, year, month, docType] = pathParts.slice(startIndex);
    
    let parentFolder = null;
    
    // Step 1: Department folder is the root (already exists in Projectena)
    // We start from year level
    
    // Step 2: Find or create year folder (e.g., "2025")
    let yearFolder = await Folder.findOne({
      name: year,
      companyId: companyId,
      departmentId: departmentId,
      parentFolder: null  // Year is at root level
    });
    
    if (!yearFolder) {
      yearFolder = new Folder({
        name: year,
        description: `Documents from ${year}`,
        companyId: companyId,
        departmentId: departmentId,
        parentFolder: null,
        createdBy: userId,
        path: `/${year}`,
        isAutoCreated: true
      });
      await yearFolder.save();
      console.log(`✅ Created folder: ${year}`);
    }
    
    parentFolder = yearFolder._id;
    
    // Step 3: Find or create month folder (e.g., "November")
    let monthFolder = await Folder.findOne({
      name: month,
      companyId: companyId,
      departmentId: departmentId,
      parentFolder: parentFolder
    });
    
    if (!monthFolder) {
      monthFolder = new Folder({
        name: month,
        description: `Documents from ${month} ${year}`,
        companyId: companyId,
        departmentId: departmentId,
        parentFolder: parentFolder,
        createdBy: userId,
        path: `/${year}/${month}`,
        isAutoCreated: true
      });
      await monthFolder.save();
      console.log(`✅ Created folder: ${month}`);
    }
    
    parentFolder = monthFolder._id;
    
    // Step 4: Find or create document type folder (e.g., "Invoices")
    let docTypeFolder = await Folder.findOne({
      name: docType,
      companyId: companyId,
      departmentId: departmentId,
      parentFolder: parentFolder
    });
    
    if (!docTypeFolder) {
      docTypeFolder = new Folder({
        name: docType,
        description: `${docType} documents`,
        companyId: companyId,
        departmentId: departmentId,
        parentFolder: parentFolder,
        createdBy: userId,
        path: `/${year}/${month}/${docType}`,
        isAutoCreated: true
      });
      await docTypeFolder.save();
      console.log(`✅ Created folder: ${docType}`);
    }
    
    parentFolder = docTypeFolder._id;
    
    return parentFolder; // Return the final folder ID
    
  } catch (error) {
    console.error('Folder creation error:', error);
    throw error;
  }
}

/**
 * Convert month number to name
 * No longer needed - Intelligence Service now returns month name
 */
function getMonthName(monthNum) {
  const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];
  const index = parseInt(monthNum) - 1;
  return months[index] || monthNum;
}

/**
 * Upload and process document with auto folder creation
 */
async function uploadDocument(req, res) {
  try {
    const { companyId, departmentId, tags } = req.body;
    const user = req.user; // From auth middleware
    
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }
    
    // Step 1: Call Adaptive Intelligence Service
    const FormData = require('form-data');
    const axios = require('axios');
    
    const formData = new FormData();
    formData.append('file', req.file.buffer, req.file.originalname);
    formData.append('companyId', companyId || user.companyId);
    formData.append('departmentId', departmentId || user.departmentId);
    formData.append('uploadedBy', user._id.toString());
    formData.append('tags', JSON.stringify(tags || []));
    
    const processingResult = await axios.post(
      'http://localhost:8003/upload/analyze/projectena',
      formData,
      { headers: formData.getHeaders() }
    );
    
    const adaptiveData = processingResult.data;
    
    // Step 2: Auto-create folder hierarchy if needed
    let folderId = req.body.folderId; // Manual folder selection (optional)
    
    if (!folderId && adaptiveData.suggestedPath) {
      console.log(`📁 Auto-creating folder path: ${adaptiveData.suggestedPath}`);
      // Example path: /Finance/2025/November/Invoices/
      folderId = await ensureFolderPath(
        companyId || user.companyId,
        departmentId || user.departmentId,
        adaptiveData.suggestedPath,
        user._id
      );
      console.log(`✅ Folder ready: ${folderId}`);
    }
    
    // Step 3: Save file to storage
    const fs = require('fs').promises;
    const path = require('path');
    
    const uploadDir = path.join(
      __dirname,
      '../../uploads',
      companyId || user.companyId.toString(),
      departmentId || user.departmentId.toString()
    );
    
    await fs.mkdir(uploadDir, { recursive: true });
    const filePath = path.join(uploadDir, adaptiveData.filename);
    await fs.writeFile(filePath, req.file.buffer);
    
    // Step 4: Create document in MongoDB
    const document = new Document({
      filename: adaptiveData.filename,
      originalName: adaptiveData.originalName,
      filePath: `/uploads/${companyId || user.companyId}/${departmentId || user.departmentId}/${adaptiveData.filename}`,
      size: adaptiveData.size,
      contentType: adaptiveData.contentType,
      
      companyId: companyId || user.companyId,
      departmentId: departmentId || user.departmentId,
      folderId: folderId, // Auto-created or manual
      uploadedBy: user._id,
      
      documentType: adaptiveData.docType,
      tags: adaptiveData.tags,
      
      extractedText: adaptiveData.extractedMetadata?.ocr_text,
      extractedEntities: adaptiveData.extractedMetadata?.entities,
      
      signed: adaptiveData.signed,
      signatureCount: adaptiveData.extractedMetadata?.signature_info?.signature_count,
      signatureConfidence: adaptiveData.extractedMetadata?.signature_info?.confidence,
      
      annotatedPdfPath: adaptiveData.extractedMetadata?.annotated_pdf,
      
      confidence: adaptiveData.confidenceScore,
      ocrConfidence: adaptiveData.extractedMetadata?.ocr_confidence,
      
      status: 'processed',
      processedAt: new Date(adaptiveData.processedAt)
    });
    
    await document.save();
    
    res.json({
      success: true,
      document: document,
      folderAutoCreated: !req.body.folderId && folderId !== null
    });
    
  } catch (error) {
    console.error('Document upload error:', error);
    res.status(500).json({ error: error.message });
  }
}

module.exports = { uploadDocument };
```

#### Step 2: Update Folder Model

**File: `projectena/backend/models/Folder.js`**

```javascript
const mongoose = require('mongoose');

const FolderSchema = new mongoose.Schema({
  name: { type: String, required: true },
  description: { type: String },
  
  companyId: { type: mongoose.Schema.Types.ObjectId, ref: 'Company', required: true },
  departmentId: { type: mongoose.Schema.Types.ObjectId, ref: 'Department', required: true },
  parentFolder: { type: mongoose.Schema.Types.ObjectId, ref: 'Folder', default: null },
  
  createdBy: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  
  path: { type: String }, // Full path for display
  
  // NEW: Track auto-created folders
  isAutoCreated: { type: Boolean, default: false },
  autoCreatedAt: { type: Date },
  
  createdAt: { type: Date, default: Date.now },
  updatedAt: { type: Date, default: Date.now }
});

// Index for fast lookup
FolderSchema.index({ companyId: 1, departmentId: 1, name: 1, parentFolder: 1 });

module.exports = mongoose.model('Folder', FolderSchema);
```

#### Step 3: Update Routes

**File: `projectena/backend/routes/documents.js`**

```javascript
const express = require('express');
const router = express.Router();
const multer = require('multer');
const { uploadDocument } = require('../controllers/DokumentController');
const { authenticate } = require('../middleware/auth');

const upload = multer({ storage: multer.memoryStorage() });

router.post('/upload', authenticate, upload.single('file'), uploadDocument);

module.exports = router;
```

---

### Option B: Intelligence Service Checks Folders (OPTIONAL)

If you want the Intelligence Service to check/create folders:

**File: `python-document-intelligence-service/main.py`**

Add this function:

```python
async def ensure_folder_exists(
    company_id: str,
    department_id: str,
    suggested_path: str,
    user_id: str,
    projectena_api_url: str = "http://localhost:5000"
) -> Optional[str]:
    """
    Check if folder exists in Projectena, create if not.
    
    Args:
        company_id: Company ID
        department_id: Department ID
        suggested_path: Path like /CompanyA/Finance/Invoices/2025/11/
        user_id: User who uploaded the document
        projectena_api_url: Projectena backend URL
        
    Returns:
        Folder ID (ObjectId string) or None
    """
    try:
        import httpx
        
        # Parse path
        parts = [p for p in suggested_path.split('/') if p]
        if len(parts) < 3:
            return None
        
        # Remove company/department (first 2 parts)
        folder_parts = parts[2:]  # [docType, year, month, day?]
        
        parent_id = None
        
        # Check/create each level
        for i, folder_name in enumerate(folder_parts):
            # Capitalize first letter
            folder_name = folder_name.capitalize()
            
            async with httpx.AsyncClient() as client:
                # Check if folder exists
                response = await client.get(
                    f"{projectena_api_url}/folders",
                    params={
                        "companyId": company_id,
                        "departmentId": department_id,
                        "name": folder_name,
                        "parentFolder": parent_id or "null"
                    }
                )
                
                if response.status_code == 200:
                    folders = response.json()
                    if folders and len(folders) > 0:
                        parent_id = folders[0]["_id"]
                        logger.info(f"✅ Folder exists: {folder_name} ({parent_id})")
                    else:
                        # Create folder
                        create_response = await client.post(
                            f"{projectena_api_url}/folders",
                            json={
                                "name": folder_name,
                                "description": f"Auto-created folder for {folder_name}",
                                "companyId": company_id,
                                "departmentId": department_id,
                                "parentFolder": parent_id,
                                "createdBy": user_id,
                                "isAutoCreated": True
                            }
                        )
                        
                        if create_response.status_code in [200, 201]:
                            new_folder = create_response.json()
                            parent_id = new_folder["_id"]
                            logger.info(f"✅ Created folder: {folder_name} ({parent_id})")
                        else:
                            logger.error(f"Failed to create folder: {folder_name}")
                            return None
        
        return parent_id  # Return final folder ID
        
    except Exception as e:
        logger.error(f"Folder check/create error: {str(e)}")
        return None
```

Then update the `/upload/analyze/projectena` endpoint:

```python
@app.post("/upload/analyze/projectena")
async def analyze_for_projectena(
    file: UploadFile = File(...),
    companyId: str = Form(...),
    departmentId: str = Form(...),
    uploadedBy: str = Form(...),
    folderId: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    autoCreateFolders: bool = Form(True)  # NEW parameter
):
    # ... existing processing code ...
    
    # NEW: Auto-create folders if requested
    actual_folder_id = folderId
    
    if autoCreateFolders and not folderId:
        suggested_path = projectena_response["suggestedPath"]
        actual_folder_id = await ensure_folder_exists(
            company_id=companyId,
            department_id=departmentId,
            suggested_path=suggested_path,
            user_id=uploadedBy
        )
        
        if actual_folder_id:
            projectena_response["folderId"] = actual_folder_id
            projectena_response["folderAutoCreated"] = True
            logger.info(f"✅ Auto-created folder: {actual_folder_id}")
    
    return projectena_response
```

---

## Summary

### Current Behavior:
```
Document Upload
  ↓
Intelligence Service processes
  ↓
Returns: { suggestedPath: "/Finance/2025/November/Invoices/" }
  ↓
Projectena saves document with folderId = null ❌
  ↓
Document has no folder! ❌
```

### New Behavior (Recommended):
```
Document Upload
  ↓
Intelligence Service processes
  ↓
Returns: { suggestedPath: "/Finance/2025/November/Invoices/" }
  ↓
Projectena Backend checks folders:
  ├─ Does "2025" folder exist at root? 
  │   No → Create it ✅
  ├─ Does "November" subfolder exist under 2025?
  │   No → Create it ✅
  └─ Does "Invoices" subfolder exist under November?
      No → Create it ✅
  ↓
Returns: folderId = "507f1f77bcf86cd799439015" ✅
  ↓
Document saved with correct folder ✅
```

---

## Testing

### Test 1: Upload to non-existent folder

```bash
# Upload invoice (folder doesn't exist)
curl -X POST http://localhost:5000/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@invoice.pdf" \
  -F "companyId=507f1f77bcf86cd799439012" \
  -F "departmentId=507f1f77bcf86cd799439013"

# Expected result:
# ✅ Folder "2025" created (at root)
# ✅ Folder "November" created (under 2025)
# ✅ Folder "Invoices" created (under November)
# ✅ Document saved with folderId
# Path: Finance/2025/November/Invoices/invoice_12345.pdf
```

### Test 2: Upload to existing folder

```bash
# Upload another invoice (folder now exists)
curl -X POST http://localhost:5000/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@invoice2.pdf" \
  -F "companyId=507f1f77bcf86cd799439012" \
  -F "departmentId=507f1f77bcf86cd799439013"

# Expected result:
# ✅ Found existing "2025" folder
# ✅ Found existing "November" folder
# ✅ Found existing "Invoices" folder
# ✅ Document saved with folderId
# Path: Finance/2025/November/Invoices/invoice_67890.pdf
```

---

## Recommendation

**Use Option A** (Projectena Backend handles folders) because:
- ✅ Backend has MongoDB access
- ✅ Maintains data consistency
- ✅ Handles permissions properly
- ✅ No circular dependencies
- ✅ Cleaner separation of concerns

The Intelligence Service should **suggest paths**, but **Projectena should manage folders**.
