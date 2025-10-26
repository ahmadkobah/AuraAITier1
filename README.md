# Document Intelligence Platform

Modular service scaffold for OCR, ICR, NLP understanding, and routing/auto-classification engines. Each service is an independent FastAPI app so you can plug in DeepSeek OCR, handwriting extraction, custom NLP models, or rules/ML-based document routing.

## Repository layout

```
document-intelligence-platform/
├── README.md
├── shared/
│   └── schemas.py              # Pydantic models shared by all services
├── services/
│   ├── icr_service/
│   │   ├── app/main.py         # FastAPI entrypoint with background job stub
│   │   └── requirements.txt
│   └── classification_service/
│       ├── app/main.py
│       └── requirements.txt
├── python-ocr-service/         # DeepSeek OCR FastAPI service
├── python-nlp-service/         # Full-featured NLP engine (FastAPI)
└── DeepSeek-OCR-main, python-document-intelligence-service, etc.
```

## Running locally

1. Create a Python 3.10+ virtualenv for each service (or use separate Docker images).
2. Run OCR (DeepSeek) service:
   ```bash
   cd python-ocr-service
   python -m venv .venv && .venv/Scripts/activate
   pip install -r requirements.txt
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
3. Run the ICR (handwriting) service:
   ```bash
   cd python-icr-service
   python -m venv .venv && .venv/Scripts/activate
   pip install -r requirements.txt
   uvicorn main:app --host 0.0.0.0 --port 8001
   ```
4. Run the NLP engine from `python-nlp-service` (see its README) so `/nlp/analyze` and `/jobs` are available on port `8002`.
5. Start any remaining stub services as needed (e.g. classification on `8104`) or wire them into their real implementations.
6. Call the `/ocr/process` and `/icr/process` endpoints for uploads, `/nlp/analyze` for text enrichment, and `/jobs` on each service to submit work; poll `/jobs/{id}` or add webhooks.

## Next steps
- Replace stub logic in ICR/classification with the actual handwriting models and routing rules, while keeping the DeepSeek OCR + NLP engines as the authoritative services.
- Add authentication (API keys/JWT) so only your backend can call these services.
- Introduce a message broker (Redis, RabbitMQ, SQS) for higher throughput.
- Write Dockerfiles/docker-compose to orchestrate all engines and expose them to the main Node backend.
