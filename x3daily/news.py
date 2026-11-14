"""News sections from RSS 2.0 / Atom feeds (stdlib xml.etree only)."""
import html
import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from . import net
from .config import NEWS_MAX, NEWS_SECTIONS, NEWS_SUMMARY_MAX, NEWS_TITLE_MAX, NEWS_WINDOW_HOURS
from .vi import truncate

log = logging.getLogger(__name__)

ATOM = "{http://www.w3.org/2005/Atom}"

# Promotional / event-sales posts that feeds mix in with news. The sleep screen only fits
# ~3 headlines, so one ad costs a third of it. Bare "event" or "conference" is deliberately
# absent: real news uses them too.
PROMO_KEYWORDS = (
    "TechCrunch Disrupt", "TC Disrupt", "StrictlyVC", "TC Sessions", "TC All Stage",
    "tickets", "save $", "save up to", "register now", "early bird", "early-bird",
    "sponsored", "partner content", "webinar", "giveaway", "% off",
    "promo code", "discount code",
)


def _keyword_re(words):
    # Boundaries only on edges that are word characters, so "save $" still matches
    # "save $200" and "% off" matches "20% off". A hyphen before the keyword blocks
    # the match so "state-sponsored hackers" stays news.
    parts = []
    for w in words:
        pat = re.escape(w).replace(r"\ ", r"\s+")
        if re.match(r"\w", w):
            pat = r"(?<![\w-])" + pat
        if re.search(r"\w$", w):
            pat += r"(?!\w)"
        parts.append(pat)
    return re.compile("|".join(parts), re.IGNORECASE)


_PROMO_RE = _keyword_re(PROMO_KEYWORDS)


def is_promo(item):
    return bool(_PROMO_RE.search(item.title) or _PROMO_RE.search(item.summary))


@dataclass
class Item:
    title: str
    link: str
    published: datetime  # timezone-aware
    source: str
    summary: str = ""
    section: str = NEWS_SECTIONS[0]["file"]


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
    """Newest first, only items from the last `window_hours`, without ads or duplicate links/titles."""
    cutoff = now - timedelta(hours=window_hours)
    fresh = []
    for i in items:
        if not cutoff <= i.published <= now + timedelta(hours=1):
            continue
        if is_promo(i):
            log.info("news: promo dropped: %s", i.title)
            continue
        fresh.append(i)
    fresh.sort(key=lambda i: i.published, reverse=True)
    chosen = []
    for it in fresh:
        if any(it.link == c.link or _similar(it.title, c.title) for c in chosen):
            continue
        chosen.append(it)
        if len(chosen) == limit:
            break
    return chosen


def is_vietnamese(item):
    return any(s["lang"] == "vi" for s in NEWS_SECTIONS if s["file"] == item.section)


def collect(now):
    """Fetch every configured feed, section by section; a failing feed is skipped."""
    chosen = []
    for sec in NEWS_SECTIONS:
        items = []
        for f in sec["feeds"]:
            try:
                got = parse_feed(net.get(f["url"]), f["source"])
            except Exception as e:
                log.warning("news %s: skipped (%s)", f["source"], type(e).__name__)
                continue
            if f.get("date_only"):
                # A date without a time parses as 00:00 UTC. Treat it as the end of that day so
                # each post lands in exactly one issue (the next one), never in two or none.
                got = [replace(i, published=i.published + timedelta(days=1)) for i in got]
            items += got
        for it in select(items, now, sec["max"]):
            it.section = sec["file"]
            chosen.append(it)
    return chosen


def dump_raw(items):
    """JSON handed to the optional translation step: index + English text only.
    Vietnamese items are left out but keep their index in `items`."""
    return json.dumps([{"i": n, "title": it.title, "summary": it.summary, "source": it.source}
                       for n, it in enumerate(items) if not is_vietnamese(it)], ensure_ascii=False, indent=1)


def save_items(path, items):
    data = [dict(asdict(it), published=it.published.isoformat()) for it in items]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_items(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Item(d["title"], d["link"], datetime.fromisoformat(d["published"]), d["source"], d.get("summary", ""),
                 d.get("section", NEWS_SECTIONS[0]["file"])) for d in data]


def apply_vi(items, vi_data):
    """Merge optional translation output [{"i": int, "t": str, "s": str}] into items as
    (title, summary, translated) triples.

    The output (Gemini or Claude) is untrusted data: wrong types are ignored, lengths are capped,
    and a bad entry falls back to the original English text with translated=False.
    """
    by_i = {}
    if isinstance(vi_data, list):
        for e in vi_data:
            if isinstance(e, dict) and isinstance(e.get("i"), int) and not isinstance(e.get("i"), bool):
                by_i[e["i"]] = e
    out = []
    for n, it in enumerate(items):
        if is_vietnamese(it):
            out.append((truncate(_clean(it.title), NEWS_TITLE_MAX), truncate(_clean(it.summary), NEWS_SUMMARY_MAX), True))
            continue
        e = by_i.get(n, {})
        ok_t = isinstance(e.get("t"), str) and bool(e["t"].strip())
        ok_s = isinstance(e.get("s"), str) and bool(e["s"].strip())
        t = e["t"] if ok_t else it.title
        s = e["s"] if ok_s else it.summary
        translated = ok_t and (ok_s or not it.summary)
        out.append((truncate(_clean(t), NEWS_TITLE_MAX), truncate(_clean(s), NEWS_SUMMARY_MAX), translated))
    return out


def _clean(s):
    return re.sub(r"[\x00-\x1f\x7f]", " ", s)
