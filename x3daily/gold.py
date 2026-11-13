"""Gold ring 9999 price: PNJ public JSON, plus a CSV history kept in the repo."""
import csv
import json
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from . import net
from .config import GOLD_PERIODS, GOLD_TOLERANCE_DAYS, PNJ_HISTORY_URL, PNJ_RING_CODE, PNJ_RING_NAME, PNJ_URL
from .vi import fmt_decimal, fmt_percent

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Price:
    buy: int   # thousand VND per chi, as published
    sell: int


def parse_pnj(raw):
    data = json.loads(raw)
    for row in data["data"]:
        if row.get("masp") == PNJ_RING_CODE:
            return Price(buy=int(row["giamua"]), sell=int(row["giaban"]))
    raise ValueError("ring 9999 row not found")


def fetch_price():
    return parse_pnj(net.get(PNJ_URL))


def _k_per_chi(luong_text):
    """'137.400' (thousand VND per luong, dot = thousands separator) -> 13740 (thousand VND per chi)."""
    n = int(str(luong_text).replace(".", ""))
    if n <= 0 or n % 10:
        raise ValueError("unexpected price")
    return n // 10


def parse_pnj_history(raw):
    """Last price of the day for PNJ_RING_NAME from get-gold-price-history, or None (Sundays, holidays)."""
    best = None
    for loc in json.loads(raw).get("locations") or []:
        for gt in loc.get("gold_type") or []:
            if gt.get("name") != PNJ_RING_NAME:
                continue
            for row in gt.get("data") or []:
                try:
                    at = datetime.strptime(row["updated_at"], "%d/%m/%Y %H:%M:%S")
                    p = Price(buy=_k_per_chi(row["gia_mua"]), sell=_k_per_chi(row["gia_ban"]))
                except (KeyError, TypeError, ValueError):
                    continue
                if best is None or at > best[0]:
                    best = (at, p)
    return best[1] if best else None


def backfill(hist, start, end, get=None, pause=0.2):
    """Add missing dates in [start, end] from the PNJ history endpoint. Existing rows are never replaced.

    Returns the number of rows added. A failing day is skipped.
    """
    added = 0
    d = start
    while d <= end:
        if d not in hist:
            try:
                p = parse_pnj_history((get or net.get)(PNJ_HISTORY_URL.format(ymd=d.strftime("%Y%m%d"))))
            except Exception as e:
                log.warning("gold backfill %s: skipped (%s)", d, type(e).__name__)
                p = None
            if p:
                hist[d] = p
                added += 1
            if pause:
                time.sleep(pause)
        d += timedelta(days=1)
    return added


def to_million_per_luong(k_per_chi):
    """Thousand VND per chi -> million VND per luong (1 luong = 10 chi): 13490 -> 134.9."""
    return Decimal(int(k_per_chi)) / 100


def load_history(path):
    hist = {}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    hist[date.fromisoformat(row["date"])] = Price(int(row["buy"]), int(row["sell"]))
                except (KeyError, ValueError):
                    log.warning("gold.csv: skip bad row")
    except FileNotFoundError:
        pass
    return hist


def save_history(path, hist):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["date", "buy", "sell"])
        for d in sorted(hist):
            w.writerow([d.isoformat(), hist[d].buy, hist[d].sell])


def reference(hist, today, days, tolerance=GOLD_TOLERANCE_DAYS):
    """(date, Price) of the newest record on or before `days` ago, at most `tolerance` days older; else None."""
    target = today - timedelta(days=days)
    older = [d for d in hist if d <= target]
    if not older:
        return None
    ref = max(older)
    if (target - ref).days > tolerance or hist[ref].sell <= 0:
        return None
    return ref, hist[ref]


def change_vs(hist, today, days, current_sell, tolerance=GOLD_TOLERANCE_DAYS):
    """Percent change of the sell price against the record `days` ago, or None."""
    ref = reference(hist, today, days, tolerance)
    if ref is None:
        return None
    return fmt_percent((Decimal(current_sell) - ref[1].sell) / ref[1].sell)


def gold_block(price, hist, today):
    """The `gold` object of brief.json. Fields without data are left out."""
    block = {
        "name": "Nhẫn 9999",
        "unit": "tr/lượng",
        "buy": fmt_decimal(to_million_per_luong(price.buy)),
        "sell": fmt_decimal(to_million_per_luong(price.sell)),
    }
    for key, days in GOLD_PERIODS.items():
        val = change_vs(hist, today, days, price.sell)
        if val is not None:
            block[key] = val
    return block
