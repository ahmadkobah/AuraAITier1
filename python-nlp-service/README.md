# SmartDockAI NLP Service

A comprehensive Natural Language Processing (NLP) microservice for text analysis, sentiment analysis, entity recognition, text summarization, and more. Part of the SmartDockAI platform.

## Features

### Core NLP Tasks
- **Sentiment Analysis**: Analyze text sentiment (positive, negative, neutral) with confidence scores
- **Named Entity Recognition**: Extract entities like persons, organizations, locations, etc.
- **Keyword Extraction**: Identify important keywords and phrases with relevance scores
- **Text Summarization**: Generate concise summaries from longer texts
- **Language Detection**: Automatically detect text language with confidence
- **Text Classification**: Classify text into custom categories
- **Semantic Similarity**: Compare similarity between texts

### Additional Capabilities
- **Multi-language Support**: English, Spanish, French, German, Italian, Portuguese, Russian, Chinese
- **Batch Processing**: Process multiple texts efficiently
- **Training Data Management**: Collect, validate, and export training datasets
- **Model Training**: Fine-tune models on custom data
- **Quality Metrics**: Comprehensive validation and quality assessment

## Quick Start

### Using Docker (Recommended)

1. **Build the container**:
```bash
docker build -t smartdockai-nlp .
```

2. **Run the service**:
```bash
docker run -p 8002:8002 smartdockai-nlp
```

3. **Test the service**:
```bash
curl http://localhost:8002/health
```

### Manual Installation

1. **Install Python 3.11+**
2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Download required models**:
```bash
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet')"
```

4. **Run the service**:
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8002
```

## API Usage

### Service Information
```bash
GET /
# Returns service capabilities and supported languages
```

### Health Check
```bash
GET /health
# Returns service health status
```

### Sentiment Analysis
```bash
POST /analyze/sentiment
Content-Type: application/json

