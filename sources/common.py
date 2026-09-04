"""Small normalization helpers shared by ATS adapters."""
import re
from typing import Any

def text(value: Any) -> str:
    return "" if value is None else str(value).strip()

def remote_hint(location: str, *extra: str) -> bool | None:
    value = " ".join((location, *extra)).lower()
    return True if re.search(r"\b(?:remote|worldwide|anywhere|latam|latin america|work from home)\b", value) else None
