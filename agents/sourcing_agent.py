"""
Sourcing Agent — finds real candidate profiles from live platform APIs.

Technical roles (AI Engineer, Data Scientist):
  GitHub API → real repo owners with AI/ML projects
  HuggingFace API → real model authors
  ArXiv API → real researchers

Non-technical roles (AI PM, AI Designer):
  LLM + Brave search (no structured public APIs exist for these)

The LLM's job here is synthesis and mapping, not discovery.
Discovery is done by the APIs with real data.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from models.job_spec import JobSpec
from models.candidate import Candidate, CandidateSource, RoleType
from agents.base_agent import run_agent, PLATFORMS
from tools import github_api, huggingface_api, arxiv_api

SYSTEM_PROMPT = """You are a talent sourcer. You receive real candidate profiles fetched
from GitHub, HuggingFace, and ArXiv APIs and map them to a structured format.

Your job:
1. Select the most relevant candidates for the role from the real profiles provided
2. Fill in the structured fields accurately from the real data — do NOT invent details
3. Infer skills from actual repos, models, and papers listed in the profiles
4. Write a factual headline based on real info, not assumptions

If a field is not in the source data, leave it null — do not fabricate."""

SYSTEM_PROMPT_LLM = """You are an elite talent sourcer specializing in AI professionals.
Search for real professionals matching the requirements using the web_search tool.
Focus on finding actual people with verifiable online presence.
Return only candidates with real, checkable profile URLs."""


def _keywords(job_spec: JobSpec) -> list[str]:
    """Extract meaningful search keywords from the job spec."""
    return (job_spec.sourcing_keywords + job_spec.required_skills)[:8]


def _synthesis_prompt(raw_profiles: list[dict], job_spec: JobSpec, count: int) -> str:
    return f"""Map these REAL profiles (fetched live from APIs) to structured candidates for:

Role: {job_spec.title} at {job_spec.company}
Required skills: {', '.join(job_spec.required_skills)}
Nice to have: {', '.join(job_spec.nice_to_have_skills)}

