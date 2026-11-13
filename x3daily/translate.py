"""Optional Vietnamese translation of the news with the Gemini API (stdlib urllib only).

Reads work/news_raw.json, writes work/news_vi.json in the format `news.apply_vi` expects.
The API key is sent only in a header and never logged; error messages carry the HTTP status only.
"""
import json
import logging
import os
import re
import urllib.error
import urllib.request

from .config import GEMINI_MODEL, GEMINI_TIMEOUT, GEMINI_URL, NEWS_SUMMARY_MAX, NEWS_TITLE_MAX, ROOT, USER_AGENT

log = logging.getLogger(__name__)

PROMPT_FILE = ROOT / "prompts" / "news_translate.md"


class TranslateError(Exception):
    """Translation failed. The message never contains the key or the request body."""


def _model():
    m = os.environ.get("GEMINI_MODEL", "").strip() or GEMINI_MODEL
    if not re.fullmatch(r"[a-z0-9.\-]+", m):
        raise TranslateError("bad GEMINI_MODEL")
    return m


def build_request(raw_items, key, prompt):
    body = {
        "systemInstruction": {"parts": [{"text": prompt}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(raw_items, ensure_ascii=False)}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    return urllib.request.Request(
        GEMINI_URL.format(model=_model()), data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": key, "User-Agent": USER_AGENT})


def _post(req):
    try:
        with urllib.request.urlopen(req, timeout=GEMINI_TIMEOUT) as resp:
            return resp.read(2_000_000)
    except urllib.error.HTTPError as e:  # 429 = quota exceeded, 400/403 = bad key
        raise TranslateError("HTTP %d" % e.code) from None
    except Exception as e:
        raise TranslateError(type(e).__name__) from None


def parse_response(raw):
    """Gemini response bytes -> [{"i": int, "t": str, "s": str}] with lengths capped. Raises TranslateError."""
    try:
        data = json.loads(raw)
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        out = json.loads(text)
    except Exception:
        raise TranslateError("unexpected response") from None
    if not isinstance(out, list):
        raise TranslateError("response is not a list")
    result = []
    for e in out:
        if not (isinstance(e, dict) and isinstance(e.get("i"), int) and not isinstance(e.get("i"), bool)):
            continue
        t, s = e.get("t"), e.get("s")
        if isinstance(t, str) and t.strip():
            result.append({"i": e["i"], "t": t[: NEWS_TITLE_MAX * 2], "s": s[: NEWS_SUMMARY_MAX * 2] if isinstance(s, str) else ""})
    if not result:
        raise TranslateError("no usable entries")
    return result


def translate_items(raw_items, key, post=None):
    if not raw_items:
        return []
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    return parse_response((post or _post)(build_request(raw_items, key, prompt)))


def run(work_dir):
    """CLI entry. Returns the exit code: 0 = written or skipped (no key), 1 = API failed."""
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        log.info("translate: skipped (GOOGLE_API_KEY not set)")
        return 0
    try:
        raw_items = json.loads((work_dir / "news_raw.json").read_text(encoding="utf-8"))
        vi = translate_items(raw_items, key)
    except (TranslateError, OSError, ValueError) as e:
        log.warning("translate: failed (%s)", e if isinstance(e, TranslateError) else type(e).__name__)
        return 1
    (work_dir / "news_vi.json").write_text(json.dumps(vi, ensure_ascii=False), encoding="utf-8")
    log.info("translate: %d of %d items translated", len(vi), len(raw_items))
    return 0
