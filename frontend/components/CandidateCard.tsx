"use client";

import { useState } from "react";
import type { Candidate } from "@/lib/types";
import InterviewModal from "./InterviewModal";

interface Props {
  candidate: Candidate;
  jobId: string;
  apiUrl: string;
  starred: boolean;
  onStar: () => void;
  listView?: boolean;
}

function getSourceStyle(source: string): string {
  const s = source.toLowerCase();
  if (s.includes("linkedin"))                     return "bg-blue-100 text-blue-700";
  if (s.includes("github"))                       return "bg-livo-slate text-white";
  if (s.includes("hugging") || s.includes("hf"))  return "bg-yellow-100 text-yellow-800";
  if (s.includes("kaggle"))                       return "bg-cyan-100 text-cyan-800";
  if (s.includes("twitter") || s.includes("x.com")) return "bg-gray-900 text-white";
  if (s.includes("arxiv"))                        return "bg-red-100 text-red-700";
  return "bg-livo-primary-light text-livo-primary";
}

function getSourceLabel(source: string): string {
  const s = source.toLowerCase();
  if (s.includes("linkedin"))                    return "LinkedIn";
  if (s.includes("github"))                      return "GitHub";
  if (s.includes("hugging") || s.includes("hf")) return "HuggingFace";
  if (s.includes("kaggle"))                      return "Kaggle";
  if (s.includes("twitter"))                     return "Twitter/X";
  if (s.includes("arxiv"))                       return "ArXiv";
  return source;
}

function getExpertiseBadge(depth: string): { label: string; style: string } {
  switch (depth?.toLowerCase()) {
    case "expert":     return { label: "Expert",     style: "bg-emerald-50 text-emerald-700 border-emerald-200" };
    case "proficient": return { label: "Proficient", style: "bg-livo-primary-light text-livo-primary border-livo-primary/20" };
    case "developing": return { label: "Developing", style: "bg-amber-50 text-amber-700 border-amber-200" };
    default:           return { label: "Surface",    style: "bg-livo-bg-secondary text-livo-text-muted border-black/10" };
  }
}

function ScoreRing({ score }: { score: number }) {
  const size  = 52;
  const stroke = 4;
  const r     = (size - stroke) / 2;
  const circ  = 2 * Math.PI * r;
  const dash  = Math.min(score / 10, 1) * circ;
  // Livo semantic colours
  const color = score >= 8 ? "#1FC86E" : score >= 6 ? "#FCC804" : "#EC221F";
  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#EDEDE8" strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-sm font-bold leading-none text-livo-slate">{score.toFixed(1)}</span>
      </div>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color = value >= 8 ? "bg-livo-success" : value >= 6 ? "bg-livo-warning" : "bg-livo-danger";
  return (
    <div className="flex items-center gap-2 min-w-0">
      <span className="text-xs text-livo-text-muted w-16 flex-shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-livo-bg-secondary rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all duration-200`} style={{ width: `${value * 10}%` }} />
      </div>
      <span className="text-xs font-semibold text-livo-text-secondary w-6 text-right">{value.toFixed(1)}</span>
    </div>
  );
}

