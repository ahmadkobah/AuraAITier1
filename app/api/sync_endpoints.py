"""
================================================================================
Sync Endpoints — Cross-System Integration (CP ↔ AI Service ↔ Aura)
================================================================================

PURPOSE:
--------
Provides endpoints that the Control Panel and Aura call to synchronize data
with the AI Service. These were previously missing, causing silent failures.

ENDPOINTS:
----------
    DELETE /api/v1/documents/{doc_id}              — Delete document + FAISS cleanup
    GET    /api/v1/search/config                   — Return search configs
    POST   /api/v1/search/config/bulk-update       — Upsert search configs
    GET    /api/v1/classifications                  — Return classification definitions
    POST   /api/v1/classifications/bulk-update      — Upsert classifications
    GET    /api/v1/prompts                          — Return prompt configs
    POST   /api/v1/prompts/bulk-update              — Upsert prompt configs

CALLERS:
--------
    - Aura BE  → DELETE /api/v1/documents/{id}  (DokumentController.js)
    - CP BE    → search/config endpoints         (searchRoutes.js)
    - CP BE    → classifications endpoints       (classificationRoutes.js)
    - CP BE    → prompts endpoints               (promptRoutes.js)

================================================================================
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("sync_endpoints")

# ========================
# FastAPI Router
# ========================

sync_router = APIRouter(tags=["sync"])


# ========================
# Pydantic Models
# ========================

class BulkClassificationRequest(BaseModel):
    classifications: List[Dict[str, Any]]

class BulkSearchConfigRequest(BaseModel):
    configs: List[Dict[str, Any]]

class BulkPromptRequest(BaseModel):
    prompts: List[Dict[str, Any]]

class BulkSyncResponse(BaseModel):
    success: bool = True
    synced: int
    message: str


# ========================
# Helper — get db reference
# ========================

def _get_db():
    """Get the shared MongoDB database reference from the main app."""
    from app.api.endpoints import db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    return db


# ========================
# 1. DELETE /api/v1/documents/{doc_id}
# ========================

@sync_router.delete("/api/v1/documents/{doc_id}")
async def delete_document(doc_id: str):
    """
    Delete a document from AI Service MongoDB and invalidate FAISS index.
    Called by Aura BE when a user deletes a document.
    """
    from app.api.endpoints import safe_doc_id
    from app.utils.vector_index import invalidate as invalidate_faiss

    database = _get_db()
    documents = database["documents"]

    # Try both ObjectId and raw string to cover all stored formats
    oid = safe_doc_id(doc_id)
    result = documents.delete_one({"_id": oid})
    if result.deleted_count == 0 and oid != doc_id:
        result = documents.delete_one({"_id": doc_id})

    # Invalidate FAISS so deleted embeddings are dropped on next rebuild
    invalidate_faiss()

    if result.deleted_count > 0:
        logger.info(f"Deleted document {doc_id} from AI MongoDB")
        return {"success": True, "deleted": True, "doc_id": doc_id}

    # Return 200 even if not found — caller doesn't care (fire-and-forget)
    logger.info(f"Document {doc_id} not found in AI MongoDB (already deleted or never existed)")
    return {"success": True, "deleted": False, "doc_id": doc_id}


# ========================
# 2. GET /api/v1/search/config
# ========================

@sync_router.get("/api/v1/search/config")
async def get_search_configs():
    """
    Return all search configurations stored in AI Service.
    Called by CP BE (searchRoutes.js) for bidirectional sync conflict resolution.
    Response shape: { configs: [...] }
    """
    database = _get_db()
    collection = database["search_configs"]

    configs = []
    for doc in collection.find():
        doc["id"] = str(doc.pop("_id"))
        configs.append(doc)

    return {"configs": configs}


# ========================
# 3. POST /api/v1/search/config/bulk-update
# ========================

@sync_router.post("/api/v1/search/config/bulk-update", response_model=BulkSyncResponse)
async def bulk_update_search_configs(body: BulkSearchConfigRequest):
    """
    Upsert search configurations pushed from Control Panel.
    Called by CP BE (searchRoutes.js) after Save button.
    """
    database = _get_db()
    collection = database["search_configs"]

    synced = 0
    for cfg in body.configs:
        # Use CP's _id or id as the match key; fall back to name
        cfg_id = cfg.pop("id", None) or cfg.pop("_id", None)
        cfg["lastModified"] = cfg.get("lastModified", datetime.utcnow().isoformat())
        cfg["syncedAt"] = datetime.utcnow().isoformat()

        if cfg_id:
            collection.update_one(
                {"_id": cfg_id},
                {"$set": cfg},
                upsert=True,
            )
        elif cfg.get("name"):
            collection.update_one(
                {"name": cfg["name"]},
                {"$set": cfg},
                upsert=True,
            )
        else:
            collection.insert_one(cfg)
        synced += 1

    logger.info(f"Synced {synced} search configs from Control Panel")
    return BulkSyncResponse(synced=synced, message=f"Synced {synced} search configs")


# ========================
# 4. GET /api/v1/classifications
# ========================

@sync_router.get("/api/v1/classifications")
async def get_classifications():
    """
    Return classification definitions.
    First checks MongoDB for CP-synced classifications.
    Falls back to hardcoded LABEL_DESCRIPTIONS from classifier.py.
    Response shape: { classifications: [...] }
    """
    database = _get_db()
    collection = database["classifications"]

    # If CP has previously synced classifications, return those
    classifications = []
    for doc in collection.find():
        doc["id"] = str(doc.pop("_id"))
        classifications.append(doc)

    if classifications:
        return {"classifications": classifications}

    # Fallback: generate from hardcoded label definitions (same as classifier.py)
    _FALLBACK_LABELS = {
        'Invoice': 'Invoice: a billing document with line items, subtotals, tax, total amount, invoice number, and payment terms',
        'Receipt': 'Receipt: a proof-of-payment document from a merchant with date, items purchased, and total paid',
        'Purchase Order': 'Purchase Order: a buyer request document listing products, quantities, prices, and delivery terms',
        'Credit Note': 'Credit Note: a document reducing the amount owed by a buyer, referencing an original invoice',
        'Debit Note': 'Debit Note: a document increasing the amount owed, typically for additional charges',
        'Payment Voucher': 'Payment Voucher: an authorization document for a payment with payee, amount, and account codes',
        'Bank Statement': 'Bank Statement: a financial summary from a bank showing transactions, deposits, withdrawals, and balance',
        'Financial Statement': 'Financial Statement: a formal report of financial activities such as income statement, balance sheet, or cash flow',
        'Tax Document': 'Tax Document: a government or accounting form related to tax filing, deductions, or tax certificates',
        'Contract': 'Contract: a legally binding agreement between parties with terms, obligations, signatures, and effective dates',
        'Agreement': 'Agreement: a mutual arrangement between parties outlining shared terms and conditions',
        'Non-Disclosure Agreement': 'Non-Disclosure Agreement: a confidentiality contract restricting sharing of proprietary information',
        'Memorandum of Understanding': 'Memorandum of Understanding: a formal but non-binding document outlining mutual intentions between parties',
        'Certificate': 'Certificate: an official document attesting to a fact, qualification, or status',
        'License': 'License: an official permit granting authorization to perform an activity or use property',
        'Permit': 'Permit: a government-issued document authorizing a specific activity or construction',
        'Report': 'Report: a structured document presenting findings, analysis, data, or recommendations',
        'Business Letter': 'Business Letter: formal correspondence between organizations or individuals on business matters',
        'Memo': 'Memo: an internal communication document within an organization',
        'Proposal': 'Proposal: a document suggesting a plan, project, or business offer for consideration',
        'Quotation': 'Quotation: a document listing prices for requested goods or services',
        'Tender Document': 'Tender Document: a formal bid submission in response to a procurement request',
        'Form': 'Form: a structured document with fields to be filled in, such as an application or registration form',
        'Delivery Note': 'Delivery Note: a document accompanying goods being delivered, listing items and quantities',
        'Packing Slip': 'Packing Slip: a document inside a shipment listing the contents of the package',
        'Bill of Lading': 'Bill of Lading: a shipping document issued by a carrier detailing cargo, origin, and destination',
        'Shipping Document': 'Shipping Document: paperwork related to the transport and delivery of goods',
        'Resume': 'Resume: a personal document summarizing work experience, education, and skills for job applications',
        'Job Application': 'Job Application: a formal request for employment including personal and professional details',
        'Employment Contract': 'Employment Contract: a legal agreement specifying terms of employment between employer and employee',
        'Other': 'Other: a document that does not clearly fit any specific category',
    }

    for label, description in _FALLBACK_LABELS.items():
        classifications.append({
            "id": label.lower().replace(" ", "_"),
            "label": label,
            "description": description,
            "isActive": True,
            "source": "hardcoded",
        })

    return {"classifications": classifications}


# ========================
# 5. POST /api/v1/classifications/bulk-update
# ========================

@sync_router.post("/api/v1/classifications/bulk-update", response_model=BulkSyncResponse)
async def bulk_update_classifications(body: BulkClassificationRequest):
    """
    Upsert classification definitions pushed from Control Panel.
    Called by CP BE (classificationRoutes.js) after Save button.
    """
    database = _get_db()
    collection = database["classifications"]

    synced = 0
    for cls in body.classifications:
        cls_id = cls.pop("id", None) or cls.pop("_id", None)
        cls["lastModified"] = cls.get("lastModified", datetime.utcnow().isoformat())
        cls["syncedAt"] = datetime.utcnow().isoformat()

        if cls_id:
            collection.update_one(
                {"_id": cls_id},
                {"$set": cls},
                upsert=True,
            )
        elif cls.get("label"):
            collection.update_one(
                {"label": cls["label"]},
                {"$set": cls},
                upsert=True,
            )
        else:
            collection.insert_one(cls)
        synced += 1

    logger.info(f"Synced {synced} classifications from Control Panel")
    return BulkSyncResponse(synced=synced, message=f"Synced {synced} classifications")


# ========================
# 6. GET /api/v1/prompts
# ========================

@sync_router.get("/api/v1/prompts")
async def get_prompts():
    """
    Return prompt configurations stored in AI Service.
    Called by CP BE (promptRoutes.js) for bidirectional sync conflict resolution.
    Response shape: { prompts: [...] }
    """
    database = _get_db()
    collection = database["prompts"]

    prompts = []
    for doc in collection.find():
        doc["id"] = str(doc.pop("_id"))
        prompts.append(doc)

    return {"prompts": prompts}


# ========================
# 7. POST /api/v1/prompts/bulk-update
# ========================

@sync_router.post("/api/v1/prompts/bulk-update", response_model=BulkSyncResponse)
async def bulk_update_prompts(body: BulkPromptRequest):
    """
    Upsert prompt configurations pushed from Control Panel.
    Called by CP BE (promptRoutes.js) after Save button.
    """
    database = _get_db()
    collection = database["prompts"]

    synced = 0
    for prompt in body.prompts:
        prompt_id = prompt.pop("id", None) or prompt.pop("_id", None)
        prompt["lastModified"] = prompt.get("lastModified", datetime.utcnow().isoformat())
        prompt["syncedAt"] = datetime.utcnow().isoformat()

        if prompt_id:
            collection.update_one(
                {"_id": prompt_id},
                {"$set": prompt},
                upsert=True,
            )
        elif prompt.get("name"):
            collection.update_one(
                {"name": prompt["name"]},
                {"$set": prompt},
                upsert=True,
            )
        else:
            collection.insert_one(prompt)
        synced += 1

    logger.info(f"Synced {synced} prompts from Control Panel")
    return BulkSyncResponse(synced=synced, message=f"Synced {synced} prompts")
