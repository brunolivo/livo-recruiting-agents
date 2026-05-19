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
  if (s.includes("linkedin"))                    return "bg-blue-100 text-blue-700";
  if (s.includes("github"))                      return "bg-[#1C2631] text-white";
  if (s.includes("hugging") || s.includes("hf")) return "bg-yellow-100 text-yellow-800";
  if (s.includes("kaggle"))                      return "bg-cyan-100 text-cyan-800";
  if (s.includes("twitter") || s.includes("x.com")) return "bg-gray-900 text-white";
  if (s.includes("arxiv"))                       return "bg-red-100 text-red-700";
  return "bg-[#E8F4F7] text-[#007C92]";
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
    case "proficient": return { label: "Proficient", style: "bg-[#E8F4F7] text-[#007C92] border-[#007C92]/20" };
    case "developing": return { label: "Developing", style: "bg-amber-50 text-amber-700 border-amber-200" };
    default:           return { label: "Surface",    style: "bg-[#EDEDE8] text-[#8AA3B8] border-black/10" };
  }
}

function ScoreRing({ score }: { score: number }) {
  const size   = 52;
  const stroke = 4;
  const r      = (size - stroke) / 2;
  const circ   = 2 * Math.PI * r;
  const pct    = Math.min(score / 10, 1);
  const dash   = pct * circ;
  // Livo semantic colors
  const color  = score >= 8 ? "#1FC86E" : score >= 6 ? "#FCC804" : "#EC221F";
  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#EDEDE8" strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-sm font-bold leading-none text-[#1C2631]">{score.toFixed(1)}</span>
      </div>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color = value >= 8 ? "bg-[#1FC86E]" : value >= 6 ? "bg-[#FCC804]" : "bg-[#EC221F]";
  return (
    <div className="flex items-center gap-2 min-w-0">
      <span className="text-xs text-[#8AA3B8] w-16 flex-shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-[#EDEDE8] rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all duration-200`} style={{ width: `${value * 10}%` }} />
      </div>
      <span className="text-xs font-semibold text-[#405263] w-6 text-right">{value.toFixed(1)}</span>
    </div>
  );
}

