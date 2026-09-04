"""Offline Gmail IMAP and forwarded-alert tests."""
import io
import os
import unittest
from contextlib import redirect_stdout
from email.message import EmailMessage
from unittest.mock import MagicMock, patch
from urllib.parse import quote

from sources.email_alerts import fetch_jobs, parse_email_content, parse_email_html

LINKEDIN_HTML = '<div><h3>Junior Frontend Developer</h3><p>Remote LATAM</p><a href="https://www.linkedin.com/jobs/view/123">View job</a></div><footer><a href="https://linkedin.com/preferences">Unsubscribe</a></footer>'
INDEED_URL = "https://mx.indeed.com/viewjob?jk=abc123"
INDEED_HTML = f'<article><strong>IT Support Specialist</strong><p>Remote Mexico</p><a href="https://click.example/redirect?url={quote(INDEED_URL)}">Apply now</a></article>'

def raw_email(sender: str, subject: str, html: str) -> bytes:
    message = EmailMessage()
    message["From"] = sender; message["To"] = "bot@gmail.com"; message["Subject"] = subject
    message["Date"] = "Thu, 04 Sep 2026 10:00:00 +0000"
    message.set_content("Job alert")
    message.add_alternative(html, subtype="html")
    return message.as_bytes()

def fake_imap(messages: list[bytes]) -> MagicMock:
    connection = MagicMock()
    connection.login.return_value = ("OK", [b"logged in"])
    connection.select.return_value = ("OK", [b"1"])
    connection.search.return_value = ("OK", [b" ".join(str(index + 1).encode() for index in range(len(messages)))])
    by_id = {str(index + 1).encode(): raw for index, raw in enumerate(messages)}
    connection.fetch.side_effect = lambda message_id, query: ("OK", [(b"BODY", by_id[message_id])])
    return connection

