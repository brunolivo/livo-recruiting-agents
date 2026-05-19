"""
Papers with Code sourcer — finds real AI/ML engineers and researchers.

Papers with Code (https://paperswithcode.com) is a free, no-auth public API
that indexes ML papers *with linked GitHub implementations*.

Why this source is valuable:
  • Authors who ship code alongside their papers are exactly the
    practitioner-researcher hybrids you want for AI Engineer roles.
  • GitHub repo links let us surface real open-source contributors
    who don't appear in bio searches.
  • Covers NLP, CV, RL, tabular ML, audio — broader than ArXiv alone.

No API key required.
"""

import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

PWC_API = "https://paperswithcode.com/api/v1"

# Map role type → Papers with Code task/area filter
_TASK_MAP: dict[str, list[str]] = {
    "AI Engineer": [
        "language-modelling",
        "question-answering",
        "text-generation",
        "information-retrieval",
        "code-generation",
        "named-entity-recognition",
    ],
    "Data Scientist": [
        "tabular-data-classification",
        "time-series",
        "regression",
        "anomaly-detection",
        "recommendation-systems",
        "sentiment-analysis",
    ],
}
_DEFAULT_TASKS = ["language-modelling", "text-generation", "question-answering"]


def search_practitioners(
    role_type: str = "AI Engineer",
    keywords: list[str] | None = None,
    count: int = 10,
) -> list[dict]:
    """
    Find ML practitioners from Papers with Code.

    Strategy:
      1. Search papers matching `keywords` via the /papers/ endpoint
      2. Also pull top papers from role-relevant task areas
      3. Collect unique authors who have linked GitHub repos
    Returns structured profiles ready for synthesis.
    """
    tasks    = _TASK_MAP.get(role_type, _DEFAULT_TASKS)
    kw_list  = keywords or []

    paper_batches: list[list[dict]] = []

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures: list = []
        # Keyword-based search
        if kw_list:
            q = " ".join(kw_list[:3])
            futures.append(pool.submit(_search_papers_by_query, q, 50))
        # Task-area searches (top 2 tasks in parallel)
        for task in tasks[:2]:
            futures.append(pool.submit(_search_papers_by_task, task, 40))

        for fut in as_completed(futures):
            result = fut.result()
            if result:
                paper_batches.append(result)

    # Flatten and dedupe by paper ID
    all_papers: list[dict] = []
    seen_ids: set[str] = set()
    for batch in paper_batches:
        for paper in batch:
            pid = paper.get("id", "")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                all_papers.append(paper)

    return _build_author_profiles(all_papers, count)


def _search_papers_by_query(query: str, limit: int) -> list[dict]:
    try:
        r = httpx.get(
            f"{PWC_API}/papers/",
            params={"q": query, "ordering": "-github_star_count", "items_per_page": limit},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        return r.json().get("results", [])
    except Exception:
        return []


def _search_papers_by_task(task: str, limit: int) -> list[dict]:
    try:
        r = httpx.get(
            f"{PWC_API}/papers/",
            params={"task": task, "ordering": "-github_star_count", "items_per_page": limit},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        return r.json().get("results", [])
    except Exception:
        return []


def _build_author_profiles(papers: list[dict], count: int) -> list[dict]:
    """
    Aggregate papers by author and build profile dicts.
    Prioritises authors with GitHub repos linked to their papers.
    """
    author_data: dict[str, dict] = {}

    for paper in papers:
        authors = paper.get("authors", []) or []
        repo    = (paper.get("repository") or {})
        repo_url   = repo.get("url") or repo.get("github_url") or ""
        repo_stars = repo.get("stars", 0) or 0
        paper_title = paper.get("title", "")
        paper_url   = paper.get("url_pdf") or paper.get("paper_page") or ""
        published   = (paper.get("published") or "")[:10]

        for author in authors:
            name = (author.get("name") or "").strip()
            if not name:
                continue

            if name not in author_data:
                author_data[name] = {
                    "name":         name,
                    "papers":       [],
                    "repos":        [],
                    "total_stars":  0,
                }

            author_data[name]["papers"].append({
                "title":     paper_title,
                "url":       paper_url,
                "published": published,
            })
            if repo_url and repo_url not in author_data[name]["repos"]:
                author_data[name]["repos"].append(repo_url)
                author_data[name]["total_stars"] += repo_stars

    # Rank: authors with GitHub repos first, then by total stars
    sorted_authors = sorted(
        author_data.values(),
        key=lambda a: (len(a["repos"]) > 0, a["total_stars"], len(a["papers"])),
        reverse=True,
    )

    profiles: list[dict] = []
    for a in sorted_authors[:count]:
        papers     = a["papers"]
        latest     = sorted(papers, key=lambda p: p.get("published", ""), reverse=True)[0] if papers else {}
        top_repo   = a["repos"][0] if a["repos"] else ""
        skills     = _infer_skills_from_titles([p["title"] for p in papers])

        # Build a GitHub-style profile URL if the top repo is a GitHub link
        gh_user    = ""
        if "github.com" in top_repo:
            parts  = top_repo.rstrip("/").split("github.com/")[-1].split("/")
            gh_user = parts[0] if parts else ""

        profile_url = f"https://github.com/{gh_user}" if gh_user else \
                      f"https://paperswithcode.com/search?q_meta=&q_type=&q={a['name'].replace(' ', '+')}"

        profiles.append({
            "name":         a["name"],
            "username":     gh_user or a["name"].lower().replace(" ", "_"),
            "source":       "PapersWithCode",
            "profile_url":  profile_url,
            "headline":     f"ML Researcher/Engineer — {len(papers)} papers, {len(a['repos'])} GitHub repos",
            "location":     "",
            "notable_work": latest.get("title", ""),
            "skills":       skills,
            "publications": f"{len(papers)} papers with code on paperswithcode.com",
            "github_repos": a["repos"][:3],
            "total_stars":  a["total_stars"],
            "paper_count":  len(papers),
        })

    return profiles


def _infer_skills_from_titles(titles: list[str]) -> list[str]:
    tech_map = {
        "transformer": "Transformers", "bert": "BERT", "gpt": "GPT",
        "llm": "LLM", "language model": "LLM", "retrieval": "RAG",
        "rag": "RAG", "fine-tun": "Fine-tuning", "lora": "LoRA",
        "diffusion": "Diffusion Models", "vision": "Computer Vision",
        "multimodal": "Multimodal", "graph": "Graph Neural Networks",
        "reinforcement": "Reinforcement Learning", "nlp": "NLP",
        "question answer": "QA", "summariz": "Summarization",
        "classif": "Classification", "detect": "Object Detection",
        "speech": "Speech", "audio": "Audio",
        "time series": "Time Series", "tabular": "Tabular ML",
    }
    found: list[str] = []
    combined = " ".join(titles).lower()
    for kw, label in tech_map.items():
        if kw in combined and label not in found:
            found.append(label)
    return found[:10]
