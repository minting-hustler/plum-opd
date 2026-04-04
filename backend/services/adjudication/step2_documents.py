"""Step 2: Document validation — legibility, doctor reg#, dates, patient name match."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

from Levenshtein import distance as levenshtein_distance

from services.adjudication.types import AdjudicationInput, StepResult
from services.rag.retriever import retrieve
from services.rag.namespaces import POLICY

logger = logging.getLogger(__name__)

# Doctor registration number formats:
# Allopathic: XX/NNNNN/YYYY (state code / number / year)
# Also accept: XX/NNNNN/YY, XXXXX/NNNNN/YYYY
DOCTOR_REG_REGEX = re.compile(
    r"^[A-Z]{2,5}[/\-]\d{3,6}[/\-]\d{2,4}$", re.IGNORECASE
)

LEGIBILITY_THRESHOLD = 0.5


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _fuzzy_name_match(name1: Optional[str], name2: Optional[str]) -> bool:
    """Return True if names are close enough (Levenshtein ≤ 3, case-insensitive)."""
    if not name1 or not name2:
        return True  # can't verify if either is missing → benefit of doubt
    n1 = name1.lower().strip()
    n2 = name2.lower().strip()
    if n1 == n2:
        return True
    # Also try first-word match (some prescriptions use first name only)
    if n1.split()[0] == n2.split()[0]:
        return True
    return levenshtein_distance(n1, n2) <= 3


def check_documents(inp: AdjudicationInput) -> StepResult:
    reasons: list[str] = []
    warnings: list[str] = []
    data: dict = {}
    chunk_refs: list[str] = []

    docs = inp.extracted_data
    treatment_date = _parse_date(inp.claim.treatment_date)

    # ── 1. Legibility check ────────────────────────────────────────────────────
    illegible_docs = [
        d for d in docs
        if (d.legibility_score or 1.0) < LEGIBILITY_THRESHOLD
    ]
    if illegible_docs:
        reasons.append("ILLEGIBLE_DOCUMENTS")
        data["illegible_count"] = len(illegible_docs)
        data["illegible_warnings"] = [w for d in illegible_docs for w in d.extraction_warnings]

    # ── 2. Prescription required ───────────────────────────────────────────────
    prescription_docs = [d for d in docs if d.doc_type == "prescription"]
    if not prescription_docs:
        reasons.append("MISSING_DOCUMENTS")
        data["missing"] = "prescription"
    else:
        # ── 3. Doctor registration number ───────────────────────────────────────
        has_valid_reg = False
        for p in prescription_docs:
            reg = p.doctor_reg_number
            if reg and DOCTOR_REG_REGEX.match(reg.strip()):
                has_valid_reg = True
                break
            elif reg:
                # Has a reg# but doesn't match strict format — warn but don't reject
                # Some states/alternative medicine use different formats
                warnings.append(f"Unusual doctor reg# format: {reg}")
                has_valid_reg = True  # benefit of doubt if present

        if not has_valid_reg:
            reasons.append("DOCTOR_REG_INVALID")
            data["doctor_reg_issue"] = "No valid doctor registration number found"

        # ── 4. Patient name match ──────────────────────────────────────────────
        member_name = inp.member.full_name
        name_matched = False
        for p in prescription_docs:
            if _fuzzy_name_match(p.patient_name, member_name):
                name_matched = True
                break
        if not name_matched:
            reasons.append("PATIENT_MISMATCH")
            data["member_name"] = member_name
            data["doc_patient_names"] = [d.patient_name for d in prescription_docs]

    # ── 5. Date consistency check ──────────────────────────────────────────────
    if treatment_date:
        for doc in docs:
            doc_date = _parse_date(doc.bill_date or doc.prescription_date or doc.report_date)
            if doc_date and abs((doc_date - treatment_date).days) > 7:
                if "DATE_MISMATCH" not in reasons:
                    reasons.append("DATE_MISMATCH")
                data["treatment_date"] = str(treatment_date)
                data["mismatched_doc_date"] = str(doc_date)
                break

    # ── RAG: fetch required documents for this claim type ─────────────────────
    try:
        chunks = retrieve(
            f"required documents {inp.claim.claim_type} claim",
            POLICY,
            top_k=3,
        )
        data["policy_context"] = chunks
        chunk_refs.extend(chunks)
    except Exception as e:
        logger.warning(f"Step2 RAG failed: {e}")

    passed = len(reasons) == 0
    # Confidence degrades with each failed check
    confidence = max(0.0, 1.0 - (len(reasons) * 0.3) - (len(warnings) * 0.05))

    if not passed:
        logger.info(f"Step 2 FAILED: {reasons}")

    return StepResult(
        passed=passed,
        reasons=reasons,
        warnings=warnings,
        confidence=confidence,
        data={**data, "chunk_refs": chunk_refs},
    )
