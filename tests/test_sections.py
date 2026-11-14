"""Offline tests for news sections, Vietcombank rates and the fuel price (added 14/11/2026)."""
import json
import re
import zipfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from x3daily import brief, build, epub, fuel, fx, net, news

FX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 14, 4, 10, tzinfo=timezone(timedelta(hours=7)))


def _rss(*entries):
    items = "".join("<item><title>%s</title><link>https://ex.com/%d</link><pubDate>%s</pubDate>"
                    "<description>Tóm tắt %d</description></item>" % (t, n, d, n)
                    for n, (t, d) in enumerate(entries))
    return ('<?xml version="1.0"?><rss version="2.0"><channel>%s</channel></rss>' % items).encode("utf-8")


def _feed_get(url, timeout=0, max_bytes=0):
    if "anthropic" in url:  # date-only feed: the 04:10 run on 14/11 shows posts dated 12/11 (UTC);
        # 13/11 posts may still appear later that day, so they wait for the 15/11 issue.
        return _rss(("Wait", "Fri, 13 Nov 2026 00:00:00 +0000"), ("Claude news", "Thu, 12 Nov 2026 00:00:00 +0000"),
                    ("Old post", "Wed, 11 Nov 2026 00:00:00 +0000"))
    if "vnexpress" in url:
        return _rss(("Lãi suất tiết kiệm giảm", "Sat, 14 Nov 2026 03:00:00 +0700"))
    if "cnbc" in url:
        return _rss(("Fed holds rates", "Fri, 13 Nov 2026 20:00:00 +0000"))
    if "techcrunch" in url:
        return _rss(("New AI model", "Fri, 13 Nov 2026 18:00:00 +0000"))
    raise net.FetchError("offline")


def test_collect_tags_sections_and_shifts_date_only_feeds(monkeypatch):
    monkeypatch.setattr(net, "get", _feed_get)
    items = news.collect(NOW)
    assert [(i.section, i.title) for i in items] == [
        ("tin-ai", "New AI model"), ("hang-ai", "Claude news"),
        ("kinh-te-vn", "Lãi suất tiết kiệm giảm"), ("kinh-te-tg", "Fed holds rates")]


def test_vietnamese_items_skip_translation_but_keep_their_index(monkeypatch, tmp_path):
    monkeypatch.setattr(net, "get", _feed_get)
    items = news.collect(NOW)
    raw = json.loads(news.dump_raw(items))
    assert [r["i"] for r in raw] == [0, 1, 3]
    vi = news.apply_vi(items, [{"i": 3, "t": "Fed giữ lãi suất", "s": "Tóm tắt."}])
    assert vi[2] == ("Lãi suất tiết kiệm giảm", "Tóm tắt 0", True)
    assert vi[3] == ("Fed giữ lãi suất", "Tóm tắt.", True) and vi[0][2] is False
    news.save_items(tmp_path / "n.json", items)
    assert [i.section for i in news.load_items(tmp_path / "n.json")] == [i.section for i in items]


def test_parse_vcb_reads_selling_rates():
    assert fx.parse_vcb((FX / "vcb_20261114.json").read_bytes()) == {
        "USD": Decimal("25910.00"), "EUR": Decimal("29169.60"), "JPY": Decimal("165.52")}
    assert fx.parse_vcb(b'{"Count":0,"Data":[]}') == {}


def test_fx_fetch_compares_with_91_days_ago():
    calls = []

    def get(url, timeout=0, max_bytes=0):
        calls.append(url)
        return (FX / ("vcb_20261114.json" if url.endswith("2026-11-14") else "vcb_20260815.json")).read_bytes()

    rows = fx.fetch(date(2026, 11, 14), get=get)
    assert calls[1].endswith("date=2026-08-15")
    assert rows[0] == ("USD", Decimal("25910.00"), date(2026, 8, 15), Decimal("26330.00"))
    assert [r[0] for r in rows] == ["USD", "EUR", "JPY"]


