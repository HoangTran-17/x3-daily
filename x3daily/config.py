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
# Undocumented PNJ endpoint found 13/11/2026; date=YYYYMMDD, prices as "137.400" (thousand VND per luong).
PNJ_HISTORY_URL = "https://edge-api.pnj.io/ecom-frontend/v1/get-gold-price-history?zone=00&date={ymd}"
PNJ_RING_NAME = "Nhẫn Trơn PNJ 999.9"  # same product as N24K (tensp)

CITIES = [
    {"name": "TP.HCM", "lat": 10.8231, "lon": 106.6297},
    {"name": "Hà Tĩnh", "lat": 18.3428, "lon": 105.9057},
]
OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
    "&current=weather_code&daily=temperature_2m_max,temperature_2m_min"
    "&timezone=Asia%2FHo_Chi_Minh&forecast_days=1"
)

# News sections, in EPUB order. "file" is the EPUB page; "lang" "en" items go through Gemini.
# Feeds are RSS 2.0 or Atom. "date_only": the feed gives a date without a time (see news.collect).
NEWS_SECTIONS = [
    {"file": "tin-ai", "title": "Tin AI", "lang": "en", "max": 5, "feeds": [
        {"source": "MIT Technology Review", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed"},
        {"source": "TechCrunch", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
        {"source": "The Verge", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    ]},
    {"file": "hang-ai", "title": "Anthropic, Google", "lang": "en", "max": 5, "feeds": [
        # Anthropic publishes no RSS (checked 14/11/2026). This is a community feed scraped from
        # anthropic.com/news; it may stop updating.
        {"source": "Anthropic", "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
         "date_only": True},
        {"source": "Google", "url": "https://blog.google/technology/ai/rss/"},
        {"source": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml"},
    ]},
    {"file": "kinh-te-vn", "title": "Kinh tế Việt Nam", "lang": "vi", "max": 5, "feeds": [
        {"source": "VnExpress", "url": "https://vnexpress.net/rss/kinh-doanh.rss"},
    ]},
    {"file": "kinh-te-tg", "title": "Kinh tế thế giới", "lang": "en", "max": 3, "feeds": [
        {"source": "CNBC", "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html"},
        {"source": "BBC", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    ]},
]
NEWS_HEADLINE_SECTION = "tin-ai"  # only this section goes to brief.json (sleep screen)
NEWS_MAX = 5  # default for news.select
NEWS_WINDOW_HOURS = 24
NEWS_TITLE_MAX = 90
NEWS_SUMMARY_MAX = 300

# Optional translation (secret GOOGLE_API_KEY). Free tier of the Gemini API needs no billing.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_TIMEOUT = 60

BRIEF_MAX_BYTES = 4096  # firmware reads up to 8 KB; keep headroom
EVENT_TITLE_MAX = 60
EVENTS_MAX = 6

GOLD_PERIODS = {"d1m": 30, "d3m": 91, "d1y": 365}  # brief.json keys known by the firmware: days back
GOLD_TOLERANCE_DAYS = 7  # a reference record may be up to this many days older than the target
# EPUB comparison points: (label, days back, tolerance). 1 week uses 2 days: with 7 a record
# from 14 days ago would be shown as "1 week"; 2 still covers Sundays and one missed run.
GOLD_EPUB_PERIODS = [("1 tuần", 7, 2), ("1 tháng", 30, 7), ("3 tháng", 91, 7), ("6 tháng", 182, 7), ("12 tháng", 365, 7)]

# Vietcombank rates JSON (found 14/11/2026). A weekend or holiday date returns the last
# published rates; a future date returns Count 0.
VCB_FX_URL = "https://www.vietcombank.com.vn/api/exchangerates?date={ymd}"
FX_CODES = ["USD", "EUR", "JPY"]
FX_COMPARE_DAYS = 91  # "3 months ago", same span as the gold 3-month point
# Fuel: product name exactly as the page writes it. Plain RON 95 is no longer sold; E10 RON 95
# "Mức 3" is Petrolimex RON 95-III.
FUEL_URL = "https://giaxanghomnay.com/"
FUEL_PRODUCT = "Xăng E10 RON 95 Mức 3"
EPUB_KEEP = 7
