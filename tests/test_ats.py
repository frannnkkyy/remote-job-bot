"""Offline ATS normalization tests."""
import unittest
from sources.greenhouse import normalize_job as normalize_greenhouse
from sources.lever import normalize_job as normalize_lever
from sources.ashby import normalize_job as normalize_ashby
from sources.aggregator import normalize_job as normalize_jobicy

class AtsNormalizationTests(unittest.TestCase):
    def test_greenhouse_normalization(self) -> None:
        raw = {"id": 12, "title": "Junior Developer", "location": {"name": "Remote LATAM"}, "content": "<p>React</p>", "absolute_url": "https://boards.greenhouse.io/acme/jobs/12", "updated_at": "2026-09-04T10:00:00Z", "departments": [{"name": "Engineering"}]}
        job = normalize_greenhouse(raw, "Acme")
        self.assertEqual(job["company"], "Acme")
        self.assertTrue(job["remote"])
        self.assertEqual(set(("id", "title", "company", "location", "description", "url", "source", "published_at", "remote")).issubset(job), True)

    def test_lever_normalization(self) -> None:
        raw = {"id": "abc", "text": "IT Support Specialist", "descriptionPlain": "Entry level", "hostedUrl": "https://jobs.lever.co/acme/abc", "createdAt": 1788516000000, "categories": {"location": "Remote - Mexico", "team": "Support", "commitment": "Full-time"}}
        job = normalize_lever(raw, "Acme")
        self.assertEqual(job["title"], "IT Support Specialist")
        self.assertEqual(job["job_type"], "Full-time")
        self.assertTrue(job["remote"])

    def test_ashby_normalization(self) -> None:
        raw = {"title": "QA Tester", "location": "Remote", "isRemote": True, "workplaceType": "Remote", "descriptionPlain": "No experience", "publishedAt": "2026-09-04T10:00:00Z", "employmentType": "FullTime", "jobUrl": "https://jobs.ashbyhq.com/acme/123"}
        job = normalize_ashby(raw, "Acme")
        self.assertEqual(job["source"], "Ashby")
        self.assertEqual(job["url"], raw["jobUrl"])
        self.assertTrue(job["remote"])

    def test_jobicy_normalization(self) -> None:
        raw = {"id": 99, "jobTitle": "Marketing Assistant", "companyName": "Acme", "jobGeo": "Anywhere", "jobDescription": "Canva", "url": "https://jobicy.com/jobs/acme", "pubDate": "2026-09-04T10:00:00Z", "jobIndustry": ["Marketing"], "jobType": ["full-time"], "jobLevel": "Entry level"}
        job = normalize_jobicy(raw)
        self.assertEqual(job["location"], "Anywhere")
        self.assertEqual(job["source"], "Jobicy")
        self.assertTrue(job["remote"])

if __name__ == "__main__":
    unittest.main()
