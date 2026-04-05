"""Gemini service: document extraction + adjudication reasoning."""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from typing import Any

import google.generativeai as genai

logger = logging.getLogger(__name__)

_model: genai.GenerativeModel | None = None
_DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
_DEFAULT_EMBED_MODEL = os.environ.get("GEMINI_EMBED_MODEL", "models/gemini-embedding-001")
_DEFAULT_EMBED_DIM = int(os.environ.get("GEMINI_EMBED_DIM", "768"))


def _get_model() -> genai.GenerativeModel:
    global _model
    if _model is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY env var not set")
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel(_DEFAULT_GEMINI_MODEL)
    return _model


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed_text(text: str) -> list[float]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY env var not set")
    genai.configure(api_key=api_key)
    result = genai.embed_content(model=_DEFAULT_EMBED_MODEL, content=text)
    embedding = result["embedding"]
    if len(embedding) >= _DEFAULT_EMBED_DIM:
        return embedding[:_DEFAULT_EMBED_DIM]
    return embedding


# ── Extraction prompts ────────────────────────────────────────────────────────

_COMMON_RULES = """
Rules:
- Return ONLY a valid JSON object. No markdown, no explanation, no code fences.
- If a field is not visible or cannot be determined, use null.
- Set legibility_score < 0.5 if significant portions are unreadable or blurry.
- Set extraction_confidence < 0.3 if this does not appear to be a medical document.
- extraction_warnings should list any issues (e.g. "date partially obscured", "stamp missing").
- is_handwritten: true if handwritten, false if printed.
"""

_PRESCRIPTION_SCHEMA = """
{
  "doctor_name": "string or null",
  "doctor_reg_number": "string or null (format: StateCode/Number/Year e.g. KA/45678/2015)",
  "doctor_qualification": "string or null",
  "clinic_name": "string or null",
  "patient_name": "string or null",
  "patient_age": "number or null",
  "patient_gender": "M, F, Other, or null",
  "diagnosis": ["array of diagnosed conditions"],
  "medicines_prescribed": [
    {"name": "string", "dosage": "string", "duration": "string", "is_branded": true}
  ],
  "tests_advised": ["array of test names"],
  "prescription_date": "YYYY-MM-DD or null",
  "is_handwritten": false,
  "language_detected": "English",
  "legibility_score": 0.9,
  "extraction_warnings": [],
  "extraction_confidence": 0.95
}
"""

_BILL_SCHEMA = """
{
  "hospital_name": "string or null",
  "bill_number": "string or null",
  "bill_date": "YYYY-MM-DD or null",
  "patient_name": "string or null",
  "line_items": [
    {"description": "string", "amount": 0, "category": "consultation|diagnostic|pharmacy|dental|vision|alternative|other"}
  ],
  "consultation_fee": "number or null",
  "diagnostic_amount": "number or null",
  "pharmacy_amount": "number or null",
  "procedure_amount": "number or null",
  "total_amount": "number or null",
  "gst_amount": "number or null",
  "is_handwritten": false,
  "language_detected": "English",
  "legibility_score": 0.9,
  "extraction_warnings": [],
  "extraction_confidence": 0.95
}
"""

_DIAGNOSTIC_SCHEMA = """
{
  "lab_name": "string or null",
  "report_date": "YYYY-MM-DD or null",
  "patient_name": "string or null",
  "patient_age": "number or null",
  "test_names": ["array of test names"],
  "pathologist_name": "string or null",
  "lab_accreditation": "NABL, CAP, or null",
  "results_summary": "string or null",
  "referring_doctor": "string or null",
  "is_handwritten": false,
  "language_detected": "English",
  "legibility_score": 0.9,
  "extraction_warnings": [],
  "extraction_confidence": 0.95
}
"""

_PHARMACY_SCHEMA = """
{
  "pharmacy_name": "string or null",
  "pharmacy_license": "string or null",
  "bill_date": "YYYY-MM-DD or null",
  "patient_name": "string or null",
  "line_items": [
    {"name": "string", "quantity": 1, "unit_price": 0, "total_price": 0, "is_branded": true, "batch_number": "string or null"}
  ],
  "total_amount": "number or null",
  "prescription_reference": "string or null",
  "is_handwritten": false,
  "language_detected": "English",
  "legibility_score": 0.9,
  "extraction_warnings": [],
  "extraction_confidence": 0.95
}
"""

