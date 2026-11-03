"""Today's events from a Google Calendar secret ICS link (stdlib parser).

Limits: RRULE / EXDATE / RECURRENCE-ID are not expanded. A recurring event shows
only when its first DTSTART falls on the requested day.
Nothing here logs event text or the URL.
"""
import logging
import re
from datetime import date, datetime, timedelta, timezone

from . import net
from .config import EVENT_TITLE_MAX, EVENTS_MAX, VN
from .vi import truncate

log = logging.getLogger(__name__)


def _unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def _unescape(s):
    return re.sub(r"\\([nN,;\\])", lambda m: " " if m.group(1) in "nN" else m.group(1), s)


def _props(vevent_lines):
    props = {}
    for line in vevent_lines:
        name_part, sep, value = line.partition(":")
        if not sep:
            continue
        name, *params = name_part.split(";")
        pd = {}
        for p in params:
            k, _, v = p.partition("=")
            pd[k.upper()] = v.strip('"')
        props.setdefault(name.upper(), (pd, value))
    return props


def _tz(tzid):
    if not tzid:
        return VN
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tzid)
    except Exception:  # unknown zone or no tz database (Windows): assume Vietnam time
        return VN


def _parse_dt(pd, value):
    """Return (datetime in VN, is_all_day) or None."""
    value = value.strip()
    if pd.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        d = datetime.strptime(value[:8], "%Y%m%d")
        return d.replace(tzinfo=VN), True
    m = re.fullmatch(r"(\d{8}T\d{6})(Z?)", value)
    if not m:
        return None
    naive = datetime.strptime(m.group(1), "%Y%m%dT%H%M%S")
    tz = timezone.utc if m.group(2) else _tz(pd.get("TZID"))
    return naive.replace(tzinfo=tz).astimezone(VN), False


def events_for_day(ics_text, day):
    """List of {"time": "HH:MM" | "Cả ngày", "t": title} for `day` (a date in Vietnam time)."""
    lines = _unfold(ics_text)
    blocks, cur = [], None
    for ln in lines:
        if ln.strip().upper() == "BEGIN:VEVENT":
            cur = []
        elif ln.strip().upper() == "END:VEVENT":
            if cur is not None:
                blocks.append(cur)
            cur = None
        elif cur is not None:
            cur.append(ln)
    found = []
    for b in blocks:
        p = _props(b)
        if "DTSTART" not in p or p.get("STATUS", ({}, ""))[1].strip().upper() == "CANCELLED":
            continue
        start = _parse_dt(*p["DTSTART"])
        if not start:
            continue
        start_dt, all_day = start
        end = _parse_dt(*p["DTEND"]) if "DTEND" in p else None
        if all_day:
            first = start_dt.date()
            last = (end[0].date() - timedelta(days=1)) if end else first  # DTEND is exclusive
            last = max(first, last)
            if not first <= day <= last:
                continue
            key, label = "", "Cả ngày"
        else:
            if start_dt.date() != day:
                continue
            key, label = start_dt.strftime("%H:%M"), start_dt.strftime("%H:%M")
        title = truncate(_unescape(p.get("SUMMARY", ({}, ""))[1]) or "(Không tiêu đề)", EVENT_TITLE_MAX)
        found.append((key, {"time": label, "t": title}))
    found.sort(key=lambda x: x[0])  # all-day first, then by time
    return [e for _, e in found][:EVENTS_MAX]


def fetch_events(url, day):
    """Fetch and parse the ICS. Returns [] on any failure; logs only the error type."""
    try:
        text = net.get(url).decode("utf-8", errors="replace")
        return events_for_day(text, day)
    except Exception as e:
        log.warning("calendar: skipped (%s)", type(e).__name__)
        return []
