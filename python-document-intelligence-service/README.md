# SmartDockAI Document Intelligence Service

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Integration](https://img.shields.io/badge/Integration-✅%20Complete-brightgreen.svg)](README.md)

Advanced ML-based document understanding and intelligence platform providing comprehensive document classification, entity extraction, template matching, automated validation, and intelligent routing capabilities.

**🎯 FULLY INTEGRATED WITH OCR, ICR, AND NLP SERVICES**

## ✅ Integration Status: COMPLETE

Your Document Intelligence System is now **fully operational** with complete service integration:

- ✅ **OCR Service Integration**: Real image/PDF text extraction via HTTP client
- ✅ **ICR Service Integration**: Handwriting recognition for scanned documents  
- ✅ **NLP Service Integration**: Enhanced text analysis with sentiment and entities
- ✅ **Docker Compose Setup**: All services properly networked and configured
- ✅ **Node.js API Integration**: Complete REST API with authentication and file upload
- ✅ **End-to-End Testing**: Comprehensive integration verification scripts

### 🔗 Live Service Communication
```
File Upload → Document Intelligence (8004)
     ↓
Smart Text Extraction:
     ├── Text files: Direct processing
     ├── Images/PDFs: → OCR Service (8000) via HTTP
     ├── Handwritten: → ICR Service (8001) via HTTP
     └── Enhanced Analysis: → NLP Service (8002) via HTTP
     ↓
Complete ML Pipeline → Intelligence Results
```

## 🚀 Features

### Core Intelligence Capabilities
- **🔍 Document Classification**: Multi-algorithm document type detection with confidence scoring
- **📊 Entity Extraction**: Advanced NER for people, organizations, dates, amounts, and custom entities
- **📋 Template Matching**: Structural and content-based document template identification
- **✅ Document Validation**: Business rule and compliance validation with detailed reporting
- **🔄 Intelligent Routing**: Smart workflow routing based on content analysis and business rules

### Advanced Features
- **🤖 Multiple ML Models**: Integration of transformer models, traditional ML, and rule-based approaches
- **⚡ Real-time Processing**: Fast document analysis with sub-second response times
- **📦 Batch Processing**: Efficient handling of large document volumes
- **📈 Analytics Dashboard**: Comprehensive processing metrics and performance monitoring
- **🔧 Customizable Rules**: Flexible validation and routing rule configuration
- **🌐 RESTful API**: Complete API with OpenAPI/Swagger documentation

## 🏗️ Architecture

```
Document Intelligence Service
├── FastAPI Application (main.py)
├── Core Models
│   ├── Classification Model (ML-based document type detection)
│   ├── Extraction Model (Advanced NER and entity recognition)
│   └── Template Model (Document template matching)
├── Service Layer
│   ├── Document Classifier (High-level classification service)
│   ├── Entity Extractor (Entity extraction coordination)
│   ├── Template Manager (Template lifecycle management)
│   ├── Document Validator (Business rules and compliance)
│   └── Document Router (Intelligent workflow routing)
└── Storage
    ├── Trained Models (ML model persistence)
    └── Training Data (Dataset management)
```

## 🛠️ Installation

### Prerequisites
- Python 3.11+
- 8GB+ RAM recommended
- CUDA-compatible GPU (optional, for transformer models)

### Using Docker (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd SmartDockAI/python-document-intelligence-service

# Build and run with Docker
docker build -t smartdockai-intelligence .
docker run -p 8004:8004 smartdockai-intelligence
```

### Local Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download required NLP models
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet')"
python -m spacy download en_core_web_sm

# Start the service
uvicorn main:app --host 0.0.0.0 --port 8004 --reload
```

## 🔧 Configuration

### Environment Variables

```bash
# Service Configuration
INTELLIGENCE_SERVICE_PORT=8004
INTELLIGENCE_SERVICE_HOST=0.0.0.0

# Model Configuration
ML_MODEL_PATH=./trained_models
TRAINING_DATA_PATH=./training_data
CONFIDENCE_THRESHOLD=0.8

# Performance Settings
MAX_WORKERS=4
BATCH_SIZE=32
ENABLE_GPU=false

# Logging
LOG_LEVEL=INFO
LOG_FILE=document_intelligence.log
```

### Model Configuration

```python
# Example model configuration
config = {
    "classification": {
        "max_features": 10000,
        "ngram_range": (1, 3),
        "confidence_threshold": 0.8,
        "ensemble_weights": {
            "transformer": 0.5,
            "random_forest": 0.2,
            "gradient_boosting": 0.15,
            "logistic_regression": 0.1,
            "svm": 0.05
        }
    },
    "extraction": {
        "entity_types": ["PERSON", "ORGANIZATION", "DATE", "MONEY", "EMAIL"],
        "confidence_threshold": 0.7,
        "custom_patterns_enabled": True
    },
    "validation": {
        "strict_mode": False,
        "compliance_checks_enabled": True,
        "custom_rules_enabled": True
    }
}
```

## 📚 API Usage

### Health Check

```bash
curl http://localhost:8004/health
```

### Comprehensive Document Analysis

```python
import requests

# Analyze document with full intelligence
data = {
    "content": "INVOICE #INV-2024-001\nBill To: Acme Corp\nAmount Due: $5,247.50\nDue Date: 2024-02-15",
    "filename": "invoice_001.txt",
    "metadata": {
        "source": "email",
        "received_date": "2024-01-15T10:30:00Z"
    }
}

response = requests.post("http://localhost:8004/intelligence/analyze", json=data)
result = response.json()

print(f"Document Type: {result['classification']['document_type']}")
print(f"Confidence: {result['classification']['confidence']}")
print(f"Entities Found: {len(result['extraction']['entities'])}")
print(f"Validation Status: {'PASSED' if result['validation']['is_valid'] else 'FAILED'}")
print(f"Routing Priority: {result['routing']['priority_level']}")
```

### Individual Service Endpoints

```python
# Document Classification
classification_request = {
    "document": {
        "content": "Invoice content here...",
        "filename": "invoice.pdf"
    },
    "confidence_threshold": 0.8,
    "return_all_predictions": False
}
response = requests.post("http://localhost:8004/classification/classify", json=classification_request)

# Entity Extraction
extraction_request = {
    "document": {
        "content": "John Smith at Acme Corp owes $1,234.56 due on 2024-02-15",
        "metadata": {}
    },
    "extraction_types": ["PERSON", "ORGANIZATION", "MONEY", "DATE"],
    "custom_patterns": {
        "invoice_number": r"INV-\d{4}-\d{3}"
    }
}
response = requests.post("http://localhost:8004/extraction/extract", json=extraction_request)

# Template Matching
template_request = {
    "document": {
        "content": "Invoice with standard layout...",
        "metadata": {}
    },
    "similarity_threshold": 0.85
}
response = requests.post("http://localhost:8004/templates/match", json=template_request)

# Document Validation
validation_request = {
    "document": {
        "content": "Contract content...",
        "metadata": {}
    },
    "document_type": "contract",
    "validation_rules": ["legal_compliance", "signature_required"]
}
response = requests.post("http://localhost:8004/validation/validate", json=validation_request)

# Document Routing
routing_request = {
    "document": {
        "content": "Urgent legal notice...",
        "metadata": {}
    },
    "classification_result": {
        "document_type": "letter",
        "confidence": 0.95
    }
}
response = requests.post("http://localhost:8004/routing/route", json=routing_request)
```

### File Upload Analysis

```python
# Upload and analyze file
files = {'file': open('document.pdf', 'rb')}
data = {
    'analysis_type': 'full',
    'confidence_threshold': 0.8
}
response = requests.post("http://localhost:8004/upload/analyze", files=files, data=data)
```

### Batch Processing

```python
# Process multiple documents
batch_request = {
    "documents": [
        {"content": "Invoice 1 content...", "filename": "invoice1.txt"},
        {"content": "Contract 1 content...", "filename": "contract1.txt"},
        {"content": "Receipt 1 content...", "filename": "receipt1.txt"}
    ],
    "processing_options": {
        "include_validation": True,
        "include_routing": True,
        "confidence_threshold": 0.8
    },
    "callback_url": "https://your-api.com/webhook/batch-complete"
}
response = requests.post("http://localhost:8004/batch/process", json=batch_request)
batch_id = response.json()["batch_id"]
```

## 🤖 Machine Learning Models

### Classification Models

**Document Types Supported:**
- **Invoices**: Sales invoices, service invoices, proforma invoices
- **Contracts**: Service contracts, employment contracts, vendor agreements
- **Receipts**: Sales receipts, payment receipts, expense receipts
- **Letters**: Business letters, personal letters, formal correspondence
- **Reports**: Financial reports, technical reports, status reports
- **Forms**: Application forms, registration forms, survey forms
- **Emails**: Business emails, notification emails, marketing emails
- **Memos**: Internal memos, policy memos, announcement memos

**Model Architecture:**
- **Transformer Models**: BERT-based for contextual understanding
- **Traditional ML**: Random Forest, Gradient Boosting, SVM, Logistic Regression
- **Rule-based**: Pattern matching and keyword analysis
- **Ensemble**: Weighted combination of all approaches

### Entity Extraction

**Supported Entity Types:**
- **PERSON**: Names, titles, contact persons
- **ORGANIZATION**: Companies, institutions, departments
- **DATE**: Various date formats and temporal expressions
- **MONEY**: Amounts, currencies, financial values
- **EMAIL**: Email addresses with validation
- **PHONE**: Phone numbers in multiple formats
- **ADDRESS**: Physical addresses and locations
- **SSN**: Social Security Numbers
- **ACCOUNT_NUMBER**: Account IDs and reference numbers
- **TAX_ID**: Tax identification numbers

**Extraction Methods:**
- **Transformer NER**: BERT-based named entity recognition
- **spaCy NER**: Statistical named entity recognition
- **Pattern-based**: Regex patterns for structured data
- **Custom Models**: Domain-specific trained models

### Template Matching

**Matching Approaches:**
- **Content Similarity**: TF-IDF and cosine similarity
- **Structural Analysis**: Layout and formatting patterns
- **Pattern Recognition**: Specific document structure identification
- **Machine Learning**: Similarity scoring with trained models

**Template Categories:**
- Standard business document templates
- Industry-specific document formats
- Custom organizational templates
- Regulatory compliance templates

## ✅ Validation Framework

### Business Rules Engine

**Rule Categories:**
- **Field Validation**: Required fields, format validation
- **Business Logic**: Amount calculations, date logic
- **Compliance Checks**: Regulatory compliance, standards adherence
- **Data Quality**: Consistency checks, error detection

**Example Rules:**
```python
# Invoice validation rules
invoice_rules = {
    "required_fields": ["invoice_number", "amount", "date", "vendor"],
    "business_rules": [
        "amount_must_be_positive",
        "date_not_in_future",
        "invoice_number_unique"
    ],
    "compliance_checks": [
        "tax_calculation_correct",
        "currency_format_consistent"
    ]
}

# Contract validation rules
contract_rules = {
    "required_fields": ["parties", "effective_date", "terms", "signatures"],
    "business_rules": [
        "all_parties_identified",
        "terms_complete",
        "signatures_present"
    ],
    "compliance_checks": [
        "legal_language_compliant",
        "jurisdiction_clause_present"
    ]
}
```

### Custom Validation Rules

```python
# Add custom validation rule
custom_rule = {
    "name": "custom_amount_limit",
    "description": "Ensure amounts don't exceed organizational limits",
    "rule_type": "business_logic",
    "condition": "amount > organizational_limit",
    "action": "require_additional_approval",
    "severity": "warning"
}

response = requests.post(
    "http://localhost:8004/validation/rules/add",
    json={"rule_name": "amount_limit_check", "rule_config": custom_rule}
)
```

## 🔄 Intelligent Routing

### Routing Engine

**Routing Factors:**
- **Document Type**: Type-specific routing rules
- **Priority Level**: Urgency and importance assessment
- **Content Analysis**: Key information extraction
- **Business Rules**: Organizational workflow rules
- **Compliance Requirements**: Regulatory routing needs

**Priority Levels:**
- **Urgent**: Immediate attention required (legal notices, critical issues)
- **High**: Important documents (high-value invoices, contracts)
- **Medium**: Standard processing (regular invoices, forms)
- **Low**: Routine documents (receipts, information requests)

### Workflow Integration

**Supported Workflows:**
- **Invoice Processing**: Approval, payment, archival
- **Contract Management**: Review, approval, execution, storage
- **Expense Management**: Validation, approval, reimbursement
- **Correspondence Handling**: Response, filing, escalation

**Example Routing Configuration:**
```python
routing_config = {
    "invoice": {
        "high_value_threshold": 10000,
        "urgent_conditions": ["overdue", "disputed"],
        "approval_required": ["amount > 5000", "new_vendor"],
        "auto_approve": ["amount < 500", "trusted_vendor"]
    },
    "contract": {
        "legal_review_required": ["new_contract", "high_value"],
        "executive_approval": ["contract_value > 100000"],
        "standard_processing": ["renewal", "amendment"]
    }
}
```

## 📊 Analytics and Monitoring

### Performance Metrics

```python
# Get service analytics
response = requests.get("http://localhost:8004/analytics/stats")
analytics = response.json()

print(f"Documents Processed: {analytics['total_documents_processed']}")
print(f"Classification Accuracy: {analytics['classification_accuracy']}")
print(f"Average Processing Time: {analytics['average_processing_time']}ms")
print(f"Most Common Document Types: {analytics['most_common_document_types']}")
```

### Processing Statistics

**Classification Metrics:**
- Classification accuracy by document type
- Confidence score distributions
- Model performance comparisons
- Processing time analytics

**Extraction Metrics:**
- Entity extraction rates by type
- Confidence score distributions
- Extraction accuracy measurements
- Custom pattern effectiveness

**Validation Metrics:**
- Validation success rates
- Common validation issues
- Rule effectiveness analysis
- Compliance adherence rates

**Routing Metrics:**
- Routing accuracy and effectiveness
- Priority distribution analysis
- Workflow completion rates
- Destination utilization statistics

## 🚀 Production Deployment

### Docker Deployment

```dockerfile
# Production Dockerfile optimizations
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc g++ make libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download models
RUN python -c "import nltk; nltk.download('punkt')" && \
    python -m spacy download en_core_web_sm

# Copy application
COPY . .

# Create directories
RUN mkdir -p trained_models training_data logs temp

# Set permissions
RUN chmod -R 755 /app

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8004/health || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004", "--workers", "4"]
```

### Kubernetes Deployment

```yaml
# kubernetes-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: smartdockai-intelligence
  labels:
    app: smartdockai-intelligence
spec:
  replicas: 3
  selector:
    matchLabels:
      app: smartdockai-intelligence
  template:
    metadata:
      labels:
        app: smartdockai-intelligence
    spec:
      containers:
      - name: intelligence-service
        image: smartdockai/intelligence:latest
        ports:
        - containerPort: 8004
        env:
        - name: INTELLIGENCE_SERVICE_HOST
          value: "0.0.0.0"
        - name: INTELLIGENCE_SERVICE_PORT
          value: "8004"
        resources:
          limits:
            memory: "8Gi"
            cpu: "4"
          requests:
            memory: "4Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /health
            port: 8004
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8004
          initialDelaySeconds: 5
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: smartdockai-intelligence-service
spec:
  selector:
    app: smartdockai-intelligence
  ports:
    - protocol: TCP
      port: 8004
      targetPort: 8004
  type: LoadBalancer
```

### Performance Optimization

**Memory Management:**
```python
# Optimize memory usage
import gc
import torch

# Clear GPU memory periodically
if torch.cuda.is_available():
    torch.cuda.empty_cache()

# Force garbage collection
gc.collect()
```

**Caching Strategy:**
```python
# Redis caching for frequently accessed data
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_result(key: str, result: dict, ttl: int = 3600):
    """Cache processing results."""
    redis_client.setex(key, ttl, json.dumps(result))

def get_cached_result(key: str) -> dict:
    """Retrieve cached results."""
    cached = redis_client.get(key)
    return json.loads(cached) if cached else None
```

## 🔧 Troubleshooting

### Common Issues

**Model Loading Errors:**
```bash
# Fix NLTK data issues
python -c "import nltk; nltk.download('all')"

# Fix spaCy model issues
python -m spacy download en_core_web_sm --force
```

**Memory Issues:**
```python
# Reduce model complexity
config = {
    "max_features": 5000,  # Reduce from 10000
    "enable_transformer": False,  # Disable for lower memory
    "batch_size": 16  # Reduce batch size
}
```

**Performance Issues:**
```bash
# Enable GPU acceleration
export CUDA_VISIBLE_DEVICES=0
export ENABLE_GPU=true

# Increase worker processes
export MAX_WORKERS=8
```

### Debugging

**Enable Debug Logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Monitor Resource Usage:**
```bash
# Monitor CPU and memory
top -p $(pgrep -f "uvicorn")

# Monitor GPU usage (if available)
nvidia-smi -l 1
```

## 🤝 Contributing

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd SmartDockAI/python-document-intelligence-service

# Create development environment
python -m venv dev-env
source dev-env/bin/activate

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/ -v
```

### Code Quality

```bash
# Format code
black .
isort .

# Lint code
flake8 .
pylint app/

# Type checking
mypy app/
```

### Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/performance/

# Run with coverage
pytest --cov=app --cov-report=html
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **FastAPI**: Modern web framework for building APIs
- **spaCy**: Advanced natural language processing
- **Transformers**: State-of-the-art ML models
- **NLTK**: Natural language toolkit
- **scikit-learn**: Machine learning library
- **OpenAI**: Inspiration for AI-powered document processing

## 📞 Support

- **Documentation**: [Full API Documentation](http://localhost:8004/docs)
- **Issues**: [GitHub Issues](https://github.com/your-org/SmartDockAI/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/SmartDockAI/discussions)
- **Email**: support@smartdockai.com

---

**SmartDockAI Document Intelligence Service** - Transforming document processing with advanced AI and machine learning capabilities.