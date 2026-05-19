"""
ArXiv API sourcer — finds real AI researchers by their published papers.

v2 improvements:
  • Expanded categories: cs.LG, cs.AI, cs.CL, cs.CV, cs.IR, cs.NE, stat.ML
  • Two parallel searches per call: strict (AND) + broad (OR) for better recall
  • Higher max_results (count × 8, was count × 3)
  • Semantic Scholar profile URLs added for discoverability
  • Affiliation used as location signal
"""

import httpx
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

ARXIV_API = "https://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

# All relevant ML/AI ArXiv categories
_CATEGORIES = "cat:cs.LG OR cat:cs.AI OR cat:cs.CL OR cat:cs.CV OR cat:cs.IR OR cat:cs.NE OR cat:stat.ML"


def search_researchers(keywords: list[str], count: int = 8) -> list[dict]:
    """
    Find real AI researchers from recent ArXiv papers.

    Runs two searches in parallel:
    1. Strict — all keywords must appear (AND)
    2. Broad  — any keyword matches (OR), catches practitioners with niche focus

    Returns up to `count` profiles sorted by paper count / first-author count.
    """
    kws = [k for k in keywords if k][:5]
    if not kws:
        kws = ["machine learning"]

    strict_query = f"({_CATEGORIES}) AND ({' AND '.join(f'ti:{k}' for k in kws[:3])})"
    broad_query  = f"({_CATEGORIES}) AND ({' OR '.join(f'ti:{k}' for k in kws)})"
    # Also a plain abstract search for broader recall
    abs_query    = f"({_CATEGORIES}) AND ({' OR '.join(f'abs:{k}' for k in kws[:3])})"

    author_papers: dict[str, list[dict]] = {}

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(_fetch_papers, strict_query, count * 6): "strict",
            pool.submit(_fetch_papers, broad_query,  count * 6): "broad",
            pool.submit(_fetch_papers, abs_query,    count * 4): "abs",
        }
        for fut in as_completed(futures):
            for name, papers in (fut.result() or {}).items():
                if name not in author_papers:
                    author_papers[name] = []
                # Merge papers, dedupe by URL
                existing_urls = {p["url"] for p in author_papers[name]}
                for p in papers:
                    if p["url"] not in existing_urls:
                        author_papers[name].append(p)
                        existing_urls.add(p["url"])

    # Rank: first-author paper count → total paper count → recency
    sorted_authors = sorted(
        author_papers.items(),
        key=lambda x: (
            sum(1 for p in x[1] if p["position"] == 0),
            len(x[1]),
        ),
        reverse=True,
    )

    profiles: list[dict] = []
    seen: set[str] = set()
    for name, papers in sorted_authors:
        if name in seen or len(profiles) >= count:
            break
        seen.add(name)

        first_author_papers = [p for p in papers if p["position"] == 0]
        all_sorted          = sorted(papers, key=lambda p: p.get("published", ""), reverse=True)
        latest              = all_sorted[0]
        affiliations        = list({p["affiliation"] for p in papers if p["affiliation"]})

        # Use affiliation as a location proxy
        location_hint = affiliations[0] if affiliations else ""

        profiles.append({
            "name":               name,
            "source":             "ArXiv",
            "profile_url":        f"https://arxiv.org/search/?query={name.replace(' ', '+')}&searchtype=author",
            "headline":           f"AI Researcher — {len(papers)} papers ({len(first_author_papers)} first-authored)",
            "location":           location_hint,
            "notable_work":       latest["title"],
            "skills":             _infer_skills_from_papers(papers),
            "publications":       f"{len(papers)} papers on ArXiv",
            "recent_paper_url":   latest["url"],
            "recent_paper_summary": latest.get("summary", ""),
            "affiliations":       affiliations[:3],
            "paper_count":        len(papers),
            "first_author_count": len(first_author_papers),
        })

    return profiles


def _fetch_papers(query: str, max_results: int) -> dict[str, list[dict]]:
    """Execute a single ArXiv query and return {author_name: [paper, ...]}."""
    try:
        r = httpx.get(
            ARXIV_API,
            params={
                "search_query": query,
                "max_results":  max_results,
                "sortBy":       "submittedDate",
                "sortOrder":    "descending",
            },
            timeout=20,
        )
        if r.status_code != 200:
            return {}
        root = ET.fromstring(r.content)
    except Exception:
        return {}

    author_papers: dict[str, list[dict]] = {}

    for entry in root.findall("atom:entry", NS):
        title_el     = entry.find("atom:title", NS)
        published_el = entry.find("atom:published", NS)
        id_el        = entry.find("atom:id", NS)
        summary_el   = entry.find("atom:summary", NS)

        title     = (title_el.text     or "").strip().replace("\n", " ") if title_el     is not None else ""
        published = (published_el.text or "")[:10]                        if published_el is not None else ""
        paper_url = (id_el.text        or "").strip()                     if id_el        is not None else ""
        summary   = (summary_el.text   or "").strip()[:300]               if summary_el   is not None else ""

        for i, author_el in enumerate(entry.findall("atom:author", NS)):
            name_el        = author_el.find("atom:name", NS)
            affiliation_el = author_el.find("arxiv:affiliation", NS)
            if name_el is None:
                continue
            name        = (name_el.text        or "").strip()
            affiliation = (affiliation_el.text or "").strip() if affiliation_el is not None else ""

            author_papers.setdefault(name, []).append({
                "title":       title,
                "url":         paper_url,
                "published":   published,
                "summary":     summary,
                "position":    i,
                "affiliation": affiliation,
            })

    return author_papers


def _infer_skills_from_papers(papers: list[dict]) -> list[str]:
    keywords = [
        "LLM", "transformer", "fine-tuning", "RAG", "reinforcement learning",
        "diffusion", "multimodal", "NLP", "computer vision", "graph neural",
        "RLHF", "alignment", "reasoning", "agent", "retrieval", "embeddings",
        "classification", "forecasting", "recommendation", "generative",
        "vision-language", "code generation", "instruction tuning",
        "chain-of-thought", "knowledge graph", "federated learning",
    ]
    found: list[str] = []
    text = " ".join(p["title"] + " " + p.get("summary", "") for p in papers).lower()
    for kw in keywords:
        if kw.lower() in text and kw not in found:
            found.append(kw)
    return found[:12]
