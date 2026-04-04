from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class MedicineItem(BaseModel):
    name: str = ""
    dosage: str = ""
    duration: str = ""
    is_branded: bool = False


class LineItem(BaseModel):
    description: str = ""
    amount: int = 0
    category: str = "other"


class ExtractedDataDoc(BaseModel):
    id: str = ""
    document_id: str = ""
    claim_id: str = ""
    doc_type: str = "other"

    # Prescription fields
    doctor_name: Optional[str] = None
    doctor_reg_number: Optional[str] = None
    patient_name: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    diagnosis: list[str] = Field(default_factory=list)
    medicines_prescribed: list[dict] = Field(default_factory=list)
    tests_advised: list[str] = Field(default_factory=list)
    prescription_date: Optional[str] = None

    # Bill fields
    bill_number: Optional[str] = None
    bill_date: Optional[str] = None
    line_items: list[dict] = Field(default_factory=list)
    total_amount: Optional[int] = None
    consultation_fee: Optional[int] = None

    # Report fields
    report_date: Optional[str] = None
    test_names: list[str] = Field(default_factory=list)

    # Quality signals
    legibility_score: float = 1.0
    extraction_confidence: float = 1.0
    extraction_warnings: list[str] = Field(default_factory=list)
    is_handwritten: bool = False

    class Config:
        extra = "allow"


class ClaimDoc(BaseModel):
    id: str
    claim_number: str = ""
    member_id: str
    treatment_date: str
    claim_amount: int
    hospital_name: str = ""
    is_network: bool = False
    claim_type: str
    status: str = "PENDING"
    pre_auth_obtained: bool = False

    class Config:
        extra = "allow"


class MemberDoc(BaseModel):
    id: str
    employee_id: str = ""
    full_name: str
    join_date: str
    annual_limit: int = 50000
    annual_used: int = 0
    is_active: bool = True
    date_of_birth: Optional[str] = None

    class Config:
        extra = "allow"


class AdjudicationInput(BaseModel):
    claim: ClaimDoc
    member: MemberDoc
    extracted_data: list[ExtractedDataDoc] = Field(default_factory=list)
    annual_used_ytd: int = 0
    category_used_ytd: dict[str, int] = Field(default_factory=dict)
    prior_claims_today: int = 0


class StepResult(BaseModel):
    passed: bool
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    data: dict[str, Any] = Field(default_factory=dict)


class AdjudicationOutput(BaseModel):
    decision: Literal["APPROVED", "REJECTED", "PARTIAL", "MANUAL_REVIEW"]
    approved_amount: int = 0
    copay_amount: int = 0
    network_discount: int = 0
    confidence_score: float
    rejection_reasons: list[str] = Field(default_factory=list)
    fraud_flags: list[str] = Field(default_factory=list)
    step_results: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""
    primary_reason: str = ""
    next_steps: str = ""
    retrieved_chunks_used: list[str] = Field(default_factory=list)
