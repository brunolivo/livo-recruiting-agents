"use client";

import { useState } from "react";
import type { Candidate } from "@/lib/types";
import InterviewModal from "./InterviewModal";

interface Props {
  candidate: Candidate;
  jobId: string;
  apiUrl: string;
}

function getSourceStyle(source: string): string {
  const s = source.toLowerCase();
  if (s.includes("linkedin")) return "bg-blue-100 text-blue-700";
  if (s.includes("github")) return "bg-gray-800 text-white";
  if (s.includes("hugging") || s.includes("hf")) return "bg-yellow-100 text-yellow-800";
  if (s.includes("kaggle")) return "bg-cyan-100 text-cyan-800";
  if (s.includes("twitter") || s.includes("x.com")) return "bg-gray-900 text-white";
  if (s.includes("arxiv")) return "bg-red-100 text-red-700";
  return "bg-purple-100 text-purple-700";
}

function getSourceLabel(source: string): string {
  const s = source.toLowerCase();
  if (s.includes("linkedin")) return "LinkedIn";
  if (s.includes("github")) return "GitHub";
  if (s.includes("hugging") || s.includes("hf")) return "HuggingFace";
  if (s.includes("kaggle")) return "Kaggle";
  if (s.includes("twitter")) return "Twitter/X";
  if (s.includes("arxiv")) return "ArXiv";
  return source;
}

function ScoreCircle({ score }: { score: number }) {
  const color =
    score >= 8
      ? "border-green-400 text-green-600"
      : score >= 6
      ? "border-amber-400 text-amber-600"
      : "border-red-400 text-red-500";

  return (
    <div
      className={`w-14 h-14 rounded-full border-4 flex flex-col items-center justify-center flex-shrink-0 ${color}`}
    >
      <span className="text-lg font-bold leading-none">{score.toFixed(1)}</span>
      <span className="text-[9px] text-gray-400 leading-none mt-0.5">score</span>
    </div>
  );
}

