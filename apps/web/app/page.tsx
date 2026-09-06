"use client";

import { useState } from "react";

const phases = [
  { name: "Phase 1", label: "Oil Detection", status: "Ready" },
  { name: "Phase 2", label: "Source Reconstruction", status: "Ready" },
  { name: "Phase 3", label: "AIS Attribution", status: "Ready" },
];

export default function Home() {
  const [activePhase, setActivePhase] = useState("Phase 1");

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/95">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">VARUN</h1>
            <p className="text-xs text-slate-400">
              Vessel &amp; Oil Spill Analysis System
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
            <span className="text-sm text-slate-300">System Ready</span>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-8">
        {/* Page title */}
        <section className="mb-8">
          <p className="mb-2 text-sm font-medium text-cyan-400">
            MARITIME ANALYSIS PLATFORM
          </p>

          <h2 className="text-4xl font-bold tracking-tight">
            Investigation Dashboard
          </h2>

          <p className="mt-2 max-w-2xl text-slate-400">
            Detect oil slicks, reconstruct probable origins and attribute
            potential vessels using the VARUN analysis pipeline.
          </p>
        </section>

        {/* Phase navigation */}
        <section className="mb-8 grid gap-4 md:grid-cols-3">
          {phases.map((phase) => {
            const active = activePhase === phase.name;

            return (
              <button
                key={phase.name}
                onClick={() => setActivePhase(phase.name)}
                className={`rounded-xl border p-5 text-left transition ${
                  active
                    ? "border-cyan-500 bg-cyan-500/10"
                    : "border-slate-800 bg-slate-900 hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-cyan-400">
                    {phase.name}
                  </span>

                  <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-400">
                    {phase.status}
                  </span>
                </div>

                <h3 className="mt-4 text-xl font-semibold">
                  {phase.label}
                </h3>

                <p className="mt-1 text-sm text-slate-400">
                  Analysis pipeline stage
                </p>
              </button>
            );
          })}
        </section>

        {/* Main dashboard */}
        <section className="grid gap-6 lg:grid-cols-[1.7fr_1fr]">
          {/* Map / analysis area */}
          <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900">
            <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
              <div>
                <h3 className="font-semibold">Analysis View</h3>
                <p className="text-xs text-slate-500">
                  Active: {activePhase}
                </p>
              </div>

              <span className="rounded-md border border-slate-700 px-3 py-1 text-xs text-slate-400">
                LIVE DATA
              </span>
            </div>

            <div className="flex min-h-[430px] items-center justify-center bg-slate-950">
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full border border-cyan-500/30 bg-cyan-500/10 text-3xl">
                  ◉
                </div>

                <h4 className="text-lg font-semibold">
                  Geospatial Analysis Area
                </h4>

                <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
                  Map layers, detection regions, AIS tracks and analysis
                  artifacts will appear here after backend integration.
                </p>
              </div>
            </div>
          </div>

          {/* Run information */}
          <div className="space-y-6">
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <h3 className="font-semibold">Analysis Run</h3>

              <div className="mt-5 space-y-4">
                <Info label="Status" value="READY" />
                <Info label="Phase" value={activePhase} />
                <Info label="Data Origin" value="REAL / SYNTHETIC / MIXED" />
                <Info label="Run ID" value="Waiting for backend" />
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <h3 className="font-semibold">Pipeline</h3>

              <div className="mt-5 space-y-4">
                <PipelineStep
                  number="01"
                  title="Detection"
                  description="Identify oil-like regions"
                />
                <PipelineStep
                  number="02"
                  title="Reconstruction"
                  description="Estimate probable source"
                />
                <PipelineStep
                  number="03"
                  title="Attribution"
                  description="Rank AIS vessel candidates"
                />
              </div>
            </div>
          </div>
        </section>

        {/* Metrics */}
        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Metric title="Detections" value="—" />
          <Metric title="Origin Regions" value="—" />
          <Metric title="AIS Candidates" value="—" />
          <Metric title="Confidence" value="—" />
        </section>
      </div>
    </main>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-800 pb-3">
      <span className="text-sm text-slate-500">{label}</span>
      <span className="max-w-[60%] text-right text-sm font-medium text-slate-200">
        {value}
      </span>
    </div>
  );
}

function PipelineStep({
  number,
  title,
  description,
}: {
  number: string;
  title: string;
  description: string;
}) {
  return (
    <div className="flex gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-800 text-xs text-cyan-400">
        {number}
      </div>

      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-slate-500">{description}</p>
      </div>
    </div>
  );
}

function Metric({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-2 text-2xl font-bold">{value}</p>
    </div>
  );
}