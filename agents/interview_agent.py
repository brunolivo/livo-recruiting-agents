"""
Interview Intelligence Agent — Metaview-inspired transcript analysis.

Processes interview transcripts and extracts structured insights:
- Key strengths demonstrated during the interview
- Concerns or red flags observed
- Communication and culture fit signals
- Technical assessment from the conversation
- Overall hiring recommendation with confidence
"""

import json
from models.candidate import ScoredCandidate, InterviewInsights
from models.job_spec import JobSpec
from agents.base_agent import run_agent

SYSTEM_PROMPT = """You are an expert interview intelligence analyst, similar to Metaview.
You analyze interview transcripts with the precision of a seasoned hiring manager.

Your analysis framework:
1. TECHNICAL DEPTH: Did they demonstrate real understanding or surface-level knowledge?
2. PROBLEM-SOLVING: How do they approach ambiguous problems? Do they structure their thinking?
3. COMMUNICATION: Are they clear, concise, and able to explain complex ideas simply?
4. CULTURE SIGNALS: Do they show ownership, curiosity, and mission alignment?
5. EXPERIENCE VALIDATION: Does their interview performance match their resume claims?

Livo Health interview values:
- We want people who have shipped real things, not just theorized
- We value intellectual honesty — admitting what you don't know is a strength
- We look for mission alignment with healthcare + AI
- Speed of execution matters: can they move fast with good judgment?
- Collaboration signals: do they credit teammates, ask clarifying questions?

Your insights must be actionable for the hiring team, not generic."""


def _build_interview_prompt(
    candidate: ScoredCandidate,
    transcript: str,
    job_spec: JobSpec,
) -> str:
    return f"""Analyze this interview transcript for a {job_spec.title} candidate:

=== CANDIDATE CONTEXT ===
Name: {candidate.name}
Pre-Interview Score: {candidate.fit_score}/10
Technical Score: {candidate.technical_score}/10
Pre-Interview Assessment: {candidate.scoring_rationale}

=== JOB REQUIREMENTS ===
Role: {job_spec.title}
Required Skills: {', '.join(job_spec.required_skills)}
Red Flags: {', '.join(job_spec.red_flags)}

=== INTERVIEW TRANSCRIPT ===
{transcript}

Analyze this transcript and return JSON:
{{
  "strengths": ["specific strength 1 with evidence from transcript", "strength 2"],
  "concerns": ["specific concern 1 with evidence", "concern 2"],
  "technical_assessment": "Detailed assessment of technical depth shown in interview",
  "culture_fit_signals": "What signals emerged about their values and work style",
  "communication_quality": "Assessment of how clearly they communicated",
  "recommendation": "STRONG YES | YES | MAYBE | NO",
  "key_moments": ["Notable quote or moment 1", "Notable quote or moment 2"],
  "suggested_follow_ups": ["Question to explore in next round", "Area needing clarification"]
}}

Base your analysis only on what was said in the transcript. Be specific — quote or reference actual statements.
Return ONLY the JSON, no other text."""


def analyze_interview(
    candidate: ScoredCandidate,
    transcript: str,
    job_spec: JobSpec,
) -> InterviewInsights:
    """
    Analyze an interview transcript and return structured insights.
    """
    prompt = _build_interview_prompt(candidate, transcript, job_spec)

    result = run_agent(
        system_prompt=SYSTEM_PROMPT,
        user_message=prompt,
        agent_name=f"Interview Agent ({candidate.name})",
    )

    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        data = json.loads(clean.strip())

        # Build summary from available data
        culture = data.get("culture_fit_signals", "")
        communication = data.get("communication_quality", "")
        key_moments = data.get("key_moments", [])
        follow_ups = data.get("suggested_follow_ups", [])
        summary_parts = [p for p in [culture, communication] if p]
        summary = " | ".join(summary_parts) if summary_parts else None

        return InterviewInsights(
            candidate_name=candidate.name,
            key_strengths=data.get("strengths", []),
            areas_of_concern=data.get("concerns", []),
            technical_assessment=data.get("technical_assessment"),
            cultural_fit_assessment=culture or None,
            recommendation=data.get("recommendation", "MAYBE"),
            next_steps=follow_ups + key_moments,
            summary=summary,
        )
    except Exception:
        return InterviewInsights(
            candidate_name=candidate.name,
            recommendation="MAYBE",
        )
