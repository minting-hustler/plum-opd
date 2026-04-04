"""Typed policy constants loaded from policy_terms.json."""
from __future__ import annotations

import json
from pathlib import Path

_RAW = json.loads((Path(__file__).parent.parent / "data" / "policy_terms.json").read_text())

POLICY_ID = _RAW["policy_id"]
POLICY_EFFECTIVE_DATE = _RAW["effective_date"]

COVERAGE_DETAILS: dict = _RAW["coverage_details"]
WAITING_PERIODS: dict = _RAW["waiting_periods"]
EXCLUSIONS: list[str] = _RAW["exclusions"]
CLAIM_REQUIREMENTS: dict = _RAW["claim_requirements"]
NETWORK_HOSPITALS: list[str] = _RAW["network_hospitals"]

ANNUAL_LIMIT = 50_000
PER_CLAIM_LIMIT = 5_000
MIN_CLAIM_AMOUNT = CLAIM_REQUIREMENTS.get("minimum_claim_amount", 500)
SUBMISSION_TIMELINE_DAYS = CLAIM_REQUIREMENTS.get("submission_timeline_days", 30)

# Sub-limits per category
SUB_LIMITS: dict[str, int] = {
    "consultation": COVERAGE_DETAILS["consultation_fees"]["sub_limit"],
    "diagnostic": COVERAGE_DETAILS["diagnostic_tests"]["sub_limit"],
    "pharmacy": COVERAGE_DETAILS["pharmacy"]["sub_limit"],
    "dental": COVERAGE_DETAILS["dental"]["sub_limit"],
    "vision": COVERAGE_DETAILS["vision"]["sub_limit"],
    "alternative": COVERAGE_DETAILS["alternative_medicine"]["sub_limit"],
}

# Co-pay percentages
COPAY_RATES: dict[str, float] = {
    "consultation": COVERAGE_DETAILS["consultation_fees"]["copay_percentage"] / 100,
    "diagnostic": 0.0,
    "pharmacy": 0.0,  # only branded drugs have copay — handled specially
    "pharmacy_branded": COVERAGE_DETAILS["pharmacy"].get("branded_drugs_copay", 30) / 100,
    "dental": 0.0,
    "vision": 0.0,
    "alternative": 0.0,
}

NETWORK_DISCOUNT_RATE = COVERAGE_DETAILS["consultation_fees"].get("network_discount", 20) / 100
