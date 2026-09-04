"""Optional Jobicy public remote-jobs aggregator adapter."""
import os
from typing import Any
import requests
from .common import text

API_URL = "https://jobicy.com/api/v2/remote-jobs"
TIMEOUT = 25
MAX_JOBS = 200

def normalize_job(job: dict[str, Any]) -> dict[str, Any]:
    industries = job.get("jobIndustry") if isinstance(job.get("jobIndustry"), list) else []
    levels = [text(job.get("jobLevel"))] if job.get("jobLevel") else []
    job_types = job.get("jobType") if isinstance(job.get("jobType"), list) else []
    return {
        "id": text(job.get("id") or job.get("jobSlug")), "title": text(job.get("jobTitle")),
        "company": text(job.get("companyName")), "location": text(job.get("jobGeo")),
        "description": text(job.get("jobDescription") or job.get("jobExcerpt")), "url": text(job.get("url")),
        "source": "Jobicy", "published_at": text(job.get("pubDate")), "remote": True,
        "tags": [text(item) for item in industries + levels if text(item)],
        "job_type": ", ".join(text(item) for item in job_types if text(item)),
    }

def fetch_jobs() -> list[dict[str, Any]]:
    if os.getenv("ENABLE_JOBICY", "").strip().lower() not in {"1", "true", "yes"}:
        print("[Aggregator] skipped (not configured)")
        return []
    try:
        response = requests.get(API_URL, params={"count": MAX_JOBS}, timeout=TIMEOUT)
        response.raise_for_status()
        jobs = [normalize_job(item) for item in response.json().get("jobs", []) if isinstance(item, dict)]
        print(f"[Aggregator] {len(jobs)} jobs fetched")
        return jobs
    except Exception as exc:
        print(f"[Aggregator] failed: {exc}")
        return []
