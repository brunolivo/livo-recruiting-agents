"""
Scoring & Ranking Agent — Scores all candidates in a single batched LLM call.

All candidates are evaluated together instead of one call per person,
dramatically reducing latency.
"""

import json
from models.candidate import EnrichedCandidate, ScoredCandidate
from models.job_spec import JobSpec
from agents.base_agent import run_agent

SYSTEM_PROMPT = """You are a senior technical recruiter evaluating candidates for AI roles at Livo Health.

Livo Health culture values:
- Mission-driven: improving healthcare access through technology
- Fast-paced startup: ship fast, embrace ambiguity
- Collaborative: cross-functional partnership
- Data-driven: evidence-based decisions
- Impact-focused: patient and professional outcomes

Score each candidate on:
- technical_score (0-10): skills and experience match
- culture_score (0-10): values alignment and startup fit
- fit_score (0-10): weighted overall score
- recommended (true/false): true if fit_score >= 6.5

Be calibrated — not every candidate should be recommended. Use the full range."""


def score_and_rank_candidates(
    candidates: list[EnrichedCandidate],
    job_spec: JobSpec,
) -> list[ScoredCandidate]:
    """
    Score all candidates in a single LLM call and return them ranked by fit score.
    """
    if not candidates:
        return []

    profiles = [
        {
            "index": i,
            "name": c.name,
            "headline": c.headline or "",
            "skills": c.skills,
            "experience_years": c.experience_years,
            "notable_work": c.notable_work or "",
            "ai_expertise_depth": c.ai_expertise_depth or "",
            "recent_activity": c.recent_activity or "",
            "community_presence": c.community_presence or "",
            "enriched_summary": c.enriched_summary or "",
        }
        for i, c in enumerate(candidates)
    ]

    prompt = f"""Score these {len(candidates)} candidates for:

ROLE: {job_spec.title} at {job_spec.company}
REQUIRED SKILLS: {', '.join(job_spec.required_skills)}
NICE TO HAVE: {', '.join(job_spec.nice_to_have_skills)}
EXPERIENCE: {job_spec.experience_years_min}+ years
IDEAL BACKGROUND: {job_spec.ideal_background}
RED FLAGS: {', '.join(job_spec.red_flags)}

CANDIDATES:
{json.dumps(profiles, indent=2)}

Return a JSON array with one object per candidate, in the same order:
[
  {{
    "index": 0,
    "technical_score": 7.5,
    "culture_score": 8.0,
    "fit_score": 7.8,
    "scoring_rationale": "Brief rationale covering technical match, gaps, and culture fit",
    "recommended": true
  }}
]

Scoring: 9-10 exceptional, 7-8 strong, 5-6 potential, 3-4 weak, 1-2 no fit.
recommended=true only if fit_score >= 6.5.
Return ONLY the JSON array."""

    result = run_agent(
        system_prompt=SYSTEM_PROMPT,
        user_message=prompt,
        agent_name=f"Scoring Agent (batch {len(candidates)})",
        use_web_search=False,
    )

    scores_map: dict[int, dict] = {}
    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start, end = clean.find("["), clean.rfind("]") + 1
        if start >= 0 and end > start:
            clean = clean[start:end]
        items = json.loads(clean)
        scores_map = {item["index"]: item for item in items if "index" in item}
    except Exception:
        pass

    scored = []
    for i, candidate in enumerate(candidates):
        data = scores_map.get(i, {})
        scored.append(ScoredCandidate(
            **candidate.model_dump(),
            fit_score=float(data.get("fit_score", 5.0)),
            technical_score=float(data.get("technical_score", 5.0)),
            culture_score=float(data.get("culture_score", 5.0)),
            scoring_rationale=data.get("scoring_rationale"),
            recommended=bool(data.get("recommended", False)),
        ))

    return sorted(scored, key=lambda c: c.fit_score, reverse=True)
