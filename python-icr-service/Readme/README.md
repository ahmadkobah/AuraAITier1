# SmartDockAI ICR Service

A high-performance **Intelligent Character Recognition (ICR)** microservice specialized for handwriting recognition, signature verification, and form processing. Built with Python, TrOCR (Transformer-based OCR), and FastAPI.

## 🎯 Overview

The ICR service complements the OCR service by providing specialized handwriting recognition capabilities using state-of-the-art transformer models. It's designed for production deployment with comprehensive training capabilities and seamless integration with the SmartDockAI platform.

## ✨ Features

### Core Recognition Capabilities
- **📝 Handwriting Recognition** - Advanced text recognition from handwritten documents
- **✍️ Signature Verification** - Digital signature detection and analysis
- **📋 Form Processing** - Intelligent processing of handwritten forms
- **🔤 Character Segmentation** - Line, word, and character-level segmentation
- **🌐 Multi-language Support** - Support for multiple languages and scripts

### Advanced Processing
- **🔍 Content Analysis** - Automatic detection of handwritten vs printed text
- **⚡ Batch Processing** - Efficient processing of multiple documents
- **📊 Confidence Scoring** - Detailed confidence metrics for quality assessment
- **🎯 Adaptive Preprocessing** - Specialized image enhancement for handwriting

### Training & Model Management
- **🧠 Model Training** - Fine-tune models with custom datasets
- **📈 Training Data Collection** - Automated collection and validation
- **📋 Dataset Management** - Comprehensive dataset statistics and export
- **🔄 Model Versioning** - Support for multiple model versions

### Integration & Deployment
- **🐳 Docker Ready** - Containerized deployment with Docker Compose
- **🌐 RESTful API** - FastAPI-based microservice architecture
- **💊 Health Monitoring** - Built-in health checks and monitoring
- **🔌 Easy Integration** - Seamless integration with Node.js backend

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ICR Microservice                        │
├─────────────────────────────────────────────────────────────┤
│  FastAPI Web Server (Port 8001)                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Recognition   │  │  Preprocessing  │  │   Training   │ │
│  │    Pipeline     │  │     Service     │  │   Service    │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │  TrOCR Model    │  │ Handwriting     │  │   Training   │ │
│  │  (Transformer)  │  │  Processor      │  │   Collector  │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  Storage: Models, Training Data, Logs                      │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Docker & Docker Compose
- 4GB+ RAM (for model loading)
- CUDA-compatible GPU (optional, for faster processing)

### 1. Docker Deployment (Recommended)

```bash
# Clone the repository
git clone https://github.com/ahmadkobah/SmartDockAI.git
cd SmartDockAI

# Start ICR service with Docker Compose
docker-compose up python-icr -d

# Check service health
curl http://localhost:8001/health
```

### 2. Local Development Setup

```bash
# Navigate to ICR service directory
cd python-icr-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ICR_MODEL_PATH=./models
export TRAINING_DATA_PATH=./training_data
export MAX_IMAGE_SIZE=2048

# Run the service
python main.py
```

The service will be available at `http://localhost:8001`

## 📚 API Documentation

### Core Endpoints

#### Health Check
```http
GET /health
```
Returns service health status and component availability.

#### Service Information
```http
GET /
```
Returns service capabilities and version information.

### Recognition Endpoints

#### Recognize Handwriting
```http
POST /recognize
Content-Type: multipart/form-data

Parameters:
- file: Image file (PNG, JPG, TIFF)
- recognition_type: "full_text" | "line_by_line" | "word_by_word"
- preprocess: boolean (default: true)
```

**Example Response:**
```json
{
  "recognized_text": "Hello World",
  "confidence": 0.92,
  "recognition_type": "full_text",
  "preprocessing_applied": true,
  "timestamp": "2025-10-16T10:30:00Z"
}
```

#### Preprocess Image
```http
POST /preprocess
Content-Type: multipart/form-data

Parameters:
- file: Image file
- task_type: "line_recognition" | "word_recognition" | "character_recognition"
- return_segments: boolean
```

### Training Endpoints

