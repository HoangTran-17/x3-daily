"""Offline tests for brief.json, EPUB, OPDS and the end-to-end build (network mocked)."""
import json
import logging
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime
from pathlib import Path

import pytest

from x3daily import brief, build, epub, gold, net, news, opds
from x3daily.config import BRIEF_MAX_BYTES, VN

FX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 3, 4, 10, tzinfo=VN)
BASE = "https://example.github.io/x3-daily/"
ICS_URL = "https://calendar.example.com/private/very-secret-token/basic.ics"


def _sample_brief(**kw):
    return brief.build_brief(
        NOW,
        weather=[{"city": "TP.HCM", "now": "Mưa rào", "range": "25–32°"}],
        gold={"name": "Nhẫn 9999", "unit": "tr/lượng", "buy": "134,9", "sell": "138,9"},
        news_titles=["Tin %d " % n + "x" * 80 for n in range(5)],
        quote={"text": "Nước chảy đá mòn.", "by": "Tục ngữ"},
        events=[{"time": "09:00", "t": "Họp"}], **kw)


# ---- brief.json ----
def test_brief_schema_v1_keys_and_missing_data():
    b = _sample_brief()
    assert b["v"] == 1 and b["generated"] == "2026-11-03T04:10:00+07:00"
    assert set(b) <= {"v", "generated", "weather", "gold", "news", "events", "quote"}
    bare = brief.build_brief(NOW)
    assert set(bare) == {"v", "generated"}  # failed sources are simply absent


def test_brief_fits_4kb_even_when_oversized():
    b = _sample_brief()
    b["events"] = [{"time": "09:00", "t": "Sự kiện rất dài " * 4} for _ in range(60)]
    data = brief.fit(b)
    assert len(data) <= BRIEF_MAX_BYTES
    assert json.loads(data)["v"] == 1


def test_brief_realistic_size_is_small():
    assert len(brief.fit(_sample_brief())) < 2000


def test_public_brief_has_no_events():
    pub = brief.public_version(_sample_brief())
    assert "events" not in pub and "weather" in pub


# ---- EPUB ----
def _make_epub(path):
    items = news.parse_feed((FX / "feed.rss.xml").read_bytes(), "Src")[:2]
    hist = {date(2026, 11, 2): gold.Price(13400, 13800), date(2026, 11, 3): gold.Price(13490, 13890)}
    block = gold.gold_block(hist[date(2026, 11, 3)], hist, date(2026, 11, 3))
    epub.build(path, date(2026, 11, 3), [{"city": "TP.HCM", "now": "Mưa rào", "range": "25–32°"}],
               hist[date(2026, 11, 3)], hist, block, [(i, i.title, i.summary, False) for i in items],
               {"text": "Nước chảy đá mòn.", "by": "Tục ngữ"})


def test_epub_structure(tmp_path):
    p = tmp_path / "x.epub"
    _make_epub(p)
    with zipfile.ZipFile(p) as z:
        first = z.infolist()[0]
        assert first.filename == "mimetype" and first.compress_type == zipfile.ZIP_STORED
        assert z.testzip() is None
        for n in z.namelist():
            if n.endswith((".xhtml", ".opf", ".ncx", ".xml")):
                ET.fromstring(z.read(n))  # well-formed XML
        pages = "".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xhtml"))
        ncx = z.read("OEBPS/toc.ncx").decode("utf-8")
    assert "<table" not in pages  # CrossVi flattens tables
    assert "134,9" in pages and "Nước chảy đá mòn." in pages
    assert "https://" not in pages.split("<body>", 1)[-1]  # no URLs in the reading text
    assert ncx.count("<navPoint") == 3


def test_epub_passes_x3book_check(tmp_path):
    pytest.importorskip("x3book")
    from x3book.check import check
    from x3book.tune import tune
    raw, out = tmp_path / "raw.epub", tmp_path / "tuned.epub"
    _make_epub(raw)
    tune(str(raw), str(out), log=lambda *_: None)
    assert check(str(out), log=lambda *_: None) == []


