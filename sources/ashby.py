"""Reusable Ashby public Job Postings API adapter."""
import hashlib
from typing import Any
import requests
from config.job_boards import ASHBY_BOARDS
from .common import remote_hint, text

API_URL = "https://api.ashbyhq.com/posting-api/job-board/{board}"
TIMEOUT = 25

def normalize_job(job: dict[str, Any], company: str) -> dict[str, Any]:
    location = text(job.get("location"))
    url = text(job.get("jobUrl") or job.get("applyUrl"))
    identifier = text(job.get("id")) or hashlib.sha256(url.encode()).hexdigest()[:24]
    is_remote = job.get("isRemote")
    remote = is_remote if isinstance(is_remote, bool) else remote_hint(location, text(job.get("workplaceType")))
    tags = [text(job.get(key)) for key in ("department", "team", "employmentType", "workplaceType") if job.get(key)]
    return {
        "id": identifier, "title": text(job.get("title")), "company": company,
        "location": location, "description": text(job.get("descriptionPlain") or job.get("descriptionHtml")),
        "url": url, "source": "Ashby", "published_at": text(job.get("publishedAt")),
        "remote": remote, "tags": tags, "job_type": text(job.get("employmentType")),
    }

def fetch_jobs() -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    with requests.Session() as session:
        for board, company in ASHBY_BOARDS:
            try:
                response = session.get(API_URL.format(board=board), timeout=TIMEOUT)
                response.raise_for_status()
                company_jobs = [normalize_job(item, company) for item in response.json().get("jobs", []) if isinstance(item, dict) and item.get("isListed", True)]
                print(f"[Ashby] {company}: {len(company_jobs)} jobs")
                jobs.extend(company_jobs)
            except Exception as exc:
                print(f"[Ashby] {company} failed: {exc}")
    return jobs
