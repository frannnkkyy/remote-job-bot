"""Pipeline, canonical URL, and cross-source deduplication tests."""
import os
import unittest
from contextlib import redirect_stdout
from io import StringIO
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

    def _run_empty_cycle(self, environment: dict[str, str]):
        seen = {"existing-job"}
        with patch.dict(os.environ, environment, clear=True), \
             patch.object(main, "validate_config"), \
             patch.object(main, "send_message", return_value=True) as send_message, \
             patch.object(main, "load_seen_jobs", return_value=seen), \
             patch.object(main, "fetch_all_jobs", return_value=[]) as fetch_all_jobs, \
             patch.object(main, "save_seen_jobs") as save_seen_jobs, \
             redirect_stdout(StringIO()):
            main.main()
        return send_message, fetch_all_jobs, save_seen_jobs, seen

    def test_manual_run_sends_test_message(self) -> None:
        send_message, _, _, _ = self._run_empty_cycle({"MANUAL_RUN": "true"})
        send_message.assert_called_once_with(main.MANUAL_TEST_MESSAGE)

    def test_false_manual_run_does_not_send_test_message(self) -> None:
        send_message, _, _, _ = self._run_empty_cycle({"MANUAL_RUN": "false"})
        send_message.assert_not_called()

    def test_missing_manual_run_does_not_send_test_message(self) -> None:
        send_message, _, _, _ = self._run_empty_cycle({})
        send_message.assert_not_called()

    def test_normal_search_still_runs_after_manual_message(self) -> None:
        _, fetch_all_jobs, _, _ = self._run_empty_cycle({"MANUAL_RUN": "true"})
        fetch_all_jobs.assert_called_once_with()

    def test_manual_message_does_not_change_seen_jobs(self) -> None:
        _, _, save_seen_jobs, seen = self._run_empty_cycle({"MANUAL_RUN": "true"})
        save_seen_jobs.assert_not_called()
        self.assertEqual(seen, {"existing-job"})

if __name__ == "__main__":
    unittest.main()
