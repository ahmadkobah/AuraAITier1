FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download models during build
# Note: These are downloaded during docker build, not at runtime
RUN mkdir -p /app/models && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L12-v2')" && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" && \
    python -c "from transformers import AutoProcessor, AutoModelForCausalLM; \
    processor = AutoProcessor.from_pretrained('microsoft/trocr-large-handwritten'); \
    model = AutoModelForCausalLM.from_pretrained('microsoft/trocr-large-handwritten')" && \
    python -c "from transformers import AutoProcessor, AutoModelForCausalLM; \
    processor = AutoProcessor.from_pretrained('microsoft/Florence-2-base', trust_remote_code=True); \
    model = AutoModelForCausalLM.from_pretrained('microsoft/Florence-2-base', trust_remote_code=True)"

# Copy application code
COPY app/ /app/app/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
