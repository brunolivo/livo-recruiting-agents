"""
Sourcing Agent — Searches across professional platforms to find candidate profiles.
Inspired by Juicebox's natural language search across LinkedIn and communities.

Covers:
- LinkedIn (professional profiles)
- GitHub (AI Engineers, Data Scientists)
- HuggingFace (ML practitioners)
- Kaggle (Data Scientists)
- Dribbble/Behance (Designers)
- Twitter/X (thought leaders)
- ArXiv (researchers)
- Product communities (PMs)
"""

import json
from models.job_spec import JobSpec
from models.candidate import Candidate, CandidateSource, RoleType
from agents.base_agent import run_agent, PLATFORMS

SYSTEM_PROMPT = """You are an elite talent sourcer specializing in AI professionals.
You know exactly where to find the best AI talent across the internet.

Your sourcing strategy:
- LinkedIn: search for professionals with AI-specific titles and skills
- GitHub: find active contributors to AI/ML repos, look at profile READMEs and pinned repos
- HuggingFace: find model authors, dataset creators, and space builders
- Kaggle: find competition winners and notebook authors in ML
- Twitter/X: identify AI thought leaders with strong engagement
- Dribbble/Behance: find designers with AI product portfolios
- ArXiv: find researchers publishing on applied AI topics
- Community sources: Discord servers, Slack groups, newsletters

When you search, use SPECIFIC queries that would surface real profiles:
- For LinkedIn: Use boolean search syntax
- For GitHub: Search for repos, profiles, contributions
- For HuggingFace: Look at model hubs, spaces
- For Kaggle: Search competition leaderboards

Return candidates as a JSON array. Each candidate MUST include:
- name (realistic full name)
- role_type
- source (which platform they were found on)
- profile_url (realistic URL)
- headline (their professional headline)
- skills (list of 5-10 skills)
- notable_work (their standout project or achievement)

Be realistic - describe candidates you would actually find with these searches."""


def _build_sourcing_prompt(job_spec: JobSpec, num_candidates: int) -> str:
    platforms = PLATFORMS.get(job_spec.role_type.value + "s", job_spec.preferred_platforms)

    return f"""Search for top {job_spec.role_type.value}s for this position:

ROLE: {job_spec.title} at {job_spec.company}
REQUIRED SKILLS: {', '.join(job_spec.required_skills)}
NICE TO HAVE: {', '.join(job_spec.nice_to_have_skills)}
EXPERIENCE: {job_spec.experience_years_min}+ years
KEYWORDS: {', '.join(job_spec.sourcing_keywords)}
IDEAL BACKGROUND: {job_spec.ideal_background or 'Senior AI professional with strong portfolio'}

PLATFORMS TO SEARCH: {', '.join(platforms)}

Search across these platforms using the web_search tool. Look for:
1. LinkedIn profiles of AI professionals matching these requirements
2. GitHub profiles of engineers with relevant repos and contributions
3. HuggingFace profiles of ML practitioners (for AI Engineer/Data Scientist roles)
4. Kaggle profiles (for Data Scientists)
5. Twitter/X profiles of thought leaders in this space
6. Portfolio sites and personal pages

For each search, use specific queries like:
- "site:linkedin.com/in AI product manager LLM"
- "site:github.com machine learning engineer open source"
- "site:huggingface.co top models"
- "site:kaggle.com data scientist competition winner"

After searching, return EXACTLY {num_candidates} candidates as a JSON array:
[
  {{
    "name": "Full Name",
    "role_type": "{job_spec.role_type.value}",
    "source": "LinkedIn|GitHub|HuggingFace|Kaggle|Twitter/X|Dribbble|ArXiv|Community",
    "profile_url": "https://...",
    "headline": "Their professional headline",
    "location": "City, Country or Remote",
    "skills": ["skill1", "skill2", "skill3"],
    "experience_years": 5,
    "notable_work": "Description of their standout project or achievement",
    "open_source_contributions": "Notable repos or contributions (if applicable)",
    "publications": "Papers or articles (if applicable)",
    "portfolio_url": "https://... (for designers)"
  }}
]

Return ONLY the JSON array, no other text."""


def source_candidates(
    job_spec: JobSpec,
    num_candidates: int = 10,
) -> list[Candidate]:
    """
    Search across platforms and return a list of potential candidates.
    """
    prompt = _build_sourcing_prompt(job_spec, num_candidates)

    result = run_agent(
        system_prompt=SYSTEM_PROMPT,
        user_message=prompt,
        agent_name=f"Sourcing Agent ({job_spec.role_type.value})",
    )

    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
            clean = clean.strip()
        # Find JSON array
        start = clean.find("[")
        end = clean.rfind("]") + 1
        if start >= 0 and end > start:
            clean = clean[start:end]

        candidates_data = json.loads(clean)
        candidates = []
        for data in candidates_data:
            # Map source string to enum
            source_map = {
                "linkedin": CandidateSource.LINKEDIN,
                "github": CandidateSource.GITHUB,
                "huggingface": CandidateSource.HUGGINGFACE,
                "kaggle": CandidateSource.KAGGLE,
                "twitter/x": CandidateSource.TWITTER,
                "twitter": CandidateSource.TWITTER,
                "dribbble": CandidateSource.DRIBBBLE,
                "arxiv": CandidateSource.ARXIV,
                "community": CandidateSource.COMMUNITY,
            }
            source_str = data.get("source", "LinkedIn").lower()
            source = source_map.get(source_str, CandidateSource.LINKEDIN)

            # Map role_type string to enum
            role_map = {v.value: v for v in RoleType}
            role_str = data.get("role_type", job_spec.role_type.value)
            role = role_map.get(role_str, job_spec.role_type)

            candidates.append(Candidate(
                name=data.get("name", "Unknown"),
                role_type=role,
                source=source,
                profile_url=data.get("profile_url"),
                headline=data.get("headline"),
                location=data.get("location"),
                skills=data.get("skills", []),
                experience_years=data.get("experience_years"),
                notable_work=data.get("notable_work"),
                open_source_contributions=data.get("open_source_contributions"),
                publications=data.get("publications"),
                portfolio_url=data.get("portfolio_url"),
            ))
        return candidates
    except Exception as e:
        return []
