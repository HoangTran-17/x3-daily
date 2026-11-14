"""Vietcombank selling rates for a few currencies, today and FX_COMPARE_DAYS ago."""
import json
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from . import net
from .config import FX_CODES, FX_COMPARE_DAYS, VCB_FX_URL

log = logging.getLogger(__name__)


def parse_vcb(raw):
    """VCB JSON -> {code: Decimal selling rate} for FX_CODES. Empty dict when the day has no data."""
    data = json.loads(raw)
    out = {}
    for row in data.get("Data") or []:
        code = row.get("currencyCode")
        if code in FX_CODES:
            try:
                sell = Decimal(str(row.get("sell")))
            except InvalidOperation:
                continue
            if sell > 0:
                out[code] = sell
    return out


def fetch(day, get=None):
    """[(code, today_sell, old_day, old_sell or None)] in FX_CODES order; [] when today's rates fail."""
    get = get or net.get
    try:
        today = parse_vcb(get(VCB_FX_URL.format(ymd=day.isoformat())))
    except Exception as e:
        log.warning("fx: skipped (%s)", type(e).__name__)
        return []
    old_day = day - timedelta(days=FX_COMPARE_DAYS)
    try:
        old = parse_vcb(get(VCB_FX_URL.format(ymd=old_day.isoformat())))
    except Exception as e:
        log.warning("fx: no %d-day reference (%s)", FX_COMPARE_DAYS, type(e).__name__)
        old = {}
    return [(c, today[c], old_day, old.get(c)) for c in FX_CODES if c in today]
