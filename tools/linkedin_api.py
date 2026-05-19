"""
LinkedIn sourcer — discovers real professionals via three-layer approach.

Layer 1 — Discovery via Brave Search API (BRAVE_API_KEY set):
  Runs structured site:linkedin.com/in queries and parses snippets.
  Runs 4 parallel searches with different keyword combos + location variants.

Layer 1b — Discovery via Tavily Search API (TAVILY_API_KEY set, no credit card):
  Same structured queries via Tavily's AI-native search.
  Free tier: 1,000 searches/month at https://tavily.com — email only, no card.

Layer 2 — Enrichment (optional, requires PROXYCURL_API_KEY):
  Proxycurl fetches the full LinkedIn profile for each URL discovered in layer 1.
  Adds skills, experience, education, connections count.
  Cost: ~$0.01–0.03 per profile. Only called if the env key is set.

Layer 3 — LLM web search fallback (no search API key set):
  Uses the run_agent loop (OpenRouter built-in Brave tool) to find profiles.
  Slower but always works with zero additional keys.

Priority: Brave → Tavily → LLM fallback.
Set PROXYCURL_API_KEY in .env to enable enrichment on top of any discovery layer.
"""

import os
import re
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

BRAVE_KEY      = os.getenv("BRAVE_API_KEY", "")
TAVILY_KEY     = os.getenv("TAVILY_API_KEY", "")
PROXYCURL_KEY  = os.getenv("PROXYCURL_API_KEY", "")
BRAVE_API      = "https://api.search.brave.com/res/v1/web/search"
TAVILY_API     = "https://api.tavily.com/search"
PROXYCURL_API  = "https://nubela.co/proxycurl/api"


# ── Public entry point ────────────────────────────────────────────────────────

def search_profiles(
    keywords: list[str],
    count: int = 10,
    location: str | None = None,
) -> list[dict]:
    """
    Find real LinkedIn professionals matching the given keywords and location.

    Priority order:
      1. Brave Search API  (BRAVE_API_KEY)    — fastest, most results
      2. Tavily Search API (TAVILY_API_KEY)   — free tier, no credit card
      3. LLM web search fallback              — always works, no extra keys

    Optional: PROXYCURL_API_KEY enriches profiles from any discovery layer.
    """
    # Layer 1: Brave (direct API)
    if BRAVE_KEY:
        urls_meta = _discover_urls(keywords, count * 3, location, engine="brave")
        if urls_meta:
            if PROXYCURL_KEY:
                return _enrich_with_proxycurl(urls_meta, count)
            return [m for m in urls_meta if m.get("name")][:count]

    # Layer 1b: Tavily (direct API, free tier)
    if TAVILY_KEY:
        urls_meta = _discover_urls(keywords, count * 3, location, engine="tavily")
        if urls_meta:
            if PROXYCURL_KEY:
                return _enrich_with_proxycurl(urls_meta, count)
            return [m for m in urls_meta if m.get("name")][:count]

    # Layer 3: LLM web search fallback (always works)
    return _llm_linkedin_search(keywords, count, location)


def _llm_linkedin_search(keywords: list[str], count: int, location: str | None) -> list[dict]:
    """
    Use the existing run_agent + Brave web search to find LinkedIn profiles.
    This works even without a direct BRAVE_API_KEY because OpenRouter
    handles the Brave search as a tool call.
    """
    # Import here to avoid circular imports at module load
    from agents.base_agent import run_agent

    loc_clause = f' based in {location}' if location else ''
    kw_str     = ", ".join(keywords[:5])

    prompt = f"""Search LinkedIn for {count} real professionals matching: {kw_str}{loc_clause}.

Use web_search with queries like:
  site:linkedin.com/in {' '.join(keywords[:2])}{(' ' + location) if location else ''}
  site:linkedin.com/in {' '.join(keywords[2:4] or keywords[:2])}

For each person found return a JSON array:
[{{
  "name": "Full Name",
  "source": "LinkedIn",
  "profile_url": "https://linkedin.com/in/username",
  "headline": "their job title and company from the search snippet",
  "location": "city, country if visible",
  "skills": ["skill1", "skill2"]
}}]

Return ONLY the JSON array. Only include real profiles with actual linkedin.com/in/ URLs."""

    try:
        result = run_agent(
            system_prompt="You are a talent sourcer. Use web_search to find real LinkedIn profiles.",
            user_message=prompt,
            agent_name="LinkedIn Search (LLM)",
            use_web_search=True,
        )
        return _parse_llm_linkedin_result(result)
    except Exception:
        return []


