from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class FileReference(BaseModel):
    uri: str = Field(..., description="Location of the stored file (S3, blob, local path)")
    checksum: Optional[str] = Field(None, description="Optional integrity hash")


class DocumentPayload(BaseModel):
    content: str = Field(..., description="Full text content used by downstream intelligence services")
    filename: Optional[str] = Field(None, description="Original filename (if known)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata/context")


class OcrJobRequest(BaseModel):
    document_id: str
    company_id: str
    department_id: Optional[str]
    source_file: FileReference
    prompt: Optional[str] = Field(
        None,
        description="Custom OCR prompt, defaults to converting document into markdown",
    )


class OcrJobResult(BaseModel):
    document_id: str
    job_id: str
    status: str
    text: Optional[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float]
    processed_assets: List[FileReference] = Field(default_factory=list)


class IcrJobRequest(BaseModel):
    document_id: str
    source_file: FileReference
    fields_of_interest: List[str] = Field(default_factory=list)


class IcrJobResult(BaseModel):
    document_id: str
    job_id: str
    status: str
    signatures: List[Dict[str, Any]] = Field(default_factory=list)
    handwriting: List[Dict[str, Any]] = Field(default_factory=list)


class NlpClassificationRequest(BaseModel):
    document_id: str
    raw_text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NlpClassificationResult(BaseModel):
    document_id: str
    job_id: str
    suggested_title: Optional[str]
    suggested_tags: List[str] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: Optional[float]


class RoutingDecisionRequest(BaseModel):
    document_id: str
    company_id: str
    department_id: Optional[str]
    document: DocumentPayload
    tags: List[str] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    extracted_metadata: Dict[str, Any] = Field(default_factory=dict)


class RoutingDecisionResult(BaseModel):
    document_id: str
    target_folder_id: Optional[str]
    target_department_id: Optional[str]
    confidence: float
    rationale: Optional[str]
