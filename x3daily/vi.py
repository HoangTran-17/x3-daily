"""Vietnamese number and date formatting."""
from decimal import ROUND_HALF_UP, Decimal

WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"]


def fmt_decimal(value, places=1):
    """145.2 -> '145,2' (comma as decimal separator, half-up rounding)."""
    q = Decimal(1).scaleb(-places)
    return str(Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP)).replace(".", ",")


def fmt_percent(ratio, places=1):
    """Fractional change -> signed string: 0.031 -> '+3,1%', -0.0214 -> '-2,1%', 0 -> '0,0%'."""
    pct = (Decimal(str(ratio)) * 100).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    text = fmt_decimal(abs(pct), places)
    if pct > 0:
        return "+" + text + "%"
    if pct < 0:
        return "-" + text + "%"
    return text + "%"


def fmt_thousands(n):
    """13490 -> '13.490'."""
    return f"{int(n):,}".replace(",", ".")


def fmt_date_long(d):
    return "%s, %02d/%02d/%d" % (WEEKDAYS[d.weekday()], d.day, d.month, d.year)


def truncate(text, limit):
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
