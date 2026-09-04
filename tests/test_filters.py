"""Candidate-profile regression tests."""
import unittest
from filters import assess_job

def job(title: str, location: str = "Remote", description: str = "", source: str = "Other") -> dict:
    return {"title": title, "company": "Example", "location": location, "description": description, "url": "https://example.com/job", "source": source, "published_at": "", "remote": None, "tags": []}

class FilterTests(unittest.TestCase):
    def test_01_junior_frontend_is_excellent(self) -> None:
        result = assess_job(job("Junior Frontend Developer", "Remote LATAM", "0-1 years React JavaScript"))
        self.assertEqual(result.category, "EXCELLENT")

    def test_02_support_stack_is_excellent(self) -> None:
        result = assess_job(job("Technical Support Representative", "Remote Mexico", "Entry Level ServiceNow Microsoft 365"))
        self.assertEqual(result.category, "EXCELLENT")

    def test_03_qa_no_experience_is_good_or_excellent(self) -> None:
        self.assertIn(assess_job(job("QA Tester", description="No experience required")).category, {"GOOD", "EXCELLENT"})

    def test_04_marketing_assistant_is_good(self) -> None:
        self.assertEqual(assess_job(job("Marketing Assistant", "Remote LATAM", "No experience Canva Social Media")).category, "GOOD")

    def test_05_frontend_two_years_is_good(self) -> None:
        self.assertEqual(assess_job(job("Frontend Developer", description="2 years experience React JavaScript")).category, "GOOD")

    def test_06_three_years_preferred_is_not_rejected(self) -> None:
        self.assertIn(assess_job(job("Frontend Developer", description="3 years preferred React JavaScript")).category, {"GOOD", "STRETCH"})

    def test_07_three_years_required_is_penalized(self) -> None:
        result = assess_job(job("Frontend Developer", description="3+ years REQUIRED"))
        self.assertLess(result.score, 40)
        self.assertIn("3+ años", result.weaknesses[0])

    def test_08_senior_is_rejected(self) -> None:
        self.assertEqual(assess_job(job("Senior Software Engineer", description="7+ years")).category, "REJECT")

    def test_09_us_only_is_rejected(self) -> None:
        self.assertEqual(assess_job(job("Software Engineer", "Remote - US only")).rejection, "geo restriction")

    def test_10_remote_london_is_rejected(self) -> None:
        self.assertEqual(assess_job(job("Frontend Developer", "Remote - London")).rejection, "geo restriction")

    def test_11_london_worldwide_can_pass(self) -> None:
        self.assertNotEqual(assess_job(job("Frontend Developer", "Remote - London", "Worldwide candidates accepted")).category, "REJECT")

    def test_12_incidental_senior_experience_is_not_penalized(self) -> None:
        result = assess_job(job("Frontend Developer", description="Our senior engineers have 5+ years experience"))
        self.assertEqual(result.category, "GOOD")
        self.assertEqual(result.weaknesses, [])

    def test_13_lead_generation_is_not_seniority(self) -> None:
        result = assess_job(job("Marketing Specialist", "Remote LATAM", "Lead generation"))
        self.assertNotEqual(result.rejection, "senior")

    def test_14_store_manager_is_irrelevant(self) -> None:
        self.assertEqual(assess_job(job("Store Manager")).rejection, "irrelevant role")

    def test_15_office_maid_is_irrelevant(self) -> None:
        self.assertEqual(assess_job(job("Office Maid")).rejection, "irrelevant role")

    def test_16_it_support_without_years_is_good(self) -> None:
        self.assertEqual(assess_job(job("IT Support Specialist")).category, "GOOD")

    def test_remote_source_needs_no_duplicate_remote_text(self) -> None:
        self.assertEqual(assess_job(job("IT Support Specialist", location="", source="Remotive")).category, "GOOD")

    def test_incidental_hybrid_team_is_allowed(self) -> None:
        self.assertEqual(assess_job(job("QA Tester", description="We also have hybrid teams in other countries.")).category, "GOOD")

    def test_four_years_required_is_rejected(self) -> None:
        self.assertEqual(assess_job(job("Frontend Developer", description="Minimum 4+ years required React")).category, "REJECT")

if __name__ == "__main__":
    unittest.main()
