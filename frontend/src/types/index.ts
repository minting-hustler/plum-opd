export interface Member {
  id: string;
  employee_id: string;
  full_name: string;
  date_of_birth: string;
  gender: "M" | "F" | "Other";
  email: string;
  join_date: string;
  annual_limit: number;
  annual_used: number;
  is_active: boolean;
  firebase_uid: string;
  category_used_ytd: Record<string, number>;
}

export type ClaimType =
  | "consultation"
  | "diagnostic"
  | "pharmacy"
  | "dental"
  | "vision"
  | "alternative";

export type ClaimStatus =
  | "PENDING"
  | "PROCESSING"
  | "APPROVED"
  | "REJECTED"
  | "PARTIAL"
  | "MANUAL_REVIEW";

export interface Claim {
  id: string;
  claim_number: string;
  member_id: string;
  treatment_date: string;
  claim_amount: number;
  hospital_name: string;
  is_network: boolean;
  claim_type: ClaimType;
  status: ClaimStatus;
  pre_auth_obtained: boolean;
  submitted_at: string;
  processed_at?: string;
  adjudication_result?: AdjudicationResult;
}

export interface StepResult {
  passed: boolean;
  reasons: string[];
  warnings: string[];
  confidence: number;
  data: Record<string, unknown>;
}

export interface AdjudicationResult {
  claim_id: string;
  decision: ClaimStatus;
  approved_amount: number;
  copay_amount: number;
  network_discount: number;
  confidence_score: number;
  rejection_reasons: string[];
  fraud_flags: string[];
  step_results: Record<string, StepResult>;
  notes: string;
  primary_reason: string;
  next_steps: string;
  retrieved_chunks_used: string[];
  decided_by?: string;
  decided_at?: string;
}

export interface ExtractionPreview {
  doctor_name?: string;
  doctor_reg_number?: string;
  patient_name?: string;
  diagnosis?: string[];
  total_amount?: number;
  bill_date?: string;
  legibility_score: number;
  extraction_confidence: number;
  extraction_warnings: string[];
  is_handwritten: boolean;
}

export interface UploadedDocument {
  document_id: string;
  download_url: string;
  file_name: string;
  doc_type: string;
  extraction_preview: ExtractionPreview;
}

// Human-readable rejection reason labels
export const REJECTION_LABELS: Record<string, string> = {
  POLICY_INACTIVE: "Policy was not active on the treatment date",
  WAITING_PERIOD: "Waiting period has not been completed",
  MEMBER_NOT_COVERED: "Member is not covered under this policy",
  BELOW_MIN_AMOUNT: "Claim amount is below the minimum threshold (₹500)",
  ILLEGIBLE_DOCUMENTS: "One or more documents are illegible or unclear",
  MISSING_DOCUMENTS: "Required documents are missing (e.g. prescription)",
  INVALID_PRESCRIPTION: "Prescription is invalid or incomplete",
  DOCTOR_REG_INVALID: "Doctor registration number is missing or invalid",
  DATE_MISMATCH: "Document dates do not match the treatment date",
  PATIENT_MISMATCH: "Patient name on documents does not match policy records",
  SERVICE_NOT_COVERED: "This type of treatment is not covered under the policy",
  EXCLUDED_CONDITION: "The treatment or condition is explicitly excluded",
  PRE_AUTH_MISSING: "Pre-authorisation was required but not obtained (MRI/CT Scan)",
  ANNUAL_LIMIT_EXCEEDED: "Annual benefit limit has been exhausted",
  SUB_LIMIT_EXCEEDED: "Category sub-limit has been exhausted",
  PER_CLAIM_EXCEEDED: "Claim amount exceeds the per-claim limit of ₹5,000",
  NOT_MEDICALLY_NECESSARY: "Treatment does not appear to be medically necessary",
  LATE_SUBMISSION: "Claim submitted after the 30-day submission window",
  DUPLICATE_CLAIM: "This appears to be a duplicate claim",
};
