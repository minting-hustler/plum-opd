import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { onAuth } from "../lib/auth";
import { getMemberByUid, createClaim, adjudicateClaim } from "../lib/api";
import type { Member, ClaimType, UploadedDocument } from "../types";
import DocumentUploader from "../components/DocumentUploader";
import { ArrowLeft, ArrowRight, CheckCircle2 } from "lucide-react";

const CLAIM_TYPES: { value: ClaimType; label: string }[] = [
  { value: "consultation", label: "Doctor Consultation" },
  { value: "diagnostic", label: "Diagnostic Tests" },
  { value: "pharmacy", label: "Pharmacy / Medicines" },
  { value: "dental", label: "Dental Treatment" },
  { value: "vision", label: "Vision / Eye Care" },
  { value: "alternative", label: "Alternative Medicine" },
];

const ADJUDICATION_STEPS = [
  "Retrieving policy context…",
  "Checking eligibility…",
  "Validating documents…",
  "Verifying coverage…",
  "Calculating limits…",
  "Reviewing medical necessity…",
  "Composing decision…",
];

export default function ClaimNew() {
  const navigate = useNavigate();
  const [member, setMember] = useState<Member | null>(null);
  const [step, setStep] = useState(1);

  // Step 1 form state
  const [form, setForm] = useState({
    treatment_date: "",
    hospital_name: "",
    claim_type: "consultation" as ClaimType,
    claim_amount: "",
    is_network: false,
    pre_auth_obtained: false,
    notes: "",
  });

  // Step 2: uploaded documents
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDocument[]>([]);
  const [tempClaimId, setTempClaimId] = useState<string | null>(null);

  // Step 3: adjudication
  const [adjudicating, setAdjudicating] = useState(false);
  const [adjStep, setAdjStep] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    const unsub = onAuth(async (user) => {
      if (!user) { navigate("/login"); return; }
      try {
        const m = await getMemberByUid(user.uid);
        setMember(m);
      } catch {
        navigate("/login");
      }
    });
    return unsub;
  }, [navigate]);

  const handleStep1Next = async () => {
    if (!member) return;
    setError("");
    try {
      // Create a temporary claim to attach documents to
      const claim = await createClaim(member.id, {
        treatment_date: form.treatment_date,
        claim_amount: parseInt(form.claim_amount) || 0,
        hospital_name: form.hospital_name,
        is_network: form.is_network,
        claim_type: form.claim_type,
        pre_auth_obtained: form.pre_auth_obtained,
        document_ids: [],
        notes: form.notes || undefined,
      });
      setTempClaimId(claim.id);
      setStep(2);
    } catch {
      setError("Failed to create claim. Please try again.");
    }
  };

  const handleSubmit = async () => {
    if (!tempClaimId) return;
    setStep(3);
    setAdjudicating(true);

    // Animate through adjudication steps
    for (let i = 0; i < ADJUDICATION_STEPS.length; i++) {
      await new Promise((r) => setTimeout(r, 900));
      setAdjStep(i + 1);
    }

    try {
      await adjudicateClaim(tempClaimId);
      navigate(`/claims/${tempClaimId}`);
    } catch {
      setError("Adjudication failed. Please try again.");
      setAdjudicating(false);
    }
  };

  if (!member) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-plum-600" />
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
          <h1 className="font-semibold text-gray-900">Submit OPD Claim</h1>
        </div>
      </header>

      {/* Step indicator */}
      <div className="max-w-2xl mx-auto px-4 py-4">
        <div className="flex items-center gap-2 mb-6">
          {["Claim Details", "Upload Documents", "Review & Submit"].map((label, i) => (
            <div key={i} className="flex items-center gap-2 flex-1">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0
                ${step > i + 1 ? "bg-green-500 text-white" : step === i + 1 ? "bg-plum-600 text-white" : "bg-gray-200 text-gray-400"}`}>
                {step > i + 1 ? <CheckCircle2 size={16} /> : i + 1}
              </div>
              <span className={`text-sm hidden sm:block ${step === i + 1 ? "text-plum-600 font-medium" : "text-gray-400"}`}>
                {label}
              </span>
              {i < 2 && <div className="flex-1 h-px bg-gray-200 hidden sm:block" />}
            </div>
          ))}
        </div>

        {/* Step 1: Claim Details */}
        {step === 1 && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
            <h2 className="font-semibold text-gray-900">Claim Details</h2>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Claim Type</label>
              <select value={form.claim_type} onChange={(e) => setForm((f) => ({ ...f, claim_type: e.target.value as ClaimType }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-plum-500">
                {CLAIM_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Treatment Date</label>
                <input required type="date" value={form.treatment_date}
                  onChange={(e) => setForm((f) => ({ ...f, treatment_date: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-plum-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Claim Amount (₹)</label>
                <input required type="number" min="500" value={form.claim_amount}
                  onChange={(e) => setForm((f) => ({ ...f, claim_amount: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-plum-500"
                  placeholder="1500" />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Hospital / Clinic Name</label>
              <input type="text" value={form.hospital_name}
                onChange={(e) => setForm((f) => ({ ...f, hospital_name: e.target.value }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-plum-500"
                placeholder="Apollo Hospitals, City Clinic…" />
            </div>

            <div className="flex items-center gap-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_network}
                  onChange={(e) => setForm((f) => ({ ...f, is_network: e.target.checked }))}
                  className="w-4 h-4 text-plum-600 rounded" />
                <span className="text-sm text-gray-700">Network hospital (20% discount)</span>
              </label>
              {(form.claim_type === "diagnostic") && (
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={form.pre_auth_obtained}
                    onChange={(e) => setForm((f) => ({ ...f, pre_auth_obtained: e.target.checked }))}
                    className="w-4 h-4 text-plum-600 rounded" />
                  <span className="text-sm text-gray-700">Pre-authorisation obtained (MRI/CT)</span>
                </label>
              )}
            </div>

            {error && <p className="text-red-600 text-sm">{error}</p>}

            <button
              onClick={handleStep1Next}
              disabled={!form.treatment_date || !form.claim_amount}
              className="w-full bg-plum-600 hover:bg-plum-700 text-white font-medium py-2.5 rounded-lg transition disabled:opacity-50 flex items-center justify-center gap-2">
              Continue <ArrowRight size={16} />
            </button>
          </div>
        )}

        {/* Step 2: Documents */}
        {step === 2 && tempClaimId && (
          <div className="space-y-4">
            <DocumentUploader
              claimId={tempClaimId}
              memberId={member.id}
              claimType={form.claim_type}
              onUploaded={(doc) => setUploadedDocs((d) => [...d, doc])}
            />

            <div className="flex gap-3">
              <button onClick={() => setStep(1)}
                className="flex-1 border border-gray-300 text-gray-700 font-medium py-2.5 rounded-lg hover:bg-gray-50 transition flex items-center justify-center gap-2">
                <ArrowLeft size={16} /> Back
              </button>
              <button
                onClick={() => setStep(3)}
                disabled={uploadedDocs.length === 0}
                className="flex-2 bg-plum-600 hover:bg-plum-700 text-white font-medium py-2.5 px-6 rounded-lg transition disabled:opacity-50 flex items-center justify-center gap-2">
                Review <ArrowRight size={16} />
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Review + submit */}
        {step === 3 && !adjudicating && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
            <h2 className="font-semibold text-gray-900">Review Your Claim</h2>

            <div className="divide-y divide-gray-100">
              {[
                ["Type", CLAIM_TYPES.find((t) => t.value === form.claim_type)?.label || form.claim_type],
                ["Treatment Date", form.treatment_date],
                ["Hospital", form.hospital_name || "—"],
                ["Claim Amount", `₹${parseInt(form.claim_amount || "0").toLocaleString("en-IN")}`],
                ["Network Hospital", form.is_network ? "Yes (20% discount applies)" : "No"],
                ["Documents Uploaded", `${uploadedDocs.length} file(s)`],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between py-2.5 text-sm">
                  <span className="text-gray-500">{label}</span>
                  <span className="font-medium text-gray-900">{value}</span>
                </div>
              ))}
            </div>

            <div className="bg-plum-50 border border-plum-100 rounded-lg p-3 text-sm text-plum-700">
              Our AI will now review your claim against the policy terms. This usually takes 15-30 seconds.
            </div>

            {error && <p className="text-red-600 text-sm">{error}</p>}

            <div className="flex gap-3">
              <button onClick={() => setStep(2)}
                className="flex-1 border border-gray-300 text-gray-700 font-medium py-2.5 rounded-lg hover:bg-gray-50 transition">
                Back
              </button>
              <button onClick={handleSubmit}
                className="flex-2 bg-plum-600 hover:bg-plum-700 text-white font-medium py-2.5 px-8 rounded-lg transition">
                Submit &amp; Adjudicate
              </button>
            </div>
          </div>
        )}

        {/* Adjudication progress */}
        {adjudicating && (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-plum-600 mx-auto mb-6" />
            <h2 className="font-semibold text-gray-900 mb-4">Adjudicating Claim…</h2>
            <div className="space-y-2 text-left max-w-xs mx-auto">
              {ADJUDICATION_STEPS.map((s, i) => (
                <div key={i} className={`flex items-center gap-2 text-sm transition-all ${
                  i < adjStep ? "text-green-600" : i === adjStep ? "text-plum-600 font-medium" : "text-gray-300"
                }`}>
                  {i < adjStep ? <CheckCircle2 size={16} /> : (
                    <div className={`w-4 h-4 rounded-full border-2 ${i === adjStep ? "border-plum-600 animate-pulse" : "border-gray-200"}`} />
                  )}
                  {s}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