def _parse_llm_linkedin_result(raw: str) -> list[dict]:
    """Parse the LLM's JSON response for LinkedIn profiles."""
    import json, re
    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start, end = clean.find("["), clean.rfind("]") + 1
        if start >= 0 and end > start:
            clean = clean[start:end]
        items = json.loads(clean)
    except Exception:
        return []

    profiles: list[dict] = []
    for item in items:
        url = item.get("profile_url", "")
        if not url or "linkedin.com/in/" not in url.lower():
            continue
        profiles.append({
            "name":        item.get("name", ""),
            "username":    url.rstrip("/").split("/in/")[-1].split("/")[0],
            "source":      "LinkedIn",
            "profile_url": url,
            "headline":    item.get("headline", ""),
            "location":    item.get("location", ""),
            "skills":      item.get("skills", []),
            "email":       None,
        })
    return profiles


# ── Layer 1: URL discovery via Brave ─────────────────────────────────────────

def _discover_urls(
    keywords: list[str],
    target: int,
    location: str | None,
    engine: str = "brave",
) -> list[dict]:
    """
    Run multiple searches in parallel and collect unique LinkedIn profile URLs.
    engine: "brave" | "tavily"
    Returns raw snippet dicts: {name, profile_url, headline, location, source}.
    """
    queries = _build_queries(keywords, location)

    seen_urls: set[str] = set()
    results: list[dict] = []

    def _run_query(q: str) -> list[dict]:
        if engine == "tavily":
            return _tavily_linkedin_search(q, count=10)
        return _brave_linkedin_search(q, count=10)

    with ThreadPoolExecutor(max_workers=min(len(queries), 5)) as pool:
        futures = [pool.submit(_run_query, q) for q in queries]
        for fut in as_completed(futures):
            for item in (fut.result() or []):
                url = item.get("profile_url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    results.append(item)
            if len(results) >= target:
                break

    return results[:target]


def _build_queries(keywords: list[str], location: str | None) -> list[str]:
    """
    Build 4–5 diverse Brave search queries targeting LinkedIn profiles.
    """
    kw1 = " ".join(keywords[:2])
    kw2 = " ".join(keywords[2:4]) if len(keywords) >= 4 else keywords[0]
    kw3 = " ".join(keywords[:3])
    loc  = f' "{location}"' if location else ""
    city = f' "{location.split(",")[0].strip()}"' if location and "," in location else loc

    queries = [
        f'site:linkedin.com/in {kw1}{loc}',
        f'site:linkedin.com/in {kw2}{city}',
        f'site:linkedin.com/in {kw3}',
        f'linkedin.com/in {kw1} AI{loc}',
    ]
    if location:
        queries.append(f'site:linkedin.com/in {keywords[0]}{loc} -recruiter -hr')

    # Dedupe while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    return unique


def _brave_linkedin_search(query: str, count: int = 10) -> list[dict]:
    """
    Call Brave Search API and parse LinkedIn profile snippets.
    """
    try:
        r = httpx.get(
            BRAVE_API,
            headers={"X-Subscription-Token": BRAVE_KEY, "Accept": "application/json"},
            params={"q": query, "count": count, "search_lang": "en"},
            timeout=12,
        )
        if r.status_code != 200:
            return []
        items = r.json().get("web", {}).get("results", [])
    except Exception:
        return []

    profiles: list[dict] = []
    for item in items:
        url   = item.get("url", "")
        title = item.get("title", "")
        desc  = item.get("description", "") or item.get("extra_snippets", [""])[0] if item.get("extra_snippets") else item.get("description", "")

        # Only keep linkedin.com/in/* profile pages (not /company, /jobs, /posts)
        if not _is_profile_url(url):
            continue

        parsed = _parse_snippet(url, title, str(desc))
        if parsed:
            profiles.append(parsed)

    return profiles


def _tavily_linkedin_search(query: str, count: int = 10) -> list[dict]:
    """
    Call Tavily Search API and parse LinkedIn profile results.
    Free tier: 1,000 searches/month — sign up at https://tavily.com (email only, no card).
    """
    try:
        r = httpx.post(
            TAVILY_API,
            json={
                "api_key":        TAVILY_KEY,
                "query":          query,
                "max_results":    count,
                "search_depth":   "basic",
                "include_domains": ["linkedin.com"],
            },
            timeout=15,
        )
        if r.status_code != 200:
            return []
        items = r.json().get("results", [])
    except Exception:
        return []

    profiles: list[dict] = []
    for item in items:
        url   = item.get("url", "")
        title = item.get("title", "")
        desc  = item.get("content", "")

        if not _is_profile_url(url):
            continue

        parsed = _parse_snippet(url, title, str(desc))
        if parsed:
            profiles.append(parsed)

    return profiles


def _is_profile_url(url: str) -> bool:
    """Return True only for individual profile pages."""
    u = url.lower()
    if "linkedin.com/in/" not in u:
        return False
    # Exclude company, jobs, posts, pulse pages
    for exclude in ("/company/", "/jobs/", "/posts/", "/pulse/", "/school/", "/groups/"):
        if exclude in u:
            return False
    return True


def _parse_snippet(url: str, title: str, description: str) -> dict | None:
    """
    Extract structured profile data from a Brave snippet.

    LinkedIn title formats:
      "First Last - Job Title at Company | LinkedIn"
      "First Last - Title · Company | LinkedIn"
      "First Last | LinkedIn"
    """
    # Clean title
    clean_title = re.sub(r"\s*\|\s*LinkedIn.*$", "", title, flags=re.IGNORECASE).strip()
    clean_title = re.sub(r"\s*-\s*LinkedIn.*$", "", clean_title, flags=re.IGNORECASE).strip()

    if not clean_title or clean_title.lower() in ("linkedin", ""):
        return None

    # Split name from headline
    parts   = re.split(r"\s*[-·]\s*", clean_title, maxsplit=1)
    name    = parts[0].strip()
    headline = parts[1].strip() if len(parts) > 1 else ""

    # Reject obviously non-person entries
    if not name or len(name.split()) > 5 or any(w in name.lower() for w in ("linkedin", "job", "career", "recruiter")):
        return None

    # Extract location from description
    # Patterns: "Barcelona, Spain · Senior Engineer"  |  "London, UK"
    location = _extract_location(description)

    # Extract skills/technologies mentioned in snippet
    skills = _extract_skills_from_text(description + " " + headline)

    # Username from URL slug
    slug = url.rstrip("/").split("/in/")[-1].split("/")[0].split("?")[0]

    return {
        "name":        name,
        "username":    slug,
        "source":      "LinkedIn",
        "profile_url": _clean_url(url),
        "headline":    headline or description[:120],
        "location":    location,
        "skills":      skills,
        "email":       None,
        "_snippet":    description[:300],   # kept for synthesis context
    }


def _extract_location(text: str) -> str:
    """Pull a location string out of a LinkedIn snippet."""
    # Pattern 1: "City, Country ·"  or  "City, State ·"
    m = re.search(r"([A-Z][a-zA-Z\s]+,\s*[A-Z][a-zA-Z\s]+)\s*[·|]", text)
    if m:
        candidate = m.group(1).strip()
        if len(candidate) < 60:
            return candidate

    # Pattern 2: plain "City, Country" anywhere
    m = re.search(r"\b([A-Z][a-z]{2,},\s*[A-Z][a-z]{2,})\b", text)
    if m:
        return m.group(1).strip()

    return ""


def _extract_skills_from_text(text: str) -> list[str]:
    """Pull technology keywords from a snippet — quick heuristic."""
    tech_keywords = [
        "Python", "PyTorch", "TensorFlow", "LLM", "RAG", "NLP", "ML", "AI",
        "HuggingFace", "Transformers", "MLOps", "Kubernetes", "Docker",
        "SQL", "Spark", "AWS", "GCP", "Azure", "React", "TypeScript",
        "fine-tuning", "LangChain", "OpenAI", "Scikit-learn", "Pandas",
        "Deep Learning", "Computer Vision", "Reinforcement Learning",
        "Data Science", "Machine Learning", "Generative AI",
    ]
    found: list[str] = []
    text_lower = text.lower()
    for kw in tech_keywords:
        if kw.lower() in text_lower and kw not in found:
            found.append(kw)
    return found[:10]


def _clean_url(url: str) -> str:
    """Strip tracking params and normalise the LinkedIn URL."""
    base = url.split("?")[0].rstrip("/")
    # Ensure https
    if base.startswith("http://"):
        base = "https://" + base[7:]
    return base


# ── Layer 2: Proxycurl enrichment (optional) ─────────────────────────────────

def _enrich_with_proxycurl(snippets: list[dict], count: int) -> list[dict]:
    """
    Enrich up to `count` profiles via Proxycurl.
    Falls back to the snippet data if a lookup fails.
    """
    to_enrich = snippets[:count]

    enriched: list[dict] = []

    def _lookup(snippet: dict) -> dict:
        url = snippet.get("profile_url", "")
        if not url:
            return snippet
        full = _proxycurl_lookup(url)
        if full:
            return full
        return snippet

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_lookup, s): s for s in to_enrich}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                enriched.append(result)

    return enriched[:count]


