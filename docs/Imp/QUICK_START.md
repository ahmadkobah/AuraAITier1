# Quick Start Guide: Enhanced OCR System

## 🚀 What's New

Your adaptive document processing system now has three major enhancements:

1. **Hybrid OCR Routing** - Automatically routes simple docs to TrOCR (fast) and complex docs to DeepSeek (accurate)
2. **Structured NLP** - Parses markdown tables and uses section context for better entity extraction
3. **Mixed Document Support** - Handles documents with both printed and handwritten text

---

## 📦 Installation

### 1. Install New Dependencies

**OCR Service:**
```powershell
cd python-ocr-service
pip install opencv-python>=4.8.0 numpy>=1.24.0
```

**NLP Service:**
```powershell
cd python-nlp-service
# No new dependencies needed
```

**ICR Service:**
```powershell
cd python-icr-service
# opencv-python should already be installed
```

---

## 🎮 Usage Examples

### 1. OCR with Intelligent Routing

**Simple Document (Auto-routes to TrOCR):**
```powershell
curl -X POST http://localhost:8000/ocr/process `
  -F "file=@simple_receipt.png"
```

**Complex Document (Auto-routes to DeepSeek):**
```powershell
curl -X POST http://localhost:8000/ocr/process `
  -F "file=@invoice_with_table.png"
```

**Response includes routing decision:**
```json
{
  "text": "Extracted text...",
  "engine": "DeepSeek",
  "metadata": {
    "routing_decision": {
      "complexity_score": 0.85,
      "has_tables": true,
      "has_multi_column": false,
      "recommended_engine": "deepseek"
    }
  }
}
```

---

### 2. Structured NLP Analysis

**Analyze markdown-formatted text from DeepSeek OCR:**
```powershell
# First: Get OCR output (will be markdown if DeepSeek is used)
$ocrResponse = curl -X POST http://localhost:8000/ocr/process `
  -F "file=@invoice.png" | ConvertFrom-Json

# Then: Analyze structure
curl -X POST http://localhost:8001/nlp/analyze-structured `
  -H "Content-Type: application/json" `
  -d "{`"text`": `"$($ocrResponse.text)`", `"analysis_types`": [`"entities`"]}"
```

**Response includes:**
```json
{
  "structure": {
    "sections": 8,
    "tables": 2,
    "headers": 3,
    "has_tables": true,
    "document_title": "Invoice #12345"
  },
  "entities": [
    {
      "text": "Microsoft Corp",
      "type": "ORGANIZATION",
      "role": "vendor",
      "section_context": "Vendor Information",
      "confidence": 0.95
    },
    {
      "text": "$1,234.56",
      "type": "MONEY",
      "role": "total",
      "table_context": {
        "column_name": "Total",
        "row_index": 5
      }
    }
  ],
  "table_data": {
    "line_items": [
      {"Item": "Widget", "Quantity": "10", "Price": "$99.99"}
    ],
    "totals": [
      {"field": "Subtotal", "values": ["$999.90"]},
      {"field": "Tax", "values": ["$79.99"]},
      {"field": "Total", "values": ["$1079.89"]}
    ]
  }
}
```

---

### 3. Mixed Document Processing

**Analyze document for mixed content:**
```powershell
curl -X POST http://localhost:8002/hybrid/analyze `
  -F "file=@filled_form.png"
```

**Response:**
```json
{
  "analysis": {
    "is_mixed": true,
    "printed_count": 12,
    "handwritten_count": 5,
    "signature_count": 1,
    "processing_strategy": "hybrid"
  },
  "recommendation": {
    "strategy": "hybrid",
    "use_ocr": true,
    "use_icr": true
  }
}
```

**Process mixed document:**
```powershell
curl -X POST http://localhost:8002/hybrid/process `
  -F "file=@filled_form.png"
```

**Response:**
```json
{
  "analysis": { /* same as above */ },
  "regions": [
    {
      "type": "printed",
      "text": "Name: ______________",
      "engine": "DeepSeek",
      "confidence": 0.98
    },
    {
      "type": "handwritten",
      "text": "John Smith",
      "engine": "ICR",
      "confidence": 0.87,
      "bbox": {"x": 100, "y": 50, "width": 200, "height": 30}
    },
    {
      "type": "signature",
      "text": "[SIGNATURE DETECTED]",
      "engine": "ICR",
      "confidence": 0.92
    }
  ],
  "combined_text": "Name: John Smith\n[SIGNATURE]"
}
```

---

## 🔧 Service Health Checks

**OCR Service:**
```powershell
curl http://localhost:8000/health
```
```json
{
  "status": "ok",
  "mode": "hybrid_routing",
  "engines_available": ["TrOCR", "DeepSeek"],
  "routing_enabled": true
}
```

**NLP Service:**
```powershell
curl http://localhost:8001/health
```
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "services": {
    "nlp_model": "ready",
    "text_processor": "ready"
  }
}
```

**ICR Service:**
```powershell
curl http://localhost:8002/health
```
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "capabilities": {
    "handwriting_recognition": true,
    "signature_detection": true,
    "mixed_document_support": true,
    "hybrid_ocr_icr": true
  }
}
```

---

## 📊 Workflow Examples

### Complete Invoice Processing

```powershell
# 1. OCR extraction (with routing)
$ocr = curl -X POST http://localhost:8000/ocr/process `
  -F "file=@invoice.png" | ConvertFrom-Json

