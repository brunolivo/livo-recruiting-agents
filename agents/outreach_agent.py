"""
Outreach Agent — Crafts hyper-personalized outreach messages for each candidate.
Inspired by Juicebox's personalized messaging feature.

Creates platform-specific outreach that:
- References the candidate's specific work (not generic)
- Speaks to their motivations (not just the job)
- Uses the right tone for the platform (LinkedIn vs email vs Twitter)
- Includes a specific hook based on their recent activity
"""

import json
from models.candidate import ScoredCandidate, OutreachedCandidate
from models.job_spec import JobSpec
from agents.base_agent import run_agent

SYSTEM_PROMPT = """You are a world-class recruiting outreach specialist who writes messages
that candidates actually respond to.

Your outreach philosophy:
- NEVER send generic "I came across your profile" messages
- Always reference something SPECIFIC about their work
- Lead with value to THEM, not the job description
- Match the platform's communication style
- Keep it concise — respect their time
- Create genuine curiosity about the opportunity

Platform styles:
- LinkedIn: Professional but warm, 150-200 words max
- Email: Slightly longer, can include more context, 200-300 words
- Twitter/X DM: Very short, casual, 50-80 words max, reference a specific tweet

Livo Health's story to share:
- We're using AI to transform healthcare staffing in Spain
- We match nurses and doctors with hospitals using intelligent scheduling
- We're growing fast and building cutting-edge AI products
- Strong engineering culture, mission-driven team
- Competitive comp, remote-friendly

Your messages must feel like they came from a real person who did their homework."""


def _build_outreach_prompt(candidate: ScoredCandidate, job_spec: JobSpec) -> str:
    # Choose best channel based on source
    channel_map = {
        "LinkedIn": "LinkedIn InMail",
        "GitHub": "Email",
        "HuggingFace": "Email",
        "Kaggle": "Email",
        "Twitter/X": "Twitter DM",
        "Dribbble": "Email",
        "ArXiv": "Email",
        "Community": "LinkedIn InMail",
    }
    channel = channel_map.get(candidate.source.value, "LinkedIn InMail")

    return f"""Write a personalized outreach message for this candidate:

=== CANDIDATE ===
Name: {candidate.name}
Role Being Recruited For: {job_spec.title}
Source Platform: {candidate.source.value}
Outreach Channel: {channel}
Headline: {candidate.headline}
Notable Work: {candidate.notable_work}
Recent Activity: {candidate.recent_activity}
AI Expertise: {candidate.ai_expertise_depth}
Scoring Rationale: {candidate.scoring_rationale}

=== WHAT MAKES THEM STAND OUT ===
Technical Score: {candidate.technical_score}/10
Why we want them: Pick 2-3 specific things from their profile that impressed us

Generate a JSON response with:
{{
  "outreach_subject": "Email subject line or LinkedIn message title (for email/DM)",
  "outreach_message": "The full personalized outreach message",
  "outreach_channel": "{channel}",
  "key_hook": "The specific thing about their work we're referencing"
}}

Message requirements:
- Start with their specific achievement or work (not their name or a generic opener)
- Mention Livo Health and what we're building in 1-2 sentences
- Connect their specific expertise to what we need
- Include a clear but soft call to action (30-minute chat)
- Sound human, not like a template

Return ONLY the JSON, no other text."""


def generate_outreach(candidate: ScoredCandidate, job_spec: JobSpec) -> OutreachedCandidate:
    """
    Generate a personalized outreach message for a candidate.
    """
    prompt = _build_outreach_prompt(candidate, job_spec)

    result = run_agent(
        system_prompt=SYSTEM_PROMPT,
        user_message=prompt,
        agent_name=f"Outreach Agent ({candidate.name})",
    )

    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        data = json.loads(clean.strip())

        return OutreachedCandidate(
            **candidate.model_dump(),
            outreach_subject=data.get("outreach_subject"),
            outreach_message=data.get("outreach_message"),
            outreach_channel=data.get("outreach_channel"),
        )
    except Exception:
        return OutreachedCandidate(**candidate.model_dump())


def generate_outreach_batch(
    candidates: list[ScoredCandidate],
    job_spec: JobSpec,
) -> list[OutreachedCandidate]:
    """
    Generate outreach for a batch of recommended candidates.
    """
    return [generate_outreach(c, job_spec) for c in candidates if c.recommended]