REAL PROFILES (do not invent — only use what's here):
{json.dumps(raw_profiles, indent=2)}

Select the top {count} most relevant and return as a JSON array:
[
  {{
    "name": "exact name from profile",
    "role_type": "{job_spec.role_type.value}",
    "source": "GitHub|HuggingFace|ArXiv",
    "profile_url": "exact URL from profile",
    "headline": "factual headline from their actual bio/work",
    "location": "from profile or null",
    "skills": ["from their actual repos/models/papers"],
    "experience_years": null,
    "notable_work": "from their actual top repo/model/paper",
    "open_source_contributions": "GitHub repos or HF models if applicable",
    "publications": "paper titles if ArXiv source"
  }}
]

Return ONLY the JSON array. Use only data present in the profiles above."""


def _llm_sourcing_prompt(job_spec: JobSpec, num_candidates: int) -> str:
    platforms = PLATFORMS.get(job_spec.role_type.value + "s", job_spec.preferred_platforms)
    return f"""Search for {num_candidates} real {job_spec.role_type.value}s for:

ROLE: {job_spec.title} at {job_spec.company}
REQUIRED SKILLS: {', '.join(job_spec.required_skills)}
EXPERIENCE: {job_spec.experience_years_min}+ years
PLATFORMS: {', '.join(platforms)}

Use web_search to find real professionals. Search queries like:
- "site:linkedin.com/in {job_spec.role_type.value} AI"
- "site:twitter.com {' '.join(job_spec.sourcing_keywords[:3])}"

Return EXACTLY {num_candidates} real candidates as a JSON array:
[{{
  "name": "Real Full Name",
  "role_type": "{job_spec.role_type.value}",
  "source": "LinkedIn|Twitter/X|Community|Dribbble",
  "profile_url": "real URL",
  "headline": "their actual headline",
  "location": "city, country",
  "skills": ["skill1", "skill2"],
  "experience_years": 5,
  "notable_work": "their standout work",
  "portfolio_url": "portfolio if designer"
}}]

Return ONLY the JSON array."""


def _parse_candidates(raw: str, job_spec: JobSpec) -> list[Candidate]:
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
    role_map = {v.value: v for v in RoleType}

    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
            clean = clean.strip()
        start, end = clean.find("["), clean.rfind("]") + 1
        if start >= 0 and end > start:
            clean = clean[start:end]
        items = json.loads(clean)
    except Exception:
        return []

    candidates = []
    for d in items:
        source_str = (d.get("source") or "LinkedIn").lower()
        source = source_map.get(source_str, CandidateSource.LINKEDIN)
        role = role_map.get(d.get("role_type", ""), job_spec.role_type)
        candidates.append(Candidate(
            name=d.get("name", "Unknown"),
            role_type=role,
            source=source,
            profile_url=d.get("profile_url"),
            headline=d.get("headline"),
            location=d.get("location"),
            skills=d.get("skills", []),
            experience_years=d.get("experience_years"),
            notable_work=d.get("notable_work"),
            open_source_contributions=d.get("open_source_contributions"),
            publications=d.get("publications"),
            portfolio_url=d.get("portfolio_url"),
        ))
    return candidates


def source_candidates(job_spec: JobSpec, num_candidates: int = 10) -> list[Candidate]:
    """
    Source real candidates. Uses platform APIs for technical roles,
    falls back to LLM + Brave search for PM and Designer roles.
    """
    if job_spec.role_type in (RoleType.AI_ENGINEER, RoleType.DATA_SCIENTIST):
        return _source_technical(job_spec, num_candidates)
    else:
        return _source_via_llm(job_spec, num_candidates)


def _source_technical(job_spec: JobSpec, num_candidates: int) -> list[Candidate]:
    """Use GitHub, HuggingFace, and ArXiv APIs to find real technical candidates."""
    keywords = _keywords(job_spec)

    # Run all three APIs in parallel
    with ThreadPoolExecutor(max_workers=3) as pool:
        gh_fut = pool.submit(github_api.search_engineers, keywords, num_candidates)
        hf_fut = pool.submit(huggingface_api.search_practitioners, job_spec.role_type.value, num_candidates // 2)
        ax_fut = pool.submit(arxiv_api.search_researchers, keywords[:3], max(1, num_candidates // 3))
        gh = gh_fut.result() or []
        hf = hf_fut.result() or []
        ax = ax_fut.result() or []

    raw_profiles: list[dict] = gh + hf + ax

    if not raw_profiles:
        # All APIs failed — fall back to LLM
        return _source_via_llm(job_spec, num_candidates)

    # LLM synthesizes raw API data into structured Candidate objects (no web search needed)
    prompt = _synthesis_prompt(raw_profiles, job_spec, num_candidates)
    result = run_agent(
        system_prompt=SYSTEM_PROMPT,
        user_message=prompt,
        agent_name=f"Sourcing Agent ({job_spec.role_type.value})",
        use_web_search=False,
    )
    candidates = _parse_candidates(result, job_spec)

    # If synthesis failed, build candidates directly from raw profiles
    if not candidates:
        candidates = _direct_map(raw_profiles[:num_candidates], job_spec)

    return candidates[:num_candidates]


def _source_via_llm(job_spec: JobSpec, num_candidates: int) -> list[Candidate]:
    """For PM and Designer roles — use LLM + Brave to search LinkedIn/Twitter/Dribbble."""
    prompt = _llm_sourcing_prompt(job_spec, num_candidates)
    result = run_agent(
        system_prompt=SYSTEM_PROMPT_LLM,
        user_message=prompt,
        agent_name=f"Sourcing Agent ({job_spec.role_type.value})",
    )
    return _parse_candidates(result, job_spec)


def _direct_map(raw_profiles: list[dict], job_spec: JobSpec) -> list[Candidate]:
    """Fallback: map raw API profiles directly to Candidate objects without LLM."""
    source_map = {
        "GitHub": CandidateSource.GITHUB,
        "HuggingFace": CandidateSource.HUGGINGFACE,
        "ArXiv": CandidateSource.ARXIV,
    }
    candidates = []
    for p in raw_profiles:
        source = source_map.get(p.get("source", ""), CandidateSource.GITHUB)
        candidates.append(Candidate(
            name=p.get("name", "Unknown"),
            role_type=job_spec.role_type,
            source=source,
            profile_url=p.get("profile_url"),
            headline=p.get("headline"),
            location=p.get("location"),
            skills=p.get("skills", []),
            notable_work=p.get("notable_work"),
            open_source_contributions=", ".join(
                r["name"] for r in p.get("top_repos", [])[:3]
            ) or None,
            publications=p.get("publications"),
        ))
    return candidates
