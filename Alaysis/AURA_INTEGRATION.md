# Aura App Integration Analysis

## Summary of Your 3 Requirements

### 1. ✅ Signature Detection (YES/NO)

**Current Status:** ⚠️ PARTIALLY IMPLEMENTED

**What Works:**
- ICR Service detects signatures from images
- Returns detailed signature data with confidence scores
- Location and verification information included

**What's Missing:**
- No simple `signed: true/false` field
- Response is complex - not a simple yes/no

**Current Response:**
```json
{
  "signatures": [
    {
      "is_genuine": true,
      "confidence": 0.91,
      "location": [x, y, w, h]
    }
  ]
}
```

**Needed Response:**
```json
{
  "signed": true,              // NEW: Simple yes/no
  "signature_count": 1,        // NEW: How many signatures
  "signature_confidence": 0.91, // NEW: Overall confidence
  "signatures": [...]          // Existing detailed data
}
```

**Fix Required:** Add 3 new fields to `IcrJobResult` schema (15 minutes)

---

### 2. ❌ Department-Based Folder Storage

**Current Status:** ⚠️ LOGIC EXISTS, NO FILE OPERATIONS

**What Works:**
- Routing logic determines correct department
- Classification identifies document types
- Maps documents to departments (finance, legal, HR, etc.)

**What's Missing:**
- Does NOT actually save files to folders
- Does NOT create directory structures
- Returns department NAMES only, not file paths
- No physical file storage

**Current Response:**
```json
{
  "routing_destinations": ["finance_department"],
  "destination_details": {
    "finance_department": {
      "department": "finance"
    }
  }
}
```

**Needed Response:**
```json
{
  "department": "finance",
  "file_path": "/departments/finance/invoices/2024/11/invoice_001.pdf",
  "target_folder": "/departments/finance/invoices/2024/11/",
  "suggested_filename": "invoice_001.pdf"
}
```

**Fix Required:** Add file path generation function (1-2 hours)

---

### 3. ❓ Aura App Data Format

**Current Status:** ❓ UNKNOWN - NEED YOUR APP SCHEMA

**Problem:** Cannot verify without access to Projectena/Aura codebase

**Questions Needed:**
1. What exact fields does Aura app expect?
2. What format? JSON? XML?
3. Field naming conventions?
4. Does it need webhooks?
5. Database IDs required?

**Current Generic Response:**
```json
{
  "classification": {...},
  "extraction": {...},
  "routing": {...},
  "validation": {...},
  "nlp_analysis": {...}
}
```

**Action Required:** You need to share Aura app's expected API schema

---

## Missing Features Summary

### HIGH PRIORITY (Must Have)

1. **Simple signature boolean field** - 15 min fix
2. **File path generation** - 1-2 hour implementation  
3. **Aura-compatible response format** - Need Aura schema first

### MEDIUM PRIORITY

4. Actual file system storage (vs just paths)
5. Department folder structure configuration
6. Automatic filename generation

### LOW PRIORITY

7. Multi-tenant support
8. Custom routing rules
9. Audit logging
10. File versioning

---

## Quick Fixes Needed

### Fix #1: Add Signature Yes/No (Easy - 15 min)

**File:** `shared/schemas.py`

```python
class IcrJobResult(BaseModel):
    document_id: str
    job_id: str
    status: str
    signed: bool = False                     # NEW
    signature_detected: bool = False         # NEW
    signature_count: int = 0                 # NEW
    signature_confidence: Optional[float] = None  # NEW
    signatures: List[Dict[str, Any]] = Field(default_factory=list)
    handwriting: List[Dict[str, Any]] = Field(default_factory=list)
```

**File:** `python-icr-service/main.py` (line ~363)

```python
def build_icr_job_result(...):
    is_signed = len(signatures) > 0
    
    return IcrJobResult(
        ...existing fields...,
        signed=is_signed,
        signature_detected=is_signed,
        signature_count=len(signatures),
        signature_confidence=signatures[0]["confidence"] if signatures else 0.0
    )
```

