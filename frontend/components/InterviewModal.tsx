"use client";

import { useState } from "react";
import type { Candidate, InterviewInsights } from "@/lib/types";

interface Props {
  candidate: Candidate;
  jobId: string;
  apiUrl: string;
  onClose: () => void;
}

const RECOMMENDATION_STYLES: Record<string, string> = {
  "STRONG YES": "bg-emerald-50 text-emerald-800 border border-emerald-300",
  YES:           "bg-livo-primary-light text-livo-primary border border-livo-primary/30",
  MAYBE:         "bg-amber-50 text-amber-800 border border-amber-300",
  NO:            "bg-red-50 text-livo-danger border border-red-300",
};

export default function InterviewModal({ candidate, jobId, apiUrl, onClose }: Props) {
  const [transcript, setTranscript] = useState("");
  const [loading, setLoading]       = useState(false);
  const [insights, setInsights]     = useState<InterviewInsights | null>(null);
  const [error, setError]           = useState("");

  const analyze = async () => {
    if (!transcript.trim()) return;
    setLoading(true); setError(""); setInsights(null);
    try {
      const res = await fetch(`${apiUrl}/jobs/${jobId}/interview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_name: candidate.name, transcript: transcript.trim() }),
      });
      if (!res.ok) { const text = await res.text(); throw new Error(text || `HTTP ${res.status}`); }
      setInsights(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const rec      = insights?.recommendation?.toUpperCase() ?? "";
  const recStyle = RECOMMENDATION_STYLES[rec] ?? "bg-livo-bg-secondary text-livo-text-secondary border border-black/10";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className="absolute inset-0 bg-livo-slate/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-white rounded-lg shadow-[0_8px_40px_8px_rgba(0,0,0,0.18)] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-black/10 sticky top-0 bg-white rounded-t-lg">
          <div>
            <h2 id="modal-title" className="font-display text-lg font-semibold text-livo-slate">Interview Analysis</h2>
            <p className="text-sm text-livo-primary font-medium">{candidate.name}</p>
          </div>
          <button onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full text-livo-text-muted hover:text-livo-text-secondary hover:bg-livo-bg-page transition-colors duration-200"
            aria-label="Close modal">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 px-6 py-5 space-y-5">
          <div>
            <label className="block text-sm font-medium text-livo-slate mb-1.5">Interview Transcript</label>
            <textarea value={transcript} onChange={(e) => setTranscript(e.target.value)}
              placeholder="Paste interview transcript here…" rows={10}
              className="w-full rounded-lg border border-black/10 px-3 py-2.5 text-sm text-livo-slate placeholder-livo-text-muted focus:outline-none focus:ring-2 focus:ring-livo-primary focus:border-transparent resize-y transition-all duration-200"
            />
          </div>

          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-livo-danger">{error}</div>
          )}

          <button onClick={analyze} disabled={loading || !transcript.trim()}
            className="w-full py-2.5 px-4 bg-livo-primary text-white rounded-full font-medium text-sm hover:bg-livo-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 flex items-center justify-center gap-2">
            {loading ? (
              <><svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>Analyzing…</>
            ) : "Analyze Interview"}
          </button>

          {insights && (
            <div className="space-y-5 pt-2 border-t border-black/5">
              {insights.recommendation && (
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-livo-text-secondary">Recommendation:</span>
                  <span className={`px-3 py-1 rounded-full text-sm font-bold uppercase tracking-wide ${recStyle}`}>
                    {insights.recommendation}
                  </span>
                </div>
              )}
              {insights.summary && (
                <p className="text-sm text-livo-text-secondary leading-relaxed bg-livo-bg-page rounded-lg px-4 py-3">{insights.summary}</p>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {insights.key_strengths.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-livo-success mb-2 flex items-center gap-1.5">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                      Strengths
                    </h3>
                    <ul className="space-y-1.5">
                      {insights.key_strengths.map((s, i) => (
                        <li key={i} className="text-sm text-livo-text-secondary flex items-start gap-2">
                          <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-livo-success flex-shrink-0" />{s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {insights.areas_of_concern.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-livo-danger mb-2 flex items-center gap-1.5">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /></svg>
                      Concerns
                    </h3>
                    <ul className="space-y-1.5">
                      {insights.areas_of_concern.map((c, i) => (
                        <li key={i} className="text-sm text-livo-text-secondary flex items-start gap-2">
                          <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-livo-danger flex-shrink-0" />{c}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              {insights.technical_assessment && (
                <div>
                  <h3 className="text-sm font-semibold text-livo-slate mb-1.5">Technical Assessment</h3>
                  <p className="text-sm text-livo-text-secondary leading-relaxed">{insights.technical_assessment}</p>
                </div>
              )}
              {insights.cultural_fit_assessment && (
                <div>
                  <h3 className="text-sm font-semibold text-livo-slate mb-1.5">Cultural Fit</h3>
                  <p className="text-sm text-livo-text-secondary leading-relaxed">{insights.cultural_fit_assessment}</p>
                </div>
              )}
              {insights.next_steps.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-livo-slate mb-2">Suggested Next Steps</h3>
                  <ol className="space-y-1.5 list-none">
                    {insights.next_steps.map((step, i) => (
                      <li key={i} className="text-sm text-livo-text-secondary flex items-start gap-2.5">
                        <span className="flex-shrink-0 w-5 h-5 rounded-full bg-livo-primary-light text-livo-primary text-xs font-bold flex items-center justify-center mt-0.5">
                          {i + 1}
                        </span>
                        {step}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
