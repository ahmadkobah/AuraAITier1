"""
ADAPTIVE DOCUMENT PROCESSING SYSTEM - ARCHITECTURE & DATA FLOW
================================================================

This document explains how the entire system works, from entry to exit points.
"""

# =============================================================================
# SYSTEM ARCHITECTURE OVERVIEW
# =============================================================================

ARCHITECTURE = """
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ADAPTIVE DOCUMENT PROCESSING SYSTEM                      │
│                           (Microservices Architecture)                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────┐
│  CLIENT (User/Application)                                                │
│  - Web Browser                                                            │
│  - Mobile App                                                             │
│  - API Client                                                             │
│  - Backend Service                                                        │
└───────────────┬───────────────────────────────────────────────────────────┘
                │
                │ HTTP/REST API Request
                │ (Upload Document + Metadata)
                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  🎯 ENTRY POINT: Document Intelligence Service (Port 8003/8004)          │
│  ═══════════════════════════════════════════════════════════════════      │
│                                                                           │
│  Main Orchestrator & Router                                              │
│  File: python-document-intelligence-service/main.py                      │
│                                                                           │
│  KEY ENDPOINTS:                                                           │
│  • POST /upload/analyze          - Main upload entry point               │
│  • POST /intelligence/analyze    - Text-based analysis                   │
│  • POST /batch/process           - Batch document processing             │
│  • GET  /health                  - Health check                          │
│                                                                           │
│  RESPONSIBILITIES:                                                        │
│  1. Receive uploaded documents (files or text)                           │
│  2. Determine processing strategy                                        │
│  3. Orchestrate calls to specialized services                            │
│  4. Aggregate results from all services                                  │
│  5. Apply business logic & routing rules                                 │
│  6. Return comprehensive analysis                                        │
└───────────────┬───────────────────────────────────────────────────────────┘
                │
                │ Orchestrates calls to:
                │
    ┌───────────┼──────────┬─────────────┬──────────────┐
    ▼           ▼          ▼             ▼              ▼
┌────────┐  ┌────────┐  ┌────────┐  ┌──────────┐  ┌──────────┐
│  OCR   │  │  ICR   │  │  NLP   │  │Template  │  │ Routing  │
│Service │  │Service │  │Service │  │ Manager  │  │  Engine  │
│Port    │  │Port    │  │Port    │  │(Internal)│  │(Internal)│
│ 8000   │  │ 8001   │  │ 8002   │  │          │  │          │
└────────┘  └────────┘  └────────┘  └──────────┘  └──────────┘
"""

# =============================================================================
# DETAILED DATA FLOW
# =============================================================================

