"""Step 1: Basic eligibility — policy active, member active, waiting periods."""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from services.adjudication.types import AdjudicationInput, StepResult
from services.rag.retriever import retrieve
from services.rag.namespaces import POLICY

logger = logging.getLogger(__name__)

POLICY_EFFECTIVE_DATE = date(2024, 1, 1)

# Keyword → waiting period in days
WAITING_PERIOD_KEYWORDS: dict[str, int] = {
    "diabetes": 90,
    "diabetic": 90,
    "type 2 diabetes": 90,
    "type 1 diabetes": 90,
    "hypertension": 90,
    "high blood pressure": 90,
    "bp": 90,
    "joint replacement": 730,
    "knee replacement": 730,
    "hip replacement": 730,
    "maternity": 270,
    "pregnancy": 270,
    "prenatal": 270,
    "antenatal": 270,
}

# Pre-existing conditions → 365-day wait
PRE_EXISTING_KEYWORDS = [
    "pre-existing", "pre existing", "chronic", "congenital",
    "hereditary", "genetic disorder",
]


def _parse_date(date_str: str) -> Optional[date]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
    return None


def _get_all_diagnoses(inp: AdjudicationInput) -> list[str]:
    diagnoses = []
    for doc in inp.extracted_data:
        diagnoses.extend([d.lower() for d in doc.diagnosis])
    return diagnoses


def check_eligibility(inp: AdjudicationInput) -> StepResult:
    reasons: list[str] = []
    warnings: list[str] = []
    data: dict = {}

    treatment_date = _parse_date(inp.claim.treatment_date)
    join_date = _parse_date(inp.member.join_date)

    # 1. Policy active check
    if treatment_date and treatment_date < POLICY_EFFECTIVE_DATE:
        reasons.append("POLICY_INACTIVE")
        data["treatment_date"] = str(treatment_date)
        data["policy_effective_date"] = str(POLICY_EFFECTIVE_DATE)

    # 2. Member active check
    if not inp.member.is_active:
        reasons.append("MEMBER_NOT_COVERED")

    # 3. Waiting period check
    if treatment_date and join_date:
        days_since_join = (treatment_date - join_date).days
        data["days_since_join"] = days_since_join

        # Initial 30-day waiting period
        if days_since_join < 30:
            reasons.append("WAITING_PERIOD")
            data["waiting_period_type"] = "initial_30_days"
            data["waiting_period_remaining"] = 30 - days_since_join
        else:
            # Check condition-specific waiting periods
            diagnoses = _get_all_diagnoses(inp)
            diag_text = " ".join(diagnoses)

            triggered_wait = None
            for keyword, wait_days in WAITING_PERIOD_KEYWORDS.items():
                if keyword in diag_text:
                    if days_since_join < wait_days:
                        # Use the longest applicable waiting period
                        if triggered_wait is None or wait_days > triggered_wait[1]:
                            triggered_wait = (keyword, wait_days)

            if triggered_wait:
                reasons.append("WAITING_PERIOD")
                data["waiting_period_type"] = f"condition_specific_{triggered_wait[0]}"
                data["waiting_period_days"] = triggered_wait[1]
                data["waiting_period_remaining"] = triggered_wait[1] - days_since_join

            # Pre-existing condition check (365 days)
            if "WAITING_PERIOD" not in reasons:
                for keyword in PRE_EXISTING_KEYWORDS:
                    if keyword in diag_text:
                        if days_since_join < 365:
                            reasons.append("WAITING_PERIOD")
                            data["waiting_period_type"] = "pre_existing_365_days"
                            data["waiting_period_remaining"] = 365 - days_since_join
                        break

        # Minimum claim amount check
        if inp.claim.claim_amount < 500:
            reasons.append("BELOW_MIN_AMOUNT")
            data["minimum_amount"] = 500
            data["claim_amount"] = inp.claim.claim_amount

    # RAG: fetch waiting period policy text for context (non-blocking)
    try:
        diag_query = " ".join(_get_all_diagnoses(inp)[:3]) or "waiting period policy"
        policy_chunks = retrieve(f"waiting period {diag_query}", POLICY, top_k=2)
        data["policy_context"] = policy_chunks
    except Exception as e:
        logger.warning(f"Step1 RAG failed: {e}")

    passed = len(reasons) == 0
    confidence = 1.0 if passed else 0.0

    if not passed:
        logger.info(f"Step 1 FAILED: {reasons}")

    return StepResult(
        passed=passed,
        reasons=reasons,
        warnings=warnings,
        confidence=confidence,
        data=data,
    )
