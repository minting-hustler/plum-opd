import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getClaim } from "../lib/api";
import type { Claim } from "../types";
import AdjudicationResult from "../components/AdjudicationResult";
import ClaimTimeline from "../components/ClaimTimeline";
import { ArrowLeft } from "lucide-react";

export default function ClaimDetail() {
  const { id } = useParams<{ id: string }>();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    getClaim(id)
      .then(setClaim)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-plum-600" />
      </div>
    );
  }

  if (!claim) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500">
        Claim not found.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-2xl mx-auto flex items-center gap-3">
          <Link to="/dashboard" className="text-gray-400 hover:text-gray-600">
            <ArrowLeft size={20} />
          </Link>
          <div>
            <h1 className="font-semibold text-gray-900">{claim.claim_number}</h1>
            <p className="text-xs text-gray-400">{claim.claim_type} · ₹{claim.claim_amount.toLocaleString("en-IN")}</p>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6 space-y-4">
        <ClaimTimeline claim={claim} />

        {claim.adjudication_result ? (
          <AdjudicationResult result={claim.adjudication_result} />
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 p-6 text-center text-gray-400">
            <p>This claim has not been adjudicated yet.</p>
          </div>
        )}

        {/* Claim details card */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-900 mb-3">Claim Details</h3>
          <div className="divide-y divide-gray-100">
            {[
              ["Claim Number", claim.claim_number],
              ["Treatment Date", claim.treatment_date],
              ["Hospital", claim.hospital_name || "—"],
              ["Network Hospital", claim.is_network ? "Yes" : "No"],
              ["Claim Amount", `₹${claim.claim_amount.toLocaleString("en-IN")}`],
              ["Submitted", new Date(claim.submitted_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between py-2 text-sm">
                <span className="text-gray-500">{label}</span>
                <span className="font-medium text-gray-900">{value}</span>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
