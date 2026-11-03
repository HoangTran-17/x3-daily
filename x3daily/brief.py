"""Assemble brief.json (schema v1)."""
import json

from .config import BRIEF_MAX_BYTES


def build_brief(now, weather=None, gold=None, news_titles=None, quote=None, events=None):
    """Only keys with data are written; the firmware hides cells whose field is missing."""
    b = {"v": 1, "generated": now.isoformat(timespec="seconds")}
    if weather:
        b["weather"] = [{"city": w["city"], "now": w["now"], "range": w["range"]} for w in weather]
    if gold:
        b["gold"] = gold
    if news_titles:
        b["news"] = [{"t": t} for t in news_titles]
    if events:
        b["events"] = events
    if quote:
        b["quote"] = quote
    return b


def dumps(brief):
    return json.dumps(brief, ensure_ascii=False, separators=(",", ":"))


def fit(brief, limit=BRIEF_MAX_BYTES):
    """Return JSON bytes <= limit, dropping trailing events, then trailing news, until it fits."""
    b = dict(brief)
    while True:
        data = dumps(b).encode("utf-8")
        if len(data) <= limit:
            return data
        if b.get("news") and len(b["news"]) >= len(b.get("events", [])):
            b["news"] = b["news"][:-1] or None
            if not b["news"]:
                del b["news"]
        elif b.get("events"):
            b["events"] = b["events"][:-1]
            if not b["events"]:
                del b["events"]
        else:
            raise ValueError("brief.json cannot fit in %d bytes" % limit)


def public_version(brief):
    """Copy of the brief without any calendar data."""
    return {k: v for k, v in brief.items() if k != "events"}

