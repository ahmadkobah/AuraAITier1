# Integration Quick Start - AI Service + Projectena Backend

## TL;DR - 4 Simple Integration Steps

### Step 1: Configure Environment Variables

**Projectena .env (add these lines):**
```
AI_SERVICE_URL=http://localhost:8080
AI_POLLING_INTERVAL=30000
AI_POLLING_TIMEOUT=3600000
```

**AI Service .env (already configured):**
```
DATABASE_URL=mongodb://localhost:27017
MAIN_DB_NAME=document_processing
PORT=8080
```

---

### Step 2: Trigger AI Processing After Upload

**File: `Projectena/Controllers/DokumentController.js`**

```javascript
// At the END of createDocument function, after document is saved:

async function createDocument(req, res) {
  try {
    const doc = await documentService.createDocument(req.body, req.user);
    
    // ✨ NEW: Queue AI processing asynchronously
    const aiServiceUrl = process.env.AI_SERVICE_URL || 'http://localhost:8080';
    const pdfPath = `/uploads/${doc._id}.pdf`; // Adjust path as needed
    
    fetch(`${aiServiceUrl}/api/v1/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        doc_id: String(doc._id),
        pdf_file_path: pdfPath
      })
    }).catch(err => {
      console.error('AI Service queue failed:', err.message);
      // Don't fail user request - processing can be retried later
    });
    
    return res.status(201).json(doc);
  } catch (err) {
    console.error(err);
    return res.status(400).json({ error: err.message });
  }
}
```

---

### Step 3: Poll for AI Processing Results

**File: `Projectena/services/pollingService.js` (create new)**

```javascript
const mongoose = require('mongoose');
const Document = require('../models/DocumentModel');

const aiDb = mongoose.connection.useDb('document_processing');

/**
 * Poll MongoDB for AI processing results and update Projectena documents
 */
async function pollAiResults() {
  try {
    // Get all documents with ocrStatus = 'pending'
    const pendingDocs = await Document.find({ ocrStatus: 'pending' }).limit(10);
    
    for (const doc of pendingDocs) {
      try {
        // Check if processing completed in AI Service database
        const processedDoc = await aiDb.collection('documents').findOne({
          _id: String(doc._id)
        });
        
        if (!processedDoc) {
          console.log(`Processing not started for doc ${doc._id}`);
          continue;
        }
        
        if (processedDoc.status === 'COMPLETE') {
          // Extract key metadata from AI results
          const extractedMetadata = {
            classifications: processedDoc.processed_data.map(d => ({
              logicalNum: d.logical_doc_num,
              label: d.classification.label,
              confidence: d.classification.score
            })),
            summaries: processedDoc.processed_data.map(d => ({
              logicalNum: d.logical_doc_num,
              text: d.summary
            })),
            processedAt: new Date(processedDoc.processing_completed),
            totalDocuments: processedDoc.document_count
          };
          
          // Update Projectena document
          await Document.findByIdAndUpdate(doc._id, {
            ocrStatus: 'completed',
            extractedMetadata: extractedMetadata
          });
          
          console.log(`✅ Updated document ${doc._id} with AI results`);
        } else if (processedDoc.status === 'FAILED') {
          // Mark as failed
          await Document.findByIdAndUpdate(doc._id, {
            ocrStatus: 'completed',
            extractedMetadata: { error: processedDoc.error }
          });
          
          console.log(`❌ Document ${doc._id} failed processing: ${processedDoc.error}`);
        }
        // If status === 'PROCESSING', just wait for next poll
        
      } catch (docErr) {
        console.error(`Error processing doc ${doc._id}:`, docErr);
      }
    }
  } catch (err) {
    console.error('Polling service error:', err);
  }
}

// Start polling every 30 seconds
setInterval(pollAiResults, 30000);

module.exports = { pollAiResults };
```

**File: `Projectena/app.js` (add after route mounting):**

```javascript
// ... existing code ...

// Mount routes
app.use('/users', userRoutes);
app.use('/documents', documentRoutes);
// ... other routes ...

// ✨ NEW: Start AI results polling
require('./services/pollingService');

// Health check
app.get('/', (req, res) => res.json({ status: 'ok' }));

module.exports = app;
```

---

### Step 4: Display AI Results in API

**File: `Projectena/services/documentService.js` (update getDocumentById)**

```javascript
async function getDocumentById(id) {
  const doc = await docRepo.findById(id);
  
  if (doc && doc.extractedMetadata && doc.extractedMetadata.classifications) {
    // Already has AI results, return as-is
    return doc;
  }
  
  // Optional: Include AI processing status in response
  return {
    ...doc.toObject(),
    aiStatus: doc.ocrStatus,
    aiResults: doc.extractedMetadata
  };
}
```

---

## How It Works

```
1. User uploads PDF via React frontend
   ↓
2. Projectena receives POST /documents
   ├─ Saves document (ocrStatus: 'pending')
   ├─ Immediately triggers AI Service
   └─ Returns success to frontend (fast ✅)
   ↓
