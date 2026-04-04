"""Claim CRUD routes."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models.schemas import ClaimCreate, ClaimListResponse, ClaimResponse
from services import firebase_service as fb

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=ClaimResponse)
async def create_claim(body: ClaimCreate, member_id: str = Query(...)):
    member = fb.get_member_by_id(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    payload = {
        "treatment_date": str(body.treatment_date),
        "claim_amount": body.claim_amount,
        "hospital_name": body.hospital_name,
        "is_network": body.is_network,
        "claim_type": body.claim_type,
        "pre_auth_obtained": body.pre_auth_obtained,
        "notes": body.notes,
    }
    claim = fb.create_claim(member_id, payload)
    fb.log_audit(claim["id"], "claim_submitted", member_id, {"claim_number": claim["claim_number"]})
    return _build_response(claim)


@router.get("", response_model=ClaimListResponse)
async def list_claims(
    member_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    admin: bool = Query(False),
):
    claims = fb.list_claims(member_id=None if admin else member_id, status=status)
    # Attach adjudication result if available
    enriched = []
    for claim in claims:
        result = fb.get_adjudication_result(claim["id"])
        claim["adjudication_result"] = result
        enriched.append(_build_response(claim))
    return ClaimListResponse(claims=enriched, total=len(enriched))


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(claim_id: str):
    claim = fb.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    result = fb.get_adjudication_result(claim_id)
    claim["adjudication_result"] = result
    return _build_response(claim)


def _build_response(claim: dict) -> ClaimResponse:
    return ClaimResponse(
        id=claim["id"],
        claim_number=claim.get("claim_number", ""),
        member_id=claim.get("member_id", ""),
        treatment_date=str(claim.get("treatment_date", "")),
        claim_amount=claim.get("claim_amount", 0),
        hospital_name=claim.get("hospital_name", ""),
        is_network=claim.get("is_network", False),
        claim_type=claim.get("claim_type", ""),
        status=claim.get("status", "PENDING"),
        pre_auth_obtained=claim.get("pre_auth_obtained", False),
        submitted_at=str(claim.get("submitted_at", "")),
        processed_at=str(claim.get("processed_at")) if claim.get("processed_at") else None,
        adjudication_result=claim.get("adjudication_result"),
    )
