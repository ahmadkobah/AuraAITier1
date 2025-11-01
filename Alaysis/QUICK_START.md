# Quick Start Guide - Running the Adaptive System

## ✅ Implementation Status: COMPLETE

All fixes and new features have been implemented:
- ✅ Signature boolean field
- ✅ Company/Department ID support  
- ✅ Folder path mapping
- ✅ Projectena-compatible endpoint
- ✅ Scanner integration endpoint

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Check Python Version
```powershell
python --version
# Must be Python 3.11 or 3.12 (NOT 3.13!)
```

**If you have Python 3.13:**
```powershell
# Install Python 3.11 from python.org
# Or use pyenv to switch versions
```

### Step 2: Activate Virtual Environment
```powershell
cd C:\Users\Ahmad\Documents\GitHub\adaptive-Dokumentenverarbeitung
.venv\Scripts\Activate.ps1
```

### Step 3: Install/Update Dependencies
```powershell
# Update all service dependencies
cd python-document-intelligence-service
pip install -r requirements.txt

cd ..\python-icr-service  
pip install -r requirements.txt

cd ..\python-ocr-service
pip install -r requirements.txt

cd ..\python-nlp-service
pip install -r requirements.txt

cd ..
```

### Step 4: Start All Services

**Terminal 1 - OCR Service:**
```powershell
cd python-ocr-service
python main.py
# Runs on port 8000
```

**Terminal 2 - ICR Service:**
```powershell
cd python-icr-service
python main.py
# Runs on port 8001
```

**Terminal 3 - NLP Service:**
```powershell
cd python-nlp-service
python main.py
# Runs on port 8002
```

**Terminal 4 - Document Intelligence (Main Service):**
```powershell
cd python-document-intelligence-service
python main.py
# Runs on port 8003
```

### Step 5: Test It Works

**Test health endpoint:**
```powershell
curl http://localhost:8003/health
```

**Test Projectena endpoint:**
```powershell
# Upload a test document
curl -X POST http://localhost:8003/upload/analyze/projectena `
  -F "file=@test_document.pdf" `
  -F "companyId=test_company" `
  -F "departmentId=test_dept" `
  -F "uploadedBy=test_user"
```

---

## 📋 What's New

### 1. Projectena Endpoint
```
POST http://localhost:8003/upload/analyze/projectena

Parameters:
- file: Document file
- companyId: Company identifier (required)
- departmentId: Department identifier (required)  
- uploadedBy: User ID (required)
- folderId: Folder ID (optional)
- tags: JSON array of tags (optional)

Response: MongoDB-ready document data
```

### 2. Scanner Endpoint  
```
POST http://localhost:8003/upload/scan

Parameters:
- file: Scanned document
- scanner_id: Scanner identifier (required)
- scan_settings: JSON settings (optional)
- company_id: Company ID (optional)
- department_id: Department ID (optional)
- user_id: User ID (optional)

Response: Processed document with scanner metadata
```

### 3. Enhanced Upload Endpoint
```
POST http://localhost:8003/upload/analyze

New Parameters:
- company_id: Track company context
- department_id: Track department context
- user_id: Track user who uploaded

Response includes:
- signed: true/false (NEW!)
- folder_paths: Suggested storage paths (NEW!)
- company_id, department_id, user_id in response
```

---

## 🔧 Scanner Configuration

### Canon imageRUNNER Series
```
Menu → Network → Scan and Send Settings
Destination Type: HTTP/HTTPS
URL: http://YOUR_SERVER_IP:8003/upload/scan
Method: POST
Format: PDF
Custom Parameters: scanner_id=canon_scanner_01
```

### HP MFP Series
```
Settings → Network → HTTP POST
Server Address: YOUR_SERVER_IP
Port: 8003
Path: /upload/scan
Method: POST
```

### Xerox WorkCentre
```
Network Scanning → Scan to Server
Protocol: HTTP
Server URL: http://YOUR_SERVER_IP:8003/upload/scan
Port: 8003
```

---

## 🧪 Testing Checklist

