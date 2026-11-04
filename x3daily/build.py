"""Orchestration: `python -m x3daily collect-news` and `python -m x3daily build`."""
import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime

from . import brief, calendar_ics, epub, gold, news, opds, quotes, weather
from .config import DEFAULT_BASE_URL, GOLD_CSV, PRIVATE_DIR, QUOTES_FILE, SITE_DIR, VN, WORK_DIR

log = logging.getLogger("x3daily")


def collect_news(now):
    WORK_DIR.mkdir(exist_ok=True)
    items = news.collect(now)
    news.save_items(WORK_DIR / "news.json", items)
    (WORK_DIR / "news_raw.json").write_text(news.dump_raw(items), encoding="utf-8")
    log.info("news: %d items collected", len(items))


def _load_news(now):
    path = WORK_DIR / "news.json"
    try:
        items = news.load_items(path) if path.exists() else news.collect(now)
    except Exception as e:
        log.warning("news: skipped (%s)", type(e).__name__)
        return []
    vi = None
    vi_path = WORK_DIR / "news_vi.json"
    if vi_path.exists():
        try:
            vi = json.loads(vi_path.read_text(encoding="utf-8"))
        except Exception:
            log.warning("news: news_vi.json is not valid JSON, using original titles")
    return list(zip(items, *zip(*news.apply_vi(items, vi)))) if items else []


def _run_x3book(raw, out):
    """tune + check. Returns True only when both pass."""
    for args in (["tune", str(raw), str(out)], ["check", str(out)]):
        r = subprocess.run([sys.executable, "-m", "x3book", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            log.warning("x3book %s failed (exit %d): %s", args[0], r.returncode, (r.stderr or r.stdout)[-300:])
            return False
    return True


def build(now):
    today = now.date()
    base_url = os.environ.get("PAGES_BASE_URL", DEFAULT_BASE_URL)
    if not base_url.endswith("/"):
        base_url += "/"
    for d in (SITE_DIR, PRIVATE_DIR):
        if d.exists():
            shutil.rmtree(d)
    SITE_DIR.mkdir()
    WORK_DIR.mkdir(exist_ok=True)

    wx = weather.fetch_all()

    price, hist, block = None, gold.load_history(GOLD_CSV), None
    try:
        price = gold.fetch_price()
        hist[today] = price
        gold.save_history(GOLD_CSV, hist)
        block = gold.gold_block(price, hist, today)
    except Exception as e:
        log.warning("gold: skipped (%s)", type(e).__name__)

    items = _load_news(now)
    quote = quotes.pick(quotes.load(QUOTES_FILE), today)

    full = brief.build_brief(now, wx, block, [t for _, t, _ in items], quote)
    public = brief.public_version(full)
    (SITE_DIR / "brief.json").write_bytes(brief.fit(public))

    ics_url = os.environ.get("GCAL_ICS_URL", "").strip()
    if ics_url:
        events = calendar_ics.fetch_events(ics_url, today)
        full = brief.build_brief(now, wx, block, [t for _, t, _ in items], quote, events)
        # Written even with no events so the gist never keeps yesterday's calendar.
        PRIVATE_DIR.mkdir()
        (PRIVATE_DIR / "brief.json").write_bytes(brief.fit(full))
        log.info("calendar: %d events written to the private brief", len(events))

    build_epub(now, wx, price, hist, block, items, quote, base_url)
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")
    (SITE_DIR / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>x3-daily</title>'
        '<p><a href="brief.json">brief.json</a> | <a href="opds.xml">opds.xml</a></p>\n', encoding="utf-8")


def build_epub(now, wx, price, hist, block, items, quote, base_url):
    today = now.date()
    raw = WORK_DIR / "raw.epub"
    name = opds.epub_name(today)
    try:
        epub.build(raw, today, wx, price, hist, block or {}, items, quote)
        if _run_x3book(raw, SITE_DIR / name):
            log.info("epub: %s written", name)
        else:
            log.warning("epub: today's issue skipped")
    except Exception as e:
        log.warning("epub: today's issue skipped (%s)", type(e).__name__)
    opds.restore_previous(base_url, SITE_DIR)
    names = opds.prune(SITE_DIR)
    (SITE_DIR / "opds.xml").write_text(opds.build_feed(base_url, SITE_DIR, names, now), encoding="utf-8")
    log.info("opds: %d issues", len(names))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="x3daily")
    ap.add_argument("command", choices=["collect-news", "build"])
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    now = datetime.now(VN)
    {"collect-news": collect_news, "build": build}[args.command](now)
