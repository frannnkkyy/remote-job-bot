"""Remotive public API adapter."""

from typing import Any

import requests

API_URL = "https://remotive.com/api/remote-jobs"
TIMEOUT = 25


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def fetch_jobs() -> list[dict[str, Any]]:
    """Fetch and normalize jobs from Remotive."""
    response = requests.get(API_URL, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    return [
        {
            "id": _text(job.get("id")),
            "title": _text(job.get("title")),
            "company": _text(job.get("company_name")),
            "location": _text(job.get("candidate_required_location")),
            "description": _text(job.get("description")),
            "url": _text(job.get("url")),
            "source": "Remotive",
            "published_at": _text(job.get("publication_date")),
            "remote": True,
            "tags": job.get("tags") if isinstance(job.get("tags"), list) else [],
            "job_type": _text(job.get("job_type")),
        }
        for job in jobs
        if isinstance(job, dict)
    ]
