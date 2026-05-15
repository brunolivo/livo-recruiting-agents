"""
Scoring & Ranking Agent — Evaluates candidates against the job spec.
Similar to Talent River's candidate scoring and Juicebox's fit analysis.

Scores candidates on:
- Technical fit (skills match, depth, recency)
- Experience fit (years, relevant domain)
- Culture/mission fit (values alignment, communication style)
- Overall recommendation
"""

import json
from models.candidate import EnrichedCandidate, ScoredCandidate
from models.job_spec import JobSpec
from agents.base_agent import run_agent

SYSTEM_PROMPT = """You are a senior technical recruiter and hiring assessment specialist.
You evaluate candidates with precision and fairness, focusing on:

1. TECHNICAL FIT (0-10): How well their skills and experience match requirements
2. CULTURE FIT (0-10): Values alignment, communication style, mission fit
3. OVERALL FIT SCORE (0-10): Weighted combination considering all factors

Livo Health's culture values:
- Mission-driven: improving healthcare access through technology
- Fast-paced startup: ability to thrive with ambiguity and ship fast
- Collaborative: cross-functional partnership between product, engineering, design
- Data-driven: evidence-based decision making
- Impact-focused: obsessed with patient and professional outcomes

For each candidate, provide:
- An objective scoring with clear rationale
- Specific strengths that make them stand out
- Specific gaps or concerns
- A clear recommendation: STRONG YES / YES / MAYBE / NO

Be honest and calibrated. Not every candidate should be a YES."""


def _build_scoring_prompt(candidate: EnrichedCandidate, job_spec: JobSpec) -> str:
    return f"""Score this candidate against the job requirements:

=== JOB REQUIREMENTS ===
Role: {job_spec.title} at {job_spec.company}
Required Skills: {', '.join(job_spec.required_skills)}
Nice to Have: {', '.join(job_spec.nice_to_have_skills)}
Experience Required: {job_spec.experience_years_min}+ years
Ideal Background: {job_spec.ideal_background}
Red Flags: {', '.join(job_spec.red_flags)}

=== CANDIDATE PROFILE ===
Name: {candidate.name}
Role Type: {candidate.role_type.value}
Source: {candidate.source.value}
Headline: {candidate.headline}
Skills: {', '.join(candidate.skills)}
Experience: {candidate.experience_years} years
Notable Work: {candidate.notable_work}
AI Expertise Depth: {candidate.ai_expertise_depth}
Recent Activity: {candidate.recent_activity}
Community Presence: {candidate.community_presence}
Summary: {candidate.enriched_summary}

Score this candidate and return JSON:
{{
  "technical_score": 7.5,
  "culture_score": 8.0,
  "fit_score": 7.8,
  "scoring_rationale": "Detailed explanation of scores covering technical match, gaps, culture fit, and overall assessment",
  "recommended": true/false
}}

Scoring guide:
- 9-10: Exceptional, would be a top hire at any company
- 7-8: Strong candidate, clear fit, minor gaps
- 5-6: Potential candidate, notable gaps but worth exploring
- 3-4: Weak fit, significant gaps
- 1-2: Does not meet requirements

Return ONLY the JSON, no other text."""


def score_candidate(candidate: EnrichedCandidate, job_spec: JobSpec) -> ScoredCandidate:
    """
    Score a single candidate against the job spec.
    """
    prompt = _build_scoring_prompt(candidate, job_spec)

    result = run_agent(
        system_prompt=SYSTEM_PROMPT,
        user_message=prompt,
        agent_name=f"Scoring Agent ({candidate.name})",
    )

    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        data = json.loads(clean.strip())

        return ScoredCandidate(
            **candidate.model_dump(),
            fit_score=float(data.get("fit_score", 5.0)),
            technical_score=float(data.get("technical_score", 5.0)),
            culture_score=float(data.get("culture_score", 5.0)),
            scoring_rationale=data.get("scoring_rationale"),
            recommended=bool(data.get("recommended", False)),
        )
    except Exception:
        return ScoredCandidate(**candidate.model_dump())


def score_and_rank_candidates(
    candidates: list[EnrichedCandidate],
    job_spec: JobSpec,
) -> list[ScoredCandidate]:
    """
    Score all candidates and return them ranked by fit score.
    """
    scored = [score_candidate(c, job_spec) for c in candidates]
    return sorted(scored, key=lambda c: c.fit_score, reverse=True)
