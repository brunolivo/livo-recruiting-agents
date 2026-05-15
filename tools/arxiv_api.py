"""
ArXiv API sourcer — finds real AI researchers by their published papers.

Uses ArXiv's Atom feed API (no auth required).
Targets cs.LG (Machine Learning) and cs.AI (Artificial Intelligence) categories.
"""

import httpx
import xml.etree.ElementTree as ET

ARXIV_API = "https://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def search_researchers(keywords: list[str], count: int = 8) -> list[dict]:
    """
    Find real AI researchers from recent ArXiv papers.
    Returns structured profiles ready for synthesis.
    """
    kw_query = " AND ".join(f'"{k}"' for k in keywords[:3])
    query = f"(cat:cs.LG OR cat:cs.AI OR cat:cs.CL) AND ({kw_query})"

    try:
        r = httpx.get(
            ARXIV_API,
            params={
                "search_query": query,
                "max_results": count * 3,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
            timeout=15,
        )
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
    except Exception:
        return []

    seen: set[str] = set()
    author_papers: dict[str, list[dict]] = {}

    for entry in root.findall("atom:entry", NS):
        title_el = entry.find("atom:title", NS)
        published_el = entry.find("atom:published", NS)
        id_el = entry.find("atom:id", NS)
        summary_el = entry.find("atom:summary", NS)
        title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""
        published = (published_el.text or "")[:10] if published_el is not None else ""
        paper_url = (id_el.text or "").strip() if id_el is not None else ""
        summary = (summary_el.text or "").strip()[:300] if summary_el is not None else ""

        for i, author_el in enumerate(entry.findall("atom:author", NS)):
            name_el = author_el.find("atom:name", NS)
            affiliation_el = author_el.find("arxiv:affiliation", NS)
            if name_el is None:
                continue
            name = (name_el.text or "").strip()
            affiliation = (affiliation_el.text or "").strip() if affiliation_el is not None else ""

            paper = {
                "title": title,
                "url": paper_url,
                "published": published,
                "summary": summary,
                "position": i,  # 0 = first author
                "affiliation": affiliation,
            }
            author_papers.setdefault(name, []).append(paper)

    profiles: list[dict] = []
    # Prioritize first authors with multiple papers
    sorted_authors = sorted(
        author_papers.items(),
        key=lambda x: (
            sum(1 for p in x[1] if p["position"] == 0),
            len(x[1]),
        ),
        reverse=True,
    )

    for name, papers in sorted_authors:
        if name in seen or len(profiles) >= count:
            break
        seen.add(name)

        first_author_papers = [p for p in papers if p["position"] == 0]
        latest = papers[0]
        affiliations = list({p["affiliation"] for p in papers if p["affiliation"]})

        profiles.append({
            "name": name,
            "source": "ArXiv",
            "profile_url": f"https://arxiv.org/search/?query={name.replace(' ', '+')}&searchtype=author",
            "headline": f"AI Researcher — {len(papers)} papers ({len(first_author_papers)} as first author)",
            "location": affiliations[0] if affiliations else "",
            "notable_work": latest["title"],
            "skills": _infer_skills_from_papers(papers),
            "publications": f"{len(papers)} papers on ArXiv",
            "recent_paper_url": latest["url"],
            "recent_paper_summary": latest["summary"],
            "affiliations": affiliations[:2],
            "paper_count": len(papers),
        })

    return profiles


def _infer_skills_from_papers(papers: list[dict]) -> list[str]:
    keywords = [
        "LLM", "transformer", "fine-tuning", "RAG", "reinforcement learning",
        "diffusion", "multimodal", "NLP", "computer vision", "graph neural",
        "RLHF", "alignment", "reasoning", "agent", "retrieval", "embeddings",
        "classification", "forecasting", "recommendation",
    ]
    found: list[str] = []
    text = " ".join(p["title"] + " " + p.get("summary", "") for p in papers).lower()
    for kw in keywords:
        if kw.lower() in text and kw not in found:
            found.append(kw)
    return found[:10]
