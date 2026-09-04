"""Reusable Lever public Postings API adapter."""
from datetime import datetime, timezone
from typing import Any
import requests
from config.job_boards import LEVER_COMPANIES
from .common import remote_hint, text

GLOBAL_URL = "https://api.lever.co/v0/postings/{site}"
EU_URL = "https://api.eu.lever.co/v0/postings/{site}"
TIMEOUT = 25

def normalize_job(job: dict[str, Any], company: str) -> dict[str, Any]:
    categories = job.get("categories") or {}
    location = text(categories.get("location"))
    description = text(job.get("descriptionPlain") or job.get("description"))
    lists = " ".join(text(item.get("content")) for item in (job.get("lists") or []) if isinstance(item, dict))
    created = job.get("createdAt")
    try:
        published = datetime.fromtimestamp(float(created) / 1000, timezone.utc).isoformat() if created else ""
    except (TypeError, ValueError, OSError):
        published = ""
    tags = [text(categories.get(key)) for key in ("team", "department", "commitment", "level") if categories.get(key)]
    return {
        "id": text(job.get("id")), "title": text(job.get("text")), "company": company,
        "location": location, "description": f"{description} {lists}".strip(),
        "url": text(job.get("hostedUrl") or job.get("applyUrl")), "source": "Lever",
        "published_at": published, "remote": remote_hint(location, text(job.get("workplaceType"))),
        "tags": tags, "job_type": text(categories.get("commitment")),
    }

def fetch_jobs() -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    with requests.Session() as session:
        for configured_site, company in LEVER_COMPANIES:
            is_eu = configured_site.startswith("eu:")
            site = configured_site[3:] if is_eu else configured_site
            try:
                endpoint = (EU_URL if is_eu else GLOBAL_URL).format(site=site)
                response = session.get(endpoint, params={"mode": "json", "limit": 200}, headers={"Accept": "application/json"}, timeout=TIMEOUT)
                response.raise_for_status()
                company_jobs = [normalize_job(item, company) for item in response.json() if isinstance(item, dict)]
                print(f"[Lever] {company}: {len(company_jobs)} jobs")
                jobs.extend(company_jobs)
            except Exception as exc:
                print(f"[Lever] {company} failed: {exc}")
    return jobs
