"use client";

import { useState, useEffect, useRef } from "react";
import type { HealthcareProfessional, Shift, ShiftStats } from "@/lib/types";
import ProfessionalCard from "@/components/ProfessionalCard";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "https://recruitingagents.vercel.app";

type View = "form" | "running" | "results";

interface FormData {
  shift_description: string;
  facility_name: string;
  unit: string;
  num_professionals: number;
}

interface ProgressEntry {
  stage: string;
  message: string;
}

const ROLE_OPTIONS = [
  { value: "Matrona dia 22 a las 20h20 a las 08am turno de 12 horas", label: "Matrona · 12h noche", icon: "👩‍⚕️" },
  { value: "Enfermero/a día 22 turno de mañana de 07h a 15h",         label: "Enfermera/o · Mañana", icon: "🏥" },
  { value: "Médico/a urgencias día 22 de 22h a 08h turno 10 horas",   label: "Médico/a · Urgencias", icon: "🩺" },
  { value: "Técnico/a día 22 turno tarde de 15h a 22h",               label: "Técnico/a · Tarde", icon: "🔬" },
];

const PIPELINE_STAGES = [
  { key: "parse",    label: "Analizar turno"  },
  { key: "sourcing", label: "Buscar perfiles" },
  { key: "scoring",  label: "Puntuar"         },
  { key: "outreach", label: "Mensajes"        },
];

const STAGE_COLORS: Record<string, string> = {
  parse:    "bg-livo-primary-light text-livo-primary",
  sourcing: "bg-blue-50 text-blue-700",
  scoring:  "bg-amber-50 text-amber-700",
  outreach: "bg-emerald-50 text-emerald-700",
};

function getStageBadge(stage: string) {
  return STAGE_COLORS[stage.toLowerCase()] ?? "bg-livo-bg-secondary text-livo-text-secondary";
}

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
      <span className={`text-xs font-medium hidden sm:block text-center leading-tight ${
        isDone   ? "text-livo-success" :
        isActive ? "text-livo-primary" :
                   "text-livo-text-muted"
      }`}>
        {stage.label}
      </span>
    </div>
  );
}

