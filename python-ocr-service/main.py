
import asyncio
import hashlib
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4
import httpx
from PIL import Image
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import AutoModel, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

try:
    from shared.schemas import FileReference, OcrJobRequest, OcrJobResult
except ImportError:  # pragma: no cover - fallback definition
    class FileReference(BaseModel):  # type: ignore
        uri: str
        checksum: Optional[str] = None

    class OcrJobRequest(BaseModel):  # type: ignore
        document_id: str
        company_id: str
        department_id: Optional[str]
        source_file: FileReference
        prompt: Optional[str] = None

    class OcrJobResult(BaseModel):  # type: ignore
        document_id: str
        job_id: str
        status: str
        text: Optional[str]
        metadata: Dict[str, Any] = {}
        confidence: Optional[float]
        processed_assets: List[FileReference] = []

DEFAULT_PROMPT = os.getenv(
    "OCR_DEFAULT_PROMPT",
    "<image>\n<|grounding|>Convert the document to markdown.",
)
MODEL_NAME = os.getenv("OCR_MODEL_NAME", "microsoft/trocr-base-printed")
OUTPUT_DIR = Path(os.getenv("OCR_OUTPUT_DIR", "./ocr_outputs"))
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
DTYPE = torch.bfloat16 if DEVICE.type == "cuda" else torch.float32

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class TrOCREngine:
    def __init__(self):
        self.pipeline = None
        self.lock = asyncio.Lock()

    async def ensure_loaded(self):
        if self.pipeline is not None:
            return
        async with self.lock:
            if self.pipeline is not None:
                return
            await asyncio.get_running_loop().run_in_executor(None, self._load_sync)

    def _load_sync(self):
        from transformers import pipeline
        self.pipeline = pipeline("image-to-text", model=MODEL_NAME, device=DEVICE)

    async def run_inference(
        self,
        image_path: Path,
        prompt: Optional[str] = None,
        base_size: int = 1024,
        image_size: int = 640,
        crop_mode: bool = True,
        test_compress: bool = True,
        save_results: bool = True,
    ) -> Dict[str, Any]:
        await self.ensure_loaded()
        prompt_text = prompt or DEFAULT_PROMPT
        job_output_dir = OUTPUT_DIR / uuid4().hex
        job_output_dir.mkdir(parents=True, exist_ok=True)

        def _infer():
            start = time.time()
            # Use the transformers pipeline for OCR
            image = Image.open(image_path).convert('RGB')
            result = self.pipeline(image)
            generated_text = result[0]['generated_text'] if result else ""
            duration = time.time() - start
            return generated_text, duration

        loop = asyncio.get_running_loop()
        text, duration = await loop.run_in_executor(None, _infer)

        artifacts = [p for p in job_output_dir.glob("**/*") if p.is_file()]
        return {
            "text": text if isinstance(text, str) else str(text),
            "duration": duration,
            "artifacts": artifacts,
            "prompt": prompt_text,
            "output_dir": job_output_dir,
        }


def compute_checksum(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def save_upload_to_temp(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "upload").suffix
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as tmp_file:
        shutil.copyfileobj(upload.file, tmp_file)
    return Path(tmp_path)


def resolve_source_file(source: FileReference) -> Tuple[Path, Optional[Path]]:
    uri = source.uri
    if uri.startswith("http://") or uri.startswith("https://"):
        tmp_dir = Path(tempfile.mkdtemp())
        target = tmp_dir / Path(uri).name
        with httpx.stream("GET", uri, timeout=60.0) as r:
            r.raise_for_status()
            with target.open("wb") as fh:
                for chunk in r.iter_bytes():
                    fh.write(chunk)
        return target, tmp_dir
    path = Path(uri)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {uri}")
    return path, None


engine = TrOCREngine()
app = FastAPI(title="TrOCR OCR Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: Dict[str, OcrJobResult] = {}


@app.post("/ocr/process")
async def ocr_process(file: UploadFile = File(...), prompt: Optional[str] = None):
    if file.content_type and not file.content_type.startswith(("image/", "application/pdf")):
        raise HTTPException(status_code=400, detail="File must be an image or PDF")
    tmp_path = save_upload_to_temp(file)
    try:
        result = await engine.run_inference(tmp_path, prompt=prompt)
        metadata = {
            "prompt": result["prompt"],
            "output_dir": str(result["output_dir"]),
            "artifacts": [str(a) for a in result["artifacts"]],
        }
        return {
            "text": result["text"],
            "confidence": 0.92,
            "metadata": metadata,
            "processing_time": result["duration"],
        }
    finally:
        tmp_path.unlink(missing_ok=True)


async def _run_job(job_id: str, payload: OcrJobRequest):
    cleanup_dir: Optional[Path] = None
    try:
        source_path, cleanup_dir = resolve_source_file(payload.source_file)
        result = await engine.run_inference(source_path, prompt=payload.prompt)
        processed_assets = [payload.source_file]
        for artifact in result["artifacts"]:
            processed_assets.append(
                FileReference(uri=str(artifact), checksum=compute_checksum(artifact))
            )
        jobs[job_id] = OcrJobResult(
            document_id=payload.document_id,
            job_id=job_id,
            status="completed",
            text=result["text"],
            metadata={
                "prompt": result["prompt"],
                "output_dir": str(result["output_dir"]),
            },
            confidence=0.92,
            processed_assets=processed_assets,
        )
    except Exception as exc:
        jobs[job_id] = OcrJobResult(
            document_id=payload.document_id,
            job_id=job_id,
            status="failed",
            text=None,
            metadata={"error": str(exc)},
            confidence=None,
            processed_assets=[payload.source_file],
        )
    finally:
        if cleanup_dir and cleanup_dir.exists():
            shutil.rmtree(cleanup_dir, ignore_errors=True)


@app.post("/jobs", response_model=OcrJobResult)
async def create_job(req: OcrJobRequest):
    job_id = f"ocr_{req.document_id}_{uuid4().hex[:6]}"
    jobs[job_id] = OcrJobResult(
        document_id=req.document_id,
        job_id=job_id,
        status="queued",
        text=None,
        metadata={},
        confidence=None,
        processed_assets=[],
    )
    asyncio.create_task(_run_job(job_id, req))
    return jobs[job_id]


@app.get("/jobs/{job_id}", response_model=OcrJobResult)
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "device": DEVICE.type,
        "using_gpu": DEVICE.type == "cuda",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
