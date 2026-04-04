"""POST /documents/upload — upload file, extract with Gemini, store in Firestore."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from services import firebase_service as fb
from services.gemini_service import extract_document
from services.rag.retriever import retrieve
from services.rag.namespaces import POLICY

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/heic",
    "application/pdf",
}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    claim_id: str = Form(...),
    doc_type: str = Form(...),
    member_id: str = Form(...),
):
    # Validate file type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: JPEG, PNG, WEBP, HEIC, PDF"
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 20MB limit")

    # Upload to Firebase Storage
    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
    storage_path = f"{member_id}/{claim_id}/{uuid.uuid4()}.{file_ext}"

    try:
        download_url = fb.upload_file(file_bytes, storage_path, file.content_type)
    except Exception as e:
        logger.error(f"Firebase Storage upload failed: {e}")
        raise HTTPException(status_code=500, detail="File upload failed")

    # Save document record
    document_id = fb.save_document(
        claim_id=claim_id,
        doc_type=doc_type,
        storage_path=storage_path,
        download_url=download_url,
        file_name=file.filename or "document",
        mime_type=file.content_type,
    )

    # RAG: get relevant policy context for this doc type before extracting
    try:
        policy_chunks = retrieve(
            f"{doc_type} required fields {claim_id}",
            POLICY,
            top_k=3,
        )
        policy_context = "\n".join(policy_chunks)
    except Exception:
        policy_context = ""

    # Extract with Gemini
    try:
        extracted = await extract_document(
            file_bytes=file_bytes,
            mime_type=file.content_type,
            doc_type=doc_type,
            policy_context=policy_context,
        )
    except Exception as e:
        logger.error(f"Gemini extraction failed: {e}")
        extracted = {
            "legibility_score": 0.0,
            "extraction_confidence": 0.0,
            "extraction_warnings": ["Extraction service unavailable"],
        }

    # Store extracted data
    fb.save_extracted_data(document_id, claim_id, extracted)

    # Build extraction preview for the frontend
    preview = {
        "doctor_name": extracted.get("doctor_name"),
        "doctor_reg_number": extracted.get("doctor_reg_number"),
        "patient_name": extracted.get("patient_name"),
        "diagnosis": extracted.get("diagnosis", []),
        "total_amount": extracted.get("total_amount"),
        "bill_date": extracted.get("bill_date"),
        "legibility_score": extracted.get("legibility_score", 1.0),
        "extraction_confidence": extracted.get("extraction_confidence", 1.0),
        "extraction_warnings": extracted.get("extraction_warnings", []),
        "is_handwritten": extracted.get("is_handwritten", False),
    }

    return {
        "document_id": document_id,
        "download_url": download_url,
        "extraction_preview": preview,
    }