#### Add Training Sample
```http
POST /training/add_sample
Content-Type: multipart/form-data

Parameters:
- ground_truth: Correct text transcription
- file: Image file
- category: Sample category (default: "general")
- metadata: Additional metadata (JSON string)
```

#### Get Training Statistics
```http
GET /training/stats
```

#### Start Model Training
```http
POST /training/start

Body:
{
  "epochs": 5,
  "batch_size": 8,
  "learning_rate": 1e-5
}
```

### Model Endpoints

#### Get Model Information
```http
GET /model/info
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ICR_MODEL_PATH` | `./models` | Directory for model storage |
| `TRAINING_DATA_PATH` | `./training_data` | Directory for training data |
| `MAX_IMAGE_SIZE` | `2048` | Maximum image dimension (pixels) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `PYTHONPATH` | `/app` | Python path for imports |

### Model Configuration

The service uses Microsoft's TrOCR model by default. You can customize the model in `app/models/trocr_model.py`:

```python
# Default model configuration
MODEL_NAME = "microsoft/trocr-base-handwritten"
PROCESSOR_NAME = "microsoft/trocr-base-handwritten"
```

### Preprocessing Configuration

Customize preprocessing parameters in the service initialization:

```python
preprocessing_config = {
    "noise_reduction": "medium",  # light, medium, heavy
    "skew_detection": True,
    "min_line_height": 20,
    "max_line_height": 200
}
```

## 🧪 Usage Examples

### Python Integration

```python
import requests

# Recognize handwriting
with open('handwriting.png', 'rb') as f:
    response = requests.post(
        'http://localhost:8001/recognize',
        files={'file': f},
        params={'recognition_type': 'line_by_line'}
    )
    result = response.json()
    print(f"Recognized: {result['lines']}")
```

### Node.js Integration

```javascript
const PythonICRIntegration = require('./src/services/PythonICRIntegration');

const icr = new PythonICRIntegration();

// Process handwriting
const result = await icr.processHandwriting('handwriting.png', {
    recognitionType: 'line_by_line',
    addToTraining: false
});

console.log('Recognized text:', result.summary.recognizedText);
```

### cURL Examples

```bash
# Recognize handwriting
curl -X POST "http://localhost:8001/recognize" \
  -F "file=@handwriting.png" \
  -F "recognition_type=full_text"

# Add training sample
curl -X POST "http://localhost:8001/training/add_sample" \
  -F "file=@sample.png" \
  -F "ground_truth=Hello World" \
  -F "category=general"

# Get training stats
curl "http://localhost:8001/training/stats"
```

## 🏋️ Training Custom Models

### 1. Collect Training Data

```python
# Add training samples via API
import requests

with open('handwriting_sample.png', 'rb') as f:
    response = requests.post(
        'http://localhost:8001/training/add_sample',
        files={'file': f},
        data={
            'ground_truth': 'The actual text content',
            'category': 'handwriting',
            'metadata': '{"source": "form", "quality": "high"}'
        }
    )
```

### 2. Monitor Dataset

```bash
# Check training statistics
curl "http://localhost:8001/training/stats"
```

### 3. Start Training

```bash
curl -X POST "http://localhost:8001/training/start" \
  -H "Content-Type: application/json" \
  -d '{
    "epochs": 10,
    "batch_size": 16,
    "learning_rate": 5e-6
  }'
```

## 🐳 Docker Compose Integration

The ICR service integrates seamlessly with the SmartDockAI platform:

```yaml
services:
  python-icr:
    build:
      context: ./python-icr-service
    ports:
      - "8001:8001"
    environment:
      PYTHONPATH: /app
      ICR_MODEL_PATH: /app/models
      TRAINING_DATA_PATH: /app/training_data
    volumes:
      - ./python-icr-service/training_data:/app/training_data
      - ./python-icr-service/models:/app/models
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8001/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## 📊 Performance & Scaling

### Performance Metrics
- **Recognition Speed**: ~2-5 seconds per image (CPU)
- **GPU Acceleration**: 3-5x faster with CUDA support
- **Memory Usage**: ~2-4GB RAM for model loading
- **Throughput**: 10-50 images/minute (depending on hardware)

### Scaling Recommendations
- **Horizontal Scaling**: Deploy multiple ICR service instances
- **GPU Support**: Use NVIDIA Docker for GPU acceleration
- **Load Balancing**: Use nginx or cloud load balancers
- **Caching**: Implement Redis caching for frequent requests

## 🔍 Monitoring & Debugging

### Health Monitoring

```bash
# Check service health
curl http://localhost:8001/health

