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
  location: string;
}

interface ProgressEntry {
  stage: string;
  message: string;
}

const ROLE_OPTIONS = [
  { value: "AI Engineer",         icon: "⚙️", desc: "LLMs, RAG, MLOps, production AI" },
  { value: "Data Scientist",      icon: "📊", desc: "ML models, forecasting, analytics" },
  { value: "AI Product Manager",  icon: "🎯", desc: "AI strategy & product roadmap" },
  { value: "AI Designer",         icon: "🎨", desc: "Human-AI interaction design" },
];

const EXAMPLE_PROMPTS: Record<string, { label: string; text: string }[]> = {
  "AI Engineer": [
    { label: "Senior LLM engineer", text: "Senior AI engineer with 5+ years experience building LLM-powered products. Strong in Python, RAG pipelines, and deploying models to production. Healthcare or regulated industry background is a plus." },
    { label: "MLOps / infra",        text: "MLOps engineer who can own our model deployment infrastructure. Experience with model serving, monitoring, and CI/CD for ML. PyTorch and HuggingFace ecosystem." },
    { label: "NLP specialist",       text: "NLP engineer specialising in text classification, entity extraction, and fine-tuning transformer models. Experience with clinical or medical text is highly valued." },
  ],
  "Data Scientist": [
    { label: "Applied ML scientist", text: "Applied data scientist with strong ML fundamentals — forecasting, classification, and experimentation. Experience in healthcare data or marketplace dynamics preferred." },
    { label: "Demand forecasting",   text: "Data scientist with deep experience in demand forecasting and time-series modelling. Comfortable owning end-to-end: from data cleaning to model deployment." },
  ],
  "AI Product Manager": [
    { label: "AI PM – growth stage", text: "AI Product Manager who has shipped LLM-powered features in a fast-moving startup. Comfortable writing prompts, reading model evals, and aligning engineering and business goals." },
    { label: "Healthcare tech PM",   text: "Product Manager with experience in healthcare SaaS or staffing technology. Strong data intuition and track record of driving adoption of AI features." },
  ],
  "AI Designer": [
    { label: "AI UX designer", text: "UX designer who has designed interfaces for AI-assisted workflows — chatbots, recommendation systems, or automated scheduling. Strong in Figma and user research." },
  ],
};

const PIPELINE_STAGES = [
  { key: "job_spec",    label: "Job Spec"   },
  { key: "sourcing",   label: "Sourcing"   },
  { key: "enrichment", label: "Enrichment" },
  { key: "scoring",    label: "Scoring"    },
  { key: "outreach",   label: "Outreach"   },
];

function StageStatus({
  stage, currentStage, completedStages,
}: {
  stage: { key: string; label: string };
  currentStage: string;
  completedStages: Set<string>;
}) {
  const isActive = currentStage === stage.key;
  const isDone   = completedStages.has(stage.key);
  return (
    <div className="flex flex-col items-center gap-1">
      <div className={`w-3 h-3 rounded-full transition-all duration-200 ${
        isDone   ? "bg-livo-success" :
        isActive ? "bg-livo-primary ring-4 ring-livo-primary-light" :
                   "bg-livo-bg-secondary"
      }`} />
      <span className={`text-xs font-medium hidden sm:block ${
        isDone   ? "text-livo-success" :
        isActive ? "text-livo-primary" :
                   "text-livo-text-muted"
      }`}>
        {stage.label}
      </span>
    </div>
  );
}

const STAGE_COLORS: Record<string, string> = {
  job_spec:    "bg-livo-primary-light text-livo-primary",
  sourcing:    "bg-blue-50 text-blue-700",
  enrichment:  "bg-cyan-50 text-cyan-700",
  scoring:     "bg-amber-50 text-amber-700",
  outreach:    "bg-emerald-50 text-emerald-700",
};
function getStageBadge(stage: string) {
  return STAGE_COLORS[stage.toLowerCase()] ?? "bg-livo-bg-secondary text-livo-text-secondary";
}

