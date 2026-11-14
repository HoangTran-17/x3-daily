"""Offline tests for the optional Gemini translation. The API is never called."""
import json
import logging
import urllib.error
import zipfile
from pathlib import Path

import pytest

from x3daily import build, translate

from test_output import NOW, sandbox  # noqa: F401  (pytest fixture)

FX = Path(__file__).parent / "fixtures"
KEY = "test-key-should-never-leak"
RAW = [{"i": 0, "title": "Google launches a new AI model", "summary": "Faster and cheaper.", "source": "Google AI"},
       {"i": 1, "title": "New AI safety research", "summary": "Testing before release.", "source": "MIT"}]


def test_parse_response_from_fixture():
    out = translate.parse_response((FX / "gemini.json").read_bytes())
    assert [e["i"] for e in out] == [0, 1]  # entry with a non-int index dropped
    assert out[0]["t"].startswith("Google ra mắt")


@pytest.mark.parametrize("raw", [b"not json", b'{"candidates": []}',
                                 b'{"candidates":[{"content":{"parts":[{"text":"{}"}]}}]}',
                                 b'{"candidates":[{"content":{"parts":[{"text":"[{\\"i\\":\\"0\\"}]"}]}}]}'])
def test_parse_response_rejects_bad_output(raw):
    with pytest.raises(translate.TranslateError):
        translate.parse_response(raw)


def test_parse_response_caps_long_text():
    text = json.dumps([{"i": 0, "t": "x" * 5000, "s": "y" * 5000}])
    raw = json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]}).encode()
    out = translate.parse_response(raw)
    assert len(out[0]["t"]) <= 180 and len(out[0]["s"]) <= 600


def test_request_sends_key_in_header_only(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    seen = {}

    def fake_post(req):
        seen["req"] = req
        return (FX / "gemini.json").read_bytes()

    out = translate.translate_items(RAW, KEY, post=fake_post)
    req = seen["req"]
    assert len(out) == 2 and req.get_method() == "POST"
    assert req.full_url.endswith("/models/gemini-3.5-flash-lite:generateContent")
    assert req.get_header("X-goog-api-key") == KEY
    assert KEY not in req.full_url and KEY.encode() not in req.data
    body = json.loads(req.data)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "Google launches" in body["contents"][0]["parts"][0]["text"]


def test_bad_model_name_is_rejected(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "../evil?x=1")
    with pytest.raises(translate.TranslateError):
        translate.build_request(RAW, KEY, "p")


def _work(tmp_path):
    (tmp_path / "news_raw.json").write_text(json.dumps(RAW), encoding="utf-8")
    return tmp_path


def test_run_without_key_skips(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert translate.run(_work(tmp_path)) == 0
    assert not (tmp_path / "news_vi.json").exists()


def test_run_writes_news_vi(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", KEY)
    monkeypatch.setattr(translate, "_post", lambda req: (FX / "gemini.json").read_bytes())
    assert translate.run(_work(tmp_path)) == 0
    vi = json.loads((tmp_path / "news_vi.json").read_text(encoding="utf-8"))
    assert vi[1]["t"] == "Nghiên cứu mới về an toàn AI"


def test_run_api_error_fails_without_leaking_key(tmp_path, monkeypatch, caplog):
    def quota(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)

    monkeypatch.setenv("GOOGLE_API_KEY", KEY)
    monkeypatch.setattr(translate.urllib.request, "urlopen", quota)
    caplog.set_level(logging.DEBUG)
    assert translate.run(_work(tmp_path)) == 1
    assert not (tmp_path / "news_vi.json").exists()
    assert "HTTP 429" in caplog.text and KEY not in caplog.text


def test_translate_items_retries_503_then_succeeds():
    calls, waits = [], []

    def flaky(req):
        calls.append(1)
        if len(calls) < 3:
            raise translate.TranslateError("HTTP 503", transient=True)
        return (FX / "gemini.json").read_bytes()

    out = translate.translate_items([{"title": "a", "summary": "b"}], KEY, post=flaky, sleep=waits.append)
    assert out and len(calls) == 3 and waits == [5, 15]


def test_translate_items_gives_up_after_three_503():
    calls = []

    def down(req):
        calls.append(1)
        raise translate.TranslateError("HTTP 503", transient=True)

    with pytest.raises(translate.TranslateError):
        translate.translate_items([{"title": "a", "summary": "b"}], KEY, post=down, sleep=lambda d: None)
    assert len(calls) == 3


def test_translate_items_does_not_retry_429():
    calls = []

    def quota(req):
        calls.append(1)
        raise translate.TranslateError("HTTP 429")

    with pytest.raises(translate.TranslateError):
        translate.translate_items([{"title": "a", "summary": "b"}], KEY, post=quota, sleep=lambda d: None)
    assert len(calls) == 1


# ---- EPUB shows Vietnamese text, or "(chưa dịch)" when there is no translation ----
def _news_page(sandbox):
    with zipfile.ZipFile(sandbox / "_site" / "bao-sang-20261103.epub") as z:
        # The sandbox serves its RSS fixture as blog.google, which feeds the "Anthropic, Google" page.
        return z.read("OEBPS/hang-ai.xhtml").decode("utf-8")


def test_epub_uses_translation_from_fixture(sandbox):
    work = sandbox / "work"
    work.mkdir()
    out = translate.parse_response((FX / "gemini.json").read_bytes())
    (work / "news_vi.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    build.build(NOW)
    page = _news_page(sandbox)
    assert "Google ra mắt mô hình AI mới cho nhà phát triển" in page
    assert page.count("(chưa dịch)") == max(0, page.count("<h2>") - 2)  # fixture translates items 0 and 1


def test_epub_marks_untranslated_news(sandbox):
    build.build(NOW)
    page = _news_page(sandbox)
    assert page.count("<h2>") >= 1 and page.count("(chưa dịch)") == page.count("<h2>")
