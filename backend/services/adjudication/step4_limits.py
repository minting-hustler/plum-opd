"""Step 4: Limit validation — sub-limits, per-claim cap, annual limit, co-pay, network discount."""
from __future__ import annotations

import logging

from policy.policy_terms import (
    ANNUAL_LIMIT,
    COPAY_RATES,
    NETWORK_DISCOUNT_RATE,
    PER_CLAIM_LIMIT,
    SUB_LIMITS,
)
from services.adjudication.types import AdjudicationInput, StepResult

logger = logging.getLogger(__name__)


def _get_covered_amount(inp: AdjudicationInput, step3_data: dict) -> int:
    """Derive the claimable base amount from Step 3 coverage result."""
    coverage = step3_data.get("coverage_result", {})
    covered_items = coverage.get("covered_items", [])

    # If Step 3 gave us covered line items, sum those
    if covered_items:
        all_items = []
        for doc in inp.extracted_data:
            all_items.extend(doc.line_items)

        covered_total = 0
        covered_names = {c.lower() for c in covered_items}
        for item in all_items:
            desc = item.get("description", "").lower()
            amt = item.get("amount", 0)
            # Match if description contains any covered item name
            if any(c in desc or desc in c for c in covered_names):
                covered_total += amt

        if covered_total > 0:
            return covered_total

    # Fallback: use claim amount
    return inp.claim.claim_amount


def validate_limits(inp: AdjudicationInput, step3_data: dict) -> StepResult:
    reasons: list[str] = []
    warnings: list[str] = []
    data: dict = {}

    claim_type = inp.claim.claim_type
    claimable = _get_covered_amount(inp, step3_data)
    original_claimable = claimable

    # ── Sub-limit check ────────────────────────────────────────────────────────
    sub_limit = SUB_LIMITS.get(claim_type, 0)
    category_used = inp.category_used_ytd.get(claim_type, 0)
    category_available = max(0, sub_limit - category_used)

    data["sub_limit"] = sub_limit
    data["category_used_ytd"] = category_used
    data["category_available"] = category_available

    if category_available <= 0:
        reasons.append("SUB_LIMIT_EXCEEDED")
        return StepResult(passed=False, reasons=reasons, confidence=0.0, data=data)

    if claimable > category_available:
        warnings.append(f"Claim truncated to available sub-limit (₹{category_available})")
        claimable = category_available

    # ── Per-claim limit ────────────────────────────────────────────────────────
    is_partial = claimable > PER_CLAIM_LIMIT
    if is_partial:
        warnings.append(f"Claim truncated to per-claim limit (₹{PER_CLAIM_LIMIT})")
        claimable = PER_CLAIM_LIMIT

    data["per_claim_limit"] = PER_CLAIM_LIMIT
    data["original_claimable"] = original_claimable

    # ── Annual limit check ─────────────────────────────────────────────────────
    annual_available = max(0, ANNUAL_LIMIT - inp.annual_used_ytd)
    data["annual_limit"] = ANNUAL_LIMIT
    data["annual_used_ytd"] = inp.annual_used_ytd
    data["annual_available"] = annual_available

    if annual_available <= 0:
        reasons.append("ANNUAL_LIMIT_EXCEEDED")
        return StepResult(passed=False, reasons=reasons, confidence=0.0, data=data)

    if claimable > annual_available:
        warnings.append(f"Claim truncated to annual limit available (₹{annual_available})")
        claimable = annual_available
        is_partial = True

    # ── Co-pay calculation ─────────────────────────────────────────────────────
    copay_rate = COPAY_RATES.get(claim_type, 0.0)

    # Special handling: pharmacy branded drugs have higher copay
    if claim_type == "pharmacy":
        branded_amount = _get_branded_pharmacy_amount(inp)
        generic_amount = max(0, claimable - branded_amount)
        branded_copay = branded_amount * COPAY_RATES["pharmacy_branded"]
        generic_copay = 0.0
        copay_amount = int(branded_copay + generic_copay)
    else:
        copay_amount = int(claimable * copay_rate)

    approved_before_network = claimable - copay_amount
    data["copay_rate"] = copay_rate
    data["copay_amount"] = copay_amount

    # ── Network discount ───────────────────────────────────────────────────────
    network_discount = 0
    if inp.claim.is_network:
        network_discount = int(approved_before_network * NETWORK_DISCOUNT_RATE)
        data["network_discount"] = network_discount
        data["network_discount_rate"] = NETWORK_DISCOUNT_RATE

    approved_amount = approved_before_network - network_discount

    data["claimable"] = claimable
    data["approved_amount"] = approved_amount
    data["is_partial"] = is_partial

    passed = len(reasons) == 0
    confidence = 0.95 if passed else 0.0

    logger.info(
        f"Step 4: claimable={claimable}, copay={copay_amount}, "
        f"network_discount={network_discount}, approved={approved_amount}"
    )

    return StepResult(
        passed=passed,
        reasons=reasons,
        warnings=warnings,
        confidence=confidence,
        data=data,
    )


def _get_branded_pharmacy_amount(inp: AdjudicationInput) -> int:
    """Sum amounts of branded pharmacy items."""
    branded = 0
    for doc in inp.extracted_data:
        if doc.doc_type == "pharmacy_bill":
            for item in doc.line_items:
                if item.get("is_branded", False):
                    branded += item.get("amount", item.get("total_price", 0))
    return branded
