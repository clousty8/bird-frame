"""Formatage des instants UTC au format exact du contrat (api-contract.md §1.3) :
`YYYY-MM-DDTHH:MM:SSZ`, secondes, sans fraction, suffixe `Z`."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now_str() -> str:
    return format_instant(datetime.now(UTC))


def format_instant(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def unix_to_instant_str(unix_seconds: int) -> str:
    return format_instant(datetime.fromtimestamp(unix_seconds, tz=UTC))


def parse_instant(value: str) -> datetime:
    """Parse un instant `YYYY-MM-DDTHH:MM:SSZ` (ou avec décalage explicite `+02:00`)."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)
