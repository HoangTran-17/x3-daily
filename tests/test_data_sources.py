"""Offline tests for number formatting, gold, weather, news, calendar and quotes."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from x3daily import calendar_ics, gold, news, quotes, vi, weather
from x3daily.config import QUOTES_FILE, VN

FX = Path(__file__).parent / "fixtures"


# ---- Vietnamese formatting ----
def test_vietnamese_number_format():
    assert vi.fmt_decimal(145.2) == "145,2"
    assert vi.fmt_decimal(Decimal("134.95")) == "135,0"  # half-up, not banker's rounding
    assert vi.fmt_decimal(7, 1) == "7,0"
    assert vi.fmt_thousands(13490) == "13.490"


def test_percent_change_format():
    assert vi.fmt_percent(0.031) == "+3,1%"
    assert vi.fmt_percent(-0.0214) == "-2,1%"
    assert vi.fmt_percent(0) == "0,0%"
    assert vi.fmt_percent(0.4150) == "+41,5%"


# ---- gold ----
def test_parse_pnj_fixture():
    p = gold.parse_pnj((FX / "pnj.json").read_bytes())
    assert p == gold.Price(buy=13490, sell=13890)
    assert gold.to_million_per_luong(13490) == Decimal("134.9")


def test_parse_pnj_missing_ring_row():
    with pytest.raises(ValueError):
        gold.parse_pnj(b'{"data":[{"masp":"SJC","giaban":1,"giamua":1}]}')


def _hist(today, **days_to_sell):
    return {today - timedelta(days=d): gold.Price(s - 400, s) for d, s in days_to_sell.items()}


def test_gold_block_without_history_has_no_change_fields():
    today = date(2026, 11, 3)
    b = gold.gold_block(gold.Price(13490, 13890), {}, today)
    assert b == {"name": "Nhẫn 9999", "unit": "tr/lượng", "buy": "134,9", "sell": "138,9"}


def test_gold_block_percent_changes():
    today = date(2026, 11, 3)
    hist = {today - timedelta(days=30): gold.Price(13070, 13470),
            today - timedelta(days=91): gold.Price(12000, 12650),
            today - timedelta(days=365): gold.Price(9000, 9810)}
    b = gold.gold_block(gold.Price(13490, 13890), hist, today)
    assert b["d1m"] == "+3,1%"
    assert b["d3m"] == "+9,8%"
    assert b["d1y"] == "+41,6%"


def test_gold_partial_history_keeps_only_available_periods():
    today = date(2026, 11, 3)
    hist = {today - timedelta(days=33): gold.Price(13000, 13400)}  # within tolerance for 1 month only
    b = gold.gold_block(gold.Price(13490, 13890), hist, today)
    assert "d1m" in b and "d3m" not in b and "d1y" not in b


def test_gold_reference_record_too_old_is_ignored():
    today = date(2026, 11, 3)
    hist = {today - timedelta(days=60): gold.Price(13000, 13400)}  # 30 days before the 1-month target
    assert gold.change_vs(hist, today, 30, 13890) is None


def test_gold_csv_roundtrip(tmp_path):
    path = tmp_path / "gold.csv"
    h = {date(2026, 11, 3): gold.Price(13490, 13890), date(2026, 11, 2): gold.Price(13400, 13800)}
    gold.save_history(path, h)
    assert path.read_text(encoding="utf-8").splitlines()[:2] == ["date,buy,sell", "2026-11-02,13400,13800"]
    assert gold.load_history(path) == h
    assert gold.load_history(tmp_path / "missing.csv") == {}


# ---- weather ----
def test_weather_parse_fixture():
    w = weather.parse((FX / "openmeteo.json").read_bytes(), "TP.HCM")
    assert w == {"city": "TP.HCM", "now": "Nhiều mây", "range": "25–33°"}


def test_weather_codes():
    assert weather.describe(81) == "Mưa rào"
    assert weather.describe(12345) == "Không rõ"


# ---- news ----
NOW = datetime(2026, 11, 3, 2, 0, tzinfo=timezone.utc)


def test_rss_parse_drops_items_without_date_and_strips_html():
    items = news.parse_feed((FX / "feed.rss.xml").read_bytes(), "Src")
    titles = [i.title for i in items]
    assert "Item without a date" not in titles
    assert len(items) == 4
    assert items[0].summary == "The new model & its pricing."


def test_atom_parse_uses_alternate_link():
    items = news.parse_feed((FX / "feed.atom.xml").read_bytes(), "Atom")
    assert items[0].link == "https://example.org/rules"
    assert len(items) == 2


def test_select_window_and_dedupe():
    items = news.parse_feed((FX / "feed.rss.xml").read_bytes(), "A") + \
        news.parse_feed((FX / "feed.atom.xml").read_bytes(), "B")
    chosen = news.select(items, NOW)
    titles = [i.title for i in chosen]
    assert sum("faster reasoning model" in t for t in titles) == 1  # near-duplicate title removed
    assert "Old story from last week" not in titles
    assert "Too old to show" not in titles
    assert "Chip startup raises funding" in titles
    assert chosen == sorted(chosen, key=lambda i: i.published, reverse=True)


def test_select_limit():
    base = NOW - timedelta(hours=1)
    items = [news.Item("Story number %d about topic %d" % (n, n * 7), "https://x/%d" % n, base - timedelta(minutes=n), "S")
             for n in range(10)]
    assert len(news.select(items, NOW, limit=5)) == 5


def test_apply_vi_is_defensive():
    it = news.Item("Original title", "https://x/1", NOW, "S", "Original summary")
    out = news.apply_vi([it, it], [{"i": 0, "t": "Tiêu đề " + "x" * 200, "s": 5}, {"i": "1", "t": "bad"}, "junk"])
    assert len(out[0][0]) == 90 and out[0][0].endswith("…")
    assert out[0][1] == "Original summary"  # non-string summary ignored
    assert out[1] == ("Original title", "Original summary")
    assert news.apply_vi([it], None) == [("Original title", "Original summary")]
    assert "\n" not in news.apply_vi([it], [{"i": 0, "t": "a\nb", "s": "c"}])[0][0]


# ---- calendar ----
def test_ics_events_for_day():
    ev = calendar_ics.events_for_day((FX / "sample.ics").read_text(encoding="utf-8"), date(2026, 11, 3))
    assert [e["time"] for e in ev] == ["Cả ngày", "Cả ngày", "00:00", "09:00", "14:30", "19:00"]
    titles = [e["t"] for e in ev]
    assert titles[0] == "Sinh nhật bạn" and titles[1] == "Đi công tác"  # multi-day all-day event covers today
    assert "Họp nhóm firmware, review preset" in titles  # \, unescaped, UTC converted to VN time
    assert "Folded line continues here" in titles
    assert "Đã hủy" not in titles and "Ngày mai" not in titles
    assert all(len(t) <= 60 for t in titles)


def test_ics_other_day_and_garbage():
    text = (FX / "sample.ics").read_text(encoding="utf-8")
    assert [e["t"] for e in calendar_ics.events_for_day(text, date(2026, 11, 4))][-1] == "Ngày mai"
    assert calendar_ics.events_for_day("not an ics file", date(2026, 11, 3)) == []


# ---- quotes ----
def test_quotes_file_has_enough_quotes_with_authors():
    qs = quotes.load(QUOTES_FILE)
    assert len(qs) >= 60
    assert all(q["text"] and q["by"] for q in qs)


def test_quote_is_stable_within_a_day_and_rotates():
    qs = quotes.load(QUOTES_FILE)
    d = date(2026, 11, 3)
    assert quotes.pick(qs, d) == quotes.pick(qs, d)
    assert quotes.pick(qs, d) != quotes.pick(qs, d + timedelta(days=1))
    assert quotes.pick(qs, d) == quotes.pick(qs, d + timedelta(days=len(qs)))
    assert quotes.pick([], d) is None


def test_vn_timezone_is_utc_plus_7():
    assert VN.utcoffset(None) == timedelta(hours=7)
