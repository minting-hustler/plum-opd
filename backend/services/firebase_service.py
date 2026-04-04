"""Firebase Admin SDK initialisation + helpers for Firestore and Storage."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import firebase_admin
from firebase_admin import credentials, firestore, storage

# ── Initialise ────────────────────────────────────────────────────────────────

_app: Optional[firebase_admin.App] = None


def _get_app() -> firebase_admin.App:
    global _app
    if _app is not None:
        return _app

    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if not raw:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT env var is not set")

    sa_dict = json.loads(raw)
    cred = credentials.Certificate(sa_dict)
    project_id = sa_dict.get("project_id", "")
    bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET", f"{project_id}.appspot.com")

    _app = firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})
    return _app


def get_db() -> firestore.Client:
    _get_app()
    return firestore.client()


def get_bucket():
    _get_app()
    return storage.bucket()


# ── Helpers ───────────────────────────────────────────────────────────────────

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(doc_data: dict) -> dict:
    """Convert firestore DatetimeWithNanoseconds to ISO string for JSON."""
    result = {}
    for k, v in doc_data.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        elif isinstance(v, dict):
            result[k] = _serialize(v)
        else:
            result[k] = v
    return result


# ── Member helpers ─────────────────────────────────────────────────────────────

def get_member_by_uid(firebase_uid: str) -> Optional[dict]:
    db = get_db()
    docs = db.collection("members").where("firebase_uid", "==", firebase_uid).limit(1).stream()
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        return _serialize(data)
    return None


def get_member_by_id(member_id: str) -> Optional[dict]:
    db = get_db()
    doc = db.collection("members").document(member_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return _serialize(data)


def create_member(data: dict) -> dict:
    db = get_db()
    member_id = str(uuid.uuid4())
    payload = {
        **data,
        "annual_limit": 50000,
        "annual_used": 0,
        "is_active": True,
        "created_at": now_utc(),
    }
    db.collection("members").document(member_id).set(payload)
    payload["id"] = member_id
    return _serialize(payload)


def get_category_used_ytd(member_id: str) -> dict[str, int]:
    """Sum approved claim amounts by category for the current calendar year."""
    db = get_db()
    year_start = datetime(datetime.now().year, 1, 1, tzinfo=timezone.utc)
    results: dict[str, int] = {}
    docs = (
        db.collection("claims")
        .where("member_id", "==", member_id)
        .where("status", "in", ["APPROVED", "PARTIAL"])
        .stream()
    )
    for doc in docs:
        d = doc.to_dict()
        submitted = d.get("submitted_at")
        if submitted and hasattr(submitted, "replace"):
            if submitted.replace(tzinfo=timezone.utc) < year_start:
                continue
        ct = d.get("claim_type", "other")
        # fetch the approved_amount from adjudication_results
        res = db.collection("adjudication_results").document(doc.id).get()
        if res.exists:
            amt = res.to_dict().get("approved_amount", 0)
            results[ct] = results.get(ct, 0) + amt
    return results


# ── Claim helpers ──────────────────────────────────────────────────────────────

def _next_claim_number() -> str:
    db = get_db()
    count_ref = db.collection("_counters").document("claims")
    count_doc = count_ref.get()
    n = (count_doc.to_dict() or {}).get("count", 0) + 1
    count_ref.set({"count": n})
    return f"CLM-{datetime.now().year}-{n:05d}"


def create_claim(member_id: str, data: dict) -> dict:
    db = get_db()
    claim_id = str(uuid.uuid4())
    payload = {
        **data,
        "member_id": member_id,
        "claim_number": _next_claim_number(),
        "status": "PENDING",
        "submitted_at": now_utc(),
        "processed_at": None,
    }
    db.collection("claims").document(claim_id).set(payload)
    payload["id"] = claim_id
    return _serialize(payload)


def get_claim(claim_id: str) -> Optional[dict]:
    db = get_db()
    doc = db.collection("claims").document(claim_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return _serialize(data)


def list_claims(member_id: Optional[str] = None, status: Optional[str] = None) -> list[dict]:
    db = get_db()
    q = db.collection("claims")
    if member_id:
        q = q.where("member_id", "==", member_id)
    if status:
        q = q.where("status", "==", status)
    results = []
    for doc in q.order_by("submitted_at", direction=firestore.Query.DESCENDING).stream():
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(_serialize(data))
    return results


def update_claim_status(claim_id: str, status: str) -> None:
    db = get_db()
    db.collection("claims").document(claim_id).update(
        {"status": status, "processed_at": now_utc()}
    )


# ── Document helpers ───────────────────────────────────────────────────────────

def save_document(claim_id: str, doc_type: str, storage_path: str,
                  download_url: str, file_name: str, mime_type: str) -> str:
    db = get_db()
    doc_id = str(uuid.uuid4())
    db.collection("documents").document(doc_id).set({
        "claim_id": claim_id,
        "doc_type": doc_type,
        "storage_path": storage_path,
        "download_url": download_url,
        "file_name": file_name,
        "mime_type": mime_type,
        "uploaded_at": now_utc(),
    })
    return doc_id


def get_documents_for_claim(claim_id: str) -> list[dict]:
    db = get_db()
    docs = db.collection("documents").where("claim_id", "==", claim_id).stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(_serialize(data))
    return results


# ── Extracted data helpers ────────────────────────────────────────────────────

def save_extracted_data(document_id: str, claim_id: str, extracted: dict) -> str:
    db = get_db()
    doc_id = str(uuid.uuid4())
    db.collection("extracted_data").document(doc_id).set({
        "document_id": document_id,
        "claim_id": claim_id,
        **extracted,
        "extracted_at": now_utc(),
    })
    return doc_id


def get_extracted_data_for_claim(claim_id: str) -> list[dict]:
    db = get_db()
    docs = db.collection("extracted_data").where("claim_id", "==", claim_id).stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(_serialize(data))
    return results


# ── Adjudication result helpers ───────────────────────────────────────────────

def save_adjudication_result(claim_id: str, result: dict) -> None:
    db = get_db()
    db.collection("adjudication_results").document(claim_id).set({
        **result,
        "decided_at": now_utc(),
    })


def get_adjudication_result(claim_id: str) -> Optional[dict]:
    db = get_db()
    doc = db.collection("adjudication_results").document(claim_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["claim_id"] = claim_id
    return _serialize(data)


def increment_annual_used(member_id: str, amount: int) -> None:
    """Atomically increment annual_used on the member document."""
    db = get_db()
    ref = db.collection("members").document(member_id)
    ref.update({"annual_used": firestore.Increment(amount)})


# ── Audit log ─────────────────────────────────────────────────────────────────

def log_audit(claim_id: str, event_type: str, actor: str, payload: dict) -> None:
    db = get_db()
    db.collection("audit_log").add({
        "claim_id": claim_id,
        "event_type": event_type,
        "actor": actor,
        "payload": payload,
        "created_at": now_utc(),
    })


# ── Storage upload ─────────────────────────────────────────────────────────────

def upload_file(file_bytes: bytes, destination_path: str, content_type: str) -> str:
    """Upload bytes to Firebase Storage and return public download URL."""
    bucket = get_bucket()
    blob = bucket.blob(destination_path)
    blob.upload_from_string(file_bytes, content_type=content_type)
    blob.make_public()
    return blob.public_url


# ── Prior claims today (fraud check) ──────────────────────────────────────────

def count_claims_today(member_id: str, treatment_date: str) -> int:
    db = get_db()
    docs = (
        db.collection("claims")
        .where("member_id", "==", member_id)
        .where("treatment_date", "==", treatment_date)
        .stream()
    )
    return sum(1 for _ in docs)
