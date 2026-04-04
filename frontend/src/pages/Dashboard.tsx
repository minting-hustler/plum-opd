import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { onAuth } from "../lib/auth";
import { logOut } from "../lib/auth";
import { getMemberByUid, listClaims } from "../lib/api";
import type { Member, Claim } from "../types";
import ClaimCard from "../components/ClaimCard";
import { PlusCircle, LogOut, ShieldCheck } from "lucide-react";

const CATEGORY_LABELS: Record<string, string> = {
  consultation: "Consultation",
  diagnostic: "Diagnostics",
  pharmacy: "Pharmacy",
  dental: "Dental",
  vision: "Vision",
  alternative: "Alternative Medicine",
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [member, setMember] = useState<Member | null>(null);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsub = onAuth(async (user) => {
      if (!user) { navigate("/login"); return; }
      try {
        const m = await getMemberByUid(user.uid);
        setMember(m);
        const { claims: c } = await listClaims({ member_id: m.id });
        setClaims(c);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    });
    return unsub;
  }, [navigate]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-plum-600" />
      </div>
    );
  }

  if (!member) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500">
        Member profile not found.
      </div>
    );
  }

  const usedPct = Math.min(100, (member.annual_used / member.annual_limit) * 100);
  const remaining = member.annual_limit - member.annual_used;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-plum-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">P</span>
            </div>
            <span className="font-semibold text-gray-900">Plum OPD Claims</span>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/admin" className="text-sm text-gray-500 hover:text-plum-600 flex items-center gap-1">
              <ShieldCheck size={16} /> Admin
            </Link>
            <button onClick={() => { logOut(); navigate("/login"); }}
              className="text-sm text-gray-500 hover:text-red-600 flex items-center gap-1">
              <LogOut size={16} /> Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {/* Welcome */}
        <div>
          <h2 className="text-xl font-bold text-gray-900">Welcome, {member.full_name.split(" ")[0]}</h2>
          <p className="text-gray-500 text-sm">Policy ID: PLUM_OPD_2024 · Employee: {member.employee_id}</p>
        </div>

        {/* Annual limit card */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-sm text-gray-500">Annual Benefit Used</p>
              <p className="text-2xl font-bold text-gray-900">
                ₹{member.annual_used.toLocaleString("en-IN")}
                <span className="text-base font-normal text-gray-400"> / ₹{member.annual_limit.toLocaleString("en-IN")}</span>
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">Remaining</p>
              <p className={`text-lg font-bold ${remaining < 10000 ? "text-red-600" : "text-green-600"}`}>
                ₹{remaining.toLocaleString("en-IN")}
              </p>
            </div>
          </div>
          <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${usedPct > 80 ? "bg-red-500" : usedPct > 50 ? "bg-yellow-500" : "bg-green-500"}`}
              style={{ width: `${usedPct}%` }}
            />
          </div>
          <p className="text-xs text-gray-400 mt-1">{usedPct.toFixed(1)}% used</p>

          {/* Per-category breakdown */}
          {Object.keys(member.category_used_ytd).length > 0 && (
            <div className="mt-4 grid grid-cols-3 gap-2">
              {Object.entries(member.category_used_ytd).map(([cat, amt]) => (
                <div key={cat} className="bg-gray-50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500">{CATEGORY_LABELS[cat] || cat}</p>
                  <p className="font-semibold text-sm text-gray-800">₹{amt.toLocaleString("en-IN")}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Claims list */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900">My Claims ({claims.length})</h3>
            <Link to="/claims/new"
              className="flex items-center gap-1.5 bg-plum-600 hover:bg-plum-700 text-white text-sm font-medium px-3 py-2 rounded-lg transition">
              <PlusCircle size={16} /> New Claim
            </Link>
          </div>

          {claims.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-10 text-center text-gray-400">
              No claims yet.{" "}
              <Link to="/claims/new" className="text-plum-600 hover:underline">Submit your first claim</Link>
            </div>
          ) : (
            <div className="space-y-3">
              {claims.map((claim) => (
                <ClaimCard key={claim.id} claim={claim} />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