export default function CandidateCard({ candidate, jobId, apiUrl, starred, onStar, listView }: Props) {
  const [outreachOpen, setOutreachOpen]         = useState(false);
  const [copied, setCopied]                     = useState(false);
  const [emailCopied, setEmailCopied]           = useState(false);
  const [showFullRationale, setShowFullRationale] = useState(false);
  const [showModal, setShowModal]               = useState(false);

  const MAX_SKILLS   = listView ? 8 : 5;
  const visibleSkills = candidate.skills.slice(0, MAX_SKILLS);
  const extraSkills   = candidate.skills.length - MAX_SKILLS;
  const expertise     = getExpertiseBadge(candidate.ai_expertise_depth ?? "");

  const handleCopy = async () => {
    const text = [
      candidate.outreach_subject ? `Subject: ${candidate.outreach_subject}` : "",
      "",
      candidate.outreach_message ?? "",
    ].join("\n").trim();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* ignore */ }
  };

  const handleCopyEmail = async () => {
    if (!candidate.email) return;
    try {
      await navigator.clipboard.writeText(candidate.email);
      setEmailCopied(true);
      setTimeout(() => setEmailCopied(false), 2000);
    } catch { /* ignore */ }
  };

  if (listView) {
    return (
      <>
        <div className="bg-white border border-black/10 rounded-lg px-5 py-4 hover:shadow-card transition-shadow duration-200 flex items-center gap-4">
          {/* Star */}
          <button onClick={onStar} className={`flex-shrink-0 transition-colors duration-200 ${starred ? "text-amber-400" : "text-[#EDEDE8] hover:text-amber-300"}`}>
            <svg className="w-5 h-5" fill={starred ? "currentColor" : "none"} viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
            </svg>
          </button>
          {/* Score */}
          <ScoreRing score={candidate.fit_score} />
          {/* Name + meta */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              {candidate.profile_url ? (
                <a href={candidate.profile_url} target="_blank" rel="noopener noreferrer"
                  className="font-bold text-[#1C2631] hover:text-[#007C92] transition-colors duration-200">
                  {candidate.name}
                </a>
              ) : (
                <span className="font-bold text-[#1C2631]">{candidate.name}</span>
              )}
              {candidate.recommended && (
                <span className="px-2 py-0.5 bg-[#E8F4F7] text-[#007C92] text-xs font-semibold rounded-full border border-[#007C92]/20">
                  Recommended
                </span>
              )}
              <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${getSourceStyle(candidate.source)}`}>
                {getSourceLabel(candidate.source)}
              </span>
              {candidate.ai_expertise_depth && (
                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${expertise.style}`}>
                  {expertise.label}
                </span>
              )}
            </div>
            <p className="text-sm text-[#405263] truncate mt-0.5">{candidate.headline}</p>
            <div className="flex items-center gap-3 mt-1 flex-wrap">
              {candidate.location && <span className="text-xs text-[#8AA3B8]">📍 {candidate.location}</span>}
              {candidate.email && (
                <button onClick={handleCopyEmail} className="text-xs text-[#007C92] hover:text-[#005362] flex items-center gap-1 transition-colors duration-200">
                  ✉️ {emailCopied ? "Copied!" : candidate.email}
                </button>
              )}
            </div>
          </div>
          {/* Skills */}
          <div className="hidden lg:flex flex-wrap gap-1 max-w-xs">
            {visibleSkills.map(s => (
              <span key={s} className="px-2 py-0.5 bg-[#E8F4F7] text-[#007C92] text-xs rounded-md border border-[#007C92]/20 font-medium">{s}</span>
            ))}
            {extraSkills > 0 && <span className="px-2 py-0.5 bg-[#EDEDE8] text-[#8AA3B8] text-xs rounded-md font-medium">+{extraSkills}</span>}
          </div>
          {/* Score bars */}
          <div className="hidden xl:flex flex-col gap-1 w-40">
            <ScoreBar label="Technical" value={candidate.technical_score} />
            <ScoreBar label="Culture"   value={candidate.culture_score} />
          </div>
          {/* Actions */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {candidate.outreach_message && (
              <button onClick={handleCopy}
                className="text-xs px-3 py-1.5 rounded-full border border-black/10 text-[#405263] hover:bg-[#F5F5F2] transition-colors duration-200">
                {copied ? "✓ Copied" : "Copy outreach"}
              </button>
            )}
            <button onClick={() => setShowModal(true)}
              className="text-xs px-3 py-1.5 rounded-full border border-[#007C92]/30 bg-[#E8F4F7] text-[#007C92] hover:bg-[#d0eaef] transition-colors duration-200">
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
      <div className="bg-white rounded-lg border border-black/10 shadow-card hover:shadow-[0_4px_24px_4px_rgba(0,0,0,0.13)] transition-shadow duration-200 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-5 pt-5 pb-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                {candidate.profile_url ? (
                  <a href={candidate.profile_url} target="_blank" rel="noopener noreferrer"
                    className="text-base font-bold text-[#1C2631] hover:text-[#007C92] transition-colors duration-200">
                    {candidate.name}
                  </a>
                ) : (
                  <span className="text-base font-bold text-[#1C2631]">{candidate.name}</span>
                )}
                {candidate.recommended && (
                  <span className="px-2 py-0.5 bg-[#E8F4F7] text-[#007C92] text-xs font-semibold rounded-full border border-[#007C92]/20">
                    Recommended
                  </span>
                )}
              </div>
              {candidate.headline && (
                <p className="text-sm text-[#405263] mt-0.5 leading-snug line-clamp-2">{candidate.headline}</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {/* Star button */}
              <button onClick={onStar} className={`transition-colors duration-200 ${starred ? "text-amber-400" : "text-[#EDEDE8] hover:text-amber-300"}`}>
                <svg className="w-5 h-5" fill={starred ? "currentColor" : "none"} viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                </svg>
              </button>
              <ScoreRing score={candidate.fit_score} />
            </div>
          </div>

          {/* Meta row */}
          <div className="flex items-center gap-2 flex-wrap mt-2">
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${getSourceStyle(candidate.source)}`}>
              {getSourceLabel(candidate.source)}
            </span>
            {candidate.ai_expertise_depth && (
              <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${expertise.style}`}>
                {expertise.label}
              </span>
            )}
            {candidate.location && (
              <span className="text-xs text-[#8AA3B8]">📍 {candidate.location}</span>
            )}
            {candidate.experience_years != null && (
              <span className="text-xs text-[#8AA3B8]">{candidate.experience_years}y exp</span>
            )}
          </div>

          {/* Email */}
          {candidate.email && (
            <button onClick={handleCopyEmail}
              className="mt-2 flex items-center gap-1.5 text-xs text-[#007C92] hover:text-[#005362] transition-colors duration-200">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              {emailCopied ? "✓ Copied!" : candidate.email}
            </button>
          )}
        </div>

        {/* Score bars */}
        <div className="px-5 py-2.5 bg-[#F5F5F2] border-y border-black/5 space-y-1.5">
          <ScoreBar label="Technical" value={candidate.technical_score} />
          <ScoreBar label="Culture"   value={candidate.culture_score} />
        </div>

        {/* Skills */}
        <div className="px-5 py-3">
          <div className="flex flex-wrap gap-1.5">
            {visibleSkills.map((skill) => (
              <span key={skill} className="px-2 py-0.5 bg-[#E8F4F7] text-[#007C92] text-xs rounded-md border border-[#007C92]/20 font-medium">
                {skill}
              </span>
            ))}
            {extraSkills > 0 && (
              <span className="px-2 py-0.5 bg-[#EDEDE8] text-[#8AA3B8] text-xs rounded-md font-medium">+{extraSkills} more</span>
            )}
          </div>
        </div>

        {/* Notable work */}
        {candidate.notable_work && (
          <div className="px-5 pb-3">
            <p className="text-xs text-[#405263] leading-relaxed">
              <span className="font-semibold text-[#1C2631]">Notable: </span>
              {candidate.notable_work}
            </p>
          </div>
        )}

        {/* Community presence / enriched summary */}
        {(candidate.community_presence || candidate.enriched_summary) && (
          <div className="px-5 pb-3">
            <p className="text-xs text-[#405263] leading-relaxed line-clamp-2">
              {candidate.community_presence || candidate.enriched_summary}
            </p>
          </div>
        )}

        {/* Scoring rationale */}
        {candidate.scoring_rationale && (
          <div className="px-5 pb-3">
            <p className={`text-xs text-[#405263] leading-relaxed ${showFullRationale ? "" : "line-clamp-2"}`}>
              {candidate.scoring_rationale}
            </p>
            {candidate.scoring_rationale.length > 120 && (
              <button onClick={() => setShowFullRationale(!showFullRationale)}
                className="text-xs text-[#007C92] hover:text-[#005362] mt-0.5 font-medium transition-colors duration-200">
                {showFullRationale ? "Show less" : "Show more"}
              </button>
            )}
          </div>
        )}

        {/* Outreach */}
        {(candidate.outreach_message || candidate.outreach_subject) && (
          <div className="border-t border-black/5">
            <button
              onClick={() => setOutreachOpen(!outreachOpen)}
              className="w-full px-5 py-3 flex items-center justify-between text-sm font-medium text-[#405263] hover:bg-[#F5F5F2] transition-colors duration-200"
            >
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4 text-[#007C92]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                Outreach
                {candidate.outreach_channel && (
                  <span className="text-xs text-[#8AA3B8] font-normal">via {candidate.outreach_channel}</span>
                )}
              </span>
              <svg className={`w-4 h-4 text-[#8AA3B8] transition-transform duration-200 ${outreachOpen ? "rotate-180" : ""}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {outreachOpen && (
              <div className="px-5 pb-4 space-y-2">
                {candidate.outreach_subject && (
                  <div className="bg-[#F5F5F2] rounded-lg px-3 py-2">
                    <span className="text-xs font-semibold text-[#8AA3B8] uppercase tracking-wide">Subject</span>
                    <p className="text-sm text-[#1C2631] mt-0.5 font-medium">{candidate.outreach_subject}</p>
                  </div>
                )}
                {candidate.outreach_message && (
                  <div className="bg-[#F5F5F2] rounded-lg px-3 py-2">
                    <p className="text-sm text-[#405263] whitespace-pre-wrap leading-relaxed">{candidate.outreach_message}</p>
                  </div>
                )}
                <button onClick={handleCopy}
                  className="w-full py-1.5 px-3 rounded-full border border-black/10 text-xs font-medium text-[#405263] hover:bg-[#F5F5F2] transition-colors duration-200 flex items-center justify-center gap-1.5">
                  {copied ? (
                    <><svg className="w-3.5 h-3.5 text-[#1FC86E]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg><span className="text-[#1FC86E]">Copied!</span></>
                  ) : (
                    <><svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>Copy message</>
                  )}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="mt-auto px-5 pb-5 pt-3 border-t border-black/5">
          <button onClick={() => setShowModal(true)}
            className="w-full py-2 px-4 rounded-full border border-[#007C92]/30 bg-[#E8F4F7] text-[#007C92] text-sm font-medium hover:bg-[#d0eaef] transition-colors duration-200 flex items-center justify-center gap-2">
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
