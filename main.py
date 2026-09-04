"""Fetch, filter, deduplicate, and deliver remote job alerts."""

import hashlib
import json
import os
import re
from collections import Counter

from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from filters import MIN_SCORE, JobAssessment, assess_job, clean_html
from sources import SOURCES
from sources.email_alerts import fetch_jobs as fetch_email_alert_jobs
from telegram_bot import send_job, send_message, validate_config


BASE_DIR = Path(__file__).resolve().parent
SEEN_JOBS_PATH = BASE_DIR / "data" / "seen_jobs.json"
MANUAL_TEST_MESSAGE = "🤖 Remote Job Bot activo\n✅ GitHub Actions funcionando\n🔎 Buscando nuevas vacantes..."


# ============================================================
# FUENTES
# ============================================================

# Conservamos todas las fuentes que ya tienes:
#
# - Remotive
# - RemoteOK
# - Arbeitnow
#
# Y agregamos las alertas de correo:
#
# - LinkedIn
# - Indeed
# - Computrabajo
# - Glassdoor
#
# según las alertas que lleguen a Outlook.

ALL_SOURCES = [
    *SOURCES,
    ("Email Alerts", fetch_email_alert_jobs),
]


# ============================================================
# IDENTIFICADORES
# ============================================================

def stable_id(job: dict[str, Any]) -> str:
    """Return a stable identifier for a job."""

    canonical = canonical_url(str(job.get("url", "")))
    if canonical:
        return "url:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    raw = "|".join(
        str(
            job.get(
                key,
                "",
            )
        )
        .strip()
        .lower()
        for key in (
            "source",
            "company",
            "title",
            "url",
        )
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def canonical_url(value: str) -> str:
    """Normalize a URL and discard common tracking parameters."""
    try:
        parts = urlsplit(value.strip())
        if not parts.scheme or not parts.netloc:
            return ""
        tracking_keys = {"trk", "trackingid", "gclid", "fbclid"}
        query = [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True) if not key.lower().startswith("utm_") and key.lower() not in tracking_keys]
        path = re.sub(r"/+$", "", parts.path) or "/"
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))
    except ValueError:
        return ""


def duplicate_fingerprint(
    job: dict[str, Any],
) -> str:
    """
    Generate a fingerprint independent of the source.

    This helps avoid receiving the same vacancy if it appears
    in RemoteOK and later arrives through LinkedIn, for example.
    """

    company = clean_html(
        job.get(
            "company",
            "",
        )
    ).lower()

    title = clean_html(
        job.get(
            "title",
            "",
        )
    ).lower()

    # Normalize common differences.
    company = " ".join(
        company.split()
    )

    title = " ".join(
        title.split()
    )

    if not company:
        return ""
    raw = f"{company}|{title}"

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def source_priority(job: dict[str, Any]) -> int:
    """Prefer direct ATS links over boards/alerts and aggregators."""
    source = str(job.get("source", "")).lower()
    if source in {"greenhouse", "lever", "ashby"}:
        return 3
    if source == "jobicy" or "aggregator" in source:
        return 0
    if "alert" in source:
        return 1
    return 2


# ============================================================
# SEEN JOBS
# ============================================================

def load_seen_jobs() -> set[str]:
    """Load sent identifiers, recovering safely from invalid state."""

    try:

        data = json.loads(
            SEEN_JOBS_PATH.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            data,
            list,
        ):

            raise ValueError(
                "seen_jobs.json must contain a JSON array"
            )

        return {
            str(item)
            for item in data
        }

    except FileNotFoundError:

        return set()

    except (
        json.JSONDecodeError,
        ValueError,
    ) as exc:

        print(
            f"[Warning] Could not read seen jobs: {exc}"
        )

        return set()


