"""
Sourcing Agent — finds real candidate profiles from live platform APIs.

Technical roles (AI Engineer, Data Scientist):
  GitHub API    → real repo owners with AI/ML projects
  HuggingFace API → real model authors
  ArXiv API     → real researchers
  LinkedIn      → professionals found via Brave search + optional Proxycurl enrichment

Non-technical roles (AI PM, AI Designer):
  LinkedIn      → Brave site:linkedin.com/in search + optional Proxycurl enrichment
  LLM + Brave   → web search fallback for Twitter/X, Dribbble, communities

The LLM's job here is synthesis and mapping, not discovery.
Discovery is done by the APIs with real data.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from models.job_spec import JobSpec
from models.candidate import Candidate, CandidateSource, RoleType
from agents.base_agent import run_agent, PLATFORMS
from tools import github_api, huggingface_api, arxiv_api, linkedin_api, papers_with_code_api, semantic_scholar_api

SYSTEM_PROMPT = """You are a talent sourcer. You receive real candidate profiles fetched
from GitHub, HuggingFace, ArXiv, LinkedIn, Papers with Code, and Semantic Scholar and map them to a structured format.

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
    # Use up to 10 keywords: sourcing_keywords first, then required skills, then nice-to-haves
    combined = job_spec.sourcing_keywords + job_spec.required_skills + job_spec.nice_to_have_skills
    # Dedupe while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for k in combined:
        if k.lower() not in seen:
            seen.add(k.lower())
            unique.append(k)
    return unique[:10]


def _loc_terms(location: str) -> list[str]:
    return [t.strip().lower() for t in location.replace(",", " ").split() if len(t.strip()) > 2]


def _annotate_location(profiles: list[dict], location: str | None) -> list[dict]:
    """
    Add a _loc_match field to each profile: "match" | "unknown" | "no_match".
    This lets the LLM and scoring agent make deterministic decisions without guessing.
    """
    if not location:
        return profiles
    terms = _loc_terms(location)
    for p in profiles:
        raw_loc = (p.get("location") or "").lower().strip()
        # Also check affiliations (ArXiv) and company field
        extra = " ".join([
            (p.get("company") or ""),
            " ".join(p.get("affiliations", [])),
        ]).lower()
        haystack = f"{raw_loc} {extra}"

        if not raw_loc and not extra.strip():
            p["_loc_match"] = "unknown"
        elif any(t in haystack for t in terms):
            p["_loc_match"] = "match"
        else:
            p["_loc_match"] = "no_match"
    return profiles


def _sort_by_location(profiles: list[dict]) -> list[dict]:
    """Sort profiles: match → unknown → no_match."""
    order = {"match": 0, "unknown": 1, "no_match": 2}
    return sorted(profiles, key=lambda p: order.get(p.get("_loc_match", "unknown"), 1))


