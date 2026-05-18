"""
GitHub API sourcer — finds real engineers and data scientists.

Two-strategy approach:
1. User search — finds people whose bio/location mentions AI/ML keywords
2. Repo search — finds repo owners with starred AI/ML projects (fallback)

Rate limits: 60 req/hour unauthenticated, 5000/hour with GITHUB_TOKEN.
"""

import os
import httpx

GITHUB_API = "https://api.github.com"
_TOKEN = os.getenv("GITHUB_TOKEN", "")


def _headers() -> dict:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if _TOKEN:
        h["Authorization"] = f"Bearer {_TOKEN}"
    return h


def _get(url: str, params: dict | None = None) -> dict | list | None:
    try:
        r = httpx.get(url, headers=_headers(), params=params, timeout=12)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None


def search_engineers(keywords: list[str], count: int = 10, location: str | None = None) -> list[dict]:
    """
    Find real AI engineers/data scientists. Tries user search first (with location
    filter when provided), then falls back to global search, then repo-owner search.
    """
    profiles = _search_by_users(keywords, count, location=location)
    if len(profiles) < 3 and location:
        # Not enough local results — retry globally
        profiles = _search_by_users(keywords, count, location=None)
    if len(profiles) < 3:
        profiles += _search_by_repos(keywords, count - len(profiles))
    return profiles[:count]


def _search_by_users(keywords: list[str], count: int, location: str | None = None) -> list[dict]:
    """Search GitHub users whose bio/name matches AI/ML keywords."""
    core_kw = " ".join(keywords[:2])
    # Use the city part only (e.g. "Barcelona" from "Barcelona, Spain")
    city = location.split(",")[0].strip() if location else None
    loc_filter = f" location:{city}" if city else ""
    query = f"{core_kw} in:bio{loc_filter} repos:>3 followers:>10"

    data = _get(f"{GITHUB_API}/search/users", {
        "q": query, "sort": "followers", "order": "desc", "per_page": min(count * 2, 30),
    })
    if not data or not data.get("items"):
        return []

    seen: set[str] = set()
    profiles: list[dict] = []

    for user in data["items"][:count * 2]:
        login = user.get("login", "")
        if not login or login in seen:
            continue
        seen.add(login)
        profile = _build_profile(login)
        if profile:
            profiles.append(profile)
        if len(profiles) >= count:
            break

    return profiles


def _search_by_repos(keywords: list[str], count: int) -> list[dict]:
    """Find real engineers by searching AI/ML repos and collecting unique owners."""
    # Build a simpler query — avoid overly specific multi-word combos
    ai_terms = [k for k in keywords if k.lower() in (
        "llm", "rag", "machine-learning", "deep-learning", "pytorch", "tensorflow",
        "transformers", "nlp", "computer-vision", "reinforcement-learning",
        "machine learning", "deep learning", "natural language processing",
    )]
    query_kw = ai_terms[0] if ai_terms else keywords[0] if keywords else "machine-learning"
    query = f'"{query_kw}" language:Python stars:>5'

    data = _get(f"{GITHUB_API}/search/repositories", {
        "q": query, "sort": "stars", "order": "desc", "per_page": 40,
    })
    if not data or not data.get("items"):
        # Last resort: search popular AI repos
        data = _get(f"{GITHUB_API}/search/repositories", {
            "q": "machine-learning language:Python stars:>100",
            "sort": "stars", "order": "desc", "per_page": 40,
        })
    if not data:
        return []

    seen: set[str] = set()
    profiles: list[dict] = []

    for repo in data.get("items", []):
        owner = repo.get("owner", {})
        login = owner.get("login", "")
        if not login or login in seen or owner.get("type") != "User":
            continue
        seen.add(login)
        profile = _build_profile(login, featured_repo=repo)
        if profile:
            profiles.append(profile)
        if len(profiles) >= count:
            break

    return profiles


def _build_profile(login: str, featured_repo: dict | None = None) -> dict | None:
    user = _get(f"{GITHUB_API}/users/{login}")
    if not user:
        return None

    repos_data = _get(f"{GITHUB_API}/users/{login}/repos", {
        "sort": "stars", "per_page": 6,
    }) or []

    top_repos = [
        {
            "name": r["name"],
            "description": r.get("description") or "",
            "stars": r.get("stargazers_count", 0),
            "language": r.get("language") or "",
            "topics": r.get("topics", []),
        }
        for r in repos_data[:6]
    ]

    languages = list({r["language"] for r in top_repos if r["language"]})
    all_topics: list[str] = []
    for r in top_repos:
        all_topics.extend(r.get("topics", []))
    skills = list(dict.fromkeys(languages + all_topics))[:12]

    if featured_repo:
        notable = (
            f"{featured_repo['name']} ({featured_repo.get('stargazers_count', 0)} stars)"
            + (f" — {featured_repo['description']}" if featured_repo.get("description") else "")
        )
    elif top_repos:
        r = top_repos[0]
        notable = f"{r['name']} ({r['stars']} stars)" + (f" — {r['description']}" if r["description"] else "")
    else:
        notable = f"{user.get('public_repos', 0)} public repos"

    return {
        "name": user.get("name") or login,
        "username": login,
        "source": "GitHub",
        "profile_url": user["html_url"],
        "headline": user.get("bio") or f"Software Engineer · {', '.join(languages[:3])}",
        "location": user.get("location") or "",
        "company": (user.get("company") or "").strip("@"),
        "followers": user.get("followers", 0),
        "public_repos": user.get("public_repos", 0),
        "blog": user.get("blog") or "",
        "email": user.get("email") or "",
        "skills": skills,
        "notable_work": notable,
        "top_repos": top_repos,
    }
