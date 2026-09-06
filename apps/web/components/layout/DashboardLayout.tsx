"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CaseSummary } from "@/lib/contracts";

interface DashboardLayoutProps {
  caseSummary?: CaseSummary;
  children: React.ReactNode;
}

export default function DashboardLayout({ caseSummary, children }: DashboardLayoutProps) {
  const pathname = usePathname();
  const caseId = caseSummary?.caseId || "CASE-S1-DEMO-001";

  const navItems = [
    { label: "1. OVERVIEW", href: `/cases`, tag: "SUMMARY", active: pathname === "/cases" || pathname === `/cases/${caseId}` },
    { label: "2. PHASE 1 DETECT", href: `/cases/${caseId}/detection`, tag: "SAR U-NET", active: pathname.includes("/detection") },
    { label: "3. PHASE 2 DRIFT", href: `/cases/${caseId}/drift`, tag: "OPENOIL", active: pathname.includes("/drift") },
    { label: "4. PHASE 3 ATTRIBUTION", href: `/cases/${caseId}/attribution`, tag: "TOP-3 AIS", active: pathname.includes("/attribution") },
  ];

  return (
    <div className="min-h-screen bg-[#030914] text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-slate-950">
      {/* TOP SYSTEM HEADER */}
      <header className="px-6 py-3.5 bg-[#061224] border-b border-cyan-900/40 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center space-x-4">
          <Link href="/" className="flex items-center space-x-2 text-cyan-400 hover:text-cyan-300 font-mono text-xs transition">
            <span>← VARUN-ASTRA HOME</span>
          </Link>
          <span className="text-cyan-900">|</span>
          <div className="flex items-center space-x-2">
            <span className="font-mono text-sm font-extrabold tracking-wider text-white">
              VARUN-ASTRA
            </span>
            <span className="text-xs font-mono text-cyan-400 font-bold bg-cyan-950 px-2 py-0.5 rounded border border-cyan-800">
              FOUR-SCREEN EVIDENCE DASHBOARD
            </span>
          </div>
        </div>

        {/* CASE SUMMARY HEADER BADGES */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 text-xs font-mono">
            <span className="text-slate-400">SELECTED CASE:</span>
            <span className="bg-[#0b1a30] text-cyan-300 border border-cyan-800 px-2.5 py-1 rounded font-bold">
              {caseId}
            </span>
          </div>

          <div className="flex items-center space-x-2 px-3 py-1 bg-emerald-950/60 border border-emerald-500/40 rounded text-xs font-mono text-emerald-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>OFFLINE REPLAY READY</span>
          </div>
        </div>
      </header>

      {/* PHASE NAVIGATION TAB BAR */}
      <nav className="bg-[#050e1d] border-b border-cyan-900/30 px-6 py-2 flex items-center space-x-2 z-30">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`px-4 py-2 text-xs font-mono font-bold rounded-lg transition flex items-center space-x-2 ${
              item.active
                ? "bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20"
                : "text-slate-400 hover:text-slate-200 hover:bg-[#0a1b33]"
            }`}
          >
            <span>{item.label}</span>
            <span className={`px-1.5 py-0.2 text-[10px] rounded ${
              item.active ? "bg-slate-900/40 text-slate-950" : "bg-cyan-500/20 text-cyan-400"
            }`}>
              {item.tag}
            </span>
          </Link>
        ))}
      </nav>

      {/* MAIN SCREEN BODY */}
      <main className="flex-1 p-4 lg:p-6">{children}</main>
    </div>
  );
}
