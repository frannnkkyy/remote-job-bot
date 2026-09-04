"""Read-only Gmail job-alert source using IMAP SSL and an App Password."""
from __future__ import annotations

import email
import hashlib
import html
import imaplib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.message import Message
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from bs4 import BeautifulSoup, Tag

IMAP_HOST, IMAP_PORT = "imap.gmail.com", 993
MAX_EMAILS, DAYS_BACK, MAX_UNWRAP = 100, 5, 5
ALERT_HINTS = ("linkedin", "indeed", "glassdoor", "computrabajo", "wellfound", "job", "jobs", "career", "vacancy", "employment", "empleo", "vacante")
SECURITY_ALERT_HINTS = (
    "security alert",
    "2-step verification",
    "two-step verification",
    "account security",
    "sign-in alert",
    "signin alert",
    "new sign-in",
    "password changed",
    "password was changed",
    "recovery email",
    "microsoft security alert",
)
PLATFORMS = (("linkedin", "LinkedIn"), ("indeed", "Indeed"), ("glassdoor", "Glassdoor"), ("computrabajo", "Computrabajo"), ("wellfound", "Wellfound"))
JOB_DOMAINS = ("linkedin.com", "indeed.com", "glassdoor.com", "computrabajo.com", "wellfound.com", "greenhouse.io", "lever.co", "ashbyhq.com")
NAVIGATION_TEXT = ("view all jobs", "see more jobs", "manage alerts", "manage job alerts", "unsubscribe", "privacy", "terms", "settings", "login", "sign in", "home", "profile", "help", "preferences", "company page")
GENERIC_ACTIONS = ("apply", "apply now", "view job", "see job", "ver empleo", "ver oferta", "ver vacante", "postularme", "learn more")
REDIRECT_KEYS = ("url", "target", "redirect", "redirect_url", "redirecturl", "destination", "dest", "u", "q")
JOB_PATHS = ("/jobs/view/", "/comm/jobs/view/", "/viewjob", "/rc/clk", "/pagead/clk", "/job-listing/", "/jobs/", "/job/", "/position/", "/oferta-de-trabajo", "jk=")

@dataclass
class ParseStats:
    platform: str
    anchors: int = 0
    candidates: int = 0
    rejected: int = 0
    decisions: list[tuple[str, str, str, str]] | None = None

    def __post_init__(self) -> None:
        if self.decisions is None:
            self.decisions = []

def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()

def _decode(value: str | None) -> str:
    result: list[str] = []
    for content, charset in decode_header(value or ""):
        result.append(content.decode(charset or "utf-8", errors="replace") if isinstance(content, bytes) else str(content))
    return "".join(result).strip()

def _message_bodies(message: Message) -> tuple[str, str]:
    """Recursively collect HTML and plain bodies; decoding transfer encoding and charset."""
    html_parts: list[str] = []
    text_parts: list[str] = []
    parts = message.walk() if message.is_multipart() else (message,)
    for part in parts:
        if part.is_multipart() or "attachment" in str(part.get("Content-Disposition", "")).lower():
            continue
        content_type = part.get_content_type()
        if content_type not in {"text/html", "text/plain"}:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        decoded = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        (html_parts if content_type == "text/html" else text_parts).append(decoded)
    return "\n".join(html_parts), "\n".join(text_parts)

def _unwrap_url(value: str) -> tuple[str, bool]:
    current = html.unescape(value.strip())
    wrapped = False
    for _ in range(MAX_UNWRAP):
        decoded = html.unescape(unquote(current))
        try:
            query = parse_qs(urlsplit(decoded).query)
        except ValueError:
            break
        nested = next((query[key][0] for key in REDIRECT_KEYS if query.get(key)), "")
        nested = html.unescape(unquote(nested))
        if not nested.startswith(("http://", "https://")) or nested == current:
            current = decoded
            break
        current, wrapped = nested, True
    return current, wrapped

def _platform(*values: str) -> str:
    combined = " ".join(values).lower()
    return next((label for marker, label in PLATFORMS if marker in combined), "Other")

def _safe_subject(subject: str) -> str:
    return re.sub(r"[\w.+-]+@[\w.-]+", "[email]", _text(subject))[:180]

def _is_job_alert(sender: str, subject: str, visible_body: str) -> bool:
    """Classify mail before counting or parsing it as a job alert."""
    header = f"{sender} {subject}".lower()
    searchable = f"{header} {visible_body.lower()}"
    security_sender = any(marker in header for marker in ("accounts.google.com", "account-security-noreply", "microsoft account team"))
    security_message = security_sender or any(hint in searchable for hint in SECURITY_ALERT_HINTS)
    return not security_message and any(hint in searchable for hint in ALERT_HINTS)

