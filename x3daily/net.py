"""Read-only HTTP GET helper. The only non-GET request in the project is the optional
translation POST in translate.py (sends public RSS text only)."""
import gzip
import io
import urllib.request

from .config import HTTP_TIMEOUT, USER_AGENT


class FetchError(Exception):
    """Fetch failed. The message never contains the URL (it may be a secret)."""


def get(url, timeout=HTTP_TIMEOUT, max_bytes=5_000_000):
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(max_bytes + 1)
    except Exception as e:  # urllib errors may embed the URL, so re-raise without it
        raise FetchError(type(e).__name__) from None
    if len(data) > max_bytes:
        raise FetchError("response too large")
    if data[:2] == bytes((0x1F, 0x8B)):  # gzip magic number
        # deepmind.google serves its RSS gzip-compressed without a Content-Encoding header (14/11/2026).
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as g:
                data = g.read(max_bytes + 1)
        except (OSError, EOFError):
            raise FetchError("bad gzip body") from None
        if len(data) > max_bytes:
            raise FetchError("response too large")
    return data
