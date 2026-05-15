"""
HuggingFace API sourcer — finds real ML practitioners by their published models.

Searches the HuggingFace model hub for individual contributors (not big orgs).
Model downloads and likes are strong signals of real-world AI depth.
"""

import httpx

HF_API = "https://huggingface.co/api"

# Filter out large organizations — we want individual practitioners
_ORG_BLOCKLIST = {
    "microsoft", "google", "meta-llama", "mistralai", "openai", "facebook",
    "tiiuae", "bigscience", "EleutherAI", "allenai", "salesforce", "amazon",
    "huggingface", "stabilityai", "databricks", "nvidia", "cerebras",
}

# Map role type to HF pipeline tasks
TASK_MAP = {
    "AI Engineer": ["text-generation", "text2text-generation", "question-answering"],
    "Data Scientist": ["tabular-classification", "tabular-regression", "time-series-forecasting", "text-classification"],
}


def search_practitioners(role_type: str = "AI Engineer", count: int = 10) -> list[dict]:
    """
    Find real HuggingFace model authors for a given role type.
    Returns structured profiles ready for synthesis.
    """
    tasks = TASK_MAP.get(role_type, ["text-generation"])
    seen_authors: set[str] = set()
    profiles: list[dict] = []

    for task in tasks:
        if len(profiles) >= count:
            break
        batch = _fetch_task_authors(task, seen_authors, count - len(profiles))
        profiles.extend(batch)

    return profiles


def _fetch_task_authors(task: str, seen: set[str], limit: int) -> list[dict]:
    try:
        r = httpx.get(
            f"{HF_API}/models",
            params={"sort": "downloads", "direction": -1, "limit": 100, "filter": task},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        models = r.json()
    except Exception:
        return []

    # Group by author
    author_models: dict[str, list[dict]] = {}
    for model in models:
        raw_id = model.get("id") or model.get("modelId") or ""
        author = model.get("author") or (raw_id.split("/")[0] if "/" in raw_id else "")
        if not author or author.lower() in _ORG_BLOCKLIST:
            continue
        author_models.setdefault(author, []).append(model)

    profiles: list[dict] = []
    for author, author_model_list in author_models.items():
        if author in seen or len(profiles) >= limit:
            break
        seen.add(author)

        total_downloads = sum(m.get("downloads", 0) for m in author_model_list)
        total_likes = sum(m.get("likes", 0) for m in author_model_list)
        top_model = max(author_model_list, key=lambda m: m.get("downloads", 0))
        top_model_name = (top_model.get("id") or "").split("/")[-1]
        model_names = [
            (m.get("id") or "").split("/")[-1]
            for m in sorted(author_model_list, key=lambda m: m.get("downloads", 0), reverse=True)[:3]
        ]

        profiles.append({
            "name": author,
            "username": author,
            "source": "HuggingFace",
            "profile_url": f"https://huggingface.co/{author}",
            "headline": f"ML Practitioner — {len(author_model_list)} models published on HuggingFace",
            "notable_work": f"Top model: {top_model_name} ({total_downloads:,} total downloads)",
            "skills": _infer_skills(author_model_list),
            "model_count": len(author_model_list),
            "total_downloads": total_downloads,
            "total_likes": total_likes,
            "model_names": model_names,
            "task": task,
        })

    return profiles


def _infer_skills(models: list[dict]) -> list[str]:
    skills: list[str] = []
    for m in models:
        tags = m.get("tags") or []
        for tag in tags:
            if tag.lower() in (
                "pytorch", "tensorflow", "jax", "transformers", "diffusers",
                "llm", "rlhf", "lora", "gguf", "quantization", "fine-tuning",
                "text-generation", "text-classification", "computer-vision",
            ):
                if tag not in skills:
                    skills.append(tag)
    return skills[:10]