### Fix #2: Add File Paths (Medium - 1-2 hours)

**File:** `python-document-intelligence-service/app/routing/document_router.py`

Add new function:

```python
async def generate_file_paths(
    self,
    document_type: str,
    department: str,
    metadata: Dict[str, Any]
) -> Dict[str, str]:
    from datetime import datetime
    
    base_paths = {
        "finance": "/departments/finance",
        "legal": "/departments/legal",
        "hr": "/departments/hr"
    }
    
    now = datetime.now()
    year = now.strftime("%Y")
    month = now.strftime("%m")
    
    base = base_paths.get(department, "/departments/general")
    primary_path = f"{base}/{document_type}/{year}/{month}/"
    
    doc_id = metadata.get("document_id", "unknown")
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"{document_type}_{doc_id}_{timestamp}.pdf"
    
    return {
        "primary_path": primary_path,
        "full_path": primary_path + filename,
        "filename": filename,
        "department": department
    }
```

### Fix #3: Create Aura-Compatible Endpoint

**File:** `python-document-intelligence-service/main.py`

```python
@app.post("/upload/analyze/aura")
async def analyze_for_aura(
    file: UploadFile = File(...),
    company_id: str = Form(...),
    department_id: Optional[str] = Form(None)
):
    # Process normally
    result = await analyze_uploaded_file(file, "full", 0.8)
    
    # Transform to Aura format
    return {
        "document_id": result["document_id"],
        "company_id": company_id,
        "department_id": department_id,
        
        # Simple signature check
        "is_signed": result["icr_metadata"].get("signed", False),
        "has_signature": result["icr_metadata"].get("signature_detected", False),
        
        # Document info
        "document_type": result["classification"]["document_type"],
        "confidence": result["classification"]["confidence"],
        
        # Department routing
        "department": result["routing"]["routing_destinations"][0],
        "file_path": result["routing"]["file_paths"]["full_path"],
        "target_folder": result["routing"]["file_paths"]["primary_path"],
        
        # Extracted data
        "extracted_text": result["extraction"]["text_content"],
        "entities": result["extraction"]["entities"],
        
        # Status
        "status": "processed",
        "is_valid": result["validation"]["is_valid"]
    }
```

---

## How to Use from Aura App

### API Call Example

```javascript
// From your Aura/Projectena app
const formData = new FormData();
formData.append('file', uploadedFile);
formData.append('company_id', 'your_company_id');
formData.append('department_id', 'finance');

const response = await fetch('http://localhost:8003/upload/analyze/aura', {
  method: 'POST',
  body: formData
});

const data = await response.json();

// Check if signed
if (data.is_signed) {
  console.log('Document is signed');
}

// Get department and file path
console.log('Department:', data.department);
console.log('Save to:', data.file_path);

// Save to your system
await saveDocument({
  id: data.document_id,
  path: data.file_path,
  department: data.department,
  signed: data.is_signed,
  entities: data.entities
});
```

---

## Next Steps

1. ✅ **Review this analysis**
2. 📋 **Share Aura app's expected data format** (if you have specific requirements)
3. 🔧 **Apply Fix #1** (Signature yes/no) - 15 minutes
4. 🔧 **Apply Fix #2** (File paths) - 1-2 hours
5. 🔧 **Apply Fix #3** (Aura endpoint) - 1 hour
6. 🧪 **Test integration** with Aura app

**Total Time:** ~3-4 hours of development

---

## Important Notes

⚠️ **The system currently:**
- ✅ Detects signatures (but no simple yes/no field)
- ✅ Determines correct department (but doesn't create folders)
- ❌ Does NOT physically move/save files
- ❌ Returns generic JSON (not Aura-specific format)

⚠️ **After fixes, the system will:**
- ✅ Return simple `signed: true/false`
- ✅ Provide file paths for departments
- ✅ Return Aura-compatible JSON format
- ❌ Still won't physically save files (unless you want that added)

**Question:** Do you want the system to actually save files to the file system, or just return the paths for your Aura app to handle storage?