def _safe_path(url: str) -> tuple[str, str]:
    try:
        parts = urlsplit(url)
        host = parts.netloc.lower().removeprefix("www.")
        path = re.sub(r"(?<=/)[A-Za-z0-9_-]{18,}(?=/|$)", "...", parts.path)
        return host, path[:140] or "/"
    except ValueError:
        return "invalid", "/"

def _title_from_container(anchor: Tag) -> tuple[str, str]:
    label = _text(anchor.get_text(" ", strip=True))
    if label and label.lower() not in GENERIC_ACTIONS and label.lower() not in NAVIGATION_TEXT and 4 <= len(label) <= 180:
        return label, label
    for container in list(anchor.parents)[:5]:
        if not isinstance(container, Tag):
            continue
        heading = container.find(["h1", "h2", "h3", "h4", "strong", "b"])
        if heading:
            candidate = _text(heading.get_text(" ", strip=True))
            if 4 <= len(candidate) <= 180 and candidate.lower() not in GENERIC_ACTIONS + NAVIGATION_TEXT:
                return candidate, _text(container.get_text(" ", strip=True))[:1800]
    return "", label

def _link_decision(url: str, original_url: str, anchor_text: str, context: str, title: str) -> tuple[bool, str]:
    combined = f"{anchor_text} {context}".lower()
    navigation_value = f"{anchor_text} {url}"
    if any(term in navigation_value.lower() for term in NAVIGATION_TEXT):
        return False, "navigation/footer"
    if not anchor_text and not title:
        return False, "empty anchor"
    if not url.startswith(("http://", "https://")):
        return False, "invalid URL"
    try:
        host = urlsplit(url).netloc.lower()
    except ValueError:
        return False, "invalid URL"
    if not host or urlsplit(url).path in {"", "/"}:
        return False, "homepage"
    known = any(domain in host for domain in JOB_DOMAINS)
    path_job = any(marker in url.lower() for marker in JOB_PATHS)
    original_platform = any(domain in original_url.lower() for domain in JOB_DOMAINS)
    title_signal = bool(title and title.lower() not in GENERIC_ACTIONS and len(title.split()) >= 2)
    context_signal = bool(re.search(r"\b(?:job|vacan(?:cy|te)|position|role|apply|empleo|trabajo|remote)\b", combined, re.I))
    if known and path_job:
        return True, f"{_platform(host)} job URL"
    if (known or original_platform) and title_signal and context_signal:
        return True, "platform link with job context"
    if title_signal and path_job:
        return True, "tracking redirect with job context"
    if not known and not original_platform:
        return False, "unknown domain"
    return False, "no job context"

def _location(context: str) -> str:
    for pattern, label in ((r"remote\s*[-–|]?\s*m[eé]xico|m[eé]xico\s+remote", "Remote - Mexico"), (r"remote\s*[-–|]?\s*latam|latin america", "Remote - LATAM"), (r"worldwide|work from anywhere|candidates worldwide", "Worldwide"), (r"fully remote|100% remote|\bremote\b|home office", "Remote")):
        if re.search(pattern, context, re.I):
            return label
    return ""

def _normalized_job(title: str, context: str, url: str, source: str, received_at: str) -> dict[str, Any]:
    location = _location(context)
    identifier = hashlib.sha256(f"{source}|{title}|{url}".lower().encode()).hexdigest()[:24]
    return {"id": identifier, "title": title, "company": "", "location": location, "description": context, "url": url, "source": f"{source} Alert" if source != "Other" else "Email Alert", "published_at": received_at, "remote": True if location else None, "tags": [], "job_type": ""}

def _parse_html(sender: str, subject: str, received_at: str, body: str) -> tuple[list[dict[str, Any]], ParseStats]:
    soup = BeautifulSoup(body, "html.parser")
    visible = _text(soup.get_text(" ", strip=True))
    anchors = soup.find_all("a", href=True)
    stats = ParseStats(_platform(subject, visible, " ".join(str(a.get("href", "")) for a in anchors)), anchors=len(anchors))
    jobs: list[dict[str, Any]] = []
    for anchor in anchors:
        original = html.unescape(str(anchor.get("href", "")))
        url, wrapped = _unwrap_url(original)
        label = _text(anchor.get_text(" ", strip=True))
        title, context = _title_from_container(anchor)
        accepted, reason = _link_decision(url, original, label, context, title)
        host, path = _safe_path(url)
        if len(stats.decisions or []) < 10:
            stats.decisions.append((label or title or "(empty)", host, path, ("accepted: " if accepted else "rejected: ") + ("wrapped " if wrapped and accepted else "") + reason))
        if not accepted:
            stats.rejected += 1
            continue
        stats.candidates += 1
        jobs.append(_normalized_job(title, context, url, _platform(subject, visible, original, url), received_at))
    return jobs, stats

