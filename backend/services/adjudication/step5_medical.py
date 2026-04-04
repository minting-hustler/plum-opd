"""Step 5: Medical necessity review + fraud detection."""
from __future__ import annotations

import logging
import statistics

from services.adjudication.types import AdjudicationInput, StepResult
from services.gemini_service import check_medical_necessity
from services.rag.retriever import retrieve, retrieve_with_metadata
from services.rag.namespaces import CLAIMS, MEDICAL

logger = logging.getLogger(__name__)

# Amount thresholds per claim_type (above which we flag for review)
AMOUNT_THRESHOLDS: dict[str, int] = {
    "consultation": 3000,
    "diagnostic": 12000,
    "pharmacy": 10000,
    "dental": 8000,
    "vision": 4000,
    "alternative": 7000,
}


def _get_all_diagnoses(inp: AdjudicationInput) -> list[str]:
    result = []
    for doc in inp.extracted_data:
        result.extend(doc.diagnosis)
    return result


def _get_all_medicines(inp: AdjudicationInput) -> list[dict]:
    result = []
    for doc in inp.extracted_data:
        result.extend(doc.medicines_prescribed)
    return result


def _get_all_tests(inp: AdjudicationInput) -> list[str]:
    result = []
    for doc in inp.extracted_data:
        result.extend(doc.tests_advised)
    return result


async def review_medical_necessity(inp: AdjudicationInput) -> StepResult:
    reasons: list[str] = []
    warnings: list[str] = []
    fraud_flags: list[str] = []
    data: dict = {}
    chunk_refs: list[str] = []

    diagnoses = _get_all_diagnoses(inp)
    medicines = _get_all_medicines(inp)
    tests = _get_all_tests(inp)

    # ── RAG: retrieve medical guidelines ──────────────────────────────────────
    diag_query = " ".join(diagnoses[:3]) if diagnoses else inp.claim.claim_type
    try:
        medical_chunks = retrieve(
            f"{diag_query} standard treatment guidelines",
            MEDICAL,
            top_k=4,
        )
        chunk_refs.extend(medical_chunks)
    except Exception as e:
        logger.warning(f"Step5 medical RAG failed: {e}")
        medical_chunks = []

    # ── Gemini medical necessity check ────────────────────────────────────────
    necessity = await check_medical_necessity(
        diagnosis=diagnoses,
        medicines=medicines,
        tests_advised=tests,
        medical_chunks=medical_chunks,
    )

    necessity_score = necessity.get("necessity_score", 0.8)
    is_necessary = necessity.get("is_medically_necessary", True)
    concerns = necessity.get("concerns", [])

    data["necessity_result"] = necessity
    data["necessity_score"] = necessity_score

    if not is_necessary and necessity_score < 0.4:
        reasons.append("NOT_MEDICALLY_NECESSARY")
        data["necessity_concerns"] = concerns
    elif concerns:
        warnings.extend(concerns)

    # ── Fraud detection ───────────────────────────────────────────────────────

    # 1. Multiple claims same day
    if inp.prior_claims_today > 2:
        fraud_flags.append("MULTIPLE_CLAIMS_SAME_DAY")
        data["prior_claims_today"] = inp.prior_claims_today

    # 2. Amount anomaly — compare with similar past claims via RAG
    try:
        similar_claims = retrieve_with_metadata(
            f"{inp.claim.claim_type} {diag_query} {inp.claim.claim_amount}",
            CLAIMS,
            top_k=5,
        )
        if similar_claims:
            amounts = [
                m.get("metadata", {}).get("amount", 0)
                for m in similar_claims
                if m.get("metadata", {}).get("amount")
            ]
            if len(amounts) >= 3:
                mean_amt = statistics.mean(amounts)
                stdev_amt = statistics.stdev(amounts) if len(amounts) > 1 else mean_amt * 0.3
                if inp.claim.claim_amount > mean_amt + 2 * stdev_amt:
                    fraud_flags.append("UNUSUALLY_HIGH_AMOUNT")
                    data["mean_similar_amount"] = int(mean_amt)
                    data["claim_amount"] = inp.claim.claim_amount
            chunk_refs.extend([m.get("metadata", {}).get("text", "") for m in similar_claims])
    except Exception as e:
        logger.warning(f"Step5 claims RAG failed: {e}")

    # 3. Amount threshold heuristic
    threshold = AMOUNT_THRESHOLDS.get(inp.claim.claim_type, 10000)
    if inp.claim.claim_amount > threshold:
        warnings.append(f"Claim amount ₹{inp.claim.claim_amount} is above typical threshold (₹{threshold}) for {inp.claim.claim_type}")
        data["amount_threshold"] = threshold

    data["fraud_flags"] = fraud_flags
    data["chunk_refs"] = chunk_refs

    passed = len(reasons) == 0
    # Confidence incorporates necessity score
    base_confidence = necessity_score if passed else 0.0
    fraud_penalty = len(fraud_flags) * 0.15
    confidence = max(0.0, base_confidence - fraud_penalty)

    if fraud_flags:
        logger.info(f"Step 5 fraud flags: {fraud_flags}")
    if not passed:
        logger.info(f"Step 5 FAILED: {reasons}")

    result = StepResult(
        passed=passed,
        reasons=reasons,
        warnings=warnings,
        confidence=confidence,
        data=data,
    )
    # Attach fraud_flags to data so orchestrator can access them
    result.data["fraud_flags"] = fraud_flags
    return result