{
  "text": "I love this product! It's amazing.",
  "language": "en",
  "include_details": true
}
```

Response:
```json
{
  "sentiment": {
    "label": "positive",
    "score": 0.8543,
    "confidence": 0.9234
  },
  "text": "I love this product! It's amazing.",
  "language": "en",
  "processing_time": 0.023,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Entity Recognition
```bash
POST /analyze/entities
Content-Type: application/json

{
  "text": "John Smith works at Microsoft in Seattle.",
  "language": "en",
  "entity_types": ["PERSON", "ORG", "GPE"]
}
```

Response:
```json
{
  "entities": [
    {
      "text": "John Smith",
      "label": "PERSON",
      "start": 0,
      "end": 10,
      "confidence": 0.9876
    },
    {
      "text": "Microsoft",
      "label": "ORG",
      "start": 20,
      "end": 29,
      "confidence": 0.9543
    },
    {
      "text": "Seattle",
      "label": "GPE",
      "start": 33,
      "end": 40,
      "confidence": 0.8765
    }
  ],
  "total_entities": 3,
  "language": "en"
}
```

### Keyword Extraction
```bash
POST /analyze/keywords
Content-Type: application/json

{
  "text": "Artificial intelligence and machine learning are transforming healthcare through predictive analytics.",
  "max_keywords": 5,
  "min_score": 0.3
}
```

### Text Summarization
```bash
POST /analyze/summarize
Content-Type: application/json

{
  "text": "Very long text content here...",
  "max_length": 150,
  "min_length": 50
}
```

### Language Detection
```bash
POST /analyze/language
Content-Type: application/json

{
  "text": "Bonjour, comment allez-vous?"
}
```

### Semantic Similarity
```bash
POST /analyze/similarity
Content-Type: application/json

{
  "text1": "The cat sat on the mat",
  "text2": "A feline was sitting on a rug"
}
```

### Batch Processing
```bash
POST /analyze/batch
Content-Type: application/json

{
  "texts": [
    "First text to analyze",
    "Second text to analyze", 
    "Third text to analyze"
  ],
  "task": "sentiment",
  "language": "en"
}
```

## Configuration

Environment variables:

```bash
# Model paths
NLP_MODEL_PATH=./models
TRAINING_DATA_PATH=./training_data

# Performance settings
MAX_TEXT_LENGTH=10000
CACHE_ENABLED=true

# Model configuration
SENTIMENT_MODEL=cardiffnlp/twitter-roberta-base-sentiment-latest
NER_MODEL=dbmdz/bert-large-cased-finetuned-conll03-english
SUMMARIZATION_MODEL=facebook/bart-large-cnn
SENTENCE_MODEL=all-MiniLM-L6-v2
```

## Training Data Management

### Collect Training Data
```python
from app.training.training_data_collector import TrainingDataCollector, SentimentSample

collector = TrainingDataCollector("./training_data")

# Add sentiment sample
sample = SentimentSample(
    id="",
    text="This is excellent!",
    sentiment_label="positive",
    sentiment_score=0.9,
    task_type=TaskType.SENTIMENT_ANALYSIS,
    language="en",
    created_at=datetime.utcnow()
)

collector.add_sample(sample)
```

### Export Training Dataset
```python
# Export dataset with train/validation/test splits
file_paths = collector.export_dataset(
    task_type=TaskType.SENTIMENT_ANALYSIS,
    format="json",
    train_split=0.8,
    val_split=0.1,
    test_split=0.1
)
```

### Validate Dataset Quality
```python
validation_results = collector.validate_dataset(TaskType.SENTIMENT_ANALYSIS)
print(f"Valid samples: {validation_results['valid_samples']}")
print(f"Average quality: {validation_results['quality_metrics']['avg_quality_score']}")
```

## Model Architecture

### Base Components
- **Text Preprocessor**: Handles cleaning, tokenization, normalization
- **Multi-task NLP Model**: Unified interface for all NLP tasks
- **Training Data Collector**: Manages training samples and quality

### Supported Models
- **Transformers**: BERT, RoBERTa, BART for deep learning tasks
- **spaCy**: Industrial-strength NLP for entity recognition
- **NLTK**: Classic NLP toolkit for preprocessing
- **TextBlob**: Simple sentiment analysis and language detection
- **Sentence Transformers**: Semantic similarity and embeddings

## Performance

### Throughput
- Single text analysis: ~50-200ms per request
- Batch processing: ~10-50ms per text (depending on batch size)
- Concurrent requests: Supports multiple workers

### Resource Usage
- Memory: ~2-4GB (depending on loaded models)
- CPU: Optimized for multi-core processing
- GPU: Optional CUDA support for transformer models

## Development

### Project Structure
```
python-nlp-service/
├── main.py                    # FastAPI application
├── requirements.txt           # Python dependencies
├── Dockerfile                # Container configuration
├── app/
│   ├── models/
│   │   ├── base_nlp_model.py        # Abstract NLP interface
│   │   └── multitask_nlp_model.py   # Multi-task implementation
│   ├── processing/
│   │   └── text_processor.py        # Text preprocessing
│   ├── training/
│   │   └── training_data_collector.py # Training data management
│   └── utils/                       # Utility functions
├── models/                    # Trained model storage
└── training_data/            # Training dataset storage
```

### Adding New Tasks

1. **Extend base model interface**:
```python
# In base_nlp_model.py
class NewTaskResult:
    def __init__(self, result_data):
        self.result_data = result_data
```

2. **Implement in multi-task model**:
```python
# In multitask_nlp_model.py
async def _predict_new_task(self, text: str, **kwargs):
    # Implementation here
    return NewTaskResult(...)
```

3. **Add API endpoint**:
```python
# In main.py
@app.post("/analyze/new-task")
async def new_task_endpoint(request: NewTaskRequest):
    # Implementation here
```

### Testing

```bash
# Run tests
python -m pytest tests/

# Test specific endpoint
curl -X POST http://localhost:8002/analyze/sentiment \
  -H "Content-Type: application/json" \
  -d '{"text": "Test message", "language": "en"}'
```

## Integration

### With SmartDockAI Platform
The NLP service integrates with other SmartDockAI services:

- **Document Processing**: Analyze extracted text content
- **Search Enhancement**: Improve search with semantic similarity
- **Content Classification**: Automatically categorize documents
- **Quality Assessment**: Evaluate document content quality

### API Client Example
```python
import requests

class NLPClient:
    def __init__(self, base_url="http://localhost:8002"):
        self.base_url = base_url
    
    def analyze_sentiment(self, text, language="en"):
        response = requests.post(
            f"{self.base_url}/analyze/sentiment",
            json={"text": text, "language": language}
        )
        return response.json()
    
    def extract_entities(self, text, entity_types=None):
        response = requests.post(
            f"{self.base_url}/analyze/entities",
            json={"text": text, "entity_types": entity_types}
        )
        return response.json()

# Usage
client = NLPClient()
sentiment = client.analyze_sentiment("I love this product!")
entities = client.extract_entities("John works at Microsoft")
```

## Production Deployment

### Docker Compose Integration
```yaml
# In main docker-compose.yml
services:
  nlp-service:
    build: ./python-nlp-service
    ports:
      - "8002:8002"
    environment:
      - NLP_MODEL_PATH=/app/models
      - MAX_TEXT_LENGTH=10000
    volumes:
      - ./nlp-models:/app/models
      - ./nlp-training-data:/app/training_data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Scaling
- **Horizontal scaling**: Run multiple service instances behind load balancer
- **Model optimization**: Use quantized models for faster inference
- **Caching**: Redis for frequent text analysis results
- **Async processing**: Queue long-running tasks

## Monitoring

### Health Metrics
- Service uptime and response times
- Model loading status
- Memory and CPU usage
- Error rates by endpoint

### Logging
```python
# Structured logging example
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "nlp-service",
  "endpoint": "/analyze/sentiment",
  "processing_time": 0.023,
  "text_length": 156,
  "language": "en",
  "confidence": 0.95
}
```

## Troubleshooting

### Common Issues

1. **Model download failures**:
```bash
# Manually download models
python -m spacy download en_core_web_sm
```

2. **Memory issues with large models**:
```bash
# Use smaller model variants
export TRANSFORMERS_CACHE=/tmp/transformers
```

3. **NLTK data not found**:
```bash
# Download required NLTK data
python -c "import nltk; nltk.download('all')"
```

4. **Slow inference times**:
- Enable model caching
- Use GPU acceleration if available
- Consider model quantization

### Performance Tuning
- Adjust batch sizes for optimal throughput
- Use appropriate worker counts for your hardware
- Enable model compilation for repeated inference
- Consider using ONNX models for faster inference

## License

Part of the SmartDockAI platform. See main project for licensing information.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

For issues and feature requests, please use the main SmartDockAI repository.