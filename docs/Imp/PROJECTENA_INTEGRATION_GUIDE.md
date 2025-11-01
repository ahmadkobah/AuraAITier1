# Projectena Integration Guide - Folder Workflow

## Overview
The Intelligence Service now provides a complete `folderWorkflow` object that tells Projectena how to handle folder creation **after** document processing completes.

## Intelligence Service Response Structure

All upload endpoints now return a `folderWorkflow` object with **validated, non-empty components**:

```json
{
  "folderWorkflow": {
    "createAfterProcessing": true,
    "finalPath": "/CompanyName/2025/November/Invoices",
    "components": {
      "year": "2025",        // Never empty - fallback to current year
      "month": "November",   // Never empty - fallback to current month
      "docType": "Invoices"  // Never empty - fallback to "Unknown"
    },
    "shouldAutoCreate": true,
    "checkExistingFirst": true
  },
  "suggestedPath": "/CompanyName/2025/November/Invoices",
  "docType": "Invoices",
  "status": "processed"
}
```

### Validation Rules

The Intelligence Service automatically validates all components:

- **year**: Uses `folder_paths.year` or falls back to current year (e.g., "2025")
- **month**: Uses `folder_paths.month` or falls back to current month (e.g., "November")  
- **docType**: Uses classification result or falls back to "Unknown"

**All values are guaranteed to be non-empty strings**, preventing Mongoose validation errors.

## Affected Endpoints

1. **POST /upload/analyze/projectena** - Projectena uploads
2. **POST /upload/analyze** - General uploads (when company_id and department_id provided)
3. **POST /upload/scan** - Scanner uploads (when company_id and department_id provided)

## Projectena Implementation Workflow

### 1. Document Upload (Initial)
```javascript
// In DokumentController.js or upload handler
async uploadDocument(req, res) {
  try {
    // Step 1: Store document temporarily (no folder creation yet)
    const tempPath = `/temp/${Date.now()}_${file.originalname}`;
    
    // Step 2: Send to Intelligence Service for processing
    const intelligenceResponse = await axios.post(
      'http://127.0.0.1:8003/upload/analyze/projectena',
      formData
    );
    
    // Step 3: Extract folderWorkflow from response
    const { folderWorkflow, docType, suggestedPath } = intelligenceResponse.data;
    
    console.log('📁 Folder Workflow:', folderWorkflow);
    console.log('📄 Document Type:', docType);
    console.log('🗂️ Suggested Path:', suggestedPath);
    
    // Step 4: Create folder hierarchy AFTER processing
    if (folderWorkflow && folderWorkflow.createAfterProcessing) {
      await createFolderHierarchy(folderWorkflow, companyId, departmentId);
    }
    
  } catch (error) {
    console.error('Upload error:', error);
  }
}
```

### 2. Folder Creation Logic
```javascript
// In folderService.js
async function createFolderHierarchy(folderWorkflow, companyId, departmentId) {
  const { components, checkExistingFirst, shouldAutoCreate } = folderWorkflow;
  const { year, month, docType } = components;
  
  // Step 1: Check if folder already exists
  if (checkExistingFirst) {
    const existingFolder = await Folder.findOne({
      company: companyId,
      department: departmentId,
      path: folderWorkflow.finalPath
    });
    
    if (existingFolder) {
      console.log('✓ Folder already exists:', existingFolder.name);
      return existingFolder._id;
    }
  }
  
  // Step 2: Create folder hierarchy if it doesn't exist
  if (shouldAutoCreate) {
    // Get department folder
    const deptFolder = await Folder.findOne({
      company: companyId,
      _id: departmentId
    });
    
    if (!deptFolder) {
      throw new Error('Department folder not found');
    }
    
    // Create Year folder
    let yearFolder = await Folder.findOne({
      company: companyId,
      department: departmentId,
      parentFolder: departmentId,
      name: year
    });
    
    if (!yearFolder) {
      yearFolder = await Folder.create({
        name: year,
        company: companyId,
        department: departmentId,
        parentFolder: departmentId,
        isAutoCreated: true,
        autoCreatedAt: new Date()
      });
      console.log('✓ Created year folder:', year);
    }
    
    // Create Month folder
    let monthFolder = await Folder.findOne({
      company: companyId,
      department: departmentId,
      parentFolder: yearFolder._id,
      name: month
    });
    
    if (!monthFolder) {
      monthFolder = await Folder.create({
        name: month,
        company: companyId,
        department: departmentId,
        parentFolder: yearFolder._id,
        isAutoCreated: true,
        autoCreatedAt: new Date()
      });
      console.log('✓ Created month folder:', month);
    }
    
    // Create Document Type folder
    let docTypeFolder = await Folder.findOne({
      company: companyId,
      department: departmentId,
      parentFolder: monthFolder._id,
      name: docType
    });
    
    if (!docTypeFolder) {
      docTypeFolder = await Folder.create({
        name: docType,
        company: companyId,
        department: departmentId,
        parentFolder: monthFolder._id,
        isAutoCreated: true,
        autoCreatedAt: new Date()
      });
      console.log('✓ Created document type folder:', docType);
    }
    
    return docTypeFolder._id;
  }
}
```

