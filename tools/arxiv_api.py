"""
ArXiv API sourcer — finds real AI researchers by their published papers.

v3 — fixed query format:
  • Uses `all:keyword` (full-text) instead of `ti:keyword` (title-only)
  • OR between keywords so any match is enough
  • Single reliable query instead of 3 parallel speculative ones
  • 7 categories: cs.LG, cs.AI, cs.CL, cs.CV, cs.IR, cs.NE, stat.ML
"""

import httpx
import xml.etree.ElementTree as ET

ARXIV_API   = "https://export.arxiv.org/api/query"
NS          = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
_CATEGORIES = "cat:cs.LG OR cat:cs.AI OR cat:cs.CL OR cat:cs.CV OR cat:cs.IR OR cat:cs.NE OR cat:stat.ML"

# Map role keywords → reliable ArXiv search terms (full-text match)
_ROLE_SEEDS = {
    "AI Engineer":        ["large language model", "LLM", "RAG", "transformer", "fine-tuning", "MLOps"],
    "Data Scientist":     ["machine learning", "deep learning", "forecasting", "classification", "neural network"],
    "AI Product Manager": ["human-computer interaction", "AI system", "user study", "evaluation"],
    "AI Designer":        ["human-computer interaction", "interface design", "user experience"],
}


def search_researchers(keywords: list[str], count: int = 8) -> list[dict]:
    """
    Find real AI researchers from recent ArXiv papers.
    Returns up to `count` profiles sorted by first-author paper count.
    """
    # Pick the best search terms: job keywords first, then role seeds as fallback
    search_terms = [k for k in keywords if k and len(k) > 2][:4]
    if not search_terms:
        search_terms = ["machine learning", "deep learning"]

    # Build a broad OR query — any term matching is enough
    term_query  = " OR ".join(f'all:"{t}"' for t in search_terms)
    query       = f"({_CATEGORIES}) AND ({term_query})"

    author_papers = _fetch_papers(query, max_results=count * 8)

    if not author_papers:
        # Fallback: even broader query using just the first keyword
        fallback = f"({_CATEGORIES}) AND all:{search_terms[0].replace(' ', '+')}"
        author_papers = _fetch_papers(fallback, max_results=count * 6)

    # Rank: first-author count → total papers
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

        first_authored   = [p for p in papers if p["position"] == 0]
        latest           = sorted(papers, key=lambda p: p.get("published", ""), reverse=True)[0]
        affiliations     = list({p["affiliation"] for p in papers if p["affiliation"]})
        location_hint    = affiliations[0] if affiliations else ""

        profiles.append({
            "name":                 name,
            "source":               "ArXiv",
            "profile_url":          f"https://arxiv.org/search/?query={name.replace(' ', '+')}&searchtype=author",
            "headline":             f"AI Researcher — {len(papers)} papers ({len(first_authored)} first-authored)",
            "location":             location_hint,
            "notable_work":         latest["title"],
            "skills":               _infer_skills(papers),
            "publications":         f"{len(papers)} papers on ArXiv",
            "recent_paper_url":     latest["url"],
            "recent_paper_summary": latest.get("summary", ""),
            "affiliations":         affiliations[:3],
            "paper_count":          len(papers),
            "first_author_count":   len(first_authored),
        })

    return profiles


def _fetch_papers(query: str, max_results: int) -> dict[str, list[dict]]:
    try:
        r = httpx.get(
            ARXIV_API,
            params={
                "search_query": query,
                "max_results":  min(max_results, 200),
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
        title_el     = entry.find("atom:title",     NS)
        published_el = entry.find("atom:published",  NS)
        id_el        = entry.find("atom:id",         NS)
        summary_el   = entry.find("atom:summary",    NS)

        title     = (title_el.text     or "").strip().replace("\n", " ") if title_el     else ""
        published = (published_el.text or "")[:10]                        if published_el else ""
        paper_url = (id_el.text        or "").strip()                     if id_el        else ""
        summary   = (summary_el.text   or "").strip()[:300]               if summary_el   else ""

        for i, author_el in enumerate(entry.findall("atom:author", NS)):
            name_el        = author_el.find("atom:name",         NS)
            affiliation_el = author_el.find("arxiv:affiliation", NS)
            if name_el is None:
                continue
            name        = (name_el.text        or "").strip()
            affiliation = (affiliation_el.text or "").strip() if affiliation_el else ""

            author_papers.setdefault(name, []).append({
                "title":       title,
                "url":         paper_url,
                "published":   published,
                "summary":     summary,
                "position":    i,
                "affiliation": affiliation,
            })

    return author_papers


def _infer_skills(papers: list[dict]) -> list[str]:
    keywords = [
        "LLM", "transformer", "fine-tuning", "RAG", "reinforcement learning",
        "diffusion", "multimodal", "NLP", "computer vision", "graph neural",
        "RLHF", "alignment", "reasoning", "agent", "retrieval", "embeddings",
        "classification", "forecasting", "recommendation", "generative AI",
        "vision-language", "code generation", "instruction tuning",
        "chain-of-thought", "knowledge graph", "federated learning",
    ]
    found: list[str] = []
    text = " ".join(p["title"] + " " + p.get("summary", "") for p in papers).lower()
    for kw in keywords:
        if kw.lower() in text and kw not in found:
            found.append(kw)
    return found[:12]
