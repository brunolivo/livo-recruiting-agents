"""
GitHub API sourcer — finds real engineers and data scientists.

Strategy: search repositories matching AI/ML keywords, collect unique repo owners,
then fetch their full profiles. Repo stars and topics give strong skill signals.

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


def search_engineers(keywords: list[str], count: int = 10) -> list[dict]:
    """
    Find real AI engineers/data scientists by searching their repos.
    Returns structured profiles ready for the sourcing agent to synthesize.
    """
    query = " ".join(keywords[:5]) + " language:Python stars:>20"
    data = _get(f"{GITHUB_API}/search/repositories", {
        "q": query, "sort": "stars", "order": "desc", "per_page": 50,
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

    notable = ""
    if featured_repo:
        notable = (
            f"{featured_repo['name']} ({featured_repo.get('stargazers_count', 0)} stars)"
            + (f" — {featured_repo['description']}" if featured_repo.get("description") else "")
        )
    elif top_repos:
        r = top_repos[0]
        notable = f"{r['name']} ({r['stars']} stars)" + (f" — {r['description']}" if r["description"] else "")

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