def _proxycurl_lookup(linkedin_url: str) -> dict | None:
    """Fetch a full LinkedIn profile via Proxycurl."""
    try:
        r = httpx.get(
            f"{PROXYCURL_API}/v2/linkedin",
            headers={"Authorization": f"Bearer {PROXYCURL_KEY}"},
            params={
                "url":                      linkedin_url,
                "skills":                   "include",
                "use_cache":                "if-present",
                "fallback_to_cache":        "on-error",
            },
            timeout=15,
        )
        if r.status_code != 200:
            return None
        p = r.json()
    except Exception:
        return None

    if not p or p.get("code") == 404:
        return None

    # Map Proxycurl response to our standard profile dict
    full_name  = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
    headline   = p.get("headline") or p.get("occupation") or ""
    location   = p.get("city") or ""
    if p.get("country_full_name"):
        location = f"{location}, {p['country_full_name']}" if location else p["country_full_name"]

    # Skills
    skills = [s.get("name", "") for s in (p.get("skills") or []) if s.get("name")][:14]

    # Experience summary
    experience   = p.get("experiences") or []
    notable_work = ""
    if experience:
        latest = experience[0]
        co  = latest.get("company", "")
        ttl = latest.get("title", "")
        notable_work = f"{ttl} at {co}".strip(" at") if (ttl or co) else ""

    # Education
    edu_list   = p.get("education") or []
    education  = ", ".join(
        e.get("school", "") for e in edu_list[:2] if e.get("school")
    )

    connections = p.get("connections", 0) or 0

    return {
        "name":            full_name or p.get("public_identifier", ""),
        "username":        p.get("public_identifier", ""),
        "source":          "LinkedIn",
        "profile_url":     linkedin_url,
        "headline":        headline,
        "location":        location,
        "email":           p.get("personal_emails", [None])[0] if p.get("personal_emails") else None,
        "skills":          skills,
        "notable_work":    notable_work,
        "experience_years": _estimate_years(experience),
        "education":       education,
        "connections":     connections,
        "summary":         (p.get("summary") or "")[:300],
        "enriched":        True,
    }


def _estimate_years(experiences: list[dict]) -> int | None:
    """Rough estimate of total years of experience from Proxycurl experience list."""
    from datetime import date
    if not experiences:
        return None
    try:
        # Find earliest start date
        starts: list[int] = []
        for exp in experiences:
            sd = exp.get("starts_at") or {}
            yr = sd.get("year")
            if yr:
                starts.append(yr)
        if not starts:
            return None
        return date.today().year - min(starts)
    except Exception:
        return None