# ---- OPDS ----
def _touch_issues(d, days):
    for day in days:
        (d / ("bao-sang-202611%02d.epub" % day)).write_bytes(b"x" * 10)


def test_opds_feed_is_valid_and_keeps_seven(tmp_path):
    _touch_issues(tmp_path, range(1, 10))
    names = opds.prune(tmp_path, keep=7)
    assert names[0] == "bao-sang-20261109.epub" and len(names) == 7
    assert not (tmp_path / "bao-sang-20261101.epub").exists()
    root = ET.fromstring(opds.build_feed(BASE, tmp_path, names, NOW))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    assert root.tag == "{http://www.w3.org/2005/Atom}feed"
    assert root.find("a:id", ns).text and root.find("a:title", ns).text and root.find("a:updated", ns).text
    entries = root.findall("a:entry", ns)
    assert len(entries) == 7
    for e in entries:
        acq = [l for l in e.findall("a:link", ns) if l.get("rel") == "http://opds-spec.org/acquisition"]
        assert len(acq) == 1
        assert acq[0].get("type") == "application/epub+zip" and acq[0].get("href").startswith(BASE)
        assert e.find("a:id", ns).text and e.find("a:updated", ns).text and e.find("a:title", ns).text
    assert any(l.get("rel") == "self" for l in root.findall("a:link", ns))


def test_opds_api_feed_uses_suffix_and_self_name(tmp_path):
    _touch_issues(tmp_path, range(1, 4))
    names = opds.prune(tmp_path, keep=7)
    api = "https://api.github.com/repos/o/r/contents/"
    root = ET.fromstring(opds.build_feed(api, tmp_path, names, NOW, "?ref=device", "opds-api.xml"))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    hrefs = [l.get("href") for l in root.iter("{http://www.w3.org/2005/Atom}link")]
    assert api + "bao-sang-20261103.epub?ref=device" in hrefs
    assert [l.get("href") for l in root.findall("a:link", ns) if l.get("rel") == "self"] == [api + "opds-api.xml?ref=device"]
    old = ET.fromstring(opds.build_feed(BASE, tmp_path, names, NOW))
    assert BASE + "opds.xml" in [l.get("href") for l in old.findall("a:link", ns)]
    assert not any("?ref" in (l.get("href") or "") for l in old.iter("{http://www.w3.org/2005/Atom}link"))


def test_restore_previous_only_downloads_valid_names_from_base_url(tmp_path):
    feed = ('<feed xmlns="http://www.w3.org/2005/Atom">'
            '<entry><link rel="x" href="https://other.example/bao-sang-20261101.epub"/></entry>'
            '<entry><link rel="x" href="../evil.epub"/></entry>'
            '<entry><link rel="x" href="https://evil.example/notes.txt"/></entry></feed>')
    calls = []

    def fake(url, max_bytes=0):
        calls.append(url)
        return feed.encode() if url.endswith("opds.xml") else b"epub-bytes"

    opds.restore_previous(BASE, tmp_path, fetch=fake)
    assert calls == [BASE + "opds.xml", BASE + "bao-sang-20261101.epub"]  # host taken from BASE, not from the feed
    assert [p.name for p in tmp_path.iterdir()] == ["bao-sang-20261101.epub"]


def test_restore_previous_ignores_fetch_errors(tmp_path):
    def boom(url, max_bytes=0):
        raise net.FetchError("down")

    opds.restore_previous(BASE, tmp_path, fetch=boom)
    assert list(tmp_path.iterdir()) == []


