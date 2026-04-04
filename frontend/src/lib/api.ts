import axios from "axios";
import { auth } from "./firebase";
import type {
  AdjudicationResult,
  Claim,
  ClaimType,
  ExtractionPreview,
  Member,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: BASE_URL });

// Pre-warm the Render backend on page load
export const warmUp = () =>
  api.get("/health").catch(() => {});

// ── Members ──────────────────────────────────────────────────────────────────

export const getMemberByUid = (uid: string): Promise<Member> =>
  api.get(`/members/by-uid/${uid}`).then((r) => r.data);

export const createMember = (data: {
  employee_id: string;
  full_name: string;
  date_of_birth: string;
  gender: "M" | "F" | "Other";
  email: string;
  join_date: string;
  firebase_uid: string;
}): Promise<Member> => api.post("/members", data).then((r) => r.data);

// ── Claims ───────────────────────────────────────────────────────────────────

export const getClaim = (claimId: string): Promise<Claim> =>
  api.get(`/claims/${claimId}`).then((r) => r.data);

export const listClaims = (params?: {
  member_id?: string;
  status?: string;
  admin?: boolean;
}): Promise<{ claims: Claim[]; total: number }> =>
  api.get("/claims", { params }).then((r) => r.data);

export const createClaim = (
  memberId: string,
  data: {
    treatment_date: string;
    claim_amount: number;
    hospital_name: string;
    is_network: boolean;
    claim_type: ClaimType;
    pre_auth_obtained: boolean;
    document_ids: string[];
    notes?: string;
  }
): Promise<Claim> =>
  api.post("/claims", data, { params: { member_id: memberId } }).then((r) => r.data);

export const adjudicateClaim = (claimId: string): Promise<AdjudicationResult> =>
  api.post(`/claims/${claimId}/adjudicate`).then((r) => r.data);

export const overrideClaim = (
  claimId: string,
  data: { decision: "APPROVED" | "REJECTED"; approved_amount?: number; notes: string; actor_uid: string }
): Promise<{ status: string }> =>
  api.patch(`/claims/${claimId}/override`, data).then((r) => r.data);

// ── Document upload ───────────────────────────────────────────────────────────

export const uploadDocument = async (
  file: File,
  claimId: string,
  docType: string,
  memberId: string
): Promise<{
  document_id: string;
  download_url: string;
  extraction_preview: ExtractionPreview;
}> => {
  const form = new FormData();
  form.append("file", file);
  form.append("claim_id", claimId);
  form.append("doc_type", docType);
  form.append("member_id", memberId);
  return api.post("/documents/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  }).then((r) => r.data);
};
