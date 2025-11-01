"""Shared schemas and models for all services"""

from .schemas import (
    FileReference,
    DocumentPayload,
    OcrJobRequest,
    OcrJobResult,
    IcrJobRequest,
    IcrJobResult,
    NlpClassificationRequest,
    NlpClassificationResult,
    RoutingDecisionRequest,
    RoutingDecisionResult,
)

__all__ = [
    "FileReference",
    "DocumentPayload",
    "OcrJobRequest",
    "OcrJobResult",
    "IcrJobRequest",
    "IcrJobResult",
    "NlpClassificationRequest",
    "NlpClassificationResult",
    "RoutingDecisionRequest",
    "RoutingDecisionResult",
]
