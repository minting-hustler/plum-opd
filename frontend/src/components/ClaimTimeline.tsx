import type { Claim } from "../types";
import { FileText, Cpu, CheckCircle2, XCircle, AlertTriangle, Clock } from "lucide-react";

const STEPS = [
  { key: "submitted", label: "Submitted", icon: FileText },
  { key: "processing", label: "Processing", icon: Cpu },
  { key: "decided", label: "Decision", icon: CheckCircle2 },
];

function getActiveStep(status: string) {
  if (status === "PENDING") return 0;
  if (status === "PROCESSING") return 1;
  return 2;
}

export default function ClaimTimeline({ claim }: { claim: Claim }) {
  const active = getActiveStep(claim.status);

  const decisionIcon = () => {
    if (claim.status === "APPROVED") return <CheckCircle2 size={20} className="text-green-500" />;
    if (claim.status === "REJECTED") return <XCircle size={20} className="text-red-500" />;
    if (claim.status === "MANUAL_REVIEW") return <AlertTriangle size={20} className="text-orange-500" />;
    if (claim.status === "PARTIAL") return <CheckCircle2 size={20} className="text-yellow-500" />;
    return <Clock size={20} className="text-gray-300" />;
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center">
        {STEPS.map((step, i) => {
          const Icon = step.icon;
          const done = i < active;
          const current = i === active;
          const pending = i > active;
          return (
            <div key={step.key} className="flex items-center flex-1">
              <div className="flex flex-col items-center">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center
                  ${done ? "bg-green-100" : current ? "bg-plum-100" : "bg-gray-100"}`}>
                  {i === 2 && current ? decisionIcon() : (
                    <Icon size={18} className={done ? "text-green-600" : current ? "text-plum-600" : "text-gray-300"} />
                  )}
                </div>
                <span className={`text-xs mt-1 font-medium ${done ? "text-green-600" : current ? "text-plum-600" : "text-gray-300"}`}>
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-0.5 mx-2 ${done ? "bg-green-300" : "bg-gray-200"}`} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
