"""Retail fuel price (Petrolimex, zone 1) from the price-change history on giaxanghomnay.com.

Petrolimex loads its prices with encrypted JavaScript and PVOIL returns 403 (checked 14/11/2026),
so this reads a third-party page. Its HTML may change; any parse failure means "no data".
"""
import html
import logging
import re
from datetime import date

from . import net
from .config import FUEL_PRODUCT, FUEL_URL

log = logging.getLogger(__name__)

_DAY_RE = re.compile(r"Ngày\s+(\d{1,2})/(\d{1,2})/(\d{4})")
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


def _cell_text(s):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", s)).split())


def _price(s):
    """'19,840' -> 19840 (comma is the thousands separator on this page)."""
    if not re.fullmatch(r"\d{1,3}(,\d{3})+", s):
        raise ValueError("bad price")
    return int(s.replace(",", ""))


def parse(raw, product=FUEL_PRODUCT):
    """Newest change that lists `product` -> (effective day, new price, old price). None if absent."""
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    start = text.find("price-history-content")
    if start < 0:
        return None
    blocks = _DAY_RE.split(text[start:])  # [before, d, m, y, block, d, m, y, block, ...]
    for k in range(1, len(blocks) - 3, 4):
        for row in _ROW_RE.findall(blocks[k + 3]):
            cells = [_cell_text(c) for c in _CELL_RE.findall(row)]
            if len(cells) >= 3 and cells[0] == product:
                day = date(int(blocks[k + 2]), int(blocks[k + 1]), int(blocks[k]))
                return day, _price(cells[2]), _price(cells[1])
    return None


def fetch(get=None):
    try:
        return parse((get or net.get)(FUEL_URL))
    except Exception as e:
        log.warning("fuel: skipped (%s)", type(e).__name__)
        return None
