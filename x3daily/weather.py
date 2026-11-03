"""Weather from Open-Meteo (no API key)."""
import json
import logging
import math

from . import net
from .config import CITIES, OPEN_METEO_URL

log = logging.getLogger(__name__)

# WMO weather interpretation codes -> short Vietnamese description
_CODES = {
    0: "Trời quang", 1: "Ít mây", 2: "Có mây", 3: "Nhiều mây",
    45: "Sương mù", 48: "Sương mù",
    51: "Mưa phùn", 53: "Mưa phùn", 55: "Mưa phùn",
    56: "Mưa phùn lạnh", 57: "Mưa phùn lạnh",
    61: "Mưa nhẹ", 63: "Mưa vừa", 65: "Mưa to",
    66: "Mưa lạnh", 67: "Mưa lạnh",
    71: "Tuyết nhẹ", 73: "Tuyết", 75: "Tuyết dày", 77: "Hạt tuyết",
    80: "Mưa rào nhẹ", 81: "Mưa rào", 82: "Mưa rào lớn",
    85: "Mưa tuyết", 86: "Mưa tuyết",
    95: "Dông", 96: "Dông, mưa đá", 99: "Dông, mưa đá",
}


def describe(code):
    return _CODES.get(int(code), "Không rõ")


def _round(x):
    return int(math.floor(x + 0.5))


def parse(raw, city):
    d = json.loads(raw)
    lo = d["daily"]["temperature_2m_min"][0]
    hi = d["daily"]["temperature_2m_max"][0]
    return {"city": city, "now": describe(d["current"]["weather_code"]), "range": "%d–%d°" % (_round(lo), _round(hi))}


def fetch_all():
    """Return the city entries that could be fetched (failed cities are skipped)."""
    out = []
    for c in CITIES:
        try:
            out.append(parse(net.get(OPEN_METEO_URL.format(lat=c["lat"], lon=c["lon"])), c["name"]))
        except Exception as e:
            log.warning("weather %s: skipped (%s)", c["name"], type(e).__name__)
    return out
