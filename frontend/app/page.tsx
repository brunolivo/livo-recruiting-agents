"use client";

import { useState, useEffect, useRef } from "react";
import type { Candidate, PipelineStats } from "@/lib/types";
import CandidateCard from "@/components/CandidateCard";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "https://recruitingagents.vercel.app";

type View = "form" | "running" | "results";

interface FormData {
  description: string;
  role_type: string;
  num_candidates: number;
}

interface ProgressEntry {
  stage: string;
  message: string;
}

const ROLE_OPTIONS = [
  {
    value: "AI Engineer",
    icon: "⚙️",
    desc: "LLMs, RAG, MLOps, production AI",
  },
  {
    value: "Data Scientist",
    icon: "📊",
    desc: "ML models, forecasting, analytics",
  },
  {
    value: "AI Product Manager",
    icon: "🎯",
    desc: "AI strategy & product roadmap",
  },
  {
    value: "AI Designer",
    icon: "🎨",
    desc: "Human-AI interaction design",
  },
];

const PIPELINE_STAGES = [
  { key: "job_spec", label: "Job Spec" },
  { key: "sourcing", label: "Sourcing" },
  { key: "enrichment", label: "Enrichment" },
  { key: "scoring", label: "Scoring" },
  { key: "outreach", label: "Outreach" },
];

function StageStatus({
  stage,
  currentStage,
  completedStages,
}: {
  stage: { key: string; label: string };
  currentStage: string;
  completedStages: Set<string>;
}) {
  const isActive = currentStage === stage.key;
  const isDone = completedStages.has(stage.key);

  return (
    <div className="flex flex-col items-center gap-1">
      <div
        className={`w-3 h-3 rounded-full transition-all ${
          isDone
            ? "bg-green-500"
            : isActive
            ? "bg-indigo-600 ring-4 ring-indigo-100"
            : "bg-gray-200"
        }`}
      />
      <span
        className={`text-xs font-medium hidden sm:block ${
          isDone
            ? "text-green-600"
            : isActive
            ? "text-indigo-600"
            : "text-gray-400"
        }`}
      >
        {stage.label}
      </span>
    </div>
  );
}

const STAGE_COLORS: Record<string, string> = {
  job_spec: "bg-violet-100 text-violet-700",
  sourcing: "bg-blue-100 text-blue-700",
  enrichment: "bg-cyan-100 text-cyan-700",
  scoring: "bg-amber-100 text-amber-700",
  outreach: "bg-green-100 text-green-700",
};

function getStageBadge(stage: string): string {
  return STAGE_COLORS[stage.toLowerCase()] ?? "bg-gray-100 text-gray-600";
}

