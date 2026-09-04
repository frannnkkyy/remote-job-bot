"""Public job-source adapters."""

from collections.abc import Callable
from typing import Any

from .arbeitnow import fetch_jobs as fetch_arbeitnow
from .remoteok import fetch_jobs as fetch_remoteok
from .remotive import fetch_jobs as fetch_remotive
from .greenhouse import fetch_jobs as fetch_greenhouse
from .lever import fetch_jobs as fetch_lever
from .ashby import fetch_jobs as fetch_ashby
from .aggregator import fetch_jobs as fetch_aggregator

SourceFetcher = Callable[[], list[dict[str, Any]]]

SOURCES: tuple[tuple[str, SourceFetcher], ...] = (
    ("Remotive", fetch_remotive),
    ("RemoteOK", fetch_remoteok),
    ("Arbeitnow", fetch_arbeitnow),
    ("Greenhouse", fetch_greenhouse),
    ("Lever", fetch_lever),
    ("Ashby", fetch_ashby),
    ("Aggregator", fetch_aggregator),
)