export default function Home() {
  const [view, setView]             = useState<View>("form");
  const [formData, setFormData]     = useState<FormData>({ description: "", role_type: "AI Engineer", num_candidates: 8, location: "" });
  const [progressLog, setProgressLog]         = useState<ProgressEntry[]>([]);
  const [currentStage, setCurrentStage]       = useState("");
  const [completedStages, setCompletedStages] = useState<Set<string>>(new Set());
  const [jobId, setJobId]       = useState("");
  const [stats, setStats]       = useState<PipelineStats | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [error, setError]       = useState("");
  const logEndRef               = useRef<HTMLDivElement>(null);

  const [starred, setStarred]                     = useState<Set<string>>(new Set());
  const [viewMode, setViewMode]                   = useState<"grid" | "list">("grid");
  const [filterRecommended, setFilterRecommended] = useState(false);
  const [filterStarred, setFilterStarred]         = useState(false);
  const [filterSource, setFilterSource]           = useState("all");
  const [filterMinScore, setFilterMinScore]       = useState(0);

  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [progressLog]);

  const runPipeline = async () => {
    setView("running");
    setProgressLog([]); setCompletedStages(new Set()); setCurrentStage("");
    setError(""); setJobId(""); setStats(null); setCandidates([]);

    let res: Response;
    try {
      res = await fetch(`${API_URL}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...formData, location: formData.location.trim() || undefined }),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect to the API. Please try again.");
      setView("form"); return;
    }
    if (!res.ok) { setError(`API error: HTTP ${res.status}`); setView("form"); return; }

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "", currentEvent = "";
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n"); buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (line.startsWith("event: ")) { currentEvent = line.slice(7).trim(); }
          else if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (currentEvent === "started")  { setJobId(data.job_id ?? ""); }
              if (currentEvent === "progress") {
                const stage = (data.stage ?? "").toLowerCase();
                setCurrentStage(stage);
                setProgressLog((prev) => [...prev, { stage, message: data.message ?? "" }]);
                const idx = PIPELINE_STAGES.findIndex((s) => s.key === stage);
                if (idx > 0) setCompletedStages((prev) => { const n = new Set(prev); PIPELINE_STAGES.slice(0, idx).forEach((s) => n.add(s.key)); return n; });
              }
              if (currentEvent === "done") {
                setStats(data.stats ?? null); setCandidates(data.candidates ?? []);
                setCompletedStages(new Set(PIPELINE_STAGES.map((s) => s.key))); setView("results");
              }
              if (currentEvent === "error") { setError(data.error ?? "An unknown error occurred."); }
            } catch { /* skip */ }
            currentEvent = "";
          }
        }
      }
    } catch (err) { setError(err instanceof Error ? err.message : "Stream interrupted unexpectedly."); }
  };

  // ─── FORM VIEW ───────────────────────────────────────────────────────────
  if (view === "form") {
    const examples = EXAMPLE_PROMPTS[formData.role_type] ?? [];
    return (
      <main className="min-h-screen bg-livo-bg-page flex flex-col items-center px-4 py-12">
        <div className="w-full max-w-2xl">
          <div className="text-center mb-8">
            <div className="inline-flex items-center gap-2 bg-livo-primary text-white px-4 py-1.5 rounded-full text-sm font-semibold mb-5">
              <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
              Livo Hunter
            </div>
            <h1 className="font-display text-4xl font-semibold text-livo-slate tracking-tight leading-tight">
              Find your next<br />
              <span className="text-livo-primary">AI hire</span>
            </h1>
            <p className="text-sm text-livo-text-muted mt-3 max-w-md mx-auto leading-relaxed">
              Describe the role and we&apos;ll search GitHub, HuggingFace, and ArXiv for real candidates — scored, ranked, and outreach-ready.
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-card border border-black/10 p-8 space-y-6">
            {/* Role type */}
            <div>
              <label className="block text-sm font-semibold text-livo-slate mb-3">What role are you hiring for?</label>
              <div className="grid grid-cols-2 gap-3">
                {ROLE_OPTIONS.map((role) => {
                  const selected = formData.role_type === role.value;
                  return (
                    <button key={role.value} type="button"
                      onClick={() => setFormData((f) => ({ ...f, role_type: role.value }))}
                      className={`text-left p-4 rounded-lg border-2 transition-all duration-200 ${
                        selected ? "border-livo-primary bg-livo-primary-light" : "border-black/10 hover:border-livo-primary/30 hover:bg-livo-bg-page"
                      }`}>
                      <div className="text-2xl mb-1">{role.icon}</div>
                      <div className={`text-sm font-semibold ${selected ? "text-livo-primary" : "text-livo-slate"}`}>{role.value}</div>
                      <div className="text-xs text-livo-text-muted mt-0.5">{role.desc}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Location */}
            <div>
              <label htmlFor="location" className="block text-sm font-semibold text-livo-slate mb-1.5">
                Location
                <span className="ml-1.5 text-xs font-normal text-livo-text-muted">optional — leave blank for global search</span>
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-livo-text-muted text-base">📍</span>
                <input id="location" type="text" value={formData.location}
                  onChange={(e) => setFormData((f) => ({ ...f, location: e.target.value }))}
                  placeholder="Barcelona, Spain"
                  className="w-full rounded-lg border border-black/10 pl-9 pr-4 py-3 text-sm text-livo-slate placeholder-livo-text-muted focus:outline-none focus:ring-2 focus:ring-livo-primary focus:border-transparent transition-all duration-200"
                />
              </div>
            </div>

            {/* Job description */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="description" className="block text-sm font-semibold text-livo-slate">Role description</label>
                <span className="text-xs text-livo-text-muted">Be specific — skills, seniority, domain</span>
              </div>
              {examples.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-2">
                  {examples.map((ex) => (
                    <button key={ex.label} type="button"
                      onClick={() => setFormData((f) => ({ ...f, description: ex.text }))}
                      className="text-xs px-3 py-1.5 rounded-full border border-livo-primary/30 bg-livo-primary-light text-livo-primary hover:bg-livo-primary/20 transition-colors duration-200 font-medium">
                      {ex.label} ↗
                    </button>
                  ))}
                </div>
              )}
              <textarea id="description" value={formData.description}
                onChange={(e) => setFormData((f) => ({ ...f, description: e.target.value }))}
                placeholder={`Example: "Senior AI engineer with 4+ years experience building LLM-powered products. Strong Python and RAG skills. Healthcare or regulated industry background preferred."\n\nTips:\n• Include seniority (junior / mid / senior / staff)\n• Mention must-have skills vs nice-to-haves\n• Add domain context (healthcare, fintech, …)\n• Specify remote / hybrid / on-site`}
                rows={7}
                className="w-full rounded-lg border border-black/10 px-4 py-3 text-sm text-livo-slate placeholder-livo-text-muted focus:outline-none focus:ring-2 focus:ring-livo-primary focus:border-transparent resize-none transition-all duration-200 leading-relaxed"
              />
            </div>

            {/* Num candidates + sources */}
            <div className="flex items-center justify-between gap-4">
              <div>
                <label htmlFor="num_candidates" className="block text-xs font-semibold text-livo-text-muted uppercase tracking-wide mb-1.5">Candidates</label>
                <div className="flex items-center gap-2">
                  <input id="num_candidates" type="number" min={3} max={15} value={formData.num_candidates}
                    onChange={(e) => setFormData((f) => ({ ...f, num_candidates: Math.max(3, Math.min(15, parseInt(e.target.value) || 8)) }))}
                    className="w-20 rounded-lg border border-black/10 px-3 py-2 text-sm text-center font-semibold text-livo-slate focus:outline-none focus:ring-2 focus:ring-livo-primary focus:border-transparent"
                  />
                  <span className="text-xs text-livo-text-muted">3–15</span>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs font-semibold text-livo-text-muted uppercase tracking-wide mb-1.5">Searches</p>
                <div className="flex items-center gap-1.5 justify-end">
                  {["GitHub", "HuggingFace", "ArXiv"].map((src) => (
                    <span key={src} className="text-xs px-2 py-1 rounded-md bg-livo-bg-secondary text-livo-text-secondary font-medium">{src}</span>
                  ))}
                </div>
              </div>
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-livo-danger">{error}</div>
            )}

            <button onClick={runPipeline} disabled={!formData.description.trim()}
              className="w-full py-3.5 px-6 bg-livo-primary text-white rounded-full font-semibold text-base hover:bg-livo-primary-hover active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 shadow-card">
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
      <main className="min-h-screen bg-livo-bg-page flex flex-col items-center px-4 py-16">
        <div className="w-full max-w-2xl space-y-6">
          <div className="text-center">
            <h1 className="font-display text-2xl font-semibold text-livo-slate">Running Pipeline</h1>
            <p className="text-sm text-livo-text-muted mt-1">Finding the best {formData.role_type} candidates for Livo Health</p>
            {jobId && <p className="text-xs text-livo-text-muted/60 mt-1 font-mono">Job ID: {jobId}</p>}
          </div>

          <div className="bg-white rounded-lg border border-black/10 shadow-card px-6 py-5">
            <div className="relative">
              <div className="absolute top-1.5 left-0 right-0 h-0.5 bg-livo-bg-secondary mx-6" />
              <div className="relative flex justify-between">
                {PIPELINE_STAGES.map((stage) => (
                  <StageStatus key={stage.key} stage={stage} currentStage={currentStage} completedStages={completedStages} />
                ))}
              </div>
              <div className="flex justify-between mt-2 sm:hidden">
                {PIPELINE_STAGES.map((stage) => (
                  <span key={stage.key} className={`text-[10px] font-medium ${
                    completedStages.has(stage.key) ? "text-livo-success" :
                    currentStage === stage.key    ? "text-livo-primary" : "text-livo-text-muted"
                  }`}>{stage.label}</span>
                ))}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 justify-center">
            <span className="flex gap-1">
              <span className="w-2 h-2 bg-livo-primary rounded-full animate-bounce [animation-delay:0ms]" />
              <span className="w-2 h-2 bg-livo-primary rounded-full animate-bounce [animation-delay:150ms]" />
              <span className="w-2 h-2 bg-livo-primary rounded-full animate-bounce [animation-delay:300ms]" />
            </span>
            <span className="text-sm text-livo-text-secondary font-medium">
              {currentStage ? `Running ${currentStage}…` : "Working…"}
            </span>
          </div>

          <div className="bg-white rounded-lg border border-black/10 shadow-card overflow-hidden">
            <div className="px-5 py-3 border-b border-black/5 flex items-center justify-between">
              <span className="text-sm font-semibold text-livo-slate">Activity Log</span>
              <span className="text-xs text-livo-text-muted">{progressLog.length} events</span>
            </div>
            <div className="max-h-80 overflow-y-auto px-5 py-3 space-y-2">
              {progressLog.length === 0 ? (
                <p className="text-sm text-livo-text-muted text-center py-4">Waiting for events…</p>
              ) : (
                progressLog.map((entry, i) => (
                  <div key={i} className="flex items-start gap-2.5 animate-fadeIn">
                    <span className={`mt-0.5 px-2 py-0.5 rounded-md text-xs font-semibold flex-shrink-0 ${getStageBadge(entry.stage)}`}>
                      {entry.stage}
                    </span>
                    <span className="text-sm text-livo-text-secondary leading-snug">{entry.message}</span>
                  </div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
          </div>

          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-livo-danger flex items-center justify-between">
              <span>{error}</span>
              <button onClick={() => { setError(""); setView("form"); }}
                className="text-livo-danger hover:text-red-700 ml-4 font-medium text-xs">Back</button>
            </div>
          )}
        </div>
      </main>
    );
  }

  // ─── RESULTS VIEW ─────────────────────────────────────────────────────────
  const sortedCandidates = [...candidates].sort((a, b) => b.fit_score - a.fit_score);
  const sources          = Array.from(new Set(candidates.map((c) => c.source)));
  const filtered = sortedCandidates.filter((c) => {
    if (filterRecommended && !c.recommended)              return false;
    if (filterStarred && !starred.has(c.name))            return false;
    if (filterSource !== "all" && c.source !== filterSource) return false;
    if (c.fit_score < filterMinScore)                     return false;
    return true;
  });
  const toggleStar = (name: string) =>
    setStarred((prev) => { const s = new Set(prev); s.has(name) ? s.delete(name) : s.add(name); return s; });

  const exportCSV = () => {
    const rows = [
      ["Name","Source","Profile URL","Location","Email","Score","Technical","Culture","Recommended","Skills","Notable Work","Outreach Subject","Outreach Message"],
      ...filtered.map((c) => [
        c.name, c.source, c.profile_url ?? "", c.location ?? "", c.email ?? "",
        c.fit_score, c.technical_score, c.culture_score, c.recommended ? "Yes" : "No",
        c.skills.join("; "), c.notable_work ?? "", c.outreach_subject ?? "", c.outreach_message ?? "",
      ]),
    ];
    const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a"); a.href = url; a.download = "livo-hunter-candidates.csv"; a.click();
  };

  return (
    <main className="min-h-screen bg-livo-bg-page">
      <div className="sticky top-0 z-10 bg-white/95 backdrop-blur-sm border-b border-black/10 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="font-display text-sm font-bold text-livo-slate">{formData.role_type}</span>
              {formData.location && <span className="text-xs text-livo-text-muted">📍 {formData.location}</span>}
              <span className="text-livo-bg-secondary">|</span>
              {stats ? (
                <>
                  <StatChip label="sourced"        value={stats.sourced}     color="blue"  />
                  <StatChip label="recommended"    value={stats.recommended} color="teal"  />
                  <StatChip label="outreach ready" value={stats.outreached}  color="green" />
                  {starred.size > 0 && <StatChip label="starred" value={starred.size} color="amber" />}
                </>
              ) : (
                <span className="text-sm text-livo-text-secondary">{candidates.length} candidates</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={exportCSV}
                className="text-sm font-medium text-livo-text-secondary hover:text-livo-slate bg-livo-bg-secondary hover:bg-livo-bg-secondary/80 px-3 py-1.5 rounded-full transition-colors duration-200 flex items-center gap-1.5">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Export CSV
              </button>
              <button onClick={() => { setView("form"); setError(""); setFilterRecommended(false); setFilterStarred(false); setFilterSource("all"); setFilterMinScore(0); }}
                className="text-sm font-medium text-livo-primary hover:text-livo-primary-hover bg-livo-primary-light hover:bg-livo-primary/20 px-4 py-1.5 rounded-full transition-colors duration-200">
                ← New Search
              </button>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap pb-1">
            <button onClick={() => setFilterRecommended(!filterRecommended)}
              className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition-colors duration-200 ${
                filterRecommended ? "bg-livo-primary text-white border-livo-primary" : "bg-white text-livo-text-secondary border-black/10 hover:border-livo-primary/40"
              }`}>
              ⭐ Recommended only
            </button>
            <button onClick={() => setFilterStarred(!filterStarred)}
              className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition-colors duration-200 ${
                filterStarred ? "bg-amber-500 text-white border-amber-500" : "bg-white text-livo-text-secondary border-black/10 hover:border-amber-300"
              }`}>
              ★ Shortlisted only
            </button>
            {sources.length > 1 && (
              <select value={filterSource} onChange={(e) => setFilterSource(e.target.value)}
                className="text-xs font-semibold px-3 py-1.5 rounded-full border border-black/10 bg-white text-livo-text-secondary focus:outline-none focus:ring-1 focus:ring-livo-primary cursor-pointer">
                <option value="all">All sources</option>
                {sources.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            )}
            <div className="flex items-center gap-2">
              <span className="text-xs text-livo-text-secondary font-medium">Min score</span>
              <input type="range" min={0} max={9} step={0.5} value={filterMinScore}
                onChange={(e) => setFilterMinScore(parseFloat(e.target.value))}
                className="w-24 accent-livo-primary" />
              <span className="text-xs font-semibold text-livo-slate w-6">{filterMinScore > 0 ? filterMinScore.toFixed(1) : "–"}</span>
            </div>
            <div className="ml-auto flex items-center border border-black/10 rounded-full overflow-hidden">
              {(["grid", "list"] as const).map((mode) => (
                <button key={mode} onClick={() => setViewMode(mode)}
                  className={`px-3 py-1.5 text-xs font-semibold transition-colors duration-200 ${
                    viewMode === mode ? "bg-livo-primary text-white" : "bg-white text-livo-text-secondary hover:bg-livo-bg-page"
                  }`}>
                  {mode === "grid" ? "⊞ Grid" : "☰ List"}
                </button>
              ))}
            </div>
            <span className="text-xs text-livo-text-muted">{filtered.length} of {candidates.length}</span>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="text-5xl mb-4">{candidates.length === 0 ? "🔍" : "🎛️"}</div>
            <h2 className="font-display text-xl font-semibold text-livo-slate">
              {candidates.length === 0 ? "No candidates found" : "No candidates match your filters"}
            </h2>
            <p className="text-livo-text-muted mt-2 max-w-sm text-sm">
              {candidates.length === 0 ? "Try broadening your job description or increasing the candidate count." : "Try loosening the filters above."}
            </p>
            <button
              onClick={() => candidates.length === 0 ? setView("form") : (setFilterRecommended(false), setFilterStarred(false), setFilterSource("all"), setFilterMinScore(0))}
              className="mt-6 px-6 py-2.5 bg-livo-primary text-white rounded-full font-medium text-sm hover:bg-livo-primary-hover transition-colors duration-200">
              {candidates.length === 0 ? "Try Again" : "Clear Filters"}
            </button>
          </div>
        ) : viewMode === "list" ? (
          <div className="space-y-2">
            {filtered.map((c, i) => (
              <CandidateCard key={i} candidate={c} jobId={jobId} apiUrl={API_URL}
                starred={starred.has(c.name)} onStar={() => toggleStar(c.name)} listView />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map((c, i) => (
              <CandidateCard key={i} candidate={c} jobId={jobId} apiUrl={API_URL}
                starred={starred.has(c.name)} onStar={() => toggleStar(c.name)} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

function StatChip({ label, value, color }: { label: string; value: number; color: "blue" | "teal" | "green" | "amber" }) {
  const styles: Record<string, string> = {
    blue:  "bg-blue-50 text-blue-700 border-blue-100",
    teal:  "bg-livo-primary-light text-livo-primary border-livo-primary/20",
    green: "bg-emerald-50 text-emerald-700 border-emerald-100",
    amber: "bg-amber-50 text-amber-700 border-amber-100",
  };
  return (
    <span className={`px-2.5 py-1 rounded-full text-xs font-semibold border ${styles[color]}`}>
      {value} {label}
    </span>
  );
}
