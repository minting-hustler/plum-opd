from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ── Documents ────────────────────────────────────────────────────────────────

class UploadDocumentResponse(BaseModel):
    document_id: str
    download_url: str
    extraction_preview: dict[str, Any]


# ── Members ──────────────────────────────────────────────────────────────────

class MemberCreate(BaseModel):
    employee_id: str
    full_name: str
    date_of_birth: date
    gender: Literal["M", "F", "Other"]
    email: str
    join_date: date
    firebase_uid: str


class MemberResponse(BaseModel):
    id: str
    employee_id: str
    full_name: str
    date_of_birth: str
    gender: str
    email: str
    join_date: str
    annual_limit: int
    annual_used: int
    is_active: bool
    firebase_uid: str
    category_used_ytd: dict[str, int] = Field(default_factory=dict)


# ── Claims ───────────────────────────────────────────────────────────────────

class ClaimCreate(BaseModel):
    treatment_date: date
    claim_amount: int
    hospital_name: str
    is_network: bool = False
    claim_type: Literal["consultation", "diagnostic", "pharmacy", "dental", "vision", "alternative"]
    document_ids: list[str] = Field(default_factory=list)
    pre_auth_obtained: bool = False
    notes: Optional[str] = None


class ClaimResponse(BaseModel):
    id: str
    claim_number: str
    member_id: str
    treatment_date: str
    claim_amount: int
    hospital_name: str
    is_network: bool
    claim_type: str
    status: str
    pre_auth_obtained: bool
    submitted_at: str
    processed_at: Optional[str] = None
    adjudication_result: Optional[dict[str, Any]] = None


class ClaimListResponse(BaseModel):
    claims: list[ClaimResponse]
    total: int


# ── Adjudication ─────────────────────────────────────────────────────────────

class AdjudicationResponse(BaseModel):
    claim_id: str
    decision: Literal["APPROVED", "REJECTED", "PARTIAL", "MANUAL_REVIEW"]
    approved_amount: int
    copay_amount: int
    network_discount: int
    confidence_score: float
    rejection_reasons: list[str]
    fraud_flags: list[str]
    step_results: dict[str, Any]
    notes: str
    primary_reason: str
    next_steps: str
    retrieved_chunks_used: list[str]


# ── Admin override ────────────────────────────────────────────────────────────

class OverrideRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    approved_amount: Optional[int] = None
    notes: str
    actor_uid: str