def save_seen_jobs(
    seen: set[str],
) -> None:
    """Persist sent identifiers deterministically and atomically."""

    SEEN_JOBS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = (
        SEEN_JOBS_PATH.with_suffix(
            ".tmp"
        )
    )

    temporary.write_text(
        json.dumps(
            sorted(seen),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary.replace(
        SEEN_JOBS_PATH
    )


# ============================================================
# FETCH
# ============================================================

def fetch_all_jobs() -> list[dict[str, Any]]:
    """
    Fetch each source independently.

    If one API or Outlook fails, all other sources continue.
    """

    jobs: list[dict[str, Any]] = []

    for name, fetcher in ALL_SOURCES:

        try:

            fetched = fetcher()

            if not isinstance(
                fetched,
                list,
            ):

                print(
                    f"[{name}] Invalid response"
                )

                continue

            print(
                f"[{name}] {len(fetched)} jobs fetched"
            )

            jobs.extend(
                fetched
            )

        except Exception as exc:

            print(
                f"[{name}] Failed: {exc}"
            )

    print(
        f"[Total] {len(jobs)} jobs fetched"
    )

    return jobs


# ============================================================
# NORMALIZATION / DEDUPLICATION
# ============================================================

def normalize_and_deduplicate(
    jobs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Normalize all source formats and remove duplicates.

    Deduplicates both:
    - exact source IDs
    - similar company + title + location
    """

    unique_by_id: dict[str, dict[str, Any]] = {}

    seen_fingerprints: set[str] = set()
    fingerprint_ids: dict[str, str] = {}

    fields = (
        "id",
        "title",
        "company",
        "location",
        "description",
        "url",
        "source",
        "published_at",
        "job_type",
    )

    for job in jobs:

        normalized = {
            key: str(
                job.get(
                    key,
                    "",
                )
                or ""
            ).strip()
            for key in fields
        }

        remote_value = job.get("remote")
        normalized["remote"] = remote_value if isinstance(remote_value, bool) else None
        normalized["tags"] = [str(tag).strip() for tag in (job.get("tags") or []) if str(tag).strip()]

        normalized[
            "description"
        ] = clean_html(
            normalized[
                "description"
            ]
        )

        normalized[
            "title"
        ] = clean_html(
            normalized[
                "title"
            ]
        )

        normalized[
            "company"
        ] = clean_html(
            normalized[
                "company"
            ]
        )

        normalized[
            "location"
        ] = clean_html(
            normalized[
                "location"
            ]
        )

        # A job without these fields is not useful.
        if not normalized["title"]:
            continue

        if not normalized["url"]:
            continue

        identifier = stable_id(
            normalized
        )

        fingerprint = (
            duplicate_fingerprint(
                normalized
            )
        )

        # Exact duplicate.
        if identifier in unique_by_id:
            if source_priority(normalized) > source_priority(unique_by_id[identifier]):
                unique_by_id[identifier] = normalized
            continue

        # Same company/title/location from another source.
        if fingerprint and fingerprint in seen_fingerprints:
            existing_id = fingerprint_ids[fingerprint]
            if source_priority(normalized) > source_priority(unique_by_id[existing_id]):
                del unique_by_id[existing_id]
                unique_by_id[identifier] = normalized
                fingerprint_ids[fingerprint] = identifier
            continue

        unique_by_id[
            identifier
        ] = normalized

        if fingerprint:
            seen_fingerprints.add(fingerprint)
            fingerprint_ids[fingerprint] = identifier

    result = list(
        unique_by_id.values()
    )

    print(
        f"[Unique] {len(result)} jobs"
    )

    return result


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """Run a complete polling and delivery cycle."""

    # Check Telegram configuration first.
    validate_config()

    if os.getenv("MANUAL_RUN", "").strip().lower() == "true":
        print("[Telegram Test] manual run detected")
        if not send_message(MANUAL_TEST_MESSAGE):
            raise RuntimeError("[Telegram Test] Telegram did not accept the test message")
        print("[Telegram Test] test message sent")
    else:
        print("[Telegram Test] skipped (scheduled run)")

    seen = load_seen_jobs()

    raw_jobs = fetch_all_jobs()

    jobs = normalize_and_deduplicate(
        raw_jobs
    )

    relevant: list[tuple[int, dict[str, Any], list[str], str]] = []
    scored: list[tuple[JobAssessment, dict[str, Any]]] = []
    rejected: Counter[str] = Counter()
    remote_compatible = 0

    for job in jobs:

        try:

            assessment = assess_job(job)

        except Exception as exc:

            print(
                "[Filter] Failed to score "
                f"{job.get('title', 'Unknown')}: "
                f"{exc}"
            )

            continue

        if assessment.rejection:
            rejected[assessment.rejection] += 1
            if assessment.rejection in {"irrelevant role", "experience", "below score"}:
                remote_compatible += 1
            continue

        remote_compatible += 1
        scored.append((assessment, job))
        identifier = stable_id(job)

        if assessment.category == "REJECT" or assessment.score < MIN_SCORE:
            continue

        if identifier in seen:
            continue

        relevant.append(
            (
                assessment.score,
                {**job, "_category": assessment.category, "_weaknesses": assessment.weaknesses, "_skills": assessment.skills or [], "_experience": assessment.experience},
                assessment.reasons,
                identifier,
            )
        )

    relevant.sort(key=lambda item: item[0], reverse=True)
    accepted = sum(result.category != "REJECT" and result.score >= MIN_SCORE for result, _ in scored)
    below = len(jobs) - accepted - rejected["hybrid/onsite"] - rejected["geo restriction"] - rejected["senior"] - rejected["not remote"]
    print(f"[Remote compatible] {remote_compatible}")
    print(f"[Rejected hybrid/onsite] {rejected['hybrid/onsite']}")
    print(f"[Rejected geo restriction] {rejected['geo restriction']}")
    print(f"[Rejected senior] {rejected['senior']}")
    print(f"[Rejected not remote] {rejected['not remote']}")
    print(f"[Below score] {below}")
    print(f"[Accepted] {accepted}")

    all_scores = [result.score for result, _ in scored]
    all_scores.extend([0] * (len(jobs) - len(scored)))
    buckets = ((0, 19), (20, 39), (40, 59), (60, 79), (80, 100))
    for low, high in buckets:
        count = sum(low <= score <= high for score in all_scores)
        print(f"Score {low}-{high}: {count}")

    print("[Preview - Best matches for candidate]")
    preview = [(result, job) for result, job in scored if result.category != "REJECT"]
    for result, job in sorted(preview, key=lambda item: item[0].score, reverse=True)[:15]:
        print(f"{result.score} | {result.category} | {job.get('title', '')} | {job.get('company', '')} | {job.get('location', '')}")
    print(f"[Filter] {len(relevant)} new relevant jobs")

    sent = 0

    for (
        score,
        job,
        reasons,
        identifier,
    ) in relevant:

        try:

            success = send_job(
                job,
                score,
                reasons,
            )

            # IMPORTANT:
            # only mark the job as seen after Telegram
            # confirms it was successfully sent.
            if success:

                seen.add(
                    identifier
                )

                save_seen_jobs(
                    seen
                )

                sent += 1

        except Exception as exc:

            print(
                "[Telegram] Failed to send "
                f"{identifier}: {exc}"
            )

    print(
        f"[New] {sent} new jobs sent"
    )


if __name__ == "__main__":
    main()
