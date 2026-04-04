import { Link } from "react-router-dom";
import type { Claim, ClaimStatus } from "../types";
import { ChevronRight } from "lucide-react";

const STATUS_CONFIG: Record<ClaimStatus, { label: string; color: string }> = {
  APPROVED: { label: "Approved", color: "bg-green-100 text-green-700" },
  REJECTED: { label: "Rejected", color: "bg-red-100 text-red-700" },
  PARTIAL: { label: "Partially Approved", color: "bg-yellow-100 text-yellow-700" },
  MANUAL_REVIEW: { label: "Under Review", color: "bg-orange-100 text-orange-700" },
  PENDING: { label: "Pending", color: "bg-gray-100 text-gray-500" },
  PROCESSING: { label: "Processing", color: "bg-blue-100 text-blue-600" },
};

const TYPE_LABELS: Record<string, string> = {
  consultation: "Consultation",
  diagnostic: "Diagnostics",
  pharmacy: "Pharmacy",
  dental: "Dental",
  vision: "Vision",
  alternative: "Alternative Medicine",
};

export default function ClaimCard({ claim }: { claim: Claim }) {
  const cfg = STATUS_CONFIG[claim.status];
  const result = claim.adjudication_result;

  return (
    <Link to={`/claims/${claim.id}`}
      className="block bg-white rounded-xl border border-gray-200 hover:border-plum-300 hover:shadow-sm transition p-4">
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-gray-900 text-sm">{claim.claim_number}</span>
            <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${cfg.color}`}>
              {cfg.label}
            </span>
            {claim.is_network && (
              <span className="px-2 py-0.5 rounded-full text-xs bg-plum-100 text-plum-700">Network</span>
            )}
          </div>
          <div className="mt-1 flex items-center gap-3 text-xs text-gray-500">
            <span>{TYPE_LABELS[claim.claim_type] || claim.claim_type}</span>
            <span>·</span>
            <span>{claim.treatment_date}</span>
            {claim.hospital_name && (
              <>
                <span>·</span>
                <span className="truncate max-w-32">{claim.hospital_name}</span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 ml-3">
          <div className="text-right">
            <p className="text-sm font-semibold text-gray-900">
              ₹{claim.claim_amount.toLocaleString("en-IN")}
            </p>
            {result && result.approved_amount > 0 && (
              <p className="text-xs text-green-600 font-medium">
                ₹{result.approved_amount.toLocaleString("en-IN")} approved
              </p>
            )}
          </div>
          <ChevronRight size={16} className="text-gray-400 flex-shrink-0" />
        </div>
      </div>
    </Link>
  );
}