export default function Home() {
  const [view, setView]           = useState<View>("form");
  const [formData, setFormData]   = useState<FormData>({
    shift_description: "",
    facility_name: "Hospital General de Catalunya",
    unit: "",
    num_professionals: 15,
  });
  const [progressLog, setProgressLog]         = useState<ProgressEntry[]>([]);
  const [currentStage, setCurrentStage]       = useState("");
  const [completedStages, setCompletedStages] = useState<Set<string>>(new Set());
  const [shift, setShift]                     = useState<Shift | null>(null);
  const [stats, setStats]                     = useState<ShiftStats | null>(null);
  const [professionals, setProfessionals]     = useState<HealthcareProfessional[]>([]);
  const [error, setError]                     = useState("");
  const logEndRef                             = useRef<HTMLDivElement>(null);

  const [filterRecommended, setFilterRecommended] = useState(false);
  const [filterMinScore, setFilterMinScore]       = useState(0);
  const [viewMode, setViewMode]                   = useState<"grid" | "list">("grid");

  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [progressLog]);

  const runPipeline = async () => {
    if (!formData.shift_description.trim() || !formData.facility_name.trim()) return;
    setView("running");
    setProgressLog([]); setCompletedStages(new Set()); setCurrentStage("");
    setError(""); setShift(null); setStats(null); setProfessionals([]);

    let res: Response;
    try {
      res = await fetch(`${API_URL}/shift/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shift_description:  formData.shift_description,
          facility_name:      formData.facility_name,
          unit:               formData.unit.trim(),
          num_professionals:  formData.num_professionals,
        }),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error conectando con la API.");
      setView("form"); return;
    }
    if (!res.ok) { setError(`Error API: HTTP ${res.status}`); setView("form"); return; }

    const reader  = res.body!.getReader();
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
              if (currentEvent === "progress") {
                const stage = (data.stage ?? "").toLowerCase();
                setCurrentStage(stage);
                setProgressLog((prev) => [...prev, { stage, message: data.message ?? "" }]);
                const idx = PIPELINE_STAGES.findIndex((s) => s.key === stage);
                if (idx > 0) setCompletedStages((prev) => {
                  const n = new Set(prev);
                  PIPELINE_STAGES.slice(0, idx).forEach((s) => n.add(s.key));
                  return n;
                });
              }
              if (currentEvent === "done") {
                setShift(data.shift ?? null);
                setStats(data.stats ?? null);
                setProfessionals(data.professionals ?? []);
                setCompletedStages(new Set(PIPELINE_STAGES.map((s) => s.key)));
                setView("results");
              }
              if (currentEvent === "error") { setError(data.error ?? "Error desconocido."); }
            } catch { /* skip */ }
            currentEvent = "";
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stream interrumpido.");
    }
  };

  // ─── FORM VIEW ─────────────────────────────────────────────────────────────
  if (view === "form") {
    return (
      <main className="min-h-screen bg-livo-bg-page flex flex-col items-center px-4 py-12">
        <div className="w-full max-w-2xl">

          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center gap-2 bg-livo-primary text-white px-4 py-1.5 rounded-full text-sm font-semibold mb-5">
              <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
              Livo Hunter · Turnos Críticos
            </div>
            <h1 className="font-display text-4xl font-semibold text-livo-slate tracking-tight leading-tight">
              Cubre tu turno urgente<br />
              <span className="text-livo-primary">en minutos</span>
            </h1>
            <p className="text-sm text-livo-text-muted mt-3 max-w-md mx-auto leading-relaxed">
              Introduce el turno y el centro — buscamos en la base de datos de repetidores,
              puntuamos por historial y generamos mensajes de WhatsApp personalizados en español.
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-card border border-black/10 p-8 space-y-6">

            {/* Quick fill examples */}
            <div>
              <label className="block text-sm font-semibold text-livo-slate mb-3">
                Plantillas rápidas
              </label>
              <div className="grid grid-cols-2 gap-2">
                {ROLE_OPTIONS.map((opt) => (
                  <button key={opt.label} type="button"
                    onClick={() => setFormData((f) => ({ ...f, shift_description: opt.value }))}
                    className={`text-left p-3 rounded-lg border-2 transition-all duration-200 ${
                      formData.shift_description === opt.value
                        ? "border-livo-primary bg-livo-primary-light"
                        : "border-black/10 hover:border-livo-primary/30 hover:bg-livo-bg-page"
                    }`}>
                    <div className="text-xl mb-0.5">{opt.icon}</div>
                    <div className={`text-xs font-semibold ${formData.shift_description === opt.value ? "text-livo-primary" : "text-livo-slate"}`}>
                      {opt.label}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Shift description */}
            <div>
              <label htmlFor="shift_description" className="block text-sm font-semibold text-livo-slate mb-1.5">
                Descripción del turno
                <span className="ml-1.5 text-xs font-normal text-livo-text-muted">texto libre</span>
              </label>
              <textarea id="shift_description" value={formData.shift_description}
                onChange={(e) => setFormData((f) => ({ ...f, shift_description: e.target.value }))}
                placeholder={"Ejemplo: Matrona dia 22 a las 20h20 a las 08am turno de 12 horas"}
                rows={3}
                className="w-full rounded-lg border border-black/10 px-4 py-3 text-sm text-livo-slate placeholder-livo-text-muted focus:outline-none focus:ring-2 focus:ring-livo-primary focus:border-transparent resize-none transition-all duration-200"
              />
            </div>

            {/* Facility + Unit */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="facility_name" className="block text-sm font-semibold text-livo-slate mb-1.5">
                  Centro
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-livo-text-muted">🏥</span>
                  <input id="facility_name" type="text" value={formData.facility_name}
                    onChange={(e) => setFormData((f) => ({ ...f, facility_name: e.target.value }))}
                    placeholder="Hospital General de Catalunya"
                    className="w-full rounded-lg border border-black/10 pl-9 pr-4 py-3 text-sm text-livo-slate placeholder-livo-text-muted focus:outline-none focus:ring-2 focus:ring-livo-primary focus:border-transparent transition-all duration-200"
                  />
                </div>
              </div>
              <div>
                <label htmlFor="unit" className="block text-sm font-semibold text-livo-slate mb-1.5">
                  Unidad
                  <span className="ml-1 text-xs font-normal text-livo-text-muted">opcional</span>
                </label>
                <input id="unit" type="text" value={formData.unit}
                  onChange={(e) => setFormData((f) => ({ ...f, unit: e.target.value }))}
                  placeholder="Maternidad, UCI, Urgencias…"
                  className="w-full rounded-lg border border-black/10 px-4 py-3 text-sm text-livo-slate placeholder-livo-text-muted focus:outline-none focus:ring-2 focus:ring-livo-primary focus:border-transparent transition-all duration-200"
                />
              </div>
            </div>

            {/* Num professionals */}
            <div className="flex items-center justify-between gap-4">
              <div>
                <label htmlFor="num_professionals" className="block text-xs font-semibold text-livo-text-muted uppercase tracking-wide mb-1.5">
                  Profesionales a contactar
                </label>
                <div className="flex items-center gap-2">
                  <input id="num_professionals" type="number" min={5} max={30} value={formData.num_professionals}
                    onChange={(e) => setFormData((f) => ({ ...f, num_professionals: Math.max(5, Math.min(30, parseInt(e.target.value) || 15)) }))}
                    className="w-20 rounded-lg border border-black/10 px-3 py-2 text-sm text-center font-semibold text-livo-slate focus:outline-none focus:ring-2 focus:ring-livo-primary focus:border-transparent"
                  />
                  <span className="text-xs text-livo-text-muted">5–30</span>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs font-semibold text-livo-text-muted uppercase tracking-wide mb-1.5">Fuente</p>
                <div className="flex items-center gap-1.5 justify-end">
                  <span className="text-xs px-2 py-1 rounded-md bg-livo-bg-secondary text-livo-text-secondary font-medium">Metabase</span>
                  <span className="text-xs px-2 py-1 rounded-md bg-livo-bg-secondary text-livo-text-secondary font-medium">Repetidores</span>
                </div>
              </div>
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-livo-danger">{error}</div>
            )}

            <button onClick={runPipeline}
              disabled={!formData.shift_description.trim() || !formData.facility_name.trim()}
              className="w-full py-3.5 px-6 bg-livo-primary text-white rounded-full font-semibold text-base hover:bg-livo-primary-hover active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 shadow-card">
              Buscar profesionales disponibles →
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
            <h1 className="font-display text-2xl font-semibold text-livo-slate">Buscando profesionales…</h1>
            <p className="text-sm text-livo-text-muted mt-1">{formData.facility_name}</p>
          </div>

          {/* Stage tracker */}
          <div className="bg-white rounded-lg border border-black/10 shadow-card px-6 py-5">
            <div className="relative">
              <div className="absolute top-1.5 left-0 right-0 h-0.5 bg-livo-bg-secondary mx-6" />
              <div className="relative flex justify-between">
                {PIPELINE_STAGES.map((stage) => (
                  <StageStatus key={stage.key} stage={stage} currentStage={currentStage} completedStages={completedStages} />
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
              {currentStage ? `${currentStage}…` : "Iniciando…"}
            </span>
          </div>

          {/* Activity log */}
          <div className="bg-white rounded-lg border border-black/10 shadow-card overflow-hidden">
            <div className="px-5 py-3 border-b border-black/5 flex items-center justify-between">
              <span className="text-sm font-semibold text-livo-slate">Registro de actividad</span>
              <span className="text-xs text-livo-text-muted">{progressLog.length} eventos</span>
            </div>
            <div className="max-h-80 overflow-y-auto px-5 py-3 space-y-2">
              {progressLog.length === 0 ? (
                <p className="text-sm text-livo-text-muted text-center py-4">Esperando eventos…</p>
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
                className="text-livo-danger hover:text-red-700 ml-4 font-medium text-xs">Volver</button>
            </div>
          )}
        </div>
      </main>
    );
  }

  // ─── RESULTS VIEW ─────────────────────────────────────────────────────────
  const sorted   = [...professionals].sort((a, b) => b.fit_score - a.fit_score);
  const filtered = sorted.filter((p) => {
    if (filterRecommended && !p.recommended) return false;
    if (p.fit_score < filterMinScore)        return false;
    return true;
  });

  const exportCSV = () => {
    const rows = [
      ["Nombre","Rol","Turnos en centro","Turnos en unidad","Total turnos","Último turno","Puntuación","Recomendado","Teléfono","Email","Mensaje WhatsApp"],
      ...filtered.map((p) => [
        p.name, p.role, p.shifts_at_facility, p.shifts_in_unit,
        p.total_shifts, p.last_shift_date ?? "",
        p.fit_score, p.recommended ? "Sí" : "No",
        p.phone ?? "", p.email ?? "", p.message_body ?? "",
      ]),
    ];
    const csv  = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = "livo-turno-profesionales.csv"; a.click();
  };

  return (
    <main className="min-h-screen bg-livo-bg-page">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-white/95 backdrop-blur-sm border-b border-black/10 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-3 flex-wrap">
              {shift && (
                <>
                  <span className="font-display text-sm font-bold text-livo-slate">{shift.role}</span>
                  <span className="text-livo-bg-secondary">·</span>
                  <span className="text-sm text-livo-text-secondary">{shift.facility_name}</span>
                  {shift.unit && <span className="text-xs bg-livo-bg-secondary text-livo-text-secondary px-2 py-0.5 rounded-full">{shift.unit}</span>}
                  <span className="text-livo-bg-secondary">·</span>
                  <span className="text-xs text-livo-text-muted">{shift.date_str} {shift.display_time}</span>
                </>
              )}
            </div>
            <div className="flex items-center gap-2">
              {stats && (
                <div className="flex items-center gap-2 flex-wrap">
                  <StatChip label="encontrados"    value={stats.sourced}     color="blue"  />
                  <StatChip label="recomendados"   value={stats.recommended} color="teal"  />
                  <StatChip label="con mensaje"    value={stats.contacted}   color="green" />
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={exportCSV}
                className="text-sm font-medium text-livo-text-secondary hover:text-livo-slate bg-livo-bg-secondary hover:bg-livo-bg-secondary/80 px-3 py-1.5 rounded-full transition-colors duration-200 flex items-center gap-1.5">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Exportar CSV
              </button>
              <button onClick={() => { setView("form"); setError(""); setFilterRecommended(false); setFilterMinScore(0); }}
                className="text-sm font-medium text-livo-primary hover:text-livo-primary-hover bg-livo-primary-light hover:bg-livo-primary/20 px-4 py-1.5 rounded-full transition-colors duration-200">
                ← Nuevo turno
              </button>
            </div>
          </div>

          {/* Filters */}
          <div className="flex items-center gap-3 flex-wrap pb-1">
            <button onClick={() => setFilterRecommended(!filterRecommended)}
              className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition-colors duration-200 ${
                filterRecommended ? "bg-livo-primary text-white border-livo-primary" : "bg-white text-livo-text-secondary border-black/10 hover:border-livo-primary/40"
              }`}>
              ⭐ Solo recomendados
            </button>
            <div className="flex items-center gap-2">
              <span className="text-xs text-livo-text-secondary font-medium">Puntuación mínima</span>
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
                  {mode === "grid" ? "⊞ Grid" : "☰ Lista"}
                </button>
              ))}
            </div>
            <span className="text-xs text-livo-text-muted">{filtered.length} de {professionals.length}</span>
          </div>
        </div>
      </div>

      {/* Results */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="text-5xl mb-4">{professionals.length === 0 ? "🔍" : "🎛️"}</div>
            <h2 className="font-display text-xl font-semibold text-livo-slate">
              {professionals.length === 0 ? "Sin profesionales en la base de datos" : "Ningún profesional coincide con los filtros"}
            </h2>
            <p className="text-livo-text-muted mt-2 max-w-sm text-sm">
              {professionals.length === 0
                ? "Configura las credenciales de Metabase en el .env del backend para acceder a la base de repetidores."
                : "Prueba a reducir los filtros."}
            </p>
            <button
              onClick={() => professionals.length === 0 ? setView("form") : (setFilterRecommended(false), setFilterMinScore(0))}
              className="mt-6 px-6 py-2.5 bg-livo-primary text-white rounded-full font-medium text-sm hover:bg-livo-primary-hover transition-colors duration-200">
              {professionals.length === 0 ? "Volver" : "Limpiar filtros"}
            </button>
          </div>
        ) : viewMode === "list" ? (
          <div className="space-y-2">
            {filtered.map((p, i) => (
              <ProfessionalCard key={i} professional={p} shift={shift} listView />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map((p, i) => (
              <ProfessionalCard key={i} professional={p} shift={shift} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

function StatChip({ label, value, color }: { label: string; value: number; color: "blue" | "teal" | "green" }) {
  const styles: Record<string, string> = {
    blue:  "bg-blue-50 text-blue-700 border-blue-100",
    teal:  "bg-livo-primary-light text-livo-primary border-livo-primary/20",
    green: "bg-emerald-50 text-emerald-700 border-emerald-100",
  };
  return (
    <span className={`px-2.5 py-1 rounded-full text-xs font-semibold border ${styles[color]}`}>
      {value} {label}
    </span>
  );
}