class GmailAlertTests(unittest.TestCase):
    def test_01_not_configured(self) -> None:
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
            self.assertEqual(fetch_jobs(), [])
        self.assertIn("Gmail not configured", output.getvalue())

    def test_02_login_and_recent_search(self) -> None:
        connection = fake_imap([])
        with patch.dict(os.environ, {"JOB_EMAIL_ADDRESS": "bot@gmail.com", "JOB_EMAIL_APP_PASSWORD": "fake"}, clear=True), patch("sources.email_alerts.imaplib.IMAP4_SSL", return_value=connection):
            self.assertEqual(fetch_jobs(), [])
        connection.login.assert_called_once_with("bot@gmail.com", "fake")
        connection.search.assert_called_once()

    def test_03_reads_recent_mail_readonly_without_seen_flag(self) -> None:
        connection = fake_imap([raw_email("jobs@linkedin.com", "New jobs", LINKEDIN_HTML)])
        with patch.dict(os.environ, {"JOB_EMAIL_ADDRESS": "bot@gmail.com", "JOB_EMAIL_APP_PASSWORD": "fake"}, clear=True), patch("sources.email_alerts.imaplib.IMAP4_SSL", return_value=connection):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(len(fetch_jobs()), 1)
        connection.select.assert_called_once_with("INBOX", readonly=True)
        self.assertEqual(connection.fetch.call_args.args[1], "(BODY.PEEK[])")

    def test_04_direct_linkedin(self) -> None:
        jobs = parse_email_html("jobs@linkedin.com", "New jobs", "date", LINKEDIN_HTML)
        self.assertEqual(jobs[0]["source"], "LinkedIn Alert")

    def test_05_direct_indeed(self) -> None:
        jobs = parse_email_html("alerts@indeed.com", "Job alert", "date", INDEED_HTML)
        self.assertEqual(jobs[0]["url"], INDEED_URL)

    def test_06_forwarded_linkedin(self) -> None:
        body = "<p>Forwarded message from LinkedIn Job Alerts</p>" + LINKEDIN_HTML
        jobs = parse_email_html("owner@outlook.com", 'FW: jobs for "Developer"', "date", body)
        self.assertEqual(jobs[0]["source"], "LinkedIn Alert")

    def test_07_forwarded_indeed(self) -> None:
        body = "<p>From: Indeed Job Alerts</p>" + INDEED_HTML
        jobs = parse_email_html("owner@outlook.com", "FW: New vacancy", "date", body)
        self.assertEqual(jobs[0]["source"], "Indeed Alert")

    def test_08_footer_is_ignored(self) -> None:
        jobs = parse_email_html("jobs@linkedin.com", "Jobs", "date", LINKEDIN_HTML)
        self.assertEqual(len(jobs), 1)

    def test_09_normalized_contract(self) -> None:
        job = parse_email_html("jobs@linkedin.com", "Jobs", "date", LINKEDIN_HTML)[0]
        fields = {"id", "title", "company", "location", "description", "url", "source", "published_at", "remote"}
        self.assertTrue(fields.issubset(job))

    def test_10_maximum_recent_messages(self) -> None:
        connection = fake_imap([raw_email("jobs@linkedin.com", "Jobs", LINKEDIN_HTML)] * 105)
        with patch.dict(os.environ, {"JOB_EMAIL_ADDRESS": "bot@gmail.com", "JOB_EMAIL_APP_PASSWORD": "fake"}, clear=True), patch("sources.email_alerts.imaplib.IMAP4_SSL", return_value=connection):
            with redirect_stdout(io.StringIO()):
                fetch_jobs()
        self.assertEqual(connection.fetch.call_count, 100)

    def test_11_linkedin_comm_jobs(self) -> None:
        html = '<div><h3>Software Engineer</h3><p>Remote</p><a href="https://www.linkedin.com/comm/jobs/view/456">Apply</a></div>'
        self.assertEqual(len(parse_email_html("forwarder@outlook.com", "FW: LinkedIn jobs", "date", html)), 1)

    def test_12_indeed_rc_click(self) -> None:
        html = '<div><h3>QA Tester</h3><p>Remote</p><a href="https://www.indeed.com/rc/clk?jk=xyz">View job</a></div>'
        self.assertEqual(len(parse_email_html("alerts@indeed.com", "Jobs", "date", html)), 1)

    def test_13_nested_destination_and_html_entities(self) -> None:
        destination = quote("https://www.indeed.com/viewjob?jk=encoded")
        html = f'<div><h3>Technical Support Representative</h3><p>Remote Mexico</p><a href="https://safe.example/?q=https%3A%2F%2Ftracker.example%2Fgo%3Fdestination%3D{destination}&amp;source=mail">Apply</a></div>'
        jobs = parse_email_html("owner@outlook.com", "FW: Indeed jobs", "date", html)
        self.assertEqual(jobs[0]["url"], "https://www.indeed.com/viewjob?jk=encoded")

    def test_14_apply_uses_parent_title(self) -> None:
        html = '<div><h2>Marketing Assistant</h2><p>Company X · Remote LATAM</p><a href="https://www.linkedin.com/jobs/view/999">Apply</a></div>'
        self.assertEqual(parse_email_html("jobs@linkedin.com", "Jobs", "date", html)[0]["title"], "Marketing Assistant")

    def test_15_plain_text_fallback(self) -> None:
        plain = "Junior Software Developer\nCompany X\nRemote LATAM\nhttps://www.linkedin.com/jobs/view/777"
        jobs, stats = parse_email_content("owner@outlook.com", "FW: LinkedIn jobs", "date", plain_body=plain)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(stats.platform, "LinkedIn")

    def test_16_manage_alerts_is_ignored(self) -> None:
        html = '<a href="https://www.linkedin.com/jobs/preferences">Manage job alerts</a>'
        self.assertEqual(parse_email_html("jobs@linkedin.com", "Jobs", "date", html), [])

    def test_17_duplicate_links_make_one_job(self) -> None:
        html = '<div><h3>Frontend Developer</h3><p>Remote</p><a href="https://linkedin.com/jobs/view/42">Frontend Developer</a><a href="https://linkedin.com/jobs/view/42">Apply</a></div>'
        self.assertEqual(len(parse_email_html("jobs@linkedin.com", "Jobs", "date", html)), 1)

    def test_18_nested_multipart(self) -> None:
        inner = EmailMessage(); inner.set_content("plain fallback"); inner.add_alternative(LINKEDIN_HTML, subtype="html")
        outer = EmailMessage(); outer["From"] = "owner@outlook.com"; outer["Subject"] = "FW: LinkedIn jobs"; outer["Date"] = "Thu, 04 Sep 2026 10:00:00 +0000"; outer.make_mixed(); outer.attach(inner)
        connection = fake_imap([outer.as_bytes()])
        with patch.dict(os.environ, {"JOB_EMAIL_ADDRESS": "bot@gmail.com", "JOB_EMAIL_APP_PASSWORD": "fake"}, clear=True), patch("sources.email_alerts.imaplib.IMAP4_SSL", return_value=connection), redirect_stdout(io.StringIO()):
            self.assertEqual(len(fetch_jobs()), 1)

    def _fetch_with_output(self, messages: list[bytes]) -> tuple[list[dict], str]:
        connection = fake_imap(messages)
        output = io.StringIO()
        with patch.dict(os.environ, {"JOB_EMAIL_ADDRESS": "bot@gmail.com", "JOB_EMAIL_APP_PASSWORD": "fake"}, clear=True), patch("sources.email_alerts.imaplib.IMAP4_SSL", return_value=connection), redirect_stdout(output):
            jobs = fetch_jobs()
        return jobs, output.getvalue()

    def test_19_google_security_alert_is_not_counted_or_debugged(self) -> None:
        message = raw_email("no-reply@accounts.google.com", "Security alert", "<p>New sign-in on your Google Account</p>")
        jobs, output = self._fetch_with_output([message])
        self.assertEqual(jobs, [])
        self.assertIn("[Email Alerts] 0 alert emails, 0 jobs extracted", output)
        self.assertNotIn("[Email Debug]", output)

    def test_20_two_step_verification_is_not_counted_or_debugged(self) -> None:
        message = raw_email("no-reply@accounts.google.com", "2-Step Verification turned on", "<p>Your account is now protected.</p>")
        jobs, output = self._fetch_with_output([message])
        self.assertEqual(jobs, [])
        self.assertIn("[Email Alerts] 0 alert emails, 0 jobs extracted", output)
        self.assertNotIn("[Email Debug]", output)

    def test_21_linkedin_job_alert_is_counted(self) -> None:
        message = raw_email("jobs-noreply@linkedin.com", "LinkedIn Job Alert", LINKEDIN_HTML)
        jobs, output = self._fetch_with_output([message])
        self.assertEqual(len(jobs), 1)
        self.assertIn("[Email Alerts] 1 alert emails, 1 jobs extracted", output)
        self.assertIn("[Email Debug]", output)

    def test_22_indeed_job_alert_is_counted(self) -> None:
        message = raw_email("alerts@indeed.com", "Indeed Job Alert", INDEED_HTML)
        jobs, output = self._fetch_with_output([message])
        self.assertEqual(len(jobs), 1)
        self.assertIn("[Email Alerts] 1 alert emails, 1 jobs extracted", output)
        self.assertIn("[Email Debug]", output)

if __name__ == "__main__":
    unittest.main()
