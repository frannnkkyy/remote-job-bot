"""Arbeitnow public job-board API adapter."""

from typing import Any

import requests

API_URL = "https://www.arbeitnow.com/api/job-board-api"
TIMEOUT = 25


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def fetch_jobs() -> list[dict[str, Any]]:
    """Fetch and normalize the first page of Arbeitnow jobs."""
    response = requests.get(API_URL, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    jobs = payload.get("data", []) if isinstance(payload, dict) else []
    normalized: list[dict[str, str]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        location = _text(job.get("location"))
        if job.get("remote") and "remote" not in location.lower():
            location = f"Remote - {location}" if location else "Remote"
        normalized.append(
            {
                "id": _text(job.get("slug") or job.get("id")),
                "title": _text(job.get("title")),
                "company": _text(job.get("company_name")),
                "location": location,
                "description": _text(job.get("description")),
                "url": _text(job.get("url")),
                "source": "Arbeitnow",
                "published_at": _text(job.get("created_at")),
                "remote": job.get("remote") if isinstance(job.get("remote"), bool) else None,
                "tags": job.get("tags") if isinstance(job.get("tags"), list) else [],
                "job_type": ", ".join(str(item) for item in job.get("job_types", [])),
            }
        )
    return normalized
