"""
Outreach Agent — Generates personalized outreach for all recommended candidates
in a single batched LLM call instead of one call per person.
"""

import json
from models.candidate import ScoredCandidate, OutreachedCandidate
from models.job_spec import JobSpec
from agents.base_agent import run_agent

SYSTEM_PROMPT = """You are a world-class recruiting outreach specialist who writes messages
that candidates actually respond to.

Your outreach philosophy:
- NEVER send generic openers — always reference something specific about their work
- Lead with value to THEM, not the job description
- Match platform style: LinkedIn (150-200 words), Email (200-300 words), Twitter DM (50-80 words)
- Sound human, not templated

Livo Health: AI-powered healthcare staffing in Spain — matching nurses and doctors
with hospitals using intelligent scheduling. Fast-growing, mission-driven, remote-friendly."""

_CHANNEL_MAP = {
    "LinkedIn": "LinkedIn InMail",
    "GitHub": "Email",
    "HuggingFace": "Email",
    "Kaggle": "Email",
    "Twitter/X": "Twitter DM",
    "Dribbble": "Email",
    "ArXiv": "Email",
    "Community": "LinkedIn InMail",
}


def generate_outreach_batch(
    candidates: list[ScoredCandidate],
    job_spec: JobSpec,
) -> list[OutreachedCandidate]:
    """
    Generate personalized outreach for all recommended candidates in one LLM call.
    """
    targets = [c for c in candidates if c.recommended]
    if not targets:
        return []

    profiles = [
        {
            "index": i,
            "name": c.name,
            "channel": _CHANNEL_MAP.get(c.source.value, "LinkedIn InMail"),
            "headline": c.headline or "",
            "notable_work": c.notable_work or "",
            "recent_activity": c.recent_activity or "",
            "ai_expertise_depth": c.ai_expertise_depth or "",
            "technical_score": c.technical_score,
            "scoring_rationale": c.scoring_rationale or "",
        }
        for i, c in enumerate(targets)
    ]

    prompt = f"""Write personalized outreach messages for these {len(targets)} candidates being recruited for:

ROLE: {job_spec.title} at {job_spec.company}
REQUIRED SKILLS: {', '.join(job_spec.required_skills)}

CANDIDATES:
{json.dumps(profiles, indent=2)}

For each candidate, use their specific work and achievements — never generic openers.
Start messages with their specific achievement, not their name.

Return a JSON array:
[
  {{
    "index": 0,
    "outreach_subject": "email subject or LinkedIn title",
    "outreach_message": "full personalized message",
    "outreach_channel": "the channel from their profile",
    "key_hook": "the specific thing we're referencing about their work"
  }}
]

Return ONLY the JSON array."""

    result = run_agent(
        system_prompt=SYSTEM_PROMPT,
        user_message=prompt,
        agent_name=f"Outreach Agent (batch {len(targets)})",
        use_web_search=False,
    )

    outreach_map: dict[int, dict] = {}
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
        outreach_map = {item["index"]: item for item in items if "index" in item}
    except Exception:
        pass

    outreached = []
    for i, candidate in enumerate(targets):
        data = outreach_map.get(i, {})
        outreached.append(OutreachedCandidate(
            **candidate.model_dump(),
            outreach_subject=data.get("outreach_subject"),
            outreach_message=data.get("outreach_message"),
            outreach_channel=data.get("outreach_channel", _CHANNEL_MAP.get(candidate.source.value, "Email")),
        ))

    return outreached