def _synthesis_prompt(raw_profiles: list[dict], job_spec: JobSpec, count: int) -> str:
    if job_spec.location:
        terms = _loc_terms(job_spec.location)
        n_match   = sum(1 for p in raw_profiles if p.get("_loc_match") == "match")
        n_unknown = sum(1 for p in raw_profiles if p.get("_loc_match") == "unknown")
        loc_instruction = f"""
LOCATION FILTER — {job_spec.location} (strict):
Each profile has a _loc_match field:
  "match"    → candidate is in {job_spec.location} — ALWAYS include these first
  "unknown"  → candidate has no location info (may be remote) — include to fill remaining slots
  "no_match" → candidate is in a different location — EXCLUDE unless match+unknown < {count}

Currently: {n_match} match, {n_unknown} unknown in the pool below.
Fill the {count} slots in order: all "match" first, then "unknown", then "no_match" only if needed."""
    else:
        loc_instruction = ""

    return f"""Map these REAL profiles (fetched live from APIs) to structured candidates for:

Role: {job_spec.title} at {job_spec.company}
Required skills: {', '.join(job_spec.required_skills)}
Nice to have: {', '.join(job_spec.nice_to_have_skills)}{loc_instruction}

REAL PROFILES (do not invent — only use what's here):
{json.dumps(raw_profiles, indent=2)}

Select the top {count} most relevant and return as a JSON array:
[
  {{
    "name": "exact name from profile",
    "role_type": "{job_spec.role_type.value}",
    "source": "GitHub|HuggingFace|ArXiv|LinkedIn|PapersWithCode|SemanticScholar",
    "profile_url": "exact URL from profile",
    "headline": "factual headline from their actual bio/work",
    "location": "from profile or null",
    "email": "email if present in profile, else null",
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
        "linkedin":          CandidateSource.LINKEDIN,
        "github":            CandidateSource.GITHUB,
        "huggingface":       CandidateSource.HUGGINGFACE,
        "kaggle":            CandidateSource.KAGGLE,
        "twitter/x":         CandidateSource.TWITTER,
        "twitter":           CandidateSource.TWITTER,
        "dribbble":          CandidateSource.DRIBBBLE,
        "arxiv":             CandidateSource.ARXIV,
        "paperswithcode":    CandidateSource.GITHUB,   # closest existing enum
        "semanticscholar":   CandidateSource.ARXIV,    # academic source
        "community":         CandidateSource.COMMUNITY,
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
            email=d.get("email") or None,
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
    location = job_spec.location  # may be None

    # Run all six sources in parallel.
    # Each source targets a different population — they complement rather than overlap.
    # Ask for a large raw pool so the synthesis LLM has real selection depth.
    raw_target = max(num_candidates * 3, 24)
    with ThreadPoolExecutor(max_workers=6) as pool:
        gh_fut  = pool.submit(github_api.search_engineers,               keywords,                 raw_target,      location)
        hf_fut  = pool.submit(huggingface_api.search_practitioners,      job_spec.role_type.value, num_candidates)
        ax_fut  = pool.submit(arxiv_api.search_researchers,              keywords[:5],             max(5, num_candidates))
        li_fut  = pool.submit(linkedin_api.search_profiles,              keywords,                 num_candidates,  location)
        pwc_fut = pool.submit(papers_with_code_api.search_practitioners, job_spec.role_type.value, keywords,        num_candidates)
        s2_fut  = pool.submit(semantic_scholar_api.search_researchers,   job_spec.role_type.value, keywords[:5],    max(5, num_candidates))
        gh  = gh_fut.result()  or []
        hf  = hf_fut.result()  or []
        ax  = ax_fut.result()  or []
        li  = li_fut.result()  or []
        pwc = pwc_fut.result() or []
        s2  = s2_fut.result()  or []

    raw_profiles: list[dict] = gh + hf + ax + li + pwc + s2

    if not raw_profiles:
        return _source_via_llm(job_spec, num_candidates)

    # Annotate each profile with a location match signal, then sort: match → unknown → no_match.
    # The LLM sees local candidates first and receives hard include/exclude rules.
    location = job_spec.location
    raw_profiles = _annotate_location(raw_profiles, location)
    raw_profiles = _sort_by_location(raw_profiles)

    prompt = _synthesis_prompt(raw_profiles, job_spec, num_candidates)
    result = run_agent(
        system_prompt=SYSTEM_PROMPT,
        user_message=prompt,
        agent_name=f"Sourcing Agent ({job_spec.role_type.value})",
        use_web_search=False,
    )
    candidates = _parse_candidates(result, job_spec)

    if not candidates:
        candidates = _direct_map(raw_profiles[:num_candidates], job_spec)

    # Safety net: if location was specified, re-sort candidates so any with a matching
    # location field bubble to the top (in case the LLM still picked wrong order).
    if location and candidates:
        terms = _loc_terms(location)
        def _cand_rank(c: Candidate) -> int:
            loc = (c.location or "").lower()
            if not loc:
                return 1
            return 0 if any(t in loc for t in terms) else 2
        candidates.sort(key=_cand_rank)

    return candidates[:num_candidates]


def _source_via_llm(job_spec: JobSpec, num_candidates: int) -> list[Candidate]:
    """
    For PM and Designer roles — LinkedIn Brave search first, then LLM + Brave for the rest.
    """
    keywords = _keywords(job_spec)
    location = job_spec.location

    # LinkedIn structured discovery (no Proxycurl needed, just Brave)
    li_profiles = linkedin_api.search_profiles(keywords, num_candidates, location)

    if li_profiles:
        li_profiles = _annotate_location(li_profiles, location)
        li_profiles = _sort_by_location(li_profiles)

    # Fill remaining slots with LLM + Brave search
    remaining = num_candidates - len(li_profiles)
    llm_candidates: list[Candidate] = []
    if remaining > 0:
        prompt = _llm_sourcing_prompt(job_spec, remaining)
        result = run_agent(
            system_prompt=SYSTEM_PROMPT_LLM,
            user_message=prompt,
            agent_name=f"Sourcing Agent ({job_spec.role_type.value})",
        )
        llm_candidates = _parse_candidates(result, job_spec)

    # Convert LinkedIn profiles to Candidate objects
    li_candidates = _direct_map_linkedin(li_profiles, job_spec)

    # Merge: LinkedIn first (structured real data), then LLM candidates
    seen_names: set[str] = {c.name.lower() for c in li_candidates}
    merged = li_candidates[:]
    for c in llm_candidates:
        if c.name.lower() not in seen_names:
            merged.append(c)
            seen_names.add(c.name.lower())

    if location and merged:
        terms = _loc_terms(location)
        def _cand_rank(c: Candidate) -> int:
            loc = (c.location or "").lower()
            if not loc:
                return 1
            return 0 if any(t in loc for t in terms) else 2
        merged.sort(key=_cand_rank)

    return merged[:num_candidates]


def _direct_map_linkedin(profiles: list[dict], job_spec: JobSpec) -> list[Candidate]:
    """Map raw LinkedIn profile dicts (from linkedin_api) to Candidate objects."""
    candidates: list[Candidate] = []
    for p in profiles:
        candidates.append(Candidate(
            name=p.get("name", "Unknown"),
            role_type=job_spec.role_type,
            source=CandidateSource.LINKEDIN,
            profile_url=p.get("profile_url"),
            headline=p.get("headline"),
            location=p.get("location"),
            email=p.get("email") or None,
            skills=p.get("skills", []),
            experience_years=p.get("experience_years"),
            notable_work=p.get("notable_work"),
        ))
    return candidates


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
