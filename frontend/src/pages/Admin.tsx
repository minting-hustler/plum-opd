import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listClaims, overrideClaim } from "../lib/api";
import { onAuth } from "../lib/auth";
import type { Claim, ClaimStatus } from "../types";
import { ArrowLeft, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

const STATUS_COLORS: Record<ClaimStatus, string> = {
  APPROVED: "bg-green-100 text-green-700",
  REJECTED: "bg-red-100 text-red-700",
  PARTIAL: "bg-yellow-100 text-yellow-700",
  MANUAL_REVIEW: "bg-orange-100 text-orange-700",
  PENDING: "bg-gray-100 text-gray-600",
  PROCESSING: "bg-blue-100 text-blue-600",
};

export default function Admin() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [overrideId, setOverrideId] = useState<string | null>(null);
  const [overrideNotes, setOverrideNotes] = useState("");
  const [overrideDecision, setOverrideDecision] = useState<"APPROVED" | "REJECTED">("APPROVED");
  const [actorUid, setActorUid] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const unsub = onAuth((user) => {
      if (user) setActorUid(user.uid);
    });
    return unsub;
  }, []);

  useEffect(() => {
    listClaims({ admin: true })
      .then(({ claims: c }) => setClaims(c))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filtered = filter === "all" ? claims : claims.filter((c) => c.status === filter);
  const manualReviewCount = claims.filter((c) => c.status === "MANUAL_REVIEW").length;

  const handleOverride = async () => {
    if (!overrideId || !overrideNotes.trim()) return;
    setSubmitting(true);
    try {
      await overrideClaim(overrideId, {
        decision: overrideDecision,
        notes: overrideNotes,
        actor_uid: actorUid,
      });
      const { claims: c } = await listClaims({ admin: true });
      setClaims(c);
      setOverrideId(null);
      setOverrideNotes("");
    } catch (e) {
      console.error(e);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <Link to="/dashboard" className="text-gray-400 hover:text-gray-600">
            <ArrowLeft size={20} />
          </Link>
          <h1 className="font-semibold text-gray-900">Admin Panel</h1>
          {manualReviewCount > 0 && (
            <span className="bg-orange-100 text-orange-700 text-xs font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
              <AlertTriangle size={12} /> {manualReviewCount} manual review{manualReviewCount > 1 ? "s" : ""}
            </span>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6">
        {/* Filters */}
        <div className="flex flex-wrap gap-2 mb-4">
          {["all", "MANUAL_REVIEW", "APPROVED", "REJECTED", "PARTIAL", "PENDING"].map((s) => (
            <button key={s} onClick={() => setFilter(s)}
              className={`text-sm px-3 py-1 rounded-full border transition ${filter === s ? "bg-plum-600 text-white border-plum-600" : "border-gray-300 text-gray-600 hover:border-plum-400"}`}>
              {s === "all" ? "All Claims" : s.replace("_", " ")}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-plum-600" />
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {["Claim #", "Member", "Type", "Amount", "Status", "Confidence", "Actions"].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map((claim) => {
                  const result = claim.adjudication_result;
                  return (
                    <tr key={claim.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <Link to={`/claims/${claim.id}`} className="text-plum-600 hover:underline font-medium">
                          {claim.claim_number}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{claim.member_id.slice(0, 8)}…</td>
                      <td className="px-4 py-3 capitalize text-gray-700">{claim.claim_type}</td>
                      <td className="px-4 py-3 font-medium">₹{claim.claim_amount.toLocaleString("en-IN")}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 rounded-full text-xs font-semibold ${STATUS_COLORS[claim.status]}`}>
                          {claim.status.replace("_", " ")}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-500">
                        {result ? `${(result.confidence_score * 100).toFixed(0)}%` : "—"}
                      </td>
                      <td className="px-4 py-3">
                        {claim.status === "MANUAL_REVIEW" && (
                          <button
                            onClick={() => { setOverrideId(claim.id); setOverrideNotes(""); }}
                            className="text-xs bg-orange-100 text-orange-700 hover:bg-orange-200 px-2 py-1 rounded font-medium transition">
                            Override
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filtered.length === 0 && (
              <p className="text-center text-gray-400 py-10">No claims found.</p>
            )}
          </div>
        )}
      </main>

      {/* Override modal */}
      {overrideId && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
            <h2 className="font-semibold text-gray-900 mb-4">Override Decision</h2>

            <div className="flex gap-3 mb-4">
              <button onClick={() => setOverrideDecision("APPROVED")}
                className={`flex-1 py-2 rounded-lg border text-sm font-medium flex items-center justify-center gap-2 transition ${overrideDecision === "APPROVED" ? "bg-green-50 border-green-400 text-green-700" : "border-gray-300 text-gray-600"}`}>
                <CheckCircle2 size={16} /> Approve
              </button>
              <button onClick={() => setOverrideDecision("REJECTED")}
                className={`flex-1 py-2 rounded-lg border text-sm font-medium flex items-center justify-center gap-2 transition ${overrideDecision === "REJECTED" ? "bg-red-50 border-red-400 text-red-700" : "border-gray-300 text-gray-600"}`}>
                <XCircle size={16} /> Reject
              </button>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Reason / Notes (required)</label>
              <textarea value={overrideNotes} onChange={(e) => setOverrideNotes(e.target.value)}
                rows={3}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-plum-500"
                placeholder="Explain the override decision…" />
            </div>

            <div className="flex gap-3">
              <button onClick={() => setOverrideId(null)}
                className="flex-1 border border-gray-300 text-gray-700 py-2 rounded-lg text-sm hover:bg-gray-50">
                Cancel
              </button>
              <button onClick={handleOverride} disabled={!overrideNotes.trim() || submitting}
                className="flex-1 bg-plum-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-plum-700 disabled:opacity-50">
                {submitting ? "Saving…" : "Confirm Override"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