def _parse_plain(sender: str, subject: str, received_at: str, body: str) -> tuple[list[dict[str, Any]], ParseStats]:
    urls = re.findall(r"https?://[^\s<>\"]+", html.unescape(body))
    lines = [_text(line) for line in body.splitlines()]
    stats = ParseStats(_platform(subject, body, " ".join(urls)), anchors=0)
    jobs: list[dict[str, Any]] = []
    for raw_url in urls:
        url, wrapped = _unwrap_url(raw_url.rstrip(".,);]"))
        index = next((i for i, line in enumerate(lines) if raw_url[:30] in line), -1)
        nearby = [line for line in lines[max(0, index - 4):index + 2] if line and not line.startswith("http")]
        title = next((line for line in reversed(nearby) if 4 <= len(line) <= 180 and line.lower() not in GENERIC_ACTIONS + NAVIGATION_TEXT), "")
        context = " ".join(nearby)
        accepted, reason = _link_decision(url, raw_url, title, context, title)
        host, path = _safe_path(url)
        if len(stats.decisions or []) < 10:
            stats.decisions.append((title or "(empty)", host, path, ("accepted: " if accepted else "rejected: ") + ("wrapped " if wrapped and accepted else "") + reason))
        if accepted:
            stats.candidates += 1
            jobs.append(_normalized_job(title, context, url, _platform(subject, body, raw_url, url), received_at))
        else:
            stats.rejected += 1
    return jobs, stats

def parse_email_content(sender: str, subject: str, received_at: str, html_body: str = "", plain_body: str = "") -> tuple[list[dict[str, Any]], ParseStats]:
    jobs, stats = _parse_html(sender, subject, received_at, html_body) if html_body.strip() else _parse_plain(sender, subject, received_at, plain_body)
    unique = list({job["url"]: job for job in jobs}.values())
    return unique, stats

def parse_email_html(sender: str, subject: str, received_at: str, body: str) -> list[dict[str, Any]]:
    """Backward-compatible parser entry point used by tests."""
    return parse_email_content(sender, subject, received_at, html_body=body)[0]

def _debug(subject: str, stats: ParseStats, jobs_count: int) -> None:
    print("[Email Debug]")
    print(f"Platform: {stats.platform}")
    print(f"Subject: {_safe_subject(subject)}")
    print(f"HTML anchors found: {stats.anchors}")
    print(f"Candidate links: {stats.candidates}")
    print(f"Rejected links: {stats.rejected}")
    print(f"Jobs extracted: {jobs_count}")
    for anchor, host, path, decision in stats.decisions or []:
        print(f'Anchor: "{anchor[:100]}"')
        print(f"Host: {host}")
        print(f"Path: {path}")
        print(f"Decision: {decision}")

def fetch_jobs() -> list[dict[str, Any]]:
    """Read recent Gmail alerts without changing their read state."""
    address = os.getenv("JOB_EMAIL_ADDRESS", "").strip()
    app_password = os.getenv("JOB_EMAIL_APP_PASSWORD", "").strip()
    if not address or not app_password:
        print("[Email Alerts] skipped (Gmail not configured)")
        return []
    connection: imaplib.IMAP4_SSL | None = None
    try:
        connection = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        connection.login(address, app_password)
        connection.select("INBOX", readonly=True)
        since = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).strftime("%d-%b-%Y")
        status, data = connection.search(None, "SINCE", since)
        if status != "OK": raise RuntimeError("Gmail search failed")
        ids = (data[0].split() if data and data[0] else [])[-MAX_EMAILS:]
        alert_count = 0
        jobs: list[dict[str, Any]] = []
        for message_id in reversed(ids):
            status, payload = connection.fetch(message_id, "(BODY.PEEK[])")
            if status != "OK" or not payload or not isinstance(payload[0], tuple): continue
            message = email.message_from_bytes(payload[0][1])
            sender, subject = _decode(message.get("From")), _decode(message.get("Subject"))
            html_body, plain_body = _message_bodies(message)
            visible_body = f"{BeautifulSoup(html_body, 'html.parser').get_text(' ', strip=True)} {plain_body}"
            if not _is_job_alert(sender, subject, visible_body): continue
            alert_count += 1
            extracted, stats = parse_email_content(sender, subject, _decode(message.get("Date")), html_body, plain_body)
            _debug(subject, stats, len(extracted))
            jobs.extend(extracted)
        jobs = list({job["url"]: job for job in jobs}.values())
        print(f"[Email Alerts] {alert_count} alert emails, {len(jobs)} jobs extracted")
        return jobs
    except Exception as exc:
        print(f"[Email Alerts] Gmail IMAP error: {exc}")
        return []
    finally:
        if connection is not None:
            try: connection.logout()
            except Exception: pass