export default function CandidateCard({ candidate, jobId, apiUrl, starred, onStar, listView }: Props) {
  const [outreachOpen, setOutreachOpen]             = useState(false);
  const [copied, setCopied]                         = useState(false);
  const [emailCopied, setEmailCopied]               = useState(false);
  const [showFullRationale, setShowFullRationale]   = useState(false);
  const [showModal, setShowModal]                   = useState(false);

  const MAX_SKILLS    = listView ? 8 : 5;
  const visibleSkills = candidate.skills.slice(0, MAX_SKILLS);
  const extraSkills   = candidate.skills.length - MAX_SKILLS;
  const expertise     = getExpertiseBadge(candidate.ai_expertise_depth ?? "");

  const handleCopy = async () => {
    const text = [candidate.outreach_subject ? `Subject: ${candidate.outreach_subject}` : "", "", candidate.outreach_message ?? ""].join("\n").trim();
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* ignore */ }
  };
  const handleCopyEmail = async () => {
    if (!candidate.email) return;
    try { await navigator.clipboard.writeText(candidate.email); setEmailCopied(true); setTimeout(() => setEmailCopied(false), 2000); } catch { /* ignore */ }
  };

  if (listView) {
    return (
      <>
        <div className="bg-white border border-black/10 rounded-lg px-5 py-4 hover:shadow-card transition-shadow duration-200 flex items-center gap-4">
          <button onClick={onStar} className={`flex-shrink-0 transition-colors duration-200 ${starred ? "text-amber-400" : "text-livo-bg-secondary hover:text-amber-300"}`}>
            <svg className="w-5 h-5" fill={starred ? "currentColor" : "none"} viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
            </svg>
          </button>
          <ScoreRing score={candidate.fit_score} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              {candidate.profile_url ? (
                <a href={candidate.profile_url} target="_blank" rel="noopener noreferrer"
                  className="font-bold text-livo-slate hover:text-livo-primary transition-colors duration-200">
                  {candidate.name}
                </a>
              ) : (
                <span className="font-bold text-livo-slate">{candidate.name}</span>
              )}
              {candidate.recommended && (
                <span className="px-2 py-0.5 bg-livo-primary-light text-livo-primary text-xs font-semibold rounded-full border border-livo-primary/20">Recommended</span>
              )}
              <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${getSourceStyle(candidate.source)}`}>{getSourceLabel(candidate.source)}</span>
              {candidate.ai_expertise_depth && (
                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${expertise.style}`}>{expertise.label}</span>
              )}
            </div>
            <p className="text-sm text-livo-text-secondary truncate mt-0.5">{candidate.headline}</p>
            <div className="flex items-center gap-3 mt-1 flex-wrap">
              {candidate.location && <span className="text-xs text-livo-text-muted">📍 {candidate.location}</span>}
              {candidate.email && (
                <button onClick={handleCopyEmail} className="text-xs text-livo-primary hover:text-livo-primary-hover flex items-center gap-1 transition-colors duration-200">
                  ✉️ {emailCopied ? "Copied!" : candidate.email}
                </button>
              )}
            </div>
          </div>
          <div className="hidden lg:flex flex-wrap gap-1 max-w-xs">
            {visibleSkills.map(s => (
              <span key={s} className="px-2 py-0.5 bg-livo-primary-light text-livo-primary text-xs rounded-md border border-livo-primary/20 font-medium">{s}</span>
            ))}
            {extraSkills > 0 && <span className="px-2 py-0.5 bg-livo-bg-secondary text-livo-text-muted text-xs rounded-md font-medium">+{extraSkills}</span>}
          </div>
          <div className="hidden xl:flex flex-col gap-1 w-40">
            <ScoreBar label="Technical" value={candidate.technical_score} />
            <ScoreBar label="Culture"   value={candidate.culture_score} />
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {candidate.outreach_message && (
              <button onClick={handleCopy}
                className="text-xs px-3 py-1.5 rounded-full border border-black/10 text-livo-text-secondary hover:bg-livo-bg-page transition-colors duration-200">
                {copied ? "✓ Copied" : "Copy outreach"}
              </button>
            )}
            <button onClick={() => setShowModal(true)}
              className="text-xs px-3 py-1.5 rounded-full border border-livo-primary/30 bg-livo-primary-light text-livo-primary hover:bg-livo-primary/20 transition-colors duration-200">
              Interview
            </button>
          </div>
        </div>
        {showModal && <InterviewModal candidate={candidate} jobId={jobId} apiUrl={apiUrl} onClose={() => setShowModal(false)} />}
      </>
    );
  }

  // ─── GRID CARD ─────────────────────────────────────────────────────────────
  return (
    <>
      <div className="bg-white rounded-lg border border-black/10 shadow-card hover:shadow-card-hover transition-shadow duration-200 flex flex-col overflow-hidden">
        <div className="px-5 pt-5 pb-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                {candidate.profile_url ? (
                  <a href={candidate.profile_url} target="_blank" rel="noopener noreferrer"
                    className="text-base font-bold text-livo-slate hover:text-livo-primary transition-colors duration-200">
                    {candidate.name}
                  </a>
                ) : (
                  <span className="text-base font-bold text-livo-slate">{candidate.name}</span>
                )}
                {candidate.recommended && (
                  <span className="px-2 py-0.5 bg-livo-primary-light text-livo-primary text-xs font-semibold rounded-full border border-livo-primary/20">
                    Recommended
                  </span>
                )}
              </div>
              {candidate.headline && (
                <p className="text-sm text-livo-text-secondary mt-0.5 leading-snug line-clamp-2">{candidate.headline}</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={onStar} className={`transition-colors duration-200 ${starred ? "text-amber-400" : "text-livo-bg-secondary hover:text-amber-300"}`}>
                <svg className="w-5 h-5" fill={starred ? "currentColor" : "none"} viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                </svg>
              </button>
              <ScoreRing score={candidate.fit_score} />
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap mt-2">
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${getSourceStyle(candidate.source)}`}>
              {getSourceLabel(candidate.source)}
            </span>
            {candidate.ai_expertise_depth && (
              <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${expertise.style}`}>{expertise.label}</span>
            )}
            {candidate.location && <span className="text-xs text-livo-text-muted">📍 {candidate.location}</span>}
            {candidate.experience_years != null && <span className="text-xs text-livo-text-muted">{candidate.experience_years}y exp</span>}
          </div>

          {candidate.email && (
            <button onClick={handleCopyEmail}
              className="mt-2 flex items-center gap-1.5 text-xs text-livo-primary hover:text-livo-primary-hover transition-colors duration-200">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              {emailCopied ? "✓ Copied!" : candidate.email}
            </button>
          )}
        </div>

        <div className="px-5 py-2.5 bg-livo-bg-page border-y border-black/5 space-y-1.5">
          <ScoreBar label="Technical" value={candidate.technical_score} />
          <ScoreBar label="Culture"   value={candidate.culture_score} />
        </div>

        <div className="px-5 py-3">
          <div className="flex flex-wrap gap-1.5">
            {visibleSkills.map((skill) => (
              <span key={skill} className="px-2 py-0.5 bg-livo-primary-light text-livo-primary text-xs rounded-md border border-livo-primary/20 font-medium">
                {skill}
              </span>
            ))}
            {extraSkills > 0 && (
              <span className="px-2 py-0.5 bg-livo-bg-secondary text-livo-text-muted text-xs rounded-md font-medium">+{extraSkills} more</span>
            )}
          </div>
        </div>

        {candidate.notable_work && (
          <div className="px-5 pb-3">
            <p className="text-xs text-livo-text-secondary leading-relaxed">
              <span className="font-semibold text-livo-slate">Notable: </span>{candidate.notable_work}
            </p>
          </div>
        )}

        {(candidate.community_presence || candidate.enriched_summary) && (
          <div className="px-5 pb-3">
            <p className="text-xs text-livo-text-secondary leading-relaxed line-clamp-2">
              {candidate.community_presence || candidate.enriched_summary}
            </p>
          </div>
        )}

        {candidate.scoring_rationale && (
          <div className="px-5 pb-3">
            <p className={`text-xs text-livo-text-secondary leading-relaxed ${showFullRationale ? "" : "line-clamp-2"}`}>
              {candidate.scoring_rationale}
            </p>
            {candidate.scoring_rationale.length > 120 && (
              <button onClick={() => setShowFullRationale(!showFullRationale)}
                className="text-xs text-livo-primary hover:text-livo-primary-hover mt-0.5 font-medium transition-colors duration-200">
                {showFullRationale ? "Show less" : "Show more"}
              </button>
            )}
          </div>
        )}

        {(candidate.outreach_message || candidate.outreach_subject) && (
          <div className="border-t border-black/5">
            <button onClick={() => setOutreachOpen(!outreachOpen)}
              className="w-full px-5 py-3 flex items-center justify-between text-sm font-medium text-livo-text-secondary hover:bg-livo-bg-page transition-colors duration-200">
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4 text-livo-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                Outreach
                {candidate.outreach_channel && <span className="text-xs text-livo-text-muted font-normal">via {candidate.outreach_channel}</span>}
              </span>
              <svg className={`w-4 h-4 text-livo-text-muted transition-transform duration-200 ${outreachOpen ? "rotate-180" : ""}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {outreachOpen && (
              <div className="px-5 pb-4 space-y-2">
                {candidate.outreach_subject && (
                  <div className="bg-livo-bg-page rounded-lg px-3 py-2">
                    <span className="text-xs font-semibold text-livo-text-muted uppercase tracking-wide">Subject</span>
                    <p className="text-sm text-livo-slate mt-0.5 font-medium">{candidate.outreach_subject}</p>
                  </div>
                )}
                {candidate.outreach_message && (
                  <div className="bg-livo-bg-page rounded-lg px-3 py-2">
                    <p className="text-sm text-livo-text-secondary whitespace-pre-wrap leading-relaxed">{candidate.outreach_message}</p>
                  </div>
                )}
                <button onClick={handleCopy}
                  className="w-full py-1.5 px-3 rounded-full border border-black/10 text-xs font-medium text-livo-text-secondary hover:bg-livo-bg-page transition-colors duration-200 flex items-center justify-center gap-1.5">
                  {copied ? (
                    <><svg className="w-3.5 h-3.5 text-livo-success" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg><span className="text-livo-success">Copied!</span></>
                  ) : (
                    <><svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>Copy message</>
                  )}
                </button>
              </div>
            )}
          </div>
        )}

        <div className="mt-auto px-5 pb-5 pt-3 border-t border-black/5">
          <button onClick={() => setShowModal(true)}
            className="w-full py-2 px-4 rounded-full border border-livo-primary/30 bg-livo-primary-light text-livo-primary text-sm font-medium hover:bg-livo-primary/20 transition-colors duration-200 flex items-center justify-center gap-2">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            Analyze Interview
          </button>
        </div>
      </div>
      {showModal && <InterviewModal candidate={candidate} jobId={jobId} apiUrl={apiUrl} onClose={() => setShowModal(false)} />}
    </>
  );
}