_SCHEMAS = {
    "prescription": _PRESCRIPTION_SCHEMA,
    "bill": _BILL_SCHEMA,
    "diagnostic_report": _DIAGNOSTIC_SCHEMA,
    "pharmacy_bill": _PHARMACY_SCHEMA,
}


def _extraction_prompt(doc_type: str, policy_context: str = "") -> str:
    schema = _SCHEMAS.get(doc_type, _BILL_SCHEMA)
    ctx = f"\nRelevant policy context:\n{policy_context}\n" if policy_context else ""
    return f"""You are a medical document parser for an Indian insurance claims system.
Extract all visible information from this document image/PDF.{ctx}
Return ONLY a valid JSON object matching this schema:
{schema}
{_COMMON_RULES}"""


# ── Parse JSON from Gemini response ───────────────────────────────────────────

def _parse_json_response(text: str) -> dict:
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON object in the response
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}


# ── Main extraction function ───────────────────────────────────────────────────

async def extract_document(
    file_bytes: bytes,
    mime_type: str,
    doc_type: str,
    policy_context: str = "",
) -> dict[str, Any]:
    """Send file to Gemini and return structured extracted data."""
    model = _get_model()
    prompt = _extraction_prompt(doc_type, policy_context)
    encoded = base64.b64encode(file_bytes).decode("utf-8")

    try:
        response = model.generate_content([
            {"inline_data": {"mime_type": mime_type, "data": encoded}},
            prompt,
        ])
        extracted = _parse_json_response(response.text)
        if not extracted:
            logger.warning("Gemini returned empty/unparseable extraction result")
            return _empty_extraction(doc_type)
        return extracted
    except Exception as e:
        logger.error(f"Gemini extraction failed: {e}")
        return _empty_extraction(doc_type)


def _empty_extraction(doc_type: str) -> dict:
    return {
        "legibility_score": 0.0,
        "extraction_confidence": 0.0,
        "extraction_warnings": ["Extraction failed — could not process document"],
        "is_handwritten": False,
    }


# ── Coverage check (Step 3) ───────────────────────────────────────────────────

async def check_coverage(
    claim_type: str,
    diagnosis: list[str],
    line_items: list[dict],
    policy_chunks: list[str],
) -> dict[str, Any]:
    """Ask Gemini whether the claim is covered given retrieved policy chunks."""
    model = _get_model()
    policy_text = "\n\n".join(policy_chunks)
    items_text = json.dumps(line_items, indent=2)
    diag_text = ", ".join(diagnosis) if diagnosis else "not specified"

    prompt = f"""You are an insurance adjudication assistant.

Policy context:
{policy_text}

Claim details:
- Claim type: {claim_type}
- Diagnosis: {diag_text}
- Line items: {items_text}

Determine coverage. Return ONLY a valid JSON object:
{{
  "covered": true,
  "excluded_items": ["list of excluded line item descriptions, if any"],
  "covered_items": ["list of covered line item descriptions"],
  "partial": false,
  "pre_auth_required": false,
  "reasoning": "brief explanation"
}}

Rules:
- excluded_items: items that match exclusion clauses (cosmetic, weight loss, infertility, etc.)
- pre_auth_required: true only for MRI or CT Scan procedures
- partial: true if some items are covered and some are excluded
- Return ONLY the JSON object, no markdown."""

    try:
        response = model.generate_content(prompt)
        result = _parse_json_response(response.text)
        if not result:
            return {"covered": True, "excluded_items": [], "covered_items": [], "partial": False, "pre_auth_required": False, "reasoning": "Could not determine coverage"}
        return result
    except Exception as e:
        logger.error(f"Coverage check failed: {e}")
        return {"covered": True, "excluded_items": [], "covered_items": [], "partial": False, "pre_auth_required": False, "reasoning": "Coverage check error"}


# ── Medical necessity check (Step 5) ──────────────────────────────────────────