# ---- end to end with mocked network ----
def _fake_get(url, timeout=0, max_bytes=0):
    if "pnj.io" in url:
        return (FX / "pnj.json").read_bytes()
    if "open-meteo" in url:
        return (FX / "openmeteo.json").read_bytes()
    if url == ICS_URL:
        return (FX / "sample.ics").read_bytes()
    if "blog.google" in url:
        return (FX / "feed.rss.xml").read_bytes()
    if "theverge" in url:
        return (FX / "feed.atom.xml").read_bytes()
    raise net.FetchError("offline")


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(net, "get", _fake_get)
    monkeypatch.setattr(build, "SITE_DIR", tmp_path / "_site")
    monkeypatch.setattr(build, "WORK_DIR", tmp_path / "work")
    monkeypatch.setattr(build, "PRIVATE_DIR", tmp_path / "out-private")
    monkeypatch.setattr(build, "GOLD_CSV", tmp_path / "gold.csv")
    monkeypatch.setattr(build, "_run_x3book", lambda raw, out: Path(out).write_bytes(Path(raw).read_bytes()) or True)
    monkeypatch.setenv("PAGES_BASE_URL", BASE)
    monkeypatch.delenv("GCAL_ICS_URL", raising=False)
    return tmp_path


def _all_bytes(site):
    for p in site.rglob("*"):
        if p.is_file():
            data = p.read_bytes()
            if p.suffix == ".epub":
                with zipfile.ZipFile(p) as z:
                    data += b"".join(z.read(n) for n in z.namelist())
            yield p, data


def test_end_to_end_calendar_only_in_private_brief(sandbox, monkeypatch, caplog):
    monkeypatch.setenv("GCAL_ICS_URL", ICS_URL)
    caplog.set_level(logging.DEBUG)
    build.build(NOW)
    site = sandbox / "_site"

    public = json.loads((site / "brief.json").read_text(encoding="utf-8"))
    assert "events" not in public and public["gold"]["sell"] == "138,9"
    assert [p.name for p in site.iterdir() if p.is_dir()] == []
    private_file = sandbox / "out-private" / "brief.json"
    private = json.loads(private_file.read_text(encoding="utf-8"))
    assert len(private["events"]) >= 4
    assert len(private_file.read_bytes()) <= BRIEF_MAX_BYTES

    # nothing deployed to Pages (also not inside the EPUB) may carry calendar text
    for p, data in _all_bytes(site):
        assert "Họp nhóm".encode() not in data, p
        assert b"very-secret-token" not in data, p
    assert "Họp nhóm" not in caplog.text and "very-secret-token" not in caplog.text

    assert (site / "bao-sang-20261103.epub").exists()
    assert ET.parse(site / "opds.xml").getroot().tag.endswith("feed")
    assert b"contents/bao-sang-20261103.epub?ref=device" in (site / "opds-api.xml").read_bytes()
    assert (sandbox / "gold.csv").read_text(encoding="utf-8").splitlines()[-1] == "2026-11-03,13490,13890"


def test_end_to_end_without_calendar_writes_no_private_brief(sandbox):
    build.build(NOW)
    assert [p.name for p in (sandbox / "_site").iterdir() if p.is_dir()] == []
    assert "events" not in json.loads((sandbox / "_site" / "brief.json").read_text(encoding="utf-8"))
    assert not (sandbox / "out-private").exists()


def test_private_brief_is_rewritten_when_calendar_fetch_fails(sandbox, monkeypatch):
    # A stale private file from an earlier run must not survive into today's gist upload.
    monkeypatch.setenv("GCAL_ICS_URL", "https://calendar.example.com/down.ics")
    stale = sandbox / "out-private" / "brief.json"
    stale.parent.mkdir()
    stale.write_text('{"events":[{"time":"09:00","t":"old"}]}', encoding="utf-8")
    build.build(NOW)
    assert "events" not in json.loads(stale.read_text(encoding="utf-8"))


def test_end_to_end_survives_every_source_failing(sandbox, monkeypatch):
    def down(url, timeout=0, max_bytes=0):
        raise net.FetchError("offline")

    monkeypatch.setattr(net, "get", down)
    build.build(NOW)
    data = json.loads((sandbox / "_site" / "brief.json").read_text(encoding="utf-8"))
    assert set(data) == {"v", "generated", "quote"}  # only the offline quote remains
