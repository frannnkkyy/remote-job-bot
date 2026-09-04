"""RemoteOK public JSON feed adapter."""

from typing import Any

import requests

API_URL = "https://remoteok.com/api"
TIMEOUT = 25
HEADERS = {"User-Agent": "remote-job-bot/1.0 (+personal Telegram job alerts)"}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def fetch_jobs() -> list[dict[str, Any]]:
    """Fetch and normalize jobs from RemoteOK."""
    response = requests.get(API_URL, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    jobs = payload if isinstance(payload, list) else []
    normalized: list[dict[str, str]] = []
    for job in jobs:
        # The first feed item is commonly legal metadata rather than a vacancy.
        if not isinstance(job, dict) or not (job.get("position") or job.get("url")):
            continue
        location = job.get("location") or job.get("region") or "Remote"
        normalized.append(
            {
                "id": _text(job.get("id")),
                "title": _text(job.get("position")),
                "company": _text(job.get("company")),
                "location": _text(location),
                "description": _text(job.get("description")),
                "url": _text(job.get("url") or job.get("apply_url")),
                "source": "RemoteOK",
                "published_at": _text(job.get("date") or job.get("epoch")),
                "remote": True,
                "tags": job.get("tags") if isinstance(job.get("tags"), list) else [],
                "job_type": "",
            }
        )
    return normalized