export default function CandidateCard({ candidate, jobId, apiUrl }: Props) {
  const [outreachOpen, setOutreachOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showFullRationale, setShowFullRationale] = useState(false);
  const [showModal, setShowModal] = useState(false);

  const MAX_SKILLS = 6;
  const visibleSkills = candidate.skills.slice(0, MAX_SKILLS);
  const extraSkills = candidate.skills.length - MAX_SKILLS;

  const handleCopy = async () => {
    const text = [
      candidate.outreach_subject ? `Subject: ${candidate.outreach_subject}` : "",
      "",
      candidate.outreach_message ?? "",
    ]
      .join("\n")
      .trim();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback — ignore
    }
  };

  return (
    <>
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow flex flex-col overflow-hidden">
        {/* Card header */}
        <div className="px-5 pt-5 pb-4">
          <div className="flex items-start justify-between gap-3">
            {/* Name + headline */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                {candidate.profile_url ? (
                  <a
                    href={candidate.profile_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-base font-bold text-gray-900 hover:text-indigo-600 transition-colors"
                  >
                    {candidate.name}
                  </a>
                ) : (
                  <span className="text-base font-bold text-gray-900">{candidate.name}</span>
                )}
                {candidate.recommended && (
                  <span className="px-2 py-0.5 bg-indigo-50 text-indigo-600 text-xs font-semibold rounded-full border border-indigo-100">
                    Recommended
                  </span>
                )}
              </div>
              {candidate.headline && (
                <p className="text-sm text-gray-500 mt-0.5 leading-snug line-clamp-2">
                  {candidate.headline}
                </p>
              )}
            </div>
            <ScoreCircle score={candidate.fit_score} />
          </div>

          {/* Meta row */}
          <div className="flex items-center gap-2 flex-wrap mt-3">
            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${getSourceStyle(candidate.source)}`}
            >
              {getSourceLabel(candidate.source)}
            </span>
            {candidate.location && (
              <span className="text-xs text-gray-400 flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                {candidate.location}
              </span>
            )}
            {candidate.experience_years != null && (
              <span className="text-xs text-gray-400">
                {candidate.experience_years}y exp
              </span>
            )}
          </div>
        </div>

        {/* Sub-scores */}
        <div className="px-5 py-2 bg-gray-50 border-y border-gray-100 flex gap-4">
          {[
            { label: "Technical", value: candidate.technical_score },
            { label: "Culture", value: candidate.culture_score },
          ].map(({ label, value }) => (
            <div key={label} className="flex items-center gap-1.5">
              <span className="text-xs text-gray-500">{label}</span>
              <div className="flex gap-0.5">
                {Array.from({ length: 10 }).map((_, i) => (
                  <div
                    key={i}
                    className={`w-1.5 h-3 rounded-sm ${
                      i < Math.round(value)
                        ? value >= 8
                          ? "bg-green-400"
                          : value >= 6
                          ? "bg-amber-400"
                          : "bg-red-400"
                        : "bg-gray-200"
                    }`}
                  />
                ))}
              </div>
              <span className="text-xs font-semibold text-gray-600">{value.toFixed(1)}</span>
            </div>
          ))}
        </div>

        {/* Skills */}
        <div className="px-5 py-3">
          <div className="flex flex-wrap gap-1.5">
            {visibleSkills.map((skill) => (
              <span
                key={skill}
                className="px-2 py-0.5 bg-indigo-50 text-indigo-700 text-xs rounded-md border border-indigo-100 font-medium"
              >
                {skill}
              </span>
            ))}
            {extraSkills > 0 && (
              <span className="px-2 py-0.5 bg-gray-100 text-gray-500 text-xs rounded-md font-medium">
                +{extraSkills} more
              </span>
            )}
          </div>
        </div>

        {/* Scoring rationale */}
        {candidate.scoring_rationale && (
          <div className="px-5 pb-3">
            <p
              className={`text-xs text-gray-600 leading-relaxed ${
                showFullRationale ? "" : "line-clamp-2"
              }`}
            >
              {candidate.scoring_rationale}
            </p>
            {candidate.scoring_rationale.length > 120 && (
              <button
                onClick={() => setShowFullRationale(!showFullRationale)}
                className="text-xs text-indigo-500 hover:text-indigo-700 mt-0.5 font-medium"
              >
                {showFullRationale ? "Show less" : "Show more"}
              </button>
            )}
          </div>
        )}

        {/* Outreach section */}
        {(candidate.outreach_message || candidate.outreach_subject) && (
          <div className="border-t border-gray-100">
            <button
              onClick={() => setOutreachOpen(!outreachOpen)}
              className="w-full px-5 py-3 flex items-center justify-between text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                Outreach Message
                {candidate.outreach_channel && (
                  <span className="text-xs text-gray-400 font-normal">
                    via {candidate.outreach_channel}
                  </span>
                )}
              </span>
              <svg
                className={`w-4 h-4 text-gray-400 transition-transform ${outreachOpen ? "rotate-180" : ""}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {outreachOpen && (
              <div className="px-5 pb-4 space-y-2">
                {candidate.outreach_subject && (
                  <div className="bg-gray-50 rounded-lg px-3 py-2">
                    <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Subject</span>
                    <p className="text-sm text-gray-800 mt-0.5 font-medium">{candidate.outreach_subject}</p>
                  </div>
                )}
                {candidate.outreach_message && (
                  <div className="bg-gray-50 rounded-lg px-3 py-2">
                    <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Message</span>
                    <p className="text-sm text-gray-700 mt-0.5 whitespace-pre-wrap leading-relaxed">
                      {candidate.outreach_message}
                    </p>
                  </div>
                )}
                <button
                  onClick={handleCopy}
                  className="w-full py-1.5 px-3 rounded-lg border border-gray-200 text-xs font-medium text-gray-600 hover:bg-gray-50 transition-colors flex items-center justify-center gap-1.5"
                >
                  {copied ? (
                    <>
                      <svg className="w-3.5 h-3.5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                      </svg>
                      <span className="text-green-600">Copied!</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                      Copy
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Footer: Analyze Interview button */}
        <div className="mt-auto px-5 pb-5 pt-3 border-t border-gray-100">
          <button
            onClick={() => setShowModal(true)}
            className="w-full py-2 px-4 rounded-lg border border-indigo-200 bg-indigo-50 text-indigo-700 text-sm font-medium hover:bg-indigo-100 transition-colors flex items-center justify-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            Analyze Interview
          </button>
        </div>
      </div>

      {/* Interview modal */}
      {showModal && (
        <InterviewModal
          candidate={candidate}
          jobId={jobId}
          apiUrl={apiUrl}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  );
}