### 3. Update Document with Final Folder
```javascript
// After folder creation
const folderId = await createFolderHierarchy(folderWorkflow, companyId, departmentId);

// Save document with final folder location
const document = await Document.create({
  filename: intelligenceResponse.data.filename,
  folderId: folderId,
  companyId: companyId,
  departmentId: departmentId,
  docType: intelligenceResponse.data.docType,
  // ... other fields
});

console.log('✓ Document saved to folder:', folderId);
```

## Key Benefits

### ✅ No Duplicate Folders
- Checks if folder exists before creating
- Prevents multiple "Invoices" folders in same month

### ✅ Clean Workflow
- Upload → Process → Create Folders → Save
- No temporary folders needed
- No folder renaming required

### ✅ Better Error Handling
- If processing fails, no folders are created
- Easy to rollback on errors

### ✅ Consistent Structure
- All endpoints return same folderWorkflow format
- Works for manual uploads, scanner uploads, and API uploads

## Testing

### Test the Intelligence Service Response
```bash
curl -X POST http://127.0.0.1:8003/upload/analyze/projectena \
  -F "file=@test.pdf" \
  -F "companyId=company123" \
  -F "departmentId=dept456" \
  -F "uploadedBy=user789"
```

Expected response includes:
```json
{
  "folderWorkflow": {
    "createAfterProcessing": true,
    "finalPath": "/company123/2025/November/Invoices",
    "components": {
      "year": "2025",
      "month": "November",
      "docType": "Invoices"
    },
    "shouldAutoCreate": true,
    "checkExistingFirst": true
  }
}
```

## Next Steps for Projectena

1. **Update DokumentController.js**
   - Extract `folderWorkflow` from Intelligence Service response
   - Call `createFolderHierarchy()` after processing completes

2. **Update folderService.js**
   - Implement `createFolderHierarchy()` function
   - Use the workflow components to build folder structure
   - Check for existing folders before creating

3. **Test End-to-End**
   - Upload document
   - Verify folder hierarchy is created: Department → Year → Month → DocType
   - Upload another document of same type
   - Verify it uses existing folder (no duplicates)

## Folder Structure Example

```
Company: Acme Corp
├── Department: Finance
│   ├── 2025
│   │   ├── November
│   │   │   ├── Invoices        ← Auto-created
│   │   │   ├── Receipts        ← Auto-created
│   │   │   └── Contracts       ← Auto-created
│   │   ├── December
│   │   │   ├── Invoices        ← Auto-created
│   │   │   └── Tax Documents   ← Auto-created
│   ├── 2024
│   │   └── ...
```

## Error Handling

```javascript
try {
  const folderId = await createFolderHierarchy(folderWorkflow, companyId, departmentId);
} catch (error) {
  if (error.message.includes('Department folder not found')) {
    // Handle missing department
    console.error('Department not found:', departmentId);
  } else if (error.message.includes('Duplicate folder')) {
    // This shouldn't happen due to checkExistingFirst, but handle it
    console.warn('Duplicate folder detected');
  } else {
    // Other errors
    console.error('Folder creation error:', error);
  }
}
```

## Configuration

No configuration needed on Intelligence Service side - it's automatic for all endpoints that receive `company_id` and `department_id`.

## Summary

The Intelligence Service now provides everything Projectena needs to:
1. ✅ Wait until processing completes
2. ✅ Check if folder exists
3. ✅ Create folder hierarchy if needed
4. ✅ Avoid duplicates
5. ✅ Track auto-created folders

All changes are backward compatible - if Projectena doesn't use `folderWorkflow`, the old `suggestedPath` field still works!