DATA_FLOW = """
══════════════════════════════════════════════════════════════════════════════
STEP-BY-STEP DATA FLOW: Document Upload to Final Result
══════════════════════════════════════════════════════════════════════════════

STEP 1: CLIENT UPLOADS DOCUMENT
────────────────────────────────
Entry Point: POST /upload/analyze
Location: python-document-intelligence-service/main.py:537

Input:
  • file: UploadFile (PDF, Image, Document)
  • analysis_type: "full" | "classification" | etc.
  • confidence_threshold: 0.0-1.0

Action: Document Intelligence Service receives the file


STEP 2: DOCUMENT TYPE DETECTION
────────────────────────────────
Function: extract_text_from_file()
Location: python-document-intelligence-service/main.py

Logic Flow:
  ┌─> Is it an Image/PDF? ──YES──> Route to OCR Service (Step 3a)
  │
  └─> Has handwriting? ──YES──> Route to ICR Service (Step 3b)
      
      If text-based (docx, txt) ──> Extract directly (no service call)


STEP 3a: OCR SERVICE (Optical Character Recognition)
─────────────────────────────────────────────────────
Service: OCR Service (Port 8000)
File: python-ocr-service/main.py
Endpoint: POST /ocr/process

Technology: DeepSeek-OCR / TrOCR / Transformers
Model: Vision-Language Model for document understanding

Process:
  1. Receive image/PDF file
  2. Convert PDF to images if needed
  3. Run OCR model inference
  4. Extract text with high accuracy
  5. Generate markdown formatted output
  6. Calculate confidence scores
  7. Save processing artifacts

Output:
  {
    "text": "Extracted text content...",
    "confidence": 0.92,
    "metadata": {
      "extraction_method": "ocr_deepseek",
      "prompt": "Convert document to markdown",
      "artifacts": ["page1.png", "page2.png"]
    },
    "processing_time": 2.5
  }

Returns to: Document Intelligence Service


STEP 3b: ICR SERVICE (Intelligent Character Recognition)
─────────────────────────────────────────────────────────
Service: ICR Service (Port 8001)
File: python-icr-service/main.py
Endpoint: POST /icr/process

Technology: TrOCR for handwriting, signature detection
Model: Handwriting-specific models

Process:
  1. Receive image file
  2. Preprocess for handwriting enhancement
  3. Detect signatures and handwritten regions
  4. Run handwriting recognition
  5. Extract structured data from fields
  6. Match against expected fields

Output:
  {
    "handwriting": {
      "text": "Handwritten content...",
      "confidence": 0.85,
      "lines": [...],
      "matched_fields": ["signature", "date", "amount"]
    },
    "signatures": [
      {
        "location": [x, y, w, h],
        "confidence": 0.91
      }
    ]
  }

Returns to: Document Intelligence Service


STEP 4: NLP ANALYSIS (Natural Language Processing)
───────────────────────────────────────────────────
Service: NLP Service (Port 8002)
File: python-nlp-service/main.py
Endpoint: POST /nlp/analyze

Technology: Transformers, spaCy, BERT, VADER
Models: Multi-task NLP pipeline

Triggered: After text extraction (OCR/ICR)

Process:
  1. Receive extracted text
  2. Run multiple NLP tasks in parallel:
     
     a) SENTIMENT ANALYSIS
        └─> Determine positive/negative/neutral sentiment
        └─> Calculate sentiment scores
     
     b) ENTITY RECOGNITION (NER)
        └─> Extract: persons, organizations, locations
        └─> Extract: dates, money, percentages
        └─> Extract: emails, phone numbers
     
     c) KEYWORD EXTRACTION
        └─> Identify important keywords
        └─> Calculate TF-IDF scores
     
     d) TEXT SUMMARIZATION
        └─> Generate brief summary
     
     e) LANGUAGE DETECTION
        └─> Identify document language
     
     f) TEXT CLASSIFICATION
        └─> Categorize document type
        └─> Assign topic labels

Output:
  {
    "sentiment": {
      "label": "positive",
      "score": 0.87,
      "compound": 0.6249
    },
    "entities": [
      {"text": "John Smith", "type": "PERSON", "confidence": 0.98},
      {"text": "$1,500", "type": "MONEY", "confidence": 0.95},
      {"text": "2024-01-15", "type": "DATE", "confidence": 0.92}
    ],
    "keywords": ["invoice", "payment", "due date"],
    "summary": "Payment invoice for services rendered...",
    "language": "en",
    "document_type": "invoice"
  }

Returns to: Document Intelligence Service


STEP 5: DOCUMENT INTELLIGENCE PROCESSING
─────────────────────────────────────────
Location: Document Intelligence Service (Internal Processing)
File: python-document-intelligence-service/main.py

Combines all results and performs:

a) CLASSIFICATION
   Module: app/classification/document_classifier.py
   - Uses ML models to classify document type
   - Leverages NLP entities + OCR/ICR metadata
   - Assigns confidence scores
   
   Output: {
     "document_type": "invoice",
     "confidence": 0.94,
     "sub_categories": ["commercial", "B2B"]
   }

b) ENTITY EXTRACTION
   Module: app/extraction/entity_extractor.py
   - Extracts structured data fields
   - Validates against expected patterns
   - Enriches with context
   
   Output: {
     "entities": {
       "invoice_number": "INV-2024-001",
       "total_amount": "$1,500.00",
       "due_date": "2024-01-15",
       "vendor": "Acme Corp"
     }
   }

c) TEMPLATE MATCHING
   Module: app/templates/template_manager.py
   - Matches against known document templates
   - Identifies document structure
   
   Output: {
     "matched_template": "standard_invoice_v1",
     "similarity": 0.92
   }

d) VALIDATION
   Module: app/validation/document_validator.py
   - Validates required fields present
   - Checks data consistency
   - Identifies potential issues
   
   Output: {
     "is_valid": true,
     "validation_score": 0.96,
     "issues": []
   }

e) ROUTING DECISION
   Module: app/routing/document_router.py
   - Determines where document should go
   - Applies business rules
   - Suggests workflow actions
   
   Output: {
     "routing_destinations": ["accounting_inbox"],
     "priority_level": "normal",
     "recommended_actions": ["approve", "process_payment"]
   }


STEP 6: AGGREGATE RESULTS
──────────────────────────
Function: analyze_document_intelligence()
Location: python-document-intelligence-service/main.py:354

Combines all analysis results into comprehensive response:

{
  "classification": {...},
  "extraction": {...},
  "template_match": {...},
  "validation": {...},
  "routing": {...},
  "nlp_analysis": {...},
  "ocr_metadata": {...},
  "processing_summary": {
    "total_time": 5.2,
    "services_used": ["ocr", "nlp", "classification"],
    "confidence": 0.91
  }
}


STEP 7: RESPONSE TO CLIENT
───────────────────────────
🎯 EXIT POINT: HTTP Response

The Document Intelligence Service returns the complete analysis
to the original client.

Client receives comprehensive document understanding:
  • Extracted text
  • Document classification
  • Structured entities
  • Routing recommendations
  • Validation results
  • Processing metadata
"""

