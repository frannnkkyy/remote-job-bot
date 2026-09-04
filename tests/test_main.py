"""Pipeline, canonical URL, and cross-source deduplication tests."""
import unittest
from unittest.mock import patch
import main

def sample(source: str, url: str, company: str = "Acme") -> dict:
    return {"id": source, "title": "Junior Developer", "company": company, "location": "Remote LATAM", "description": "React", "url": url, "source": source, "published_at": "", "remote": True, "tags": [], "job_type": ""}

class MainTests(unittest.TestCase):
    def test_canonical_url_removes_only_tracking(self) -> None:
        value = main.canonical_url("HTTPS://Example.com/jobs/1/?source=career&utm_source=x&trackingId=y#top")
        self.assertEqual(value, "https://example.com/jobs/1?source=career")

    def test_email_and_greenhouse_duplicate_prefers_ats(self) -> None:
        email = sample("LinkedIn Alert", "https://boards.greenhouse.io/acme/jobs/1?utm_source=linkedin", "")
        greenhouse = sample("Greenhouse", "https://boards.greenhouse.io/acme/jobs/1")
        result = main.normalize_and_deduplicate([email, greenhouse])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source"], "Greenhouse")

    def test_company_title_duplicate_prefers_ats(self) -> None:
        board = sample("RemoteOK", "https://remoteok.com/1")
        ats = sample("Lever", "https://jobs.lever.co/acme/1")
        result = main.normalize_and_deduplicate([board, ats])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source"], "Lever")

    def test_empty_company_does_not_dedupe_by_title(self) -> None:
        first = sample("One", "https://example.com/1", "")
        second = sample("Two", "https://example.com/2", "")
        self.assertEqual(len(main.normalize_and_deduplicate([first, second])), 2)

    def test_one_source_failure_does_not_stop_others(self) -> None:
        def failed() -> list:
            raise RuntimeError("offline")
        with patch.object(main, "ALL_SOURCES", [("Bad", failed), ("Good", lambda: [sample("Good", "https://example.com/1")])]):
            self.assertEqual(len(main.fetch_all_jobs()), 1)

if __name__ == "__main__":
    unittest.main()