async def check_medical_necessity(
    diagnosis: list[str],
    medicines: list[dict],
    tests_advised: list[str],
    medical_chunks: list[str],
) -> dict[str, Any]:
    """Ask Gemini if prescribed treatment is medically appropriate."""
    model = _get_model()
    guidelines_text = "\n\n".join(medical_chunks)
    diag_text = ", ".join(diagnosis) if diagnosis else "not specified"
    med_names = [m.get("name", "") for m in medicines if m.get("name")]
    meds_text = ", ".join(med_names) if med_names else "none listed"
    tests_text = ", ".join(tests_advised) if tests_advised else "none"

    prompt = f"""You are a medical necessity reviewer for an insurance company.

Medical guidelines:
{guidelines_text}

Claim details:
- Diagnosis: {diag_text}
- Medicines prescribed: {meds_text}
- Tests advised: {tests_text}

Assess medical necessity. Return ONLY a valid JSON object:
{{
  "is_medically_necessary": true,
  "necessity_score": 0.9,
  "concerns": ["list any concerns about appropriateness"],
  "reasoning": "brief explanation"
}}

Rules:
- necessity_score: 0.0-1.0 (1.0 = clearly necessary, 0.0 = clearly unnecessary)
- If diagnosis is vague or not provided, give benefit of the doubt (score >= 0.7)
- Return ONLY the JSON object, no markdown."""

    try:
        response = model.generate_content(prompt)
        result = _parse_json_response(response.text)
        if not result:
            return {"is_medically_necessary": True, "necessity_score": 0.8, "concerns": [], "reasoning": "Unable to assess"}
        return result
    except Exception as e:
        logger.error(f"Medical necessity check failed: {e}")
        return {"is_medically_necessary": True, "necessity_score": 0.8, "concerns": [], "reasoning": "Check failed"}


# ── Final reasoning call ───────────────────────────────────────────────────────

async def generate_reasoning(
    claim_summary: dict,
    step_results: dict,
    decision: str,
    confidence: float,
    policy_chunks: list[str],
    similar_claims: list[str],
) -> dict[str, Any]:
    """Generate human-readable decision explanation."""
    model = _get_model()
    policy_text = "\n".join(policy_chunks[:3])
    similar_text = "\n".join(similar_claims[:3])

    prompt = f"""You are an insurance claims adjudicator writing a decision letter.

Policy context:
{policy_text}

Similar past claims:
{similar_text if similar_text else "No similar claims available."}

Claim summary:
- Type: {claim_summary.get('claim_type')}
- Amount: ₹{claim_summary.get('claim_amount')}
- Diagnosis: {claim_summary.get('diagnosis', 'not specified')}
- Hospital: {claim_summary.get('hospital_name')}
- Network hospital: {claim_summary.get('is_network', False)}

Decision: {decision} (confidence: {confidence:.0%})
Step results summary: {json.dumps({k: v.get('passed') for k, v in step_results.items()})}

Write a clear, empathetic decision explanation. Return ONLY a valid JSON object:
{{
  "notes": "2-3 sentence explanation of the decision in plain language",
  "primary_reason": "the single most important reason for this outcome (one sentence)",
  "next_steps": "what the claimant should do next (one sentence)"
}}"""

    try:
        response = model.generate_content(prompt)
        result = _parse_json_response(response.text)
        if not result:
            return _default_reasoning(decision)
        return result
    except Exception as e:
        logger.error(f"Reasoning generation failed: {e}")
        return _default_reasoning(decision)


def _default_reasoning(decision: str) -> dict:
    messages = {
        "APPROVED": {
            "notes": "Your claim has been reviewed and approved.",
            "primary_reason": "All policy requirements were satisfied.",
            "next_steps": "Your reimbursement will be processed within 5 business days.",
        },
        "REJECTED": {
            "notes": "Your claim could not be approved at this time.",
            "primary_reason": "The claim did not meet one or more policy requirements.",
            "next_steps": "Please review the rejection reasons and submit an appeal if you disagree.",
        },
        "PARTIAL": {
            "notes": "Your claim has been partially approved.",
            "primary_reason": "Some items were covered under the policy while others were not.",
            "next_steps": "The approved amount will be reimbursed within 5 business days.",
        },
        "MANUAL_REVIEW": {
            "notes": "Your claim has been flagged for manual review by our team.",
            "primary_reason": "Additional verification is required before a final decision can be made.",
            "next_steps": "Our team will contact you within 2-3 business days.",
        },
    }
    return messages.get(decision, messages["REJECTED"])