# =============================================================================
# SERVICE PORTS & RESPONSIBILITIES
# =============================================================================

SERVICES = """
══════════════════════════════════════════════════════════════════════════════
SERVICE BREAKDOWN
══════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│ 1. OCR SERVICE (Port 8000)                                              │
├─────────────────────────────────────────────────────────────────────────┤
│ Purpose: Convert images/PDFs to text using computer vision             │
│ Technology: DeepSeek-OCR, TrOCR, Vision Transformers                   │
│ Endpoints:                                                              │
│   • POST /ocr/process    - Process single file                         │
│   • POST /jobs           - Submit batch job                            │
│   • GET  /jobs/{id}      - Check job status                            │
│   • GET  /health         - Health check                                │
│                                                                         │
│ Input: Image files (PNG, JPG), PDF documents                           │
│ Output: Extracted text, confidence scores, artifacts                   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ 2. ICR SERVICE (Port 8001)                                              │
├─────────────────────────────────────────────────────────────────────────┤
│ Purpose: Recognize handwriting and signatures                          │
│ Technology: TrOCR handwriting models, OpenCV                           │
│ Endpoints:                                                              │
│   • POST /icr/process         - Process handwritten document           │
│   • POST /recognize           - Recognize handwriting                  │
│   • POST /preprocess          - Preprocess image                       │
│   • POST /training/add_sample - Add training sample                    │
│   • POST /training/start      - Start model training                   │
│   • GET  /health              - Health check                           │
│                                                                         │
│ Input: Images with handwriting, signatures                             │
│ Output: Recognized text, signature locations, field matches            │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ 3. NLP SERVICE (Port 8002)                                              │
├─────────────────────────────────────────────────────────────────────────┤
│ Purpose: Understand and analyze text content                           │
│ Technology: BERT, spaCy, Transformers, VADER, NLTK                     │
│ Endpoints:                                                              │
│   • POST /nlp/analyze          - Multi-task analysis                   │
│   • POST /analyze/sentiment    - Sentiment analysis                    │
│   • POST /analyze/entities     - Named entity recognition              │
│   • POST /analyze/keywords     - Keyword extraction                    │
│   • POST /analyze/summarize    - Text summarization                    │
│   • POST /analyze/language     - Language detection                    │
│   • POST /analyze/classify     - Text classification                   │
│   • POST /analyze/similarity   - Semantic similarity                   │
│   • POST /analyze/batch        - Batch processing                      │
│   • GET  /health               - Health check                          │
│                                                                         │
│ Input: Plain text                                                      │
│ Output: Entities, sentiment, keywords, summary, classification         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ 4. DOCUMENT INTELLIGENCE SERVICE (Port 8003/8004)                       │
├─────────────────────────────────────────────────────────────────────────┤
│ Purpose: Main orchestrator - coordinates all services                  │
│ Technology: FastAPI, ML models, business logic                         │
│ Endpoints:                                                              │
│   • POST /upload/analyze         - 🎯 MAIN ENTRY POINT                │
│   • POST /intelligence/analyze   - Text-based analysis                 │
│   • POST /batch/process          - Batch document processing           │
│   • GET  /analytics/stats        - Processing statistics               │
│   • GET  /health                 - Health check                        │
│                                                                         │
│ Internal Modules:                                                      │
│   • DocumentClassifier    - ML-based document classification           │
│   • EntityExtractor       - Structured data extraction                │
│   • TemplateManager       - Template matching & recognition            │
│   • DocumentValidator     - Quality & completeness validation          │
│   • DocumentRouter        - Routing & workflow decisions               │
│                                                                         │
│ Input: Any document file or text                                       │
│ Output: Complete intelligence analysis + routing decisions             │
└─────────────────────────────────────────────────────────────────────────┘
"""

# =============================================================================
# TYPICAL USE CASES
# =============================================================================

