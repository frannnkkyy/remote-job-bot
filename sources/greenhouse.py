"""Reusable Greenhouse public Job Board API adapter."""
from typing import Any
import requests
from config.job_boards import GREENHOUSE_BOARDS
from .common import remote_hint, text

API_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
TIMEOUT = 25

def normalize_job(job: dict[str, Any], company: str) -> dict[str, Any]:
    location = text((job.get("location") or {}).get("name"))
    departments = [text(item.get("name")) for item in (job.get("departments") or []) if isinstance(item, dict)]
    return {
        "id": text(job.get("id")), "title": text(job.get("title")), "company": company,
        "location": location, "description": text(job.get("content")), "url": text(job.get("absolute_url")),
        "source": "Greenhouse", "published_at": text(job.get("updated_at")), "remote": remote_hint(location),
        "tags": [item for item in departments if item], "job_type": "",
    }

def fetch_jobs() -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    with requests.Session() as session:
        for board, company in GREENHOUSE_BOARDS:
            try:
                response = session.get(API_URL.format(board=board), params={"content": "true"}, timeout=TIMEOUT)
                response.raise_for_status()
                board_jobs = [normalize_job(item, company) for item in response.json().get("jobs", []) if isinstance(item, dict)]
                print(f"[Greenhouse] {company}: {len(board_jobs)} jobs")
                jobs.extend(board_jobs)
            except Exception as exc:
                print(f"[Greenhouse] {company} failed: {exc}")
    return jobs
