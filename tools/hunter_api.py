"""
Hunter.io email finder — discovers professional email addresses for candidates.

Uses the Hunter.io Email Finder API to locate emails given a name + domain.
Falls back gracefully when the API key is missing or the email is not found.

Rate limits: 25 searches/month (free), 500/month (Starter plan).
Set HUNTER_API_KEY in environment to enable.
"""

import os
import re
import httpx

HUNTER_API = "https://api.hunter.io/v2"
_KEY = os.getenv("HUNTER_API_KEY", "")

# Domains known to be useless for email lookup
_SKIP_DOMAINS = {
    "github.com", "github.io", "huggingface.co", "arxiv.org",
    "twitter.com", "x.com", "t.co", "linkedin.com",
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
}


def _extract_domain(url: str) -> str | None:
    """Extract a company domain from a website URL."""
    if not url:
        return None
    url = url.strip().lower()
    if not url.startswith("http"):
        url = "https://" + url
    match = re.search(r"https?://(?:www\.)?([^/\s]+)", url)
    if not match:
        return None
    domain = match.group(1)
    return None if domain in _SKIP_DOMAINS else domain


def find_email(
    full_name: str,
    website: str | None = None,
    company: str | None = None,
) -> str | None:
    """
    Try to find a professional email for a person using Hunter.io.
    Returns the email string if found with ≥40% confidence, else None.
    """
    if not _KEY:
        return None

    parts = full_name.strip().split()
    if len(parts) < 2:
        return None

    domain = _extract_domain(website or "")
    if not domain and company:
        # Try company name as domain hint via Hunter's company search
        domain = _extract_domain(company) or _guess_domain(company)

    if not domain:
        return None

    try:
        r = httpx.get(
            f"{HUNTER_API}/email-finder",
            params={
                "domain": domain,
                "first_name": parts[0],
                "last_name": parts[-1],
                "api_key": _KEY,
            },
            timeout=8,
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            email = data.get("email")
            confidence = data.get("score", 0)
            return email if email and confidence >= 40 else None
        return None
    except Exception:
        return None


def _guess_domain(company: str) -> str | None:
    """Crude domain guess from company name (e.g. 'Google LLC' → 'google.com')."""
    if not company:
        return None
    name = re.sub(r"\b(inc|llc|ltd|corp|gmbh|sas|sl|s\.a\.?)\b", "", company, flags=re.I)
    name = re.sub(r"[^a-z0-9]", "", name.lower().strip())
    return f"{name}.com" if len(name) > 2 else None


def find_emails_batch(
    candidates: list[dict],
) -> dict[str, str]:
    """
    Find emails for a batch of candidates in parallel.
    Each dict should have: name, blog (website), company.
    Returns a mapping of name → email.
    """
    if not _KEY:
        return {}

    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: dict[str, str] = {}

    def _lookup(c: dict) -> tuple[str, str | None]:
        email = find_email(
            full_name=c.get("name", ""),
            website=c.get("blog") or c.get("website"),
            company=c.get("company"),
        )
        return c["name"], email

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_lookup, c): c for c in candidates}
        for fut in as_completed(futures):
            name, email = fut.result()
            if email:
                results[name] = email

    return results