USE_CASES = """
══════════════════════════════════════════════════════════════════════════════
TYPICAL USE CASES & SCENARIOS
══════════════════════════════════════════════════════════════════════════════

USE CASE 1: Process Scanned Invoice
────────────────────────────────────
1. User uploads scanned invoice PDF
2. → Document Intelligence Service receives it
3. → Routes to OCR Service (extract text)
4. → Routes to NLP Service (analyze content)
5. → Classification: Identifies as "invoice"
6. → Extraction: Pulls invoice #, amount, date, vendor
7. → Validation: Checks required fields present
8. → Routing: Sends to accounting department
9. ← Returns: Complete analysis + routing decision


USE CASE 2: Process Handwritten Form
─────────────────────────────────────
1. User uploads image of handwritten form
2. → Document Intelligence Service receives it
3. → Routes to ICR Service (recognize handwriting)
4. → Routes to NLP Service (analyze text)
5. → Extraction: Pulls form fields (name, date, signature)
6. → Validation: Verifies signature present
7. → Template Match: Matches against "application_form_v2"
8. ← Returns: Structured data + validation results


USE CASE 3: Batch Email Processing
───────────────────────────────────
1. System sends batch of emails as text
2. → Document Intelligence Service receives batch
3. → Routes to NLP Service (analyze each email)
4. → Classification: Categorizes (inquiry, complaint, request)
5. → Entity Extraction: Pulls customer info, dates, products
6. → Sentiment Analysis: Identifies urgent/angry emails
7. → Routing: Auto-routes by category & priority
8. ← Returns: Categorized emails + routing assignments


USE CASE 4: Multi-page Document Analysis
─────────────────────────────────────────
1. User uploads 20-page contract PDF
2. → Document Intelligence Service receives it
3. → Routes to OCR Service (extract all pages)
4. → Routes to NLP Service (analyze full text)
5. → Template Match: Identifies as "legal_contract"
6. → Extraction: Pulls parties, dates, terms, obligations
7. → Summary: Generates executive summary
8. → Validation: Checks required clauses present
9. ← Returns: Structured contract data + summary
"""

# =============================================================================
# ARCHITECTURE PATTERNS
# =============================================================================

PATTERNS = """
══════════════════════════════════════════════════════════════════════════════
ARCHITECTURAL PATTERNS & DESIGN
══════════════════════════════════════════════════════════════════════════════

1. MICROSERVICES ARCHITECTURE
   ✓ Each service is independent
   ✓ Can scale services separately
   ✓ Different tech stacks per service
   ✓ Fault isolation (one service failure doesn't kill all)

2. ORCHESTRATOR PATTERN
   ✓ Document Intelligence is the orchestrator
   ✓ Coordinates calls to specialized services
   ✓ Aggregates results
   ✓ Applies business logic

3. API GATEWAY PATTERN
   ✓ Single entry point (/upload/analyze)
   ✓ Routes to appropriate backend services
   ✓ Handles authentication (can be added)
   ✓ Rate limiting (can be added)

4. SHARED DATA MODEL
   ✓ shared/schemas.py defines common data structures
   ✓ All services use Pydantic models
   ✓ Type safety across services
   ✓ Easy serialization/deserialization

5. ASYNC/AWAIT PATTERN
   ✓ Non-blocking HTTP calls between services
   ✓ Parallel processing where possible
   ✓ Better resource utilization
   ✓ Faster overall processing

6. FALLBACK PATTERN
   ✓ Services have fallback implementations
   ✓ Graceful degradation if dependencies missing
   ✓ Continues processing even if one service fails
"""

# =============================================================================
# QUICK REFERENCE
# =============================================================================

QUICK_REF = """
══════════════════════════════════════════════════════════════════════════════
QUICK REFERENCE
══════════════════════════════════════════════════════════════════════════════

🎯 MAIN ENTRY POINT:
   POST http://localhost:8003/upload/analyze
   or
   POST http://localhost:8004/upload/analyze

📤 HOW TO USE:
   curl -X POST http://localhost:8003/upload/analyze \\
        -F "file=@document.pdf" \\
        -F "analysis_type=full" \\
        -F "confidence_threshold=0.8"

🔌 SERVICE URLS:
   OCR Service:    http://localhost:8000
   ICR Service:    http://localhost:8001
   NLP Service:    http://localhost:8002
   Doc Intel:      http://localhost:8003 or 8004

📊 DATA FLOW SUMMARY:
   Client → Doc Intelligence → [OCR, ICR, NLP] → Processing → Client

🗂️ SHARED SCHEMAS:
   Location: shared/schemas.py
   Contains: FileReference, OcrJobRequest, IcrJobRequest, 
             NlpClassificationRequest, etc.

⚙️ CONFIGURATION:
   Environment Variables:
   • OCR_SERVICE_URL (default: http://localhost:8000)
   • ICR_SERVICE_URL (default: http://localhost:8001)
   • NLP_SERVICE_URL (default: http://localhost:8002)
"""

# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print(ARCHITECTURE)
    print("\n\n")
    print(DATA_FLOW)
    print("\n\n")
    print(SERVICES)
    print("\n\n")
    print(USE_CASES)
    print("\n\n")
    print(PATTERNS)
    print("\n\n")
    print(QUICK_REF)
