"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { ApiClient } from "@/lib/api-client";
import { CompleteDashboardResponse, CaseSummary } from "@/lib/contracts";

export default function CaseOverviewPage() {
  const [data, setData] = useState<CompleteDashboardResponse | null>(null);
  const [casesList, setCasesList] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      const dashboard = await ApiClient.getCaseDashboard("CASE-S1-DEMO-001");
      const cases = await ApiClient.getCases();
      setData(dashboard);
      setCasesList(cases);
      setLoading(false);
    }
    loadData();
  }, []);

  if (loading || !data) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center min-h-[400px] font-mono text-cyan-400">
          <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mr-3" />
          <span>LOADING CASE OVERVIEW TELEMETRY...</span>
        </div>
      </DashboardLayout>
    );
  }

  const { caseSummary, detection, drift, attribution } = data;

  return (
    <DashboardLayout caseSummary={caseSummary}>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 font-mono text-xs">
        {/* CASE SUMMARY & PIPELINE STATUS CARD (8 COLS) */}
        <div className="lg:col-span-8 space-y-6">
          {/* MAIN CASE HEADER BANNER */}
          <div className="p-6 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-4 shadow-xl">
            <div className="flex flex-wrap justify-between items-start gap-4 border-b border-cyan-900/40 pb-4">
              <div>
                <span className="px-2.5 py-0.5 bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 rounded text-[11px]">
                  INCIDENT CASE ID: {caseSummary.caseId}
                </span>
                <h1 className="text-2xl font-bold text-white mt-2">
                  {caseSummary.title}
                </h1>
                <p className="text-slate-400 text-xs mt-1">
                  Region: {caseSummary.region}
                </p>
              </div>

              <div className="text-right space-y-1">
                <span className="px-3 py-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 rounded font-bold text-xs">
                  STATUS: {caseSummary.overallStatus}
                </span>
                <p className="text-[10px] text-slate-500">
                  Detected: {new Date(caseSummary.detectionTimestamp).toUTCString()}
                </p>
              </div>
            </div>

            {/* PIPELINE STAGE CARDS GRID */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
              {/* Phase 1 Status */}
              <div className="p-4 bg-[#030d1c] border border-cyan-900/50 rounded-lg space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-cyan-400 font-bold">PHASE 1 DETECT</span>
                  <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded text-[10px]">
                    {caseSummary.phase1Status}
                  </span>
                </div>
                <p className="text-slate-300 font-bold text-sm">
                  {detection.areaKm2} km² Slick Detected
                </p>
                <p className="text-[10px] text-slate-400">
                  Model: {detection.modelVersion}
                </p>
                <Link
                  href={`/cases/${caseSummary.caseId}/detection`}
                  className="inline-block mt-2 text-cyan-400 hover:text-cyan-300 text-[11px] underline"
                >
                  View Detection Screen ➔
                </Link>
              </div>

              {/* Phase 2 Status */}
              <div className="p-4 bg-[#030d1c] border border-cyan-900/50 rounded-lg space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-teal-400 font-bold">PHASE 2 DRIFT</span>
                  <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded text-[10px]">
                    {caseSummary.phase2Status}
                  </span>
                </div>
                <p className="text-slate-300 font-bold text-sm">
                  -48h Hindcast / +48h Forecast
                </p>
                <p className="text-[10px] text-slate-400">
                  Quality Score: {drift.currentWindQuality.qualityScore}%
                </p>
                <Link
                  href={`/cases/${caseSummary.caseId}/drift`}
                  className="inline-block mt-2 text-teal-400 hover:text-teal-300 text-[11px] underline"
                >
                  View Drift Screen ➔
                </Link>
              </div>

              {/* Phase 3 Status */}
              <div className="p-4 bg-[#030d1c] border border-cyan-900/50 rounded-lg space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-purple-400 font-bold">PHASE 3 AIS</span>
                  <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded text-[10px]">
                    {caseSummary.phase3Status}
                  </span>
                </div>
                <p className="text-slate-300 font-bold text-sm">
                  Top Rank: {attribution.topCandidates[0]?.candidateId} ({attribution.topCandidates[0]?.investigativeScore}% score)
                </p>
                <p className="text-[10px] text-slate-400">
                  {attribution.topCandidates.length} Candidates Evaluated
                </p>
                <Link
                  href={`/cases/${caseSummary.caseId}/attribution`}
                  className="inline-block mt-2 text-purple-400 hover:text-purple-300 text-[11px] underline"
                >
                  View Attribution Screen ➔
                </Link>
              </div>
            </div>
          </div>

          {/* ACTIVE CASES LIST */}
          <div className="p-6 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-4">
            <h2 className="text-sm font-bold text-cyan-400 uppercase tracking-wider">
              AVAILABLE INCIDENT CASES
            </h2>
            <div className="space-y-3">
              {casesList.map((c) => (
                <div
                  key={c.caseId}
                  className="p-4 bg-[#030d1c] border border-cyan-900/40 rounded-lg flex flex-wrap justify-between items-center gap-4 hover:border-cyan-500/50 transition"
                >
                  <div>
                    <span className="font-bold text-white">{c.caseId}</span> —{" "}
                    <span className="text-slate-300">{c.title}</span>
                    <p className="text-[10px] text-slate-400">{c.region}</p>
                  </div>
                  <div className="flex items-center space-x-3">
                    <span className="px-2 py-0.5 bg-cyan-950 text-cyan-400 border border-cyan-800 rounded text-[10px]">
                      {c.overallStatus}
                    </span>
                    <Link
                      href={`/cases/${c.caseId}/detection`}
                      className="px-3 py-1.5 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold rounded"
                    >
                      OPEN CASE ➔
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* RIGHT SIDEBAR: WARNINGS & SYSTEM DISCLAIMERS (4 COLS) */}
        <div className="lg:col-span-4 space-y-6">
          <div className="p-6 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-4">
            <h3 className="text-sm font-bold text-yellow-400 uppercase tracking-wider flex items-center space-x-2">
              <span>⚠️ SYSTEM WARNINGS & LIMITATIONS</span>
            </h3>
            <div className="space-y-3">
              {caseSummary.warnings.map((w, idx) => (
                <div key={idx} className="p-3 bg-yellow-950/30 border border-yellow-500/40 rounded text-yellow-200 text-xs">
                  {w}
                </div>
              ))}
            </div>
          </div>

          <div className="p-6 bg-[#06152b] border border-cyan-900/60 rounded-xl space-y-3">
            <h3 className="text-sm font-bold text-cyan-400 uppercase tracking-wider">
              PRIVACY & LEGAL PROTECTION
            </h3>
            <p className="text-slate-300 text-xs leading-relaxed">
              {attribution.privacyDisclaimer}
            </p>
            <div className="p-3 bg-[#030d1c] border border-cyan-900/40 rounded text-slate-400 text-[11px] italic">
              &quot;{attribution.legalDisclaimer}&quot;
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
