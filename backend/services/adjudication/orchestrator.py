"""Adjudication orchestrator: runs Steps 1-5, composes final decision."""
from __future__ import annotations

import logging
from typing import Any, Literal

from services.adjudication.step1_eligibility import check_eligibility
from services.adjudication.step2_documents import check_documents
from services.adjudication.step3_coverage import verify_coverage
from services.adjudication.step4_limits import validate_limits
from services.adjudication.step5_medical import review_medical_necessity
from services.adjudication.types import AdjudicationInput, AdjudicationOutput
from services.gemini_service import generate_reasoning
from services.rag.retriever import retrieve
from services.rag.namespaces import CLAIMS, POLICY

logger = logging.getLogger(__name__)

# Confidence weights per step
CONFIDENCE_WEIGHTS = {
    "step1": 0.15,
    "step2": 0.20,
    "step3": 0.20,
    "step4": 0.25,
    "step5": 0.20,
}

MANUAL_REVIEW_CONFIDENCE_THRESHOLD = 0.70


async def run_adjudication(inp: AdjudicationInput) -> AdjudicationOutput:
    step_results: dict[str, Any] = {}
    all_chunks: list[str] = []
    all_rejection_reasons: list[str] = []
    fraud_flags: list[str] = []

    # ── Step 1: Eligibility (hard gate) ───────────────────────────────────────
    s1 = check_eligibility(inp)
    step_results["step1"] = s1.model_dump()
    all_chunks.extend(s1.data.get("policy_context", []))

    if not s1.passed:
        all_rejection_reasons.extend(s1.reasons)
        reasoning = await _get_reasoning(inp, step_results, "REJECTED", 0.0, all_chunks)
        return AdjudicationOutput(
            decision="REJECTED",
            approved_amount=0,
            copay_amount=0,
            network_discount=0,
            confidence_score=0.0,
            rejection_reasons=all_rejection_reasons,
            fraud_flags=[],
            step_results=step_results,
            notes=reasoning.get("notes", ""),
            primary_reason=reasoning.get("primary_reason", s1.reasons[0] if s1.reasons else ""),
            next_steps=reasoning.get("next_steps", ""),
            retrieved_chunks_used=all_chunks,
        )

    # ── Step 2: Documents (hard gate) ────────────────────────────────────────
    s2 = check_documents(inp)
    step_results["step2"] = s2.model_dump()
    all_chunks.extend(s2.data.get("chunk_refs", []))

    if not s2.passed:
        all_rejection_reasons.extend(s2.reasons)
        confidence = _weighted_confidence({"step1": s1, "step2": s2})
        reasoning = await _get_reasoning(inp, step_results, "REJECTED", confidence, all_chunks)
        return AdjudicationOutput(
            decision="REJECTED",
            approved_amount=0,
            copay_amount=0,
            network_discount=0,
            confidence_score=confidence,
            rejection_reasons=all_rejection_reasons,
            fraud_flags=[],
            step_results=step_results,
            notes=reasoning.get("notes", ""),
            primary_reason=reasoning.get("primary_reason", s2.reasons[0] if s2.reasons else ""),
            next_steps=reasoning.get("next_steps", ""),
            retrieved_chunks_used=all_chunks,
        )

    # ── Step 3: Coverage ──────────────────────────────────────────────────────
    s3 = await verify_coverage(inp)
    step_results["step3"] = s3.model_dump()
    all_chunks.extend(s3.data.get("chunk_refs", []))

    if s3.reasons:
        all_rejection_reasons.extend(s3.reasons)

    is_partial_coverage = s3.data.get("is_partial", False)

    # Hard reject only if completely uncovered AND no partial
    if not s3.passed and not is_partial_coverage:
        confidence = _weighted_confidence({"step1": s1, "step2": s2, "step3": s3})
        reasoning = await _get_reasoning(inp, step_results, "REJECTED", confidence, all_chunks)
        return AdjudicationOutput(
            decision="REJECTED",
            approved_amount=0,
            copay_amount=0,
            network_discount=0,
            confidence_score=confidence,
            rejection_reasons=all_rejection_reasons,
            fraud_flags=[],
            step_results=step_results,
            notes=reasoning.get("notes", ""),
            primary_reason=reasoning.get("primary_reason", s3.reasons[0] if s3.reasons else ""),
            next_steps=reasoning.get("next_steps", ""),
            retrieved_chunks_used=all_chunks,
        )

    # ── Step 4: Limits ────────────────────────────────────────────────────────
    s4 = validate_limits(inp, s3.data)
    step_results["step4"] = s4.model_dump()

    if not s4.passed:
        all_rejection_reasons.extend(s4.reasons)
        confidence = _weighted_confidence({"step1": s1, "step2": s2, "step3": s3, "step4": s4})
        reasoning = await _get_reasoning(inp, step_results, "REJECTED", confidence, all_chunks)
        return AdjudicationOutput(
            decision="REJECTED",
            approved_amount=0,
            copay_amount=0,
            network_discount=0,
            confidence_score=confidence,
            rejection_reasons=all_rejection_reasons,
            fraud_flags=[],
            step_results=step_results,
            notes=reasoning.get("notes", ""),
            primary_reason=reasoning.get("primary_reason", s4.reasons[0] if s4.reasons else ""),
            next_steps=reasoning.get("next_steps", ""),
            retrieved_chunks_used=all_chunks,
        )

    approved_amount = s4.data.get("approved_amount", 0)
    copay_amount = s4.data.get("copay_amount", 0)
    network_discount = s4.data.get("network_discount", 0)
    is_partial_limits = s4.data.get("is_partial", False)

    # ── Step 5: Medical necessity + fraud ─────────────────────────────────────
    s5 = await review_medical_necessity(inp)
    step_results["step5"] = s5.model_dump()
    all_chunks.extend(s5.data.get("chunk_refs", []))
    fraud_flags = s5.data.get("fraud_flags", [])

    if s5.reasons:
        all_rejection_reasons.extend(s5.reasons)

    # ── Compose overall confidence ─────────────────────────────────────────────
    confidence = _weighted_confidence(
        {"step1": s1, "step2": s2, "step3": s3, "step4": s4, "step5": s5}
    )

    # ── Determine final decision ───────────────────────────────────────────────
    has_failures = bool(all_rejection_reasons)
    decision: Literal["APPROVED", "REJECTED", "PARTIAL", "MANUAL_REVIEW"]

    if fraud_flags or confidence < MANUAL_REVIEW_CONFIDENCE_THRESHOLD:
        decision = "MANUAL_REVIEW"
        approved_amount = 0  # hold payment pending review
    elif has_failures:
        decision = "REJECTED"
        approved_amount = 0
    elif is_partial_coverage or is_partial_limits:
        decision = "PARTIAL"
    else:
        decision = "APPROVED"

    # ── Final Gemini reasoning call ────────────────────────────────────────────
    # Retrieve final context
    try:
        final_policy_chunks = retrieve(
            f"{inp.claim.claim_type} {inp.claim.hospital_name} decision",
            POLICY,
            top_k=3,
        )
        final_claim_chunks = retrieve(
            f"{inp.claim.claim_type} {' '.join(s5.data.get('necessity_result', {}).get('reasoning', '').split()[:5])}",
            CLAIMS,
            top_k=3,
        )
        all_chunks.extend(final_policy_chunks + final_claim_chunks)
    except Exception as e:
        logger.warning(f"Final RAG failed: {e}")
        final_policy_chunks = []
        final_claim_chunks = []

    claim_summary = {
        "claim_type": inp.claim.claim_type,
        "claim_amount": inp.claim.claim_amount,
        "diagnosis": ", ".join(s5.data.get("necessity_result", {}).get("reasoning", "").split()[:10]),
        "hospital_name": inp.claim.hospital_name,
        "is_network": inp.claim.is_network,
    }

    reasoning = await generate_reasoning(
        claim_summary=claim_summary,
        step_results=step_results,
        decision=decision,
        confidence=confidence,
        policy_chunks=final_policy_chunks,
        similar_claims=final_claim_chunks,
    )

    logger.info(f"Adjudication complete: {decision} (confidence={confidence:.2f})")

    return AdjudicationOutput(
        decision=decision,
        approved_amount=max(0, approved_amount),
        copay_amount=copay_amount,
        network_discount=network_discount,
        confidence_score=round(confidence, 3),
        rejection_reasons=all_rejection_reasons,
        fraud_flags=fraud_flags,
        step_results=step_results,
        notes=reasoning.get("notes", ""),
        primary_reason=reasoning.get("primary_reason", ""),
        next_steps=reasoning.get("next_steps", ""),
        retrieved_chunks_used=list(set(all_chunks)),
    )


def _weighted_confidence(steps: dict) -> float:
    """Compute weighted average confidence from completed steps."""
    total_weight = 0.0
    weighted_sum = 0.0
    for step_name, result in steps.items():
        w = CONFIDENCE_WEIGHTS.get(step_name, 0.0)
        c = result.confidence if hasattr(result, "confidence") else 1.0
        weighted_sum += w * c
        total_weight += w
    if total_weight == 0:
        return 1.0
    # Scale to full weight if not all steps ran
    full_weight = sum(CONFIDENCE_WEIGHTS.values())
    return (weighted_sum / total_weight) * (total_weight / full_weight)


async def _get_reasoning(inp, step_results, decision, confidence, chunks):
    try:
        return await generate_reasoning(
            claim_summary={
                "claim_type": inp.claim.claim_type,
                "claim_amount": inp.claim.claim_amount,
                "diagnosis": "N/A",
                "hospital_name": inp.claim.hospital_name,
                "is_network": inp.claim.is_network,
            },
            step_results=step_results,
            decision=decision,
            confidence=confidence,
            policy_chunks=chunks[:3],
            similar_claims=[],
        )
    except Exception:
        from services.gemini_service import _default_reasoning
        return _default_reasoning(decision)
