"""
Profile Enrichment Agent — Enriches all candidates in a single batched LLM call.

For technical candidates (GitHub/HuggingFace/ArXiv) we already have rich profile
data from the APIs, so web search is skipped. All candidates are processed in one
request instead of one call per person.
"""

import json
from models.candidate import Candidate, EnrichedCandidate
from agents.base_agent import run_agent
from tools import hunter_api

SYSTEM_PROMPT = """You are a talent intelligence specialist who synthesizes candidate profiles
into structured enrichment data.

For each candidate, assess:
1. Depth of AI expertise (surface/developing/proficient/expert) based on their actual work
2. Recent activity — what they've been building or publishing
3. Community presence — influence, followers, published models/papers
4. A concise professional summary

Work only from the data provided. Do not invent details."""


def enrich_candidates_batch(candidates: list[Candidate]) -> list[EnrichedCandidate]:
    """
    Enrich all candidates in a single LLM call. No web search — uses profile data
    already fetched from GitHub/HuggingFace/ArXiv.
    """
    if not candidates:
        return []

    profiles = [
        {
            "index": i,
            "name": c.name,
            "source": c.source.value,
            "headline": c.headline or "",
            "skills": c.skills,
            "notable_work": c.notable_work or "",
            "location": c.location or "",
            "open_source_contributions": c.open_source_contributions or "",
            "publications": c.publications or "",
        }
        for i, c in enumerate(candidates)
    ]

    prompt = f"""Enrich these {len(candidates)} candidate profiles. Use only the data provided.

PROFILES:
{json.dumps(profiles, indent=2)}

Return a JSON array with one object per candidate, in the same order:
[
  {{
    "index": 0,
    "enriched_summary": "2-3 sentence professional synthesis",
    "ai_expertise_depth": "surface|developing|proficient|expert",
    "recent_activity": "what they've been working on based on their profile",
    "community_presence": "their influence and presence in the AI community"
  }}
]

Return ONLY the JSON array. Keep each field concise (1-2 sentences max)."""

    result = run_agent(
        system_prompt=SYSTEM_PROMPT,
        user_message=prompt,
        agent_name=f"Enrichment Agent (batch {len(candidates)})",
        use_web_search=False,
    )

    enrichment_map: dict[int, dict] = {}
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
        enrichment_map = {item["index"]: item for item in items if "index" in item}
    except Exception:
        pass

    # Parallel Hunter.io email lookups for candidates without a known email
    needs_email = [
        {"name": c.name, "blog": getattr(c, "blog", None), "company": c.company if hasattr(c, "company") else None}
        for c in candidates if not c.email
    ]
    email_map = hunter_api.find_emails_batch(needs_email) if needs_email else {}

    enriched = []
    for i, candidate in enumerate(candidates):
        data = enrichment_map.get(i, {})
        email = candidate.email or email_map.get(candidate.name)
        enriched.append(EnrichedCandidate(
            **{**candidate.model_dump(), "email": email},
            enriched_summary=data.get("enriched_summary"),
            ai_expertise_depth=data.get("ai_expertise_depth"),
            recent_activity=data.get("recent_activity"),
            community_presence=data.get("community_presence"),
        ))
    return enriched