def test_fx_without_reference_still_lists_today():
    def get(url, timeout=0, max_bytes=0):
        if url.endswith("2026-11-14"):
            return (FX / "vcb_20261114.json").read_bytes()
        raise net.FetchError("offline")

    assert [r[3] for r in fx.fetch(date(2026, 11, 14), get=get)] == [None, None, None]


def test_fuel_parse_reads_latest_change():
    assert fuel.parse((FX / "giaxang.html").read_bytes()) == (date(2026, 11, 12), 19840, 21150)


def test_fuel_parse_falls_back_to_older_change_and_rejects_bad_numbers():
    row = '<tr><td>%s</td><td>%s</td><td>%s</td><td>x</td></tr>'
    page = ('<div class="price-history-content"><h3>Ngày 20/11/2026</h3><table>%s</table>'
            '<h3>Ngày 12/11/2026</h3><table>%s</table></div>') % (
        row % ("Xăng E5 RON 92 Mức 2", "19,390", "19,000"), row % ("Xăng E10 RON 95 Mức 3", "21,150", "19,840"))
    assert fuel.parse(page) == (date(2026, 11, 12), 19840, 21150)
    assert fuel.fetch(get=lambda url: page.replace("19,840", "19.840").encode()) is None
    assert fuel.parse("<html>no table</html>") is None


def _today_text(tmp_path, rates, fuel_price):
    path = tmp_path / "x.epub"
    epub.build(path, date(2026, 11, 14), [], None, {}, {}, [], None, rates, fuel_price)
    with zipfile.ZipFile(path) as z:
        return re.sub(r"<[^>]+>", "\n", z.read("OEBPS/hom-nay.xhtml").decode("utf-8"))


def test_epub_shows_rates_and_fuel_on_one_line_each(tmp_path):
    rates = fx.fetch(date(2026, 11, 14), get=lambda url, **kw: (FX / (
        "vcb_20261114.json" if url.endswith("2026-11-14") else "vcb_20260815.json")).read_bytes())
    text = _today_text(tmp_path, rates, (date(2026, 11, 12), 19840, 21150))
    assert "USD: 25.910, 3 tháng trước 26.330 (-1,6%)" in text
    assert "EUR: 29.170, 3 tháng trước 30.976 (-5,8%)" in text
    assert "JPY: 165,52, 3 tháng trước 169,48 (-2,3%)" in text
    assert "19.840 đ/lít, từ 12/11 (giảm 1.310)" in text
    assert max(len(l) for l in text.splitlines()) <= 50


def test_epub_without_rates_or_fuel(tmp_path):
    text = _today_text(tmp_path, [], None)
    assert "Không có dữ liệu tỷ giá." in text and "Không có dữ liệu giá xăng." in text
    text = _today_text(tmp_path, [("USD", Decimal("25910"), date(2026, 8, 15), None)], None)
    assert "USD: 25.910, 3 tháng trước chưa có" in text


def test_brief_headlines_come_only_from_ai_section(tmp_path, monkeypatch):
    monkeypatch.setattr(net, "get", _feed_get)
    monkeypatch.setattr(build, "SITE_DIR", tmp_path / "_site")
    monkeypatch.setattr(build, "WORK_DIR", tmp_path / "work")
    monkeypatch.setattr(build, "PRIVATE_DIR", tmp_path / "out-private")
    monkeypatch.setattr(build, "GOLD_CSV", tmp_path / "gold.csv")
    monkeypatch.setattr(build, "_run_x3book", lambda raw, out: Path(out).write_bytes(Path(raw).read_bytes()) or True)
    monkeypatch.delenv("GCAL_ICS_URL", raising=False)
    build.build(NOW)
    data = json.loads((tmp_path / "_site" / "brief.json").read_text(encoding="utf-8"))
    assert data["news"] == [{"t": "New AI model"}]
    with zipfile.ZipFile(tmp_path / "_site" / "bao-sang-20261114.epub") as z:
        assert "Lãi suất tiết kiệm giảm" in z.read("OEBPS/kinh-te-vn.xhtml").decode("utf-8")
