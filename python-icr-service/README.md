# 📝 ICR Service - Intelligent Character Recognition

**Port:** 8001  
**Purpose:** Handwriting recognition and signature detection  
**Model:** Microsoft TrOCR (Handwritten variant)

---

## 🎯 Overview

The ICR (Intelligent Character Recognition) service specializes in recognizing handwritten text and detecting signatures in documents. It uses state-of-the-art transformer-based models (TrOCR) for accurate handwriting recognition.

### Key Features
- ✅ **Handwriting Recognition**: Convert handwritten text to digital format
- ✅ **Signature Detection**: Identify and verify signatures
- ✅ **Form Processing**: Extract data from handwritten forms
- ✅ **Training Pipeline**: Collect and improve with custom data
- ✅ **GPU Acceleration**: CUDA support for faster processing
- ✅ **Pre-trained Model**: Production-ready without training

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- CUDA-enabled GPU (optional, for acceleration)
- Dependencies installed (see requirements.txt)

### Installation

```bash
# Navigate to service directory
cd python-icr-service

# Install dependencies
pip install -r requirements.txt

# Start the service
python main.py
```

Service will start on `http://localhost:8001`

---

## 📡 API Endpoints

### 1. Process Document (Direct Upload)
```bash
POST /icr/process
```

Upload a document for immediate handwriting recognition.

**Request:**
```bash
curl -X POST http://localhost:8001/icr/process \
  -F "file=@handwritten_form.jpg"
```

**Response:**
```json
{
  "handwriting": {
    "text": "Extracted handwritten text",
    "confidence": 0.89,
    "processing_time": 2.3,
    "lines": [...]
  },
  "signatures": [
    {
      "bbox": [100, 200, 300, 250],
      "confidence": 0.95,
      "is_genuine": true
    }
  ],
  "timestamp": "2025-11-01T12:00:00"
}
```

### 2. Create Job (Async Processing)
```bash
POST /jobs
```

Create an asynchronous processing job.

**Request:**
```json
{
  "document_id": "doc_12345",
  "source_file": {
    "uri": "file:///path/to/document.jpg",
    "checksum": "abc123..."
  },
  "fields_of_interest": ["signature", "name", "date"]
}
```

**Response:**
```json
{
  "document_id": "doc_12345",
  "job_id": "icr_doc_12345_a1b2c3",
  "status": "queued",
  "signed": false,
  "signature_count": 0,
  "signatures": [],
  "handwriting": []
}
```

### 3. Get Job Status
```bash
GET /jobs/{job_id}
```

Check status and retrieve results of an asynchronous job.

### 4. Health Check
```bash
GET /health
```

Returns service health and model information.

---

## 🎓 Training (Optional)

### Do I Need to Train?

**NO** - The service uses a pre-trained model that works well for general handwriting.

**Consider training only if:**
- You have domain-specific handwriting styles
- You need to recognize specialized forms
- Performance is unsatisfactory for your use case

### Collecting Training Data

The service includes built-in training data collection:

```python
# Enable training data collection
from app.training.training_data_collector import TrainingDataCollector

collector = TrainingDataCollector(data_dir="./training_data")

# After processing, save user-corrected data
collector.add_sample(
    image=image_data,
    ground_truth=user_corrected_text,
    category="handwritten_form",
    metadata={"user_id": "user123", "confidence": 0.85}
)
```

### Training Data Requirements

To fine-tune the model effectively:
- **Minimum**: 500 labeled samples
- **Recommended**: 1,000+ samples
- **Optimal**: 5,000+ samples

Each sample needs:
- Image of handwritten text
- Correct transcription (ground truth)
- Metadata (optional but helpful)

### Export Training Dataset

```python
# Export for model training
collector.export_dataset(
    output_path="./training_export",
    format="json",
    split_ratio={"train": 0.8, "val": 0.1, "test": 0.1}
)
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Model configuration
ICR_MODEL_PATH=./models
MODEL_NAME=microsoft/trocr-base-handwritten

# Processing configuration
MAX_IMAGE_SIZE=2048
SUPPORTED_FORMATS=png,jpg,jpeg,tiff,bmp

# Training configuration
TRAINING_DATA_PATH=./training_data
ENABLE_TRAINING_COLLECTION=false

# Performance
USE_GPU=true
BATCH_SIZE=4
```

---

## 📊 Model Information

### Pre-trained Model
- **Name**: `microsoft/trocr-base-handwritten`
- **Training Data**: IAM Handwriting Database
- **Architecture**: Vision Transformer + Text Decoder
- **Performance**: ~80-90% accuracy on general handwriting

### Signature Detection
- Custom signature detection using OpenCV contours
- Confidence scoring based on shape characteristics
- Genuine/forged signature classification (basic)

---

## 🏗️ Architecture

```
ICR Service
├── main.py                          # FastAPI application
├── app/
│   ├── models/
│   │   ├── base_icr_model.py       # Base model interface
│   │   └── trocr_model.py          # TrOCR implementation
│   ├── preprocessing/
│   │   └── handwriting_processor.py # Image preprocessing
│   └── training/
│       └── training_data_collector.py # Training data management
├── training_data/                   # Collected training samples
│   ├── images/
│   └── metadata/
└── models/                          # Downloaded model cache
```

---

## 🤝 Integration with Document Intelligence

The ICR service is called by the main Document Intelligence service:

```python
# From Document Intelligence service
icr_result = await extract_text_with_icr(
    content=file_bytes,
    filename="document.jpg",
    content_type="image/jpeg"
)

# Result includes:
# - handwriting.text: Recognized text
# - handwriting.confidence: Recognition confidence
# - signatures: List of detected signatures
# - signed: Boolean (true if signatures found)
```

---

## 🐛 Troubleshooting

### Common Issues

**1. Model Download Slow**
```bash
# Pre-download the model
python -c "from transformers import pipeline; pipeline('image-to-text', model='microsoft/trocr-base-handwritten')"
```

**2. Out of Memory**
```bash
# Reduce batch size
export BATCH_SIZE=1

# Or use CPU instead of GPU
export USE_GPU=false
```

**3. Poor Recognition Quality**
- Ensure images are high resolution (300 DPI+)
- Pre-process images (noise reduction, deskew)
- Consider collecting training data for fine-tuning

---

## 📈 Performance Metrics

### Processing Speed
- **CPU**: 5-10 seconds per page
- **GPU (CUDA)**: 1-3 seconds per page

### Accuracy
- **Printed-like handwriting**: 85-95%
- **Cursive/messy handwriting**: 60-80%
- **Signature detection**: 90-95%

---

## 🔒 Production Considerations

### Scaling
- Use load balancer for multiple instances
- Consider GPU instances for high throughput
- Implement job queue (Redis/RabbitMQ) for async processing

### Security
- Validate file types and sizes
- Implement rate limiting
- Use authentication for API access
- Sanitize extracted text

### Monitoring
- Track processing times
- Monitor model performance
- Log recognition confidence scores
- Alert on low confidence results

---

## 📚 Additional Resources

- [TrOCR Paper](https://arxiv.org/abs/2109.10282)
- [Hugging Face Model Card](https://huggingface.co/microsoft/trocr-base-handwritten)
- [IAM Handwriting Database](https://fki.tic.heia-fr.ch/databases/iam-handwriting-database)

---

## 📝 License

This service uses the following open-source components:
- TrOCR: MIT License
- PyTorch: BSD License
- FastAPI: MIT License

---

**For integration guides and deployment instructions, see `/docs/deployment/`**
