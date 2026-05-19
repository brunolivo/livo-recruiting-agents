"""
GitHub API sourcer — finds real engineers and data scientists.

Location strategy:
  When a location is given, runs TWO searches in parallel:
    1. location-filtered search  (GitHub-verified location field)
    2. global search             (more results, then sorted by profile.location match)
  Results are merged location-first, so the LLM always sees local candidates at the top.

Rate limits: 60 req/hour unauthenticated, 5000/hour with GITHUB_TOKEN.
"""

import os
import httpx
from concurrent.futures import ThreadPoolExecutor

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


# ── Location helpers ──────────────────────────────────────────────────────────

def _loc_terms(location: str) -> list[str]:
    """Split "Barcelona, Spain" → ["barcelona", "spain"]"""
    return [t.strip().lower() for t in location.replace(",", " ").split() if len(t.strip()) > 2]


def _loc_rank(profile_location: str, terms: list[str]) -> int:
    """
    0 = location matches target
    1 = location unknown (not set — could be remote)
    2 = location set but doesn't match
    """
    loc = (profile_location or "").lower().strip()
    if not loc:
        return 1
    return 0 if any(t in loc for t in terms) else 2


# ── Public API ────────────────────────────────────────────────────────────────

def search_engineers(keywords: list[str], count: int = 10, location: str | None = None) -> list[dict]:
    """
    Find real AI engineers/data scientists.

    With location: runs a location-filtered search AND a global search in parallel,
    then merges results sorted by location match (matched → unknown → mismatched).
    This ensures the LLM synthesis always sees local candidates first.

    Without location: user bio search + repo-owner fallback.
    """
    if location:
        return _search_with_location(keywords, count, location)

    profiles = _search_by_users(keywords, count, city=None)
    if len(profiles) < 3:
        profiles += _search_by_repos(keywords, count - len(profiles))
    return profiles[:count]


def _search_with_location(keywords: list[str], count: int, location: str) -> list[dict]:
    """Run local + global searches in parallel and merge, location-matched first."""
    city = location.split(",")[0].strip()
    terms = _loc_terms(location)

    with ThreadPoolExecutor(max_workers=2) as pool:
        local_fut  = pool.submit(_search_by_users, keywords, count, city)
        global_fut = pool.submit(_search_by_users, keywords, count * 2, None)
        local_profiles  = local_fut.result()  or []
        global_profiles = global_fut.result() or []

    # Sort global by location match so matched ones bubble up
    global_sorted = sorted(
        global_profiles,
        key=lambda p: _loc_rank(p.get("location", ""), terms),
    )

    # Merge: local-first (deduped by username)
    seen: set[str] = {p["username"] for p in local_profiles}
    merged = local_profiles[:]
    for p in global_sorted:
        if p["username"] not in seen:
            merged.append(p)
            seen.add(p["username"])

    # If still thin, top up with repo-owner search (also sorted by location)
    if len(merged) < max(3, count // 2):
        repo_profiles = _search_by_repos(keywords, count)
        repo_sorted = sorted(
            repo_profiles,
            key=lambda p: _loc_rank(p.get("location", ""), terms),
        )
        for p in repo_sorted:
            if p["username"] not in seen:
                merged.append(p)
                seen.add(p["username"])

    return merged[:count]


# ── Internal search helpers ───────────────────────────────────────────────────

def _search_by_users(keywords: list[str], count: int, city: str | None = None) -> list[dict]:
    """Search GitHub users whose bio matches AI/ML keywords, optionally filtered by city."""
    core_kw = " ".join(keywords[:2])
    loc_filter = f" location:{city}" if city else ""
    query = f"{core_kw} in:bio{loc_filter} repos:>3 followers:>10"

    data = _get(f"{GITHUB_API}/search/users", {
        "q": query,
        "sort": "followers",
        "order": "desc",
        "per_page": min(count * 2, 30),
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
    ai_terms = [k for k in keywords if k.lower() in (
        "llm", "rag", "machine-learning", "deep-learning", "pytorch", "tensorflow",
        "transformers", "nlp", "computer-vision", "reinforcement-learning",
        "machine learning", "deep learning", "natural language processing",
    )]
    query_kw = ai_terms[0] if ai_terms else (keywords[0] if keywords else "machine-learning")
    query = f'"{query_kw}" language:Python stars:>5'

    data = _get(f"{GITHUB_API}/search/repositories", {
        "q": query, "sort": "stars", "order": "desc", "per_page": 40,
    })
    if not data or not data.get("items"):
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
