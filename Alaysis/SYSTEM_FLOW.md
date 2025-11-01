# System Flow - Quick Summary

## 🎯 Entry Point
**POST /upload/analyze** (Document Intelligence Service - Port 8003/8004)

## 📊 Data Flow

```
┌──────────────┐
│    CLIENT    │
│  (Upload)    │
└──────┬───────┘
       │
       ▼
┌────────────────────────────────────────┐
│  DOCUMENT INTELLIGENCE SERVICE         │
│  (Main Orchestrator - Port 8003/8004)  │
│                                        │
│  1. Receives file                      │
│  2. Determines document type           │
│  3. Routes to appropriate services     │
└─────┬──────────────────┬──────────────┘
      │                  │
      ├──────────┐      ├──────────┐
      ▼          ▼      ▼          ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│   OCR   │ │   ICR   │ │   NLP   │
│Port 8000│ │Port 8001│ │Port 8002│
└─────┬───┘ └─────┬───┘ └─────┬───┘
      │           │           │
      │ Extract   │ Handwrite │ Analyze
      │ text      │ recognize │ text
      │           │           │
      └───────┬───┴─────┬─────┘
              │         │
              ▼         ▼
┌────────────────────────────────────────┐
│  DOCUMENT INTELLIGENCE PROCESSING      │
│                                        │
│  • Classification                      │
│  • Entity Extraction                   │
│  • Template Matching                   │
│  • Validation                          │
│  • Routing Decision                    │
└───────────────┬────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │   RESPONSE    │
        │  (JSON Result)│
        └───────────────┘
```

## 🔄 Processing Steps

1. **Upload** → Document Intelligence Service receives file
2. **Detection** → Identifies if image/PDF/handwritten
3. **OCR** → Extracts text from images/PDFs (Port 8000)
4. **ICR** → Recognizes handwriting (Port 8001)
5. **NLP** → Analyzes extracted text (Port 8002)
6. **Intelligence** → Classifies, extracts entities, validates
7. **Routing** → Determines destination and actions
8. **Response** → Returns complete analysis to client

## 🚪 Exit Point
**JSON Response** containing:
- Extracted text
- Document classification
- Entities (dates, amounts, names, etc.)
- Validation results
- Routing recommendations
- Processing metadata

## 💡 Key Points

- **Single Entry**: One upload endpoint handles all document types
- **Automatic Routing**: System determines which services to use
- **Parallel Processing**: OCR, ICR, NLP run concurrently when possible
- **Comprehensive Output**: All analysis results in one response
- **Microservices**: Each service is independent and scalable
