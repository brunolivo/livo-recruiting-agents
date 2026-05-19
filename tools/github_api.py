"""
GitHub API sourcer — finds real engineers and data scientists.

Expansion strategy (v2):
  • Runs THREE parallel query types per search:
      1. Bio/user search  — keywords in user bio (location-filtered + global)
      2. Repo-owner search — owners of starred AI/ML repos
      3. Topic search     — repos tagged with curated ML topics
  • Country-level fallback when city search is thin
  • per_page bumped to 50 (safe GitHub limit)
  • Multiple keyword combos tried in parallel

Rate limits: 60 req/hour unauthenticated, 5 000/hour with GITHUB_TOKEN.
"""

import os
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

GITHUB_API = "https://api.github.com"
_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Curated ML/AI GitHub topics for topic-based repo search
_ML_TOPICS = [
    "machine-learning", "deep-learning", "natural-language-processing",
    "large-language-model", "llm", "rag", "mlops", "pytorch",
    "transformers", "computer-vision", "reinforcement-learning",
    "data-science", "neural-network", "huggingface",
]


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
    return [t.strip().lower() for t in location.replace(",", " ").split() if len(t.strip()) > 2]


def _loc_rank(profile_location: str, terms: list[str]) -> int:
    loc = (profile_location or "").lower().strip()
    if not loc:
        return 1
    return 0 if any(t in loc for t in terms) else 2


# ── Public API ────────────────────────────────────────────────────────────────

def search_engineers(keywords: list[str], count: int = 10, location: str | None = None) -> list[dict]:
    """
    Find real AI engineers / data scientists.

    Runs bio-search, repo-owner search, and topic-search in parallel.
    With location: also runs location-filtered variants and merges local-first.
    Returns up to `count` deduplicated profiles.
    """
    if location:
        return _search_with_location(keywords, count, location)
    return _search_global(keywords, count)


# ── Location-aware search ─────────────────────────────────────────────────────

def _search_with_location(keywords: list[str], count: int, location: str) -> list[dict]:
    """
    Parallel: local bio-search (city) + country bio-search + global multi-query.
    Merges results location-first, deduped by username.
    """
    city    = location.split(",")[0].strip()
    country = location.split(",")[-1].strip() if "," in location else ""
    terms   = _loc_terms(location)

    futures_map = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures_map["local_bio"]   = pool.submit(_search_by_users, keywords, count,       city)
        futures_map["country_bio"] = pool.submit(_search_by_users, keywords, count,       country) if country and country != city else None
        futures_map["global_bio"]  = pool.submit(_search_by_users, keywords, count * 3,   None)
        futures_map["repos"]       = pool.submit(_search_by_repos, keywords, count * 2)
        futures_map["topics"]      = pool.submit(_search_by_topics, keywords, count * 2)

        results: dict[str, list[dict]] = {}
        for key, fut in futures_map.items():
            if fut is None:
                results[key] = []
            else:
                results[key] = fut.result() or []

    local_profiles = results["local_bio"] + results["country_bio"]

    # Sort global pool by location match
    global_pool = results["global_bio"] + results["repos"] + results["topics"]
    global_sorted = sorted(global_pool, key=lambda p: _loc_rank(p.get("location", ""), terms))

    # Merge: local first, then global (deduped)
    seen: set[str] = {p["username"] for p in local_profiles}
    merged = local_profiles[:]
    for p in global_sorted:
        if p["username"] not in seen:
            merged.append(p)
            seen.add(p["username"])

    return merged[:count]


def _search_global(keywords: list[str], count: int) -> list[dict]:
    """
    Parallel multi-strategy global search (no location filter).
    """
    with ThreadPoolExecutor(max_workers=4) as pool:
        bio_fut    = pool.submit(_search_by_users,  keywords, count * 2, None)
        repos_fut  = pool.submit(_search_by_repos,  keywords, count * 2)
        topics_fut = pool.submit(_search_by_topics, keywords, count * 2)

        bio    = bio_fut.result()    or []
        repos  = repos_fut.result()  or []
        topics = topics_fut.result() or []

    seen: set[str] = set()
    merged: list[dict] = []
    for p in bio + repos + topics:
        if p["username"] not in seen:
            merged.append(p)
            seen.add(p["username"])

    return merged[:count]


# ── Search strategies ─────────────────────────────────────────────────────────