Write-Host "Engine used: $($ocr.engine)"
Write-Host "Complexity: $($ocr.metadata.routing_decision.complexity_score)"

# 2. Structured NLP analysis
$nlp = curl -X POST http://localhost:8001/nlp/analyze-structured `
  -H "Content-Type: application/json" `
  -d "{`"text`": `"$($ocr.text)`"}" | ConvertFrom-Json

Write-Host "Tables found: $($nlp.structure.tables)"
Write-Host "Entities: $($nlp.entities.Count)"

# 3. Extract specific data
foreach ($entity in $nlp.entities) {
    if ($entity.role -eq "vendor") {
        Write-Host "Vendor: $($entity.text)"
    }
    if ($entity.role -eq "total") {
        Write-Host "Total: $($entity.text)"
    }
}
```

### Form Processing

```powershell
# 1. Analyze for mixed content
$analysis = curl -X POST http://localhost:8002/hybrid/analyze `
  -F "file=@form.png" | ConvertFrom-Json

Write-Host "Strategy: $($analysis.recommendation.strategy)"

# 2. Process based on strategy
if ($analysis.recommendation.strategy -eq "hybrid") {
    $result = curl -X POST http://localhost:8002/hybrid/process `
      -F "file=@form.png" | ConvertFrom-Json
    
    Write-Host "Printed regions: $($result.analysis.printed_count)"
    Write-Host "Handwritten regions: $($result.analysis.handwritten_count)"
    Write-Host "Combined text:"
    Write-Host $result.combined_text
}
```

---

## 🎯 Best Practices

### When to Use Each Endpoint

**OCR Service:**
- `/ocr/process` - For all documents (automatic routing)
- Use when: You have any document image
- Returns: Text + routing metadata + engine used

**NLP Service:**
- `/nlp/analyze` - For plain text analysis
- `/nlp/analyze-structured` - For markdown text from DeepSeek
- Use when: OCR returned structured markdown
- Returns: Entities with context + table data

**ICR Service:**
- `/icr/process` - For handwriting only
- `/hybrid/analyze` - To check if document is mixed
- `/hybrid/process` - For mixed documents
- Use when: Document has handwriting or signatures
- Returns: Combined OCR+ICR results

---

## 🔍 Routing Decision Logic

The OCR service automatically decides which engine to use:

```
Document Analysis:
├─ Tables detected? → +0.4 complexity
├─ Multi-column? → +0.3 complexity
├─ Graphics? → +0.1 complexity
└─ Text density unusual? → +0.2 complexity

Routing Rules:
├─ Complexity < 0.3 → TrOCR (simple, fast)
├─ Complexity > 0.6 → DeepSeek (complex, accurate)
└─ 0.3 ≤ Complexity ≤ 0.6
    ├─ Has tables/multi-column? → DeepSeek
    └─ Otherwise → TrOCR
```

---

## 📈 Performance Tips

1. **Simple Documents:** Will automatically use TrOCR (faster)
2. **Complex Documents:** Will use DeepSeek (more accurate)
3. **Mixed Documents:** Use `/hybrid/analyze` first to avoid unnecessary processing
4. **Structured NLP:** Only use when OCR returned markdown (from DeepSeek)
5. **GPU Memory:** DeepSeek requires ~6GB VRAM (may need "Small" mode on RTX 3050)

---

## 🐛 Troubleshooting

### OCR Service

**DeepSeek not available:**
- Check CUDA: `python -c "import torch; print(torch.cuda.is_available())"`
- Ensure GPU memory: DeepSeek needs ~6GB VRAM
- Falls back to TrOCR automatically

**Routing always uses TrOCR:**
- Check `USE_DEEPSEEK_OCR=true` in environment
- Verify CUDA available
- Check logs for DeepSeek initialization errors

### NLP Service

**No table data extracted:**
- Ensure input text is markdown format
- DeepSeek outputs markdown, TrOCR outputs plain text
- Use `/nlp/analyze-structured` (not `/nlp/analyze`)

### ICR Service

**Mixed document not detected:**
- Ensure image quality is good
- Check minimum region size (default: 20 pixels)
- Try `/hybrid/analyze` first to see detection results

---

## 📝 Testing Checklist

- [ ] Test simple receipt → Should route to TrOCR
- [ ] Test invoice with table → Should route to DeepSeek
- [ ] Test structured NLP → Should extract table data
- [ ] Test entities with context → Should show roles
- [ ] Test form with handwriting → Should detect mixed
- [ ] Test hybrid processing → Should combine results
- [ ] Check all health endpoints → Should show "ready"

---

## 🎉 Summary

**You now have:**
✅ Intelligent OCR routing
✅ Structured document understanding
✅ Context-aware entity extraction
✅ Mixed document support
✅ Automatic table parsing
✅ Signature detection

**Next steps:**
1. Test with your documents
2. Adjust thresholds if needed
3. Monitor routing decisions
4. Collect metrics on accuracy

**Need help?**
- Check logs in each service
- Use `/health` endpoints
- Review `IMPLEMENTATION_SUMMARY.md`
- See `DEEPSEEK_ANALYSIS.md` for details
