"""AI news from RSS 2.0 / Atom feeds (stdlib xml.etree only)."""
import html
import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from . import net
from .config import NEWS_FEEDS, NEWS_MAX, NEWS_SUMMARY_MAX, NEWS_TITLE_MAX, NEWS_WINDOW_HOURS
from .vi import truncate

log = logging.getLogger(__name__)

ATOM = "{http://www.w3.org/2005/Atom}"


@dataclass
class Item:
    title: str
    link: str
    published: datetime  # timezone-aware
    source: str
    summary: str = ""


def _text(el):
    return "".join(el.itertext()).strip() if el is not None else ""


def _strip_html(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def _parse_date(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s)
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def parse_feed(raw, source):
    """Parse RSS 2.0 or Atom bytes into Items. Entries without title, link or date are dropped."""
    root = ET.fromstring(raw)
    items = []
    if root.tag == ATOM + "feed":
        for e in root.iter(ATOM + "entry"):
            link = ""
            for l in e.findall(ATOM + "link"):
                if l.get("rel", "alternate") == "alternate":
                    link = l.get("href", "")
                    break
            date = _parse_date(_text(e.find(ATOM + "published")) or _text(e.find(ATOM + "updated")))
            summ = _text(e.find(ATOM + "summary")) or _text(e.find(ATOM + "content"))
            items.append((_text(e.find(ATOM + "title")), link, date, summ))
    else:
        for e in root.iter("item"):
            date = _parse_date(_text(e.find("pubDate")) or _text(e.find("{http://purl.org/dc/elements/1.1/}date")))
            items.append((_text(e.find("title")), _text(e.find("link")), date, _text(e.find("description"))))
    out = []
    for title, link, date, summ in items:
        title = _strip_html(title)
        if title and link.startswith(("http://", "https://")) and date:
            out.append(Item(title, link, date, source, truncate(_strip_html(summ), NEWS_SUMMARY_MAX)))
    return out


def _norm(title):
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _similar(a, b):
    wa, wb = set(_norm(a).split()), set(_norm(b).split())
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= 0.7


def select(items, now, limit=NEWS_MAX, window_hours=NEWS_WINDOW_HOURS):
    """Newest first, only items from the last `window_hours`, without duplicate links or titles."""
    cutoff = now - timedelta(hours=window_hours)
    fresh = sorted((i for i in items if cutoff <= i.published <= now + timedelta(hours=1)),
                   key=lambda i: i.published, reverse=True)
    chosen = []
    for it in fresh:
        if any(it.link == c.link or _similar(it.title, c.title) for c in chosen):
            continue
        chosen.append(it)
        if len(chosen) == limit:
            break
    return chosen


def collect(now):
    """Fetch every configured feed; a failing feed is skipped."""
    items = []
    for f in NEWS_FEEDS:
        try:
            items += parse_feed(net.get(f["url"]), f["source"])
        except Exception as e:
            log.warning("news %s: skipped (%s)", f["source"], type(e).__name__)
    return select(items, now)


def dump_raw(items):
    """JSON handed to the optional Claude step: index + English text only."""
    return json.dumps([{"i": n, "title": it.title, "summary": it.summary, "source": it.source}
                       for n, it in enumerate(items)], ensure_ascii=False, indent=1)


def save_items(path, items):
    data = [dict(asdict(it), published=it.published.isoformat()) for it in items]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_items(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Item(d["title"], d["link"], datetime.fromisoformat(d["published"]), d["source"], d.get("summary", ""))
            for d in data]


def apply_vi(items, vi_data):
    """Merge optional Claude output [{"i": int, "t": str, "s": str}] into items as (title, summary) pairs.

    The Claude output is untrusted data: wrong types are ignored, lengths are capped,
    and a bad entry falls back to the original English text.
    """
    by_i = {}
    if isinstance(vi_data, list):
        for e in vi_data:
            if isinstance(e, dict) and isinstance(e.get("i"), int) and not isinstance(e.get("i"), bool):
                by_i[e["i"]] = e
    out = []
    for n, it in enumerate(items):
        e = by_i.get(n, {})
        t = e.get("t") if isinstance(e.get("t"), str) and e["t"].strip() else it.title
        s = e.get("s") if isinstance(e.get("s"), str) and e["s"].strip() else it.summary
        out.append((truncate(_clean(t), NEWS_TITLE_MAX), truncate(_clean(s), NEWS_SUMMARY_MAX)))
    return out


def _clean(s):
    return re.sub(r"[\x00-\x1f\x7f]", " ", s)
