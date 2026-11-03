"""Gold ring 9999 price: PNJ public JSON, plus a CSV history kept in the repo."""
import csv
import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from . import net
from .config import GOLD_PERIODS, GOLD_TOLERANCE_DAYS, PNJ_RING_CODE, PNJ_URL
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


def change_vs(hist, today, days, current_sell):
    """Percent change of the sell price against the record `days` ago, or None.

    Uses the newest record on or before the target date, at most GOLD_TOLERANCE_DAYS older.
    """
    target = today - timedelta(days=days)
    older = [d for d in hist if d <= target]
    if not older:
        return None
    ref = max(older)
    if (target - ref).days > GOLD_TOLERANCE_DAYS or hist[ref].sell <= 0:
        return None
    return fmt_percent((Decimal(current_sell) - hist[ref].sell) / hist[ref].sell)


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
