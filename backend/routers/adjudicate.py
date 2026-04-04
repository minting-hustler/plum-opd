"""POST /claims/{id}/adjudicate + PATCH /claims/{id}/override"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from models.schemas import AdjudicationResponse, OverrideRequest
from services import firebase_service as fb
from services.adjudication.orchestrator import run_adjudication
from services.adjudication.types import (
    AdjudicationInput,
    ClaimDoc,
    ExtractedDataDoc,
    MemberDoc,
)
from services.rag.indexer import upsert_claim_to_index

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/{claim_id}/adjudicate", response_model=AdjudicationResponse)
async def adjudicate_claim(claim_id: str):
    # Load claim
    claim_data = fb.get_claim(claim_id)
    if not claim_data:
        raise HTTPException(status_code=404, detail="Claim not found")

    if claim_data.get("status") not in ("PENDING", "PROCESSING"):
        raise HTTPException(
            status_code=400,
            detail=f"Claim status is '{claim_data['status']}' — cannot re-adjudicate"
        )

    # Mark as processing
    fb.update_claim_status(claim_id, "PROCESSING")

    # Load member
    member_data = fb.get_member_by_id(claim_data["member_id"])
    if not member_data:
        raise HTTPException(status_code=404, detail="Member not found")

    # Load extracted data
    raw_docs = fb.get_extracted_data_for_claim(claim_id)
    extracted_docs = []
    for raw in raw_docs:
        try:
            # Get doc_type from the parent document record
            parent = next(
                (d for d in fb.get_documents_for_claim(claim_id) if d["id"] == raw.get("document_id")),
                {}
            )
            raw["doc_type"] = parent.get("doc_type", "other")
            extracted_docs.append(ExtractedDataDoc(**raw))
        except Exception as e:
            logger.warning(f"Could not parse extracted_data doc: {e}")

    # YTD usage
    category_used_ytd = fb.get_category_used_ytd(member_data["id"])
    prior_claims_today = fb.count_claims_today(
        member_data["id"],
        str(claim_data.get("treatment_date", ""))
    )

    # Build input
    adj_input = AdjudicationInput(
        claim=ClaimDoc(**{k: v for k, v in claim_data.items() if k != "adjudication_result"}),
        member=MemberDoc(**member_data),
        extracted_data=extracted_docs,
        annual_used_ytd=member_data.get("annual_used", 0),
        category_used_ytd=category_used_ytd,
        prior_claims_today=prior_claims_today,
    )

    # Run adjudication
    try:
        output = await run_adjudication(adj_input)
    except Exception as e:
        logger.error(f"Adjudication failed for {claim_id}: {e}", exc_info=True)
        fb.update_claim_status(claim_id, "PENDING")
        raise HTTPException(status_code=500, detail=f"Adjudication error: {str(e)}")

    # Persist result
    result_dict = output.model_dump()
    result_dict["decided_by"] = "SYSTEM"
    fb.save_adjudication_result(claim_id, result_dict)
    fb.update_claim_status(claim_id, output.decision)

    # Increment annual_used for approved/partial claims
    if output.decision in ("APPROVED", "PARTIAL") and output.approved_amount > 0:
        fb.increment_annual_used(member_data["id"], output.approved_amount)

    # Add to RAG claims index
    try:
        diagnoses = []
        for doc in extracted_docs:
            diagnoses.extend(doc.diagnosis)
        upsert_claim_to_index(
            claim_id=claim_id,
            claim_type=claim_data.get("claim_type", ""),
            amount=claim_data.get("claim_amount", 0),
            diagnosis=", ".join(diagnoses[:3]),
            decision=output.decision,
            primary_reason=output.primary_reason,
        )
    except Exception as e:
        logger.warning(f"Failed to index claim {claim_id}: {e}")

    # Audit log
    fb.log_audit(claim_id, "adjudication_complete", "SYSTEM", {
        "decision": output.decision,
        "approved_amount": output.approved_amount,
        "confidence_score": output.confidence_score,
    })

    return AdjudicationResponse(
        claim_id=claim_id,
        **result_dict,
    )


@router.patch("/{claim_id}/override")
async def override_claim(claim_id: str, body: OverrideRequest):
    claim_data = fb.get_claim(claim_id)
    if not claim_data:
        raise HTTPException(status_code=404, detail="Claim not found")

    if claim_data.get("status") != "MANUAL_REVIEW":
        raise HTTPException(
            status_code=400,
            detail="Override only allowed for MANUAL_REVIEW claims"
        )

    # Update adjudication result
    existing = fb.get_adjudication_result(claim_id) or {}
    existing["decision"] = body.decision
    existing["approved_amount"] = body.approved_amount or existing.get("approved_amount", 0)
    existing["notes"] = body.notes
    existing["decided_by"] = body.actor_uid
    fb.save_adjudication_result(claim_id, existing)
    fb.update_claim_status(claim_id, body.decision)

    # Increment annual_used if approving
    if body.decision == "APPROVED" and body.approved_amount:
        member_data = fb.get_member_by_id(claim_data["member_id"])
        if member_data:
            fb.increment_annual_used(member_data["id"], body.approved_amount)

    fb.log_audit(claim_id, "manual_override", body.actor_uid, {
        "decision": body.decision,
        "notes": body.notes,
    })

    return {"status": "ok", "claim_id": claim_id, "new_decision": body.decision}
