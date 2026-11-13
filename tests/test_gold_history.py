"""Offline tests for gold comparison points and the PNJ history backfill."""
import re
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from x3daily import epub, gold, net, vi

FX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 13)


def test_parse_history_takes_last_record_of_ring_product():
    p = gold.parse_pnj_history((FX / "pnj_history.json").read_bytes())
    assert p == gold.Price(buy=13320, sell=13740)  # 08:35:36, not the SJC or "Vàng nữ trang" rows


def test_parse_history_empty_day():
    assert gold.parse_pnj_history(b'{"locations":[]}') is None
    assert gold.parse_pnj_history(b'{"locations":[{"name":"TPHCM","gold_type":[]}]}') is None


@pytest.mark.parametrize("text", ["137.405", "0", "abc"])
def test_history_price_must_convert_exactly(text):
    with pytest.raises(ValueError):
        gold._k_per_chi(text)


def test_backfill_adds_only_missing_days():
    hist = {TODAY - timedelta(days=1): gold.Price(1, 2)}
    calls = []

    def fake_get(url, timeout=0, max_bytes=0):
        calls.append(url)
        if url.endswith("20261110"):
            raise net.FetchError("offline")
        if url.endswith("20261111"):
            return b'{"locations":[]}'  # Sunday / holiday
        return (FX / "pnj_history.json").read_bytes()

    added = gold.backfill(hist, date(2026, 11, 9), date(2026, 11, 12), get=fake_get, pause=0)
    assert added == 1 and set(hist) == {date(2026, 11, 9), date(2026, 11, 12)}
    assert hist[date(2026, 11, 12)] == gold.Price(1, 2)  # existing row kept
    assert len(calls) == 3 and all("date=202611" in u for u in calls)


def test_one_week_uses_short_tolerance():
    old = {TODAY - timedelta(days=10): gold.Price(13000, 13400)}
    assert gold.reference(old, TODAY, 7, 2) is None  # 10 days ago is not "1 week"
    near = {TODAY - timedelta(days=9): gold.Price(13000, 13400)}
    assert gold.reference(near, TODAY, 7, 2) == (TODAY - timedelta(days=9), gold.Price(13000, 13400))


def test_fmt_signed():
    assert vi.fmt_signed(-2.9) == "-2,9" and vi.fmt_signed(1.25) == "+1,3" and vi.fmt_signed(0) == "0,0"


def _gold_text(tmp_path, hist, price):
    block = gold.gold_block(price, hist, TODAY) if price else {}
    path = tmp_path / "g.epub"
    epub.build(path, TODAY, [], price, hist, block, [], None)
    with zipfile.ZipFile(path) as z:
        html = z.read("OEBPS/vang.xhtml").decode("utf-8")
    return re.sub(r"<[^>]+>", "\n", html)


def test_epub_shows_six_points_and_missing_ones(tmp_path):
    hist = {TODAY - timedelta(days=7): gold.Price(13630, 14030),
            TODAY - timedelta(days=31): gold.Price(14200, 14600),
            TODAY - timedelta(days=365): gold.Price(15100, 15400)}
    text = _gold_text(tmp_path, hist, gold.Price(13320, 13740))
    assert "Hôm nay: mua \n133,2\n, bán \n137,4\n" in text
    assert "1 tuần trước (06/11/2026): mua 136,3, bán 140,3; bán ra -2,9 (-2,1%)" in text
    assert "1 tháng trước (13/10/2026): mua 142,0, bán 146,0; bán ra -8,6 (-5,9%)" in text
    assert "3 tháng trước: chưa có" in text and "6 tháng trước: chưa có" in text
    assert "12 tháng trước (13/11/2025): mua 151,0, bán 154,0; bán ra -16,6 (-10,8%)" in text


def test_epub_without_today_price_still_lists_points(tmp_path):
    hist = {TODAY - timedelta(days=7): gold.Price(13630, 14030)}
    text = _gold_text(tmp_path, hist, None)
    assert "Không có giá hôm nay." in text
    assert "1 tuần trước (06/11/2026): mua 136,3, bán 140,3\n" in text
    assert text.count("chưa có") == 4
