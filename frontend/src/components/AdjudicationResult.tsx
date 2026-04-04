import { useState } from "react";
import type { AdjudicationResult, StepResult } from "../types";
import { REJECTION_LABELS } from "../types";
import {
  CheckCircle2, XCircle, AlertTriangle, ChevronDown, ChevronUp,
  ShieldCheck, FileText, Stethoscope, Calculator, Brain
} from "lucide-react";

const DECISION_CONFIG = {
  APPROVED: {
    label: "Approved",
    bg: "bg-green-50",
    border: "border-green-200",
    text: "text-green-700",
    icon: <CheckCircle2 size={28} className="text-green-500" />,
  },
  REJECTED: {
    label: "Rejected",
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-700",
    icon: <XCircle size={28} className="text-red-500" />,
  },
  PARTIAL: {
    label: "Partially Approved",
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    text: "text-yellow-700",
    icon: <CheckCircle2 size={28} className="text-yellow-500" />,
  },
  MANUAL_REVIEW: {
    label: "Under Manual Review",
    bg: "bg-orange-50",
    border: "border-orange-200",
    text: "text-orange-700",
    icon: <AlertTriangle size={28} className="text-orange-500" />,
  },
};

const STEP_CONFIG: { key: string; label: string; icon: React.ReactNode }[] = [
  { key: "step1", label: "Eligibility Check", icon: <ShieldCheck size={16} /> },
  { key: "step2", label: "Document Validation", icon: <FileText size={16} /> },
  { key: "step3", label: "Coverage Verification", icon: <Stethoscope size={16} /> },
  { key: "step4", label: "Limit Calculation", icon: <Calculator size={16} /> },
  { key: "step5", label: "Medical Necessity", icon: <Brain size={16} /> },
];

