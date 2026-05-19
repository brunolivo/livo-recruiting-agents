"""
Semantic Scholar sourcer — finds real AI researchers via academic graph.

Semantic Scholar (https://www.semanticscholar.org) provides a free,
no-auth public API with rich author profiles: citation counts, h-index,
affiliation, and links to personal/lab pages.

Why this source is distinct from ArXiv:
  • ArXiv has the papers; Semantic Scholar has the author *profiles*
  • H-index and citation count are strong quality signals
  • Affiliations surface location data ArXiv often lacks
  • Covers publications beyond ArXiv (NeurIPS, ICML, ACL, CVPR, etc.)

No API key required for basic use (100 req / 5 min).
Set SEMANTIC_SCHOLAR_API_KEY for higher rate limits.
"""

import os
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

S2_API  = "https://api.semanticscholar.org/graph/v1"
_KEY    = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")

_AUTHOR_FIELDS = ",".join([
    "name", "affiliations", "paperCount", "citationCount",
    "hIndex", "externalIds", "homepage", "url",
])

# Research areas per role type
_AREA_MAP: dict[str, list[str]] = {
    "AI Engineer": [
        "large language models",
        "retrieval augmented generation",
        "natural language processing",
        "machine learning systems",
        "MLOps",
    ],
    "Data Scientist": [
        "machine learning",
        "deep learning",
        "data science",
        "statistical learning",
        "predictive modeling",
    ],
}
_DEFAULT_AREAS = ["machine learning", "large language models", "deep learning"]


def search_researchers(
    role_type: str = "AI Engineer",
    keywords: list[str] | None = None,
    count: int = 10,
) -> list[dict]:
    """
    Find AI researchers via Semantic Scholar author search.

    Runs multiple searches in parallel (keywords + role-area terms)
    and deduplicates by author ID. Returns the top `count` profiles
    sorted by citation count.
    """
    areas    = _AREA_MAP.get(role_type, _DEFAULT_AREAS)
    kw_list  = keywords or []

    queries: list[str] = []
    # Job-spec keywords first
    if kw_list:
        queries.append(" ".join(kw_list[:3]))
        if len(kw_list) >= 4:
            queries.append(" ".join(kw_list[2:5]))
    # Role-area fallback seeds
    queries.extend(areas[:3])
    # Dedupe
    queries = list(dict.fromkeys(queries))[:5]

    seen_ids: set[str] = set()
    all_authors: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(len(queries), 5)) as pool:
        futures = {pool.submit(_search_authors, q, count): q for q in queries}
        for fut in as_completed(futures):
            for author in (fut.result() or []):
                aid = author.get("authorId", "") or author.get("name", "")
                if aid and aid not in seen_ids:
                    seen_ids.add(aid)
                    all_authors.append(author)

    # Sort by citation count — highest signal researchers first
    all_authors.sort(key=lambda a: a.get("citationCount", 0) or 0, reverse=True)

    return [_build_profile(a) for a in all_authors[:count] if a.get("name")]


def _search_authors(query: str, limit: int) -> list[dict]:
    headers = {"x-api-key": _KEY} if _KEY else {}
    try:
        r = httpx.get(
            f"{S2_API}/author/search",
            headers=headers,
            params={"query": query, "fields": _AUTHOR_FIELDS, "limit": min(limit * 2, 100)},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("data", [])
        return []
    except Exception:
        return []


def _build_profile(author: dict) -> dict:
    name         = author.get("name", "Unknown")
    affiliations = author.get("affiliations", []) or []
    location     = affiliations[0] if affiliations else ""
    homepage     = author.get("homepage") or ""
    paper_count  = author.get("paperCount", 0) or 0
    citations    = author.get("citationCount", 0) or 0
    h_index      = author.get("hIndex", 0) or 0

    # Build a useful profile URL
    author_id   = author.get("authorId", "")
    profile_url = author.get("url") or (
        f"https://www.semanticscholar.org/author/{author_id}" if author_id else homepage
    )

    # Skills inferred from h-index bucket
    skills: list[str] = []
    if h_index >= 20:
        skills.append("Deep Researcher")
    if citations > 5000:
        skills.append("Highly Cited")

    headline = f"AI Researcher — {paper_count} papers"
    if h_index:
        headline += f", h-index {h_index}"
    if affiliations:
        headline += f" · {affiliations[0]}"

    notable = f"{citations:,} citations" + (f", h-index {h_index}" if h_index else "")

    return {
        "name":         name,
        "username":     author_id or name.lower().replace(" ", "_"),
        "source":       "SemanticScholar",
        "profile_url":  profile_url,
        "headline":     headline,
        "location":     location,
        "skills":       skills,
        "notable_work": notable,
        "publications": f"{paper_count} papers",
        "h_index":      h_index,
        "citations":    citations,
        "homepage":     homepage,
    }
