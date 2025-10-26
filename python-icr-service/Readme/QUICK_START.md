# Quick Start Guide - Python ICR Service

## 🚀 Current Status

✅ **Service is RUNNING** on http://localhost:8001
✅ **All dependencies installed** (126 packages)
✅ **TrOCR model loaded** and ready

## 📋 Quick Commands

### Check Service Status
```bash
# Health check
curl http://localhost:8001/health

# Service info
curl http://localhost:8001/

# Model info
curl http://localhost:8001/model/info
```

### Start/Stop Service

```bash
# Start service (if not running)
cd C:\Users\Ahmad\Desktop\python-icr-service
python main.py

# Stop service
# Press Ctrl+C in the terminal where service is running
```

### Test Endpoints

```bash
# Test handwriting recognition (requires image file)
curl -X POST "http://localhost:8001/recognize" \
  -F "file=@your_handwriting.png" \
  -F "recognition_type=full_text"

# Preprocess image
curl -X POST "http://localhost:8001/preprocess" \
  -F "file=@your_image.png" \
  -F "task_type=line_recognition"

# Add training sample
curl -X POST "http://localhost:8001/training/add_sample" \
  -F "file=@sample.png" \
  -F "ground_truth=Your text here" \
  -F "category=handwriting"

# Get training stats
curl http://localhost:8001/training/stats
```

## 🌐 Interactive API Documentation

Open in your browser:
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

## 📦 Package Versions (Latest Installed)

| Package | Version |
|---------|---------|
| PyTorch | 2.9.0 |
| Transformers | 4.55.4 |
| FastAPI | 0.119.1 |
| NumPy | 2.2.6 |
| OpenCV | 4.12.0.88 |
| Pandas | 2.3.3 |

## 🔧 Development Tools

```bash
# Format code
black .

# Check code style
flake8 .

# Type checking
mypy .

# Run tests
pytest

# Jupyter notebook
jupyter notebook
```

## 📁 Project Structure

```
python-icr-service/
├── main.py                    # FastAPI application
├── app/
│   ├── models/               # TrOCR model implementation
│   ├── preprocessing/        # Image preprocessing
│   └── training/             # Training data management
├── requirements.txt          # Latest dependencies
├── requirements.minimal.txt  # Minimal setup
├── models/                   # Downloaded models
└── training_data/           # Training datasets
```

## 🎯 Common Use Cases

### 1. Recognize Handwritten Text
```python
import requests

with open('handwriting.png', 'rb') as f:
    response = requests.post(
        'http://localhost:8001/recognize',
        files={'file': f},
        params={'recognition_type': 'line_by_line'}
    )
    print(response.json())
```

### 2. Add Training Data
```python
import requests

with open('training_sample.png', 'rb') as f:
    response = requests.post(
        'http://localhost:8001/training/add_sample',
        files={'file': f},
        data={
            'ground_truth': 'The actual text',
            'category': 'forms'
        }
    )
    print(response.json())
```

### 3. Get Service Statistics
```python
import requests

# Health check
health = requests.get('http://localhost:8001/health').json()
print(f"Status: {health['status']}")

# Training stats
stats = requests.get('http://localhost:8001/training/stats').json()
print(f"Total samples: {stats['dataset_stats']['total_samples']}")
```

## ⚠️ Important Notes

1. **Service must be running** - Start with `python main.py`
2. **Port 8001** must be available
3. **Model downloads** - First run downloads TrOCR model (~1GB)
4. **Memory** - Requires 2-4GB RAM for model

## 🐛 Troubleshooting

### Service won't start
```bash
# Check if port is in use
netstat -an | findstr 8001

# Check Python version
python --version  # Should be 3.13.x

# Reinstall dependencies
pip install -r requirements.txt
```

### Model not loading
```bash
# Check model directory
ls models/

# Clear cache and retry
rm -rf ~/.cache/huggingface/
python main.py
```

### Low performance
- Use GPU if available (requires CUDA)
- Reduce image size before processing
- Process in batches for multiple images

## 📚 Additional Resources

- **Full Documentation**: `README.md`
- **Installation Details**: `INSTALLATION_SUMMARY.md`
- **Service Status**: `SERVICE_STATUS.md`
- **API Docs**: http://localhost:8001/docs

---

**Ready to process handwriting! 🎉**