3. Frontend shows: "📄 Processing document..."
   ↓
4. AI Service processes in background (60-90 seconds)
   ├─ Extracts text
   ├─ Generates embeddings
   ├─ Classifies document type
   ├─ Generates summary
   └─ Stores in MongoDB document_processing database
   ↓
5. Projectena polls every 30 seconds
   ├─ Finds completed processing
   ├─ Updates Projectena document (ocrStatus: 'completed')
   └─ Stores extractedMetadata
   ↓
6. Frontend detects update
   └─ Shows: "✅ Processing complete! View results"
   ↓
7. User can now:
   ├─ See document classification
   ├─ Read auto-generated summary
   ├─ Search documents (semantic)
   └─ Ask questions (Q&A)
```

---

## Files to Modify

| File | Change | Complexity |
|------|--------|-----------|
| `Controllers/DokumentController.js` | Add AI Service queue call | 🟢 Easy |
| `services/pollingService.js` | Create new polling service | 🟡 Medium |
| `app.js` | Initialize polling service | 🟢 Easy |
| `services/documentService.js` | Optional: enhance responses | 🟢 Easy |

**Total implementation time: 1-2 hours**

---

## Testing Integration

### 1. Start Both Services

```powershell
# Terminal 1: Projectena Backend
cd Projectena
npm start
# Listening on port 8000

# Terminal 2: AI Service
cd adaptive-Dokumentenverarbeitung
python -m uvicorn app.main:app --port 8080
# Listening on port 8080
```

### 2. Test Document Upload

```bash
curl -X POST http://localhost:8000/documents \
  -H "Authorization: Bearer <your_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "invoice.pdf",
    "size": 125000
  }'
```

### 3. Monitor Processing

```bash
# Check AI Service logs
# Should see: "Starting Uvicorn on 0.0.0.0:8080"

# Check MongoDB
# In MongoDB Compass, watch document_processing.documents collection
# Should see new document with status: "PENDING" → "PROCESSING" → "COMPLETE"
```

### 4. Verify Results

```bash
# After ~90 seconds, check Projectena document
curl http://localhost:8000/documents/<doc_id> \
  -H "Authorization: Bearer <your_jwt_token>"

# Response should include:
# {
#   ocrStatus: "completed",
#   extractedMetadata: {
#     classifications: [...],
#     summaries: [...],
#     processedAt: "2025-11-15T22:30:00Z",
#     totalDocuments: 1
#   }
# }
```

---

## Troubleshooting

### AI Service Not Processing

**Check:**
```bash
# 1. AI Service running?
curl http://localhost:8080/health

# 2. MongoDB accessible?
# Check logs: MONGODB_CONNECTION_ERROR

# 3. Models loading?
# Check logs: "Loading models..." → "Ready: True"
```

### Polling Not Working

**Check:**
```javascript
// 1. Is polling service initialized?
// Check console: "Polling service started"

// 2. Can it access document_processing database?
// Check logs: MongoDB connection errors

// 3. Is document ID matching?
// AI Service doc_id must match Projectena _id
```

### Results Not Appearing

**Check:**
```bash
# 1. Verify in MongoDB:
db.document_processing.documents.findOne({_id: "your_doc_id"})

# 2. Check status field - should be "COMPLETE"

# 3. Verify extractedMetadata structure matches expected format
```

---

## Advanced: Enable Semantic Search & Q&A

Once documents are processed, enable AI features:

### Semantic Search

```javascript
// Projectena frontend
async function searchDocuments(query) {
  const response = await fetch('http://localhost:8080/api/v1/search', {
    method: 'POST',
    body: JSON.stringify({
      query: query,
      doc_id: currentDocumentId,
      top_k: 5
    })
  });
  
  const results = await response.json();
  // results = [{document_id, score, text_excerpt}, ...]
  displayResults(results);
}
```

### Question Answering

```javascript
// Projectena frontend
async function askQuestion(question) {
  const response = await fetch('http://localhost:8080/api/v1/query', {
    method: 'POST',
    body: JSON.stringify({
      doc_id: currentDocumentId,
      question: question
    })
  });
  
  const result = await response.json();
  // result = {answer, confidence, timestamp}
  displayAnswer(result.answer, result.confidence);
}
```

---

## Success Checklist

- [ ] AI Service running on port 8080
- [ ] Projectena backend running on port 8000
- [ ] MongoDB document_processing database accessible
- [ ] Upload document → AI processing triggered
- [ ] Polling service finds completed processing
- [ ] Projectena document updated with ocrStatus: "completed"
- [ ] extractedMetadata contains AI results
- [ ] Semantic search returns correct results
- [ ] Q&A returns relevant answers
- [ ] Performance acceptable (<15s for 5-page PDF)

---

## Support

For detailed information, see:
- `COMPATIBILITY_ANALYSIS.md` - Full technical assessment
- `README.md` - AI Service documentation
- `PORT_CONFIGURATION.md` - Port & environment setup
