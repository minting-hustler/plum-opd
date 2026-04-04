"""Step 3: Coverage verification — RAG-grounded Gemini check for covered/excluded items."""
from __future__ import annotations

import asyncio
import logging

from services.adjudication.types import AdjudicationInput, StepResult
from services.gemini_service import check_coverage
from services.rag.retriever import retrieve
from services.rag.namespaces import POLICY

logger = logging.getLogger(__name__)

# Hardcoded exclusion keywords as a fast pre-filter (reduces Gemini calls for obvious rejects)
EXCLUSION_KEYWORDS = [
    "cosmetic", "whitening", "bleaching", "aesthetic", "beauty treatment",
    "weight loss", "bariatric", "obesity treatment", "slimming",
    "infertility", "ivf", "iui", "fertility treatment",
    "experimental", "unproven",
    "self-inflicted", "suicide attempt",
    "war", "nuclear", "radioactive",
    "hiv", "aids",
    "alcohol", "drug abuse", "substance abuse",
    "vitamins", "supplements",  # unless prescribed for deficiency
]


def _get_all_line_items(inp: AdjudicationInput) -> list[dict]:
    items = []
    for doc in inp.extracted_data:
        items.extend(doc.line_items)
    return items


def _get_all_diagnoses(inp: AdjudicationInput) -> list[str]:
    diagnoses = []
    for doc in inp.extracted_data:
        diagnoses.extend(doc.diagnosis)
    return diagnoses


def _fast_exclusion_check(line_items: list[dict], diagnoses: list[str]) -> list[str]:
    """Quick keyword scan to find obviously excluded items before calling Gemini."""
    excluded = []
    all_text = " ".join(
        [item.get("description", "").lower() for item in line_items]
        + [d.lower() for d in diagnoses]
    )
    for kw in EXCLUSION_KEYWORDS:
        if kw in all_text:
            excluded.append(kw)
    return excluded


async def verify_coverage(inp: AdjudicationInput) -> StepResult:
    reasons: list[str] = []
    warnings: list[str] = []
    data: dict = {}
    chunk_refs: list[str] = []

    line_items = _get_all_line_items(inp)
    diagnoses = _get_all_diagnoses(inp)

    # ── RAG: retrieve relevant coverage/exclusion clauses ──────────────────────
    query = f"{inp.claim.claim_type} {' '.join(diagnoses[:3])} coverage exclusions"
    try:
        policy_chunks = retrieve(query, POLICY, top_k=5)
        chunk_refs.extend(policy_chunks)
    except Exception as e:
        logger.warning(f"Step3 RAG failed: {e}")
        policy_chunks = []

    # ── Fast keyword pre-check ────────────────────────────────────────────────
    fast_excluded = _fast_exclusion_check(line_items, diagnoses)
    data["fast_exclusion_hits"] = fast_excluded

    # ── Gemini coverage check ─────────────────────────────────────────────────
    coverage_result = await check_coverage(
        claim_type=inp.claim.claim_type,
        diagnosis=diagnoses,
        line_items=line_items,
        policy_chunks=policy_chunks,
    )

    excluded_items = coverage_result.get("excluded_items", [])
    covered_items = coverage_result.get("covered_items", [])
    is_partial = coverage_result.get("partial", False)
    pre_auth_required = coverage_result.get("pre_auth_required", False)
    covered = coverage_result.get("covered", True)

    data["coverage_result"] = coverage_result
    data["excluded_items"] = excluded_items
    data["covered_items"] = covered_items
    data["policy_chunks_used"] = chunk_refs

    # ── Pre-auth check ─────────────────────────────────────────────────────────
    if pre_auth_required and not inp.claim.pre_auth_obtained:
        reasons.append("PRE_AUTH_MISSING")
        data["pre_auth_required_for"] = "MRI/CT Scan"

    # ── Coverage decision ──────────────────────────────────────────────────────
    if not covered and not is_partial:
        # Determine which exclusion code to use
        diag_text = " ".join(diagnoses).lower()
        item_text = " ".join([i.get("description", "") for i in line_items]).lower()
        combined = diag_text + " " + item_text

        if any(kw in combined for kw in ["weight loss", "bariatric", "obesity", "slimming"]):
            reasons.append("SERVICE_NOT_COVERED")
        elif any(kw in combined for kw in ["cosmetic", "whitening", "aesthetic"]):
            reasons.append("EXCLUDED_CONDITION")
        elif any(kw in combined for kw in ["infertility", "ivf", "iui"]):
            reasons.append("EXCLUDED_CONDITION")
        elif excluded_items:
            reasons.append("EXCLUDED_CONDITION")
        else:
            reasons.append("SERVICE_NOT_COVERED")

    passed = len(reasons) == 0
    confidence = 0.9 if passed else 0.0
    if is_partial:
        confidence = 0.8  # partial is a soft pass

    if not passed:
        logger.info(f"Step 3 FAILED: {reasons}")

    return StepResult(
        passed=passed or is_partial,  # partial coverage still proceeds to Step 4
        reasons=reasons,
        warnings=warnings,
        confidence=confidence,
        data={
            **data,
            "is_partial": is_partial,
            "chunk_refs": chunk_refs,
        },
    )
