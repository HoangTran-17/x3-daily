"""Static configuration. Secrets come from environment variables, never from this file."""
from datetime import timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VN = timezone(timedelta(hours=7))  # Vietnam has no DST

USER_AGENT = "x3-daily/1.0 (+https://github.com/HoangTran-17/x3-daily)"
HTTP_TIMEOUT = 20

DEFAULT_BASE_URL = "https://hoangtran-17.github.io/x3-daily/"
# X3 cannot do the TLS handshake with github.io; it reads the `device` branch through the contents API.
DEFAULT_DEVICE_BASE_URL = "https://api.github.com/repos/HoangTran-17/x3-daily/contents/"
DEVICE_HREF_SUFFIX = "?ref=device"

GOLD_CSV = ROOT / "data" / "gold.csv"
QUOTES_FILE = ROOT / "quotes.txt"
WORK_DIR = ROOT / "work"
SITE_DIR = ROOT / "_site"
# Calendar brief lives outside SITE_DIR: everything in SITE_DIR ends up in a downloadable public artifact.
PRIVATE_DIR = ROOT / "out-private"

# PNJ public JSON, zone 00 = TP.HCM. Product code N24K = "Nhan Tron PNJ 999.9".
PNJ_URL = "https://edge-api.pnj.io/ecom-frontend/v1/get-gold-price?zone=00"
PNJ_RING_CODE = "N24K"

CITIES = [
    {"name": "TP.HCM", "lat": 10.8231, "lon": 106.6297},
    {"name": "Hà Tĩnh", "lat": 18.3428, "lon": 105.9057},
]
OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
    "&current=weather_code&daily=temperature_2m_max,temperature_2m_min"
    "&timezone=Asia%2FHo_Chi_Minh&forecast_days=1"
)

# Reputable AI news feeds (RSS 2.0 or Atom).
NEWS_FEEDS = [
    {"source": "Google AI", "url": "https://blog.google/technology/ai/rss/"},
    {"source": "MIT Technology Review", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed"},
    {"source": "TechCrunch", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"source": "The Verge", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
]
NEWS_MAX = 5
NEWS_WINDOW_HOURS = 24
NEWS_TITLE_MAX = 90
NEWS_SUMMARY_MAX = 300

BRIEF_MAX_BYTES = 4096  # firmware reads up to 8 KB; keep headroom
EVENT_TITLE_MAX = 60
EVENTS_MAX = 6

GOLD_PERIODS = {"d1m": 30, "d3m": 91, "d1y": 365}  # days back
GOLD_TOLERANCE_DAYS = 7  # a reference record may be up to this many days older than the target
GOLD_TABLE_DAYS = 30
EPUB_KEEP = 7
