"""
Profile Enrichment Agent — Enriches candidate profiles with additional context.
Similar to Juicebox's profile synthesis feature — combines signals from multiple sources.

Takes raw candidate data and:
- Searches for additional context about the candidate
- Synthesizes their AI expertise level
- Finds recent activity and thought leadership signals
- Evaluates their community presence
"""

import json
from models.candidate import Candidate, EnrichedCandidate
from agents.base_agent import run_agent

SYSTEM_PROMPT = """You are a talent intelligence specialist who enriches candidate profiles
with deep research and context synthesis.

For each candidate, you:
1. Research their online presence across platforms
2. Assess depth of their AI expertise (surface vs. deep)
3. Find recent activity (last 3-6 months of work)
4. Evaluate community influence (followers, engagement, speaking)
5. Synthesize a comprehensive candidate summary

You look for signals like:
- GitHub stars, forks, and recent commit activity
- HuggingFace model downloads and community engagement
- Conference talks and publications
- Open source leadership vs. just contributions
- Thought leadership on Twitter/X or LinkedIn
- Kaggle competition rankings and notebook engagement

Be honest and precise. Distinguish between candidates who are genuinely deep in AI
vs. those who just list it on their resume."""


def enrich_candidate(candidate: Candidate) -> EnrichedCandidate:
    """
    Enrich a single candidate profile with additional research.
    """
    prompt = f"""Research and enrich this candidate profile:

NAME: {candidate.name}
ROLE: {candidate.role_type.value}
SOURCE: {candidate.source.value}
PROFILE: {candidate.profile_url or 'No URL provided'}
HEADLINE: {candidate.headline or 'Not available'}
SKILLS: {', '.join(candidate.skills)}
NOTABLE WORK: {candidate.notable_work or 'Not available'}

Use web_search to find more information about this candidate:
1. Search for "{candidate.name} AI {candidate.role_type.value}"
2. If they have a GitHub, search for their repos and contributions
3. Look for any publications, talks, or articles they've written
4. Check their community presence and recent activity

Based on your research, return a JSON object with these enrichment fields:
{{
  "enriched_summary": "2-3 sentence synthesis of who this person is professionally",
  "ai_expertise_depth": "surface|developing|proficient|expert",
  "recent_activity": "Description of what they've been working on recently",
  "community_presence": "Description of their influence and presence in the AI community"
}}

Return ONLY the JSON, no other text."""

    result = run_agent(
        system_prompt=SYSTEM_PROMPT,
        user_message=prompt,
        agent_name=f"Enrichment Agent ({candidate.name})",
    )

    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        data = json.loads(clean.strip())

        return EnrichedCandidate(
            **candidate.model_dump(),
            enriched_summary=data.get("enriched_summary"),
            ai_expertise_depth=data.get("ai_expertise_depth"),
            recent_activity=data.get("recent_activity"),
            community_presence=data.get("community_presence"),
        )
    except Exception:
        return EnrichedCandidate(**candidate.model_dump())


def enrich_candidates_batch(candidates: list[Candidate]) -> list[EnrichedCandidate]:
    """
    Enrich multiple candidates. For top candidates only to save API calls.
    """
    enriched = []
    for i, candidate in enumerate(candidates):
        enriched.append(enrich_candidate(candidate))
    return enriched