# Get detailed service info
curl http://localhost:8001/

# Monitor model status
curl http://localhost:8001/model/info
```

### Logging

Logs are available in the container and can be accessed via:

```bash
# View ICR service logs
docker-compose logs python-icr

# Follow logs in real-time
docker-compose logs -f python-icr
```

### Debug Mode

Enable debug logging by setting:

```bash
export LOG_LEVEL=DEBUG
```

## 🛠️ Development

### Project Structure

```
python-icr-service/
├── app/
│   ├── models/
│   │   ├── base_icr_model.py      # Abstract ICR model interface
│   │   └── trocr_model.py         # TrOCR implementation
│   ├── preprocessing/
│   │   └── handwriting_processor.py # Specialized preprocessing
│   └── training/
│       └── training_data_collector.py # Training data management
├── models/                         # Model storage
├── training_data/                  # Training datasets
├── Dockerfile                      # Container definition
├── requirements.txt               # Python dependencies
├── main.py                       # FastAPI application
└── README.md                     # This file
```

### Adding New Models

1. Create model class inheriting from `ICRModelInterface`
2. Implement required methods: `load_model()`, `predict()`, `train()`
3. Update model registry in `main.py`

### Testing

```bash
# Run tests (when implemented)
pytest tests/

# Test with sample images
python -m pytest tests/test_recognition.py
```

## 🤝 Integration with SmartDockAI

The ICR service integrates with the main SmartDockAI platform through:

1. **Enhanced ICR Service** (`src/services/EnhancedICRService.js`)
   - Automatic content type detection
   - Intelligent routing between OCR and ICR
   - Combined result processing

2. **Node.js Integration** (`src/services/PythonICRIntegration.js`)
   - Direct API communication
   - Error handling and retries
   - Training data management

3. **Document Processing Pipeline**
   - Automatic handwriting detection
   - Mixed content processing
   - Training data collection

## 📈 Roadmap

### Upcoming Features
- [ ] **Multi-language Models** - Support for additional languages
- [ ] **Signature Verification** - Advanced signature analysis
- [ ] **Form Understanding** - Intelligent form field detection
- [ ] **Model Ensemble** - Combine multiple models for better accuracy
- [ ] **Real-time Processing** - WebSocket support for live recognition
- [ ] **Cloud Deployment** - Kubernetes deployment configurations

### Performance Improvements
- [ ] **Model Optimization** - Quantization and pruning
- [ ] **Caching Layer** - Redis-based result caching
- [ ] **Batch Processing** - Optimized batch inference
- [ ] **Streaming Processing** - Support for large documents

## 🐛 Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check Docker logs
docker-compose logs python-icr

# Verify dependencies
pip check

# Check port availability
netstat -an | grep 8001
```

#### Low Recognition Accuracy
- Ensure images are high quality (300+ DPI)
- Check image preprocessing settings
- Add more training data for specific content types
- Verify ground truth quality for training samples

#### Memory Issues
- Reduce batch size for training
- Use CPU-only mode if GPU memory is limited
- Implement model quantization

#### API Timeouts
- Increase timeout settings in client applications
- Optimize image sizes before processing
- Consider batch processing for multiple images

### Support

For issues and questions:
- Create an issue on [GitHub](https://github.com/ahmadkobah/SmartDockAI/issues)
- Check the [Wiki](https://github.com/ahmadkobah/SmartDockAI/wiki) for detailed guides
- Review logs for detailed error information

## 📄 License

This project is part of SmartDockAI and follows the same licensing terms.

## 🙏 Acknowledgments

- **Microsoft TrOCR** - Transformer-based OCR model
- **Hugging Face Transformers** - Model implementation and hosting
- **FastAPI** - High-performance web framework
- **OpenCV** - Computer vision library
- **PyTorch** - Deep learning framework

---

**Built with ❤️ for the SmartDockAI Platform**