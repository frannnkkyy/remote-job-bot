"""Telegram Bot API delivery."""

import html
import os
from typing import Any

import requests

TELEGRAM_API = "https://api.telegram.org"
TIMEOUT = 25


def validate_config() -> tuple[str, str]:
    """Read and validate required Telegram environment variables."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    missing = [name for name, value in (("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_CHAT_ID", chat_id)) if not value]
    if missing:
        raise RuntimeError(f"Missing required environment variable(s): {', '.join(missing)}")
    return token, chat_id


def format_job(job: dict[str, Any], score: int, reasons: list[str]) -> str:
    """Build a safe Telegram HTML message."""
    category = str(job.get("_category") or ("EXCELLENT" if score >= 80 else "GOOD"))
    color = {"EXCELLENT": "🔥", "GOOD": "🟢", "STRETCH": "🟡"}.get(category, "🟡")

    def esc(value: Any) -> str:
        return html.escape(str(value or ""), quote=True)

    positives = "\n".join(f"• {esc(reason)}" for reason in reasons)
    weaknesses = [str(item) for item in (job.get("_weaknesses") or [])]
    weakness_block = ""
    if weaknesses:
        weakness_block = "\n\n⚠️ <b>Punto débil:</b>\n" + "\n".join(f"• {esc(item)}" for item in weaknesses)
    details = []
    if any("junior" in reason.lower() or "entry" in reason.lower() for reason in reasons):
        details.append("🧑‍💻 Entry Level")
    skills = [str(item) for item in (job.get("_skills") or [])]
    if skills:
        details.append("🛠 " + " · ".join(esc(item) for item in skills))
    if job.get("_experience"):
        details.append("💼 " + esc(job.get("_experience")))
    details_block = ("\n" + "\n".join(details)) if details else ""
    url = esc(job.get("url"))
    fit_heading = "¿Por qué podría valer la pena?" if category == "STRETCH" else "¿Por qué encaja?"
    return (
        f"{color} <b>{score}% — {esc(category)}</b>\n\n"
        f"<b>{esc(job.get('title'))}</b>\n🏢 {esc(job.get('company'))}\n\n"
        f"🌎 {esc(job.get('location') or 'Remote')}{details_block}\n"
        f"🔎 Fuente: {esc(job.get('source'))}\n\n"
        f"<b>{fit_heading}</b>\n{positives}{weakness_block}\n\n"
        f"🔗 <b>Aplicar:</b>\n<a href=\"{url}\">{url}</a>"
    )


def send_job(job: dict[str, Any], score: int, reasons: list[str]) -> bool:
    """Send one job; return True only after Telegram confirms success."""
    return send_message(format_job(job, score, reasons), parse_mode="HTML")


def send_message(text: str, parse_mode: str | None = None) -> bool:
    """Send a text message through the configured Telegram bot."""
    token, chat_id = validate_config()
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        response = requests.post(
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            json=payload,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return bool(response.json().get("ok"))
    except requests.RequestException:
        raise RuntimeError("Telegram API request failed") from None