### Basic Functionality
- [ ] All 4 services start without errors
- [ ] Health endpoint responds (http://localhost:8003/health)
- [ ] Can upload a PDF file
- [ ] OCR extracts text correctly
- [ ] Classification detects document type

### New Features  
- [ ] Signature field returns true/false
- [ ] Company/Department IDs are tracked
- [ ] Folder paths are generated
- [ ] Projectena endpoint returns correct format
- [ ] Scanner endpoint accepts uploads

### Projectena Integration
- [ ] Response matches DocumentModel schema
- [ ] Tags are auto-generated from NLP
- [ ] extractedMetadata contains all data
- [ ] Folder paths follow company/dept hierarchy

---

## 📊 Expected Response Format

### Projectena Endpoint Response:
```json
{
  "filename": "20251101_123045_invoice.pdf",
  "originalName": "invoice.pdf",
  "size": 245678,
  "contentType": "application/pdf",
  
  "uploadedBy": "user_123",
  "companyId": "company_abc",
  "departmentId": "dept_finance",
  "folderId": "folder_xyz",
  
  "docType": "invoice",
  "tags": ["invoice", "payment", "finance", "vendor", "due"],
  
  "ocrStatus": "completed",
  
  "extractedMetadata": {
    "ocr_text": "Full extracted text...",
    "ocr_confidence": 0.95,
    "document_type": "invoice",
    "classification_confidence": 0.92,
    "entities": {
      "invoice_number": "INV-2024-001",
      "total_amount": "$1,500.00",
      "due_date": "2024-01-15",
      "vendor": "Acme Corporation"
    },
    "signature_info": {
      "signed": true,
      "signature_count": 2,
      "confidence": 0.91
    },
    "folder_paths": {
      "base_path": "/company_abc/dept_finance/invoice",
      "dated_path": "/company_abc/dept_finance/invoice/2025/11",
      "full_path": "/company_abc/dept_finance/invoice/2025/11/01"
    }
  },
  
  "signed": true,
  "confidenceScore": 0.92,
  "suggestedPath": "/company_abc/dept_finance/invoice/2025/11/01",
  "status": "processed",
  "processedAt": "2025-11-01T12:30:45Z"
}
```

---

## 🔗 Integration with Projectena

### React Frontend Example:
```javascript
// Upload document from React
const uploadDocument = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('companyId', user.companyId);
  formData.append('departmentId', user.departmentId);
  formData.append('uploadedBy', user._id);
  
  const response = await fetch(
    'http://localhost:8003/upload/analyze/projectena',
    {
      method: 'POST',
      body: formData
    }
  );
  
  const result = await response.json();
  
  // Save to MongoDB via Projectena backend
  await axios.post('/api/documents', result);
  
  return result;
};
```

### Express Backend Example:
```javascript
// Projectena backend integration
const processAndSaveDocument = async (req, res) => {
  try {
    const formData = new FormData();
    formData.append('file', req.file.buffer, req.file.originalname);
    formData.append('companyId', req.user.companyId);
    formData.append('departmentId', req.body.departmentId);
    formData.append('uploadedBy', req.user._id);
    
    // Process through adaptive system
    const processingResult = await axios.post(
      'http://localhost:8003/upload/analyze/projectena',
      formData,
      { headers: formData.getHeaders() }
    );
    
    // Save to MongoDB
    const document = new Document({
      ...processingResult.data,
      filePath: await saveFile(req.file)
    });
    
    await document.save();
    
    res.json({ success: true, document });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
};
```

---

## ⚠️ Important Notes

### Python Version Compatibility
- ✅ Python 3.11 - RECOMMENDED
- ✅ Python 3.12 - Works
- ❌ Python 3.13 - NOT COMPATIBLE (PyTorch not available yet)

### Port Requirements
- 8000 - OCR Service
- 8001 - ICR Service  
- 8002 - NLP Service
- 8003 - Document Intelligence (Main)

Make sure these ports are not in use:
```powershell
netstat -ano | findstr "8000 8001 8002 8003"
```

### Firewall Configuration
```powershell
# Allow incoming connections for scanners
netsh advfirewall firewall add rule name="Adaptive Document Processing" dir=in action=allow protocol=TCP localport=8000-8003
```

---

## 🐛 Troubleshooting

### Issue: "Module not found" errors
```powershell
# Solution: Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Services won't start
```powershell
# Check Python version
python --version

# Check if ports are in use
netstat -ano | findstr "800"

# Kill process using port (if needed)
taskkill /PID <process_id> /F
```

### Issue: Scanner can't connect
```powershell
# Check firewall
netsh advfirewall show allprofiles state

# Test endpoint manually
curl http://localhost:8003/health

# From scanner's network (use your actual IP):
curl http://192.168.1.XXX:8003/health
```

### Issue: Low accuracy
- Check document quality (resolution, clarity)
- Ensure proper lighting for scans
- Use PDF with embedded text when possible
- Check OCR confidence scores in response

---

## 📈 Performance Tips

### For Best Results:
1. Use high-resolution scans (300 DPI minimum)
2. Ensure good contrast and lighting
3. Straighten documents before scanning
4. Use PDF format when possible
5. Keep file sizes under 20MB

### Processing Times:
- Small PDF (1-3 pages): 2-5 seconds
- Medium PDF (4-10 pages): 5-12 seconds
- Large PDF (11-30 pages): 12-30 seconds
- Scanned image: 3-8 seconds

---

## ✅ Success Indicators

System is working correctly when:
- ✅ All 4 services start without errors
- ✅ `/health` endpoint returns 200 OK
- ✅ File upload returns JSON response
- ✅ `ocrStatus` is "completed"
- ✅ `signed` field is true/false boolean
- ✅ `folder_paths` are generated
- ✅ `docType` is classified correctly
- ✅ `tags` are auto-generated

---

## 📞 Next Steps

1. **Test Basic Upload:**
   - Upload a PDF through Projectena endpoint
   - Verify response format

2. **Test Signature Detection:**
   - Upload signed contract
   - Check `signed: true/false` in response

3. **Configure Scanner (Optional):**
   - Set scanner to POST to your server
   - Test automatic processing

4. **Integrate with Projectena:**
   - Update Projectena to call new endpoint
   - Save results to MongoDB
   - Display in React frontend

5. **Production Deployment:**
   - Set up proper authentication
   - Configure HTTPS
   - Add monitoring
   - Set up backups

---

**Ready to go! 🚀**

All code changes are complete and ready for testing.
Services can start as soon as Python 3.11/3.12 environment is set up.