function StepAccordion({ stepKey, label, icon, result }: {
  stepKey: string; label: string; icon: React.ReactNode; result?: StepResult
}) {
  const [open, setOpen] = useState(false);
  if (!result) return null;

  return (
    <div className="border border-gray-100 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition text-left">
        <div className="flex items-center gap-2">
          <span className={result.passed ? "text-green-500" : "text-red-500"}>{icon}</span>
          <span className="text-sm font-medium text-gray-800">{label}</span>
          {!result.passed && (
            <span className="text-xs bg-red-100 text-red-600 px-1.5 py-0.5 rounded">Failed</span>
          )}
          {result.passed && result.warnings?.length > 0 && (
            <span className="text-xs bg-yellow-100 text-yellow-600 px-1.5 py-0.5 rounded">{result.warnings.length} warning{result.warnings.length > 1 ? "s" : ""}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">{(result.confidence * 100).toFixed(0)}%</span>
          {open ? <ChevronUp size={14} className="text-gray-400" /> : <ChevronDown size={14} className="text-gray-400" />}
        </div>
      </button>

      {open && (
        <div className="px-4 pb-3 bg-gray-50 border-t border-gray-100 space-y-2">
          {result.reasons?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-red-600 mb-1">Issues Found</p>
              {result.reasons.map((r) => (
                <p key={r} className="text-xs text-red-700 bg-red-50 rounded px-2 py-1 mb-1">
                  {REJECTION_LABELS[r] || r}
                </p>
              ))}
            </div>
          )}
          {result.warnings?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-yellow-600 mb-1">Warnings</p>
              {result.warnings.map((w, i) => (
                <p key={i} className="text-xs text-yellow-700 bg-yellow-50 rounded px-2 py-1 mb-1">{w}</p>
              ))}
            </div>
          )}
          {result.passed && result.reasons?.length === 0 && result.warnings?.length === 0 && (
            <p className="text-xs text-green-600">All checks passed.</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function AdjudicationResultCard({ result }: { result: AdjudicationResult }) {
  const cfg = DECISION_CONFIG[result.decision as keyof typeof DECISION_CONFIG] || DECISION_CONFIG.REJECTED;

  return (
    <div className="space-y-4">
      {/* Main decision card */}
      <div className={`rounded-xl border ${cfg.border} ${cfg.bg} p-6`}>
        <div className="flex items-center gap-3 mb-4">
          {cfg.icon}
          <div>
            <h2 className={`text-xl font-bold ${cfg.text}`}>{cfg.label}</h2>
            <p className="text-sm text-gray-600">
              Confidence: {(result.confidence_score * 100).toFixed(0)}%
            </p>
          </div>
        </div>

        {/* Amount breakdown */}
        {result.decision !== "REJECTED" && result.approved_amount > 0 && (
          <div className="bg-white rounded-lg p-4 mb-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Claim Amount</span>
              <span className="font-medium">₹{(result.approved_amount + result.copay_amount + result.network_discount).toLocaleString("en-IN")}</span>
            </div>
            {result.copay_amount > 0 && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Co-pay Deducted</span>
                <span className="text-red-600">− ₹{result.copay_amount.toLocaleString("en-IN")}</span>
              </div>
            )}
            {result.network_discount > 0 && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Network Discount</span>
                <span className="text-red-600">− ₹{result.network_discount.toLocaleString("en-IN")}</span>
              </div>
            )}
            <div className="flex justify-between text-base font-bold border-t border-gray-100 pt-2">
              <span>Approved Amount</span>
              <span className="text-green-600">₹{result.approved_amount.toLocaleString("en-IN")}</span>
            </div>
          </div>
        )}

        {/* Notes from Gemini */}
        {result.notes && (
          <p className="text-sm text-gray-700 mb-3">{result.notes}</p>
        )}

        {/* Rejection reasons */}
        {result.rejection_reasons?.length > 0 && (
          <div className="space-y-1 mb-3">
            {result.rejection_reasons.map((r) => (
              <div key={r} className="flex items-start gap-2 text-sm text-red-700 bg-white/60 rounded px-3 py-2">
                <XCircle size={14} className="mt-0.5 flex-shrink-0" />
                {REJECTION_LABELS[r] || r}
              </div>
            ))}
          </div>
        )}

        {/* Fraud flags */}
        {result.fraud_flags?.length > 0 && (
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 mb-3">
            <p className="text-xs font-semibold text-orange-700 mb-1">Fraud Indicators Detected</p>
            {result.fraud_flags.map((f) => (
              <p key={f} className="text-xs text-orange-600">{f.replace(/_/g, " ")}</p>
            ))}
          </div>
        )}

        {/* Next steps */}
        {result.next_steps && (
          <div className="bg-white/70 rounded-lg px-3 py-2 text-sm text-gray-700">
            <span className="font-medium">Next steps: </span>{result.next_steps}
          </div>
        )}
      </div>

      {/* Step-by-step accordion */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-semibold text-gray-900 mb-3">Adjudication Breakdown</h3>
        <div className="space-y-2">
          {STEP_CONFIG.map((s) => (
            <StepAccordion
              key={s.key}
              stepKey={s.key}
              label={s.label}
              icon={s.icon}
              result={result.step_results?.[s.key] as StepResult | undefined}
            />
          ))}
        </div>
      </div>

      {/* Policy basis (RAG chunks used) */}
      {result.retrieved_chunks_used?.length > 0 && (
        <details className="bg-white rounded-xl border border-gray-200">
          <summary className="px-5 py-3 text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-50 rounded-xl">
            Policy Context Used ({result.retrieved_chunks_used.length} chunks)
          </summary>
          <div className="px-5 pb-4 space-y-2">
            {result.retrieved_chunks_used.slice(0, 5).map((chunk, i) => (
              <p key={i} className="text-xs text-gray-500 bg-gray-50 rounded p-2 leading-relaxed">
                {chunk.slice(0, 200)}{chunk.length > 200 ? "…" : ""}
              </p>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