def _search_by_users(keywords: list[str], count: int, city: str | None = None) -> list[dict]:
    """
    Run multiple keyword-combo bio searches in parallel and merge results.
    """
    # Build 3 different query strings from different keyword slices
    combos: list[str] = []
    if len(keywords) >= 2:
        combos.append(" ".join(keywords[:2]))
    if len(keywords) >= 4:
        combos.append(" ".join(keywords[2:4]))
    if len(keywords) >= 1:
        combos.append(keywords[0])
    combos = list(dict.fromkeys(combos))  # dedupe while preserving order

    all_profiles: list[dict] = []
    seen: set[str] = set()

    def _run_combo(kw: str) -> list[dict]:
        loc_filter = f" location:{city}" if city else ""
        query = f"{kw} in:bio{loc_filter} repos:>2 followers:>5"
        data = _get(f"{GITHUB_API}/search/users", {
            "q": query, "sort": "followers", "order": "desc",
            "per_page": min(count * 2, 50),
        })
        if not data or not data.get("items"):
            return []
        results: list[dict] = []
        for user in data["items"]:
            login = user.get("login", "")
            if not login:
                continue
            profile = _build_profile(login)
            if profile:
                results.append(profile)
            if len(results) >= count:
                break
        return results

    with ThreadPoolExecutor(max_workers=len(combos)) as pool:
        futures = [pool.submit(_run_combo, kw) for kw in combos]
        for fut in as_completed(futures):
            for p in (fut.result() or []):
                if p["username"] not in seen:
                    all_profiles.append(p)
                    seen.add(p["username"])

    return all_profiles[:count]


def _search_by_repos(keywords: list[str], count: int) -> list[dict]:
    """
    Find engineers by searching popular AI/ML repos and collecting unique owners.
    Tries multiple keyword terms in parallel.
    """
    ai_terms = [k for k in keywords if k.lower() in {
        "llm", "rag", "machine-learning", "deep-learning", "pytorch", "tensorflow",
        "transformers", "nlp", "computer-vision", "reinforcement-learning",
        "machine learning", "deep learning", "natural language processing",
        "mlops", "huggingface", "langchain", "fine-tuning",
    }]
    # Use up to 3 terms for parallel repo searches
    search_terms = (ai_terms[:3] if ai_terms else keywords[:3]) or ["machine-learning"]

    seen: set[str] = set()
    profiles: list[dict] = []

    def _repos_for_term(term: str) -> list[dict]:
        data = _get(f"{GITHUB_API}/search/repositories", {
            "q": f'"{term}" language:Python stars:>10',
            "sort": "stars", "order": "desc", "per_page": 40,
        })
        if not data or not data.get("items"):
            return []
        res: list[dict] = []
        for repo in data["items"]:
            owner = repo.get("owner", {})
            login = owner.get("login", "")
            if not login or owner.get("type") != "User":
                continue
            profile = _build_profile(login, featured_repo=repo)
            if profile:
                res.append(profile)
            if len(res) >= count // 2:
                break
        return res

    with ThreadPoolExecutor(max_workers=len(search_terms)) as pool:
        futures = [pool.submit(_repos_for_term, t) for t in search_terms]
        for fut in as_completed(futures):
            for p in (fut.result() or []):
                if p["username"] not in seen:
                    profiles.append(p)
                    seen.add(p["username"])
                if len(profiles) >= count:
                    break

    return profiles[:count]


def _search_by_topics(keywords: list[str], count: int) -> list[dict]:
    """
    Find engineers via GitHub topic search — curated ML topics produce
    high-signal repo owners that bio search misses.
    """
    # Pick topics most relevant to the keywords
    kw_lower = {k.lower() for k in keywords}
    relevant = [t for t in _ML_TOPICS if any(w in t for w in kw_lower)]
    if not relevant:
        relevant = _ML_TOPICS[:4]
    topics_to_try = relevant[:4]

    seen: set[str] = set()
    profiles: list[dict] = []

    def _owners_for_topic(topic: str) -> list[dict]:
        data = _get(f"{GITHUB_API}/search/repositories", {
            "q": f"topic:{topic} stars:>20 language:Python",
            "sort": "stars", "order": "desc", "per_page": 30,
        })
        if not data or not data.get("items"):
            return []
        res: list[dict] = []
        for repo in data["items"]:
            owner = repo.get("owner", {})
            login = owner.get("login", "")
            if not login or owner.get("type") != "User":
                continue
            profile = _build_profile(login, featured_repo=repo)
            if profile:
                res.append(profile)
            if len(res) >= count // 2:
                break
        return res

    with ThreadPoolExecutor(max_workers=len(topics_to_try)) as pool:
        futures = [pool.submit(_owners_for_topic, t) for t in topics_to_try]
        for fut in as_completed(futures):
            for p in (fut.result() or []):
                if p["username"] not in seen:
                    profiles.append(p)
                    seen.add(p["username"])
                if len(profiles) >= count:
                    break

    return profiles[:count]


# ── Profile builder ───────────────────────────────────────────────────────────

def _build_profile(login: str, featured_repo: dict | None = None) -> dict | None:
    user = _get(f"{GITHUB_API}/users/{login}")
    if not user:
        return None

    repos_data = _get(f"{GITHUB_API}/users/{login}/repos", {
        "sort": "stars", "per_page": 8,
    }) or []

    top_repos = [
        {
            "name": r["name"],
            "description": r.get("description") or "",
            "stars": r.get("stargazers_count", 0),
            "language": r.get("language") or "",
            "topics": r.get("topics", []),
        }
        for r in repos_data[:8]
    ]

    languages = list({r["language"] for r in top_repos if r["language"]})
    all_topics: list[str] = []
    for r in top_repos:
        all_topics.extend(r.get("topics", []))
    skills = list(dict.fromkeys(languages + all_topics))[:14]

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