export default function Home() {
  const [view, setView] = useState<View>("form");
  const [formData, setFormData] = useState<FormData>({
    description: "",
    role_type: "AI Engineer",
    num_candidates: 8,
  });
  const [progressLog, setProgressLog] = useState<ProgressEntry[]>([]);
  const [currentStage, setCurrentStage] = useState("");
  const [completedStages, setCompletedStages] = useState<Set<string>>(new Set());
  const [jobId, setJobId] = useState("");
  const [stats, setStats] = useState<PipelineStats | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [error, setError] = useState("");
  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll log to bottom
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [progressLog]);

  const runPipeline = async () => {
    setView("running");
    setProgressLog([]);
    setCompletedStages(new Set());
    setCurrentStage("");
    setError("");
    setJobId("");
    setStats(null);
    setCandidates([]);

    let res: Response;
    try {
      res = await fetch(`${API_URL}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to connect to the API. Please try again."
      );
      setView("form");
      return;
    }

    if (!res.ok) {
      setError(`API error: HTTP ${res.status}`);
      setView("form");
      return;
    }

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let currentEvent = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));

              if (currentEvent === "started") {
                setJobId(data.job_id ?? "");
              }

              if (currentEvent === "progress") {
                const stage = (data.stage ?? "").toLowerCase();
                setCurrentStage(stage);
                setProgressLog((prev) => [
                  ...prev,
                  { stage, message: data.message ?? "" },
                ]);
                // Mark previous stages as completed when we move to a new one
                const stageIndex = PIPELINE_STAGES.findIndex(
                  (s) => s.key === stage
                );
                if (stageIndex > 0) {
                  setCompletedStages((prev) => {
                    const next = new Set(prev);
                    PIPELINE_STAGES.slice(0, stageIndex).forEach((s) =>
                      next.add(s.key)
                    );
                    return next;
                  });
                }
              }

              if (currentEvent === "done") {
                setStats(data.stats ?? null);
                setCandidates(data.candidates ?? []);
                setCompletedStages(
                  new Set(PIPELINE_STAGES.map((s) => s.key))
                );
                setView("results");
              }

              if (currentEvent === "error") {
                setError(data.error ?? "An unknown error occurred.");
              }
            } catch {
              // malformed JSON — skip
            }
            currentEvent = "";
          }
        }
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Stream interrupted unexpectedly."
      );
    }
  };

  // ─── FORM VIEW ───────────────────────────────────────────────────────────
  if (view === "form") {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50 flex flex-col items-center px-4 py-16">
        <div className="w-full max-w-2xl">
          {/* Header */}
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 bg-indigo-600 text-white px-4 py-1.5 rounded-full text-sm font-semibold mb-4">
              <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
              Powered by AI Agents
            </div>
            <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight">
              <span className="text-indigo-600">Livo Health</span>
            </h1>
            <p className="text-lg text-gray-500 mt-2 font-medium">
              AI Recruiting Pipeline
            </p>
            <p className="text-sm text-gray-400 mt-1">
              Find, enrich, score, and reach out to top candidates — automatically.
            </p>
          </div>

          <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 space-y-7">
            {/* Role type */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-3">
                Role Type
              </label>
              <div className="grid grid-cols-2 gap-3">
                {ROLE_OPTIONS.map((role) => {
                  const selected = formData.role_type === role.value;
                  return (
                    <button
                      key={role.value}
                      type="button"
                      onClick={() =>
                        setFormData((f) => ({ ...f, role_type: role.value }))
                      }
                      className={`text-left p-4 rounded-xl border-2 transition-all ${
                        selected
                          ? "border-indigo-500 bg-indigo-50"
                          : "border-gray-100 hover:border-gray-200 hover:bg-gray-50"
                      }`}
                    >
                      <div className="text-2xl mb-1">{role.icon}</div>
                      <div
                        className={`text-sm font-semibold ${
                          selected ? "text-indigo-700" : "text-gray-800"
                        }`}
                      >
                        {role.value}
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">
                        {role.desc}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Job description */}
            <div>
              <label
                htmlFor="description"
                className="block text-sm font-semibold text-gray-700 mb-1.5"
              >
                Job Description
              </label>
              <textarea
                id="description"
                value={formData.description}
                onChange={(e) =>
                  setFormData((f) => ({ ...f, description: e.target.value }))
                }
                placeholder="Describe the ideal candidate — skills, experience, context about Livo Health…"
                rows={4}
                className="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none transition"
              />
            </div>

            {/* Num candidates */}
            <div>
              <label
                htmlFor="num_candidates"
                className="block text-sm font-semibold text-gray-700 mb-1.5"
              >
                Candidates to Source
              </label>
              <div className="flex items-center gap-3">
                <input
                  id="num_candidates"
                  type="number"
                  min={3}
                  max={15}
                  value={formData.num_candidates}
                  onChange={(e) =>
                    setFormData((f) => ({
                      ...f,
                      num_candidates: Math.max(
                        3,
                        Math.min(15, parseInt(e.target.value) || 8)
                      ),
                    }))
                  }
                  className="w-24 rounded-xl border border-gray-200 px-3 py-2 text-sm text-center font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
                <span className="text-xs text-gray-400">Between 3 and 15</span>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              onClick={runPipeline}
              disabled={!formData.description.trim()}
              className="w-full py-3.5 px-6 bg-indigo-600 text-white rounded-xl font-semibold text-base hover:bg-indigo-700 active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md shadow-indigo-200"
            >
              Find Candidates →
            </button>
          </div>
        </div>
      </main>
    );
  }

  // ─── RUNNING VIEW ─────────────────────────────────────────────────────────
  if (view === "running") {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50 flex flex-col items-center px-4 py-16">
        <div className="w-full max-w-2xl space-y-6">
          {/* Header */}
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-900">
              Running Pipeline
            </h1>
            <p className="text-sm text-gray-400 mt-1">
              Finding the best {formData.role_type} candidates for Livo Health
            </p>
            {jobId && (
              <p className="text-xs text-gray-300 mt-1 font-mono">
                Job ID: {jobId}
              </p>
            )}
          </div>

          {/* Stage progress bar */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm px-6 py-5">
            <div className="relative">
              {/* Connector line */}
              <div className="absolute top-1.5 left-0 right-0 h-0.5 bg-gray-100 mx-6" />
              <div className="relative flex justify-between">
                {PIPELINE_STAGES.map((stage) => (
                  <StageStatus
                    key={stage.key}
                    stage={stage}
                    currentStage={currentStage}
                    completedStages={completedStages}
                  />
                ))}
              </div>
              {/* Mobile labels */}
              <div className="flex justify-between mt-2 sm:hidden">
                {PIPELINE_STAGES.map((stage) => (
                  <span
                    key={stage.key}
                    className={`text-[10px] font-medium ${
                      completedStages.has(stage.key)
                        ? "text-green-600"
                        : currentStage === stage.key
                        ? "text-indigo-600"
                        : "text-gray-400"
                    }`}
                  >
                    {stage.label}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Pulsing indicator */}
          <div className="flex items-center gap-2 justify-center">
            <span className="flex gap-1">
              <span className="w-2 h-2 bg-indigo-600 rounded-full animate-bounce [animation-delay:0ms]" />
              <span className="w-2 h-2 bg-indigo-600 rounded-full animate-bounce [animation-delay:150ms]" />
              <span className="w-2 h-2 bg-indigo-600 rounded-full animate-bounce [animation-delay:300ms]" />
            </span>
            <span className="text-sm text-gray-500 font-medium">
              {currentStage
                ? `Running ${currentStage}…`
                : "Working…"}
            </span>
          </div>

          {/* Log */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-50 flex items-center justify-between">
              <span className="text-sm font-semibold text-gray-700">
                Activity Log
              </span>
              <span className="text-xs text-gray-400">
                {progressLog.length} events
              </span>
            </div>
            <div className="max-h-80 overflow-y-auto px-5 py-3 space-y-2">
              {progressLog.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">
                  Waiting for events…
                </p>
              ) : (
                progressLog.map((entry, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2.5 animate-fadeIn"
                  >
                    <span
                      className={`mt-0.5 px-2 py-0.5 rounded-md text-xs font-semibold flex-shrink-0 ${getStageBadge(
                        entry.stage
                      )}`}
                    >
                      {entry.stage}
                    </span>
                    <span className="text-sm text-gray-600 leading-snug">
                      {entry.message}
                    </span>
                  </div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 flex items-center justify-between">
              <span>{error}</span>
              <button
                onClick={() => { setError(""); setView("form"); }}
                className="text-red-500 hover:text-red-700 ml-4 font-medium text-xs"
              >
                Back
              </button>
            </div>
          )}
        </div>
      </main>
    );
  }

  // ─── RESULTS VIEW ─────────────────────────────────────────────────────────
  const recommended = candidates.filter((c) => c.recommended);
  const others = candidates.filter((c) => !c.recommended);
  const sortedCandidates = [...recommended, ...others];

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50">
      {/* Top bar */}
      <div className="sticky top-0 z-10 bg-white/90 backdrop-blur-sm border-b border-gray-100 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm font-bold text-gray-800">
              {formData.role_type}
            </span>
            <span className="text-gray-200">|</span>
            {stats ? (
              <>
                <StatChip label="sourced" value={stats.sourced} color="blue" />
                <StatChip label="enriched" value={stats.enriched} color="cyan" />
                <StatChip
                  label="recommended"
                  value={stats.recommended}
                  color="indigo"
                />
                <StatChip
                  label="outreach ready"
                  value={stats.outreached}
                  color="green"
                />
              </>
            ) : (
              <span className="text-sm text-gray-500">
                {candidates.length} candidates found
              </span>
            )}
          </div>
          <button
            onClick={() => {
              setView("form");
              setError("");
            }}
            className="text-sm font-medium text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 px-4 py-1.5 rounded-lg transition-colors self-start sm:self-auto"
          >
            ← New Search
          </button>
        </div>
      </div>

      {/* Candidates grid */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {sortedCandidates.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="text-5xl mb-4">🔍</div>
            <h2 className="text-xl font-bold text-gray-700">
              No candidates found
            </h2>
            <p className="text-gray-400 mt-2 max-w-sm">
              The pipeline ran but couldn&apos;t find matching candidates. Try
              broadening your job description or increasing the candidate count.
            </p>
            <button
              onClick={() => setView("form")}
              className="mt-6 px-6 py-2.5 bg-indigo-600 text-white rounded-xl font-medium text-sm hover:bg-indigo-700 transition-colors"
            >
              Try Again
            </button>
          </div>
        ) : (
          <>
            {recommended.length > 0 && (
              <div className="mb-8">
                <h2 className="text-sm font-bold text-gray-500 uppercase tracking-widest mb-4">
                  Top Recommendations
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {recommended.map((c, i) => (
                    <CandidateCard
                      key={`rec-${i}`}
                      candidate={c}
                      jobId={jobId}
                      apiUrl={API_URL}
                    />
                  ))}
                </div>
              </div>
            )}

            {others.length > 0 && (
              <div>
                {recommended.length > 0 && (
                  <h2 className="text-sm font-bold text-gray-500 uppercase tracking-widest mb-4">
                    Other Candidates
                  </h2>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {others.map((c, i) => (
                    <CandidateCard
                      key={`other-${i}`}
                      candidate={c}
                      jobId={jobId}
                      apiUrl={API_URL}
                    />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}

function StatChip({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: "blue" | "cyan" | "indigo" | "green";
}) {
  const styles = {
    blue: "bg-blue-50 text-blue-700 border-blue-100",
    cyan: "bg-cyan-50 text-cyan-700 border-cyan-100",
    indigo: "bg-indigo-50 text-indigo-700 border-indigo-100",
    green: "bg-green-50 text-green-700 border-green-100",
  };
  return (
    <span
      className={`px-2.5 py-1 rounded-full text-xs font-semibold border ${styles[color]}`}
    >
      {value} {label}
    </span>
  );
}
