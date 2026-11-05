"""Static OPDS 1.2 acquisition feed for the latest issues, plus recovery of older issues from Pages."""
import logging
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from . import net
from .config import EPUB_KEEP

log = logging.getLogger(__name__)

EPUB_RE = re.compile(r"^bao-sang-(\d{8})\.epub$")
ATOM = "{http://www.w3.org/2005/Atom}"


def epub_name(day):
    return "bao-sang-%s.epub" % day.strftime("%Y%m%d")


def issue_date(filename):
    m = EPUB_RE.match(filename)
    return datetime.strptime(m.group(1), "%Y%m%d").date() if m else None


def restore_previous(base_url, site_dir, fetch=None):
    """Download older issues listed in the live feed into site_dir (Pages deploys replace the whole site).

    Only the file name from the feed is used (matched against EPUB_RE); the host always comes
    from base_url. Any failure is ignored: the issue is simply lost.
    """
    fetch = fetch or net.get
    try:
        root = ET.fromstring(fetch(base_url + "opds.xml"))
    except Exception as e:
        log.warning("opds: previous feed not available (%s)", type(e).__name__)
        return
    for link in root.iter(ATOM + "link"):
        name = (link.get("href") or "").rsplit("/", 1)[-1]
        target = Path(site_dir) / name
        if not EPUB_RE.match(name) or target.exists():
            continue
        try:
            target.write_bytes(fetch(base_url + name, max_bytes=20_000_000))
        except Exception as e:
            log.warning("opds: cannot restore %s (%s)", name, type(e).__name__)


def prune(site_dir, keep=EPUB_KEEP):
    """Keep the newest `keep` issues, delete the rest. Returns the kept file names, newest first."""
    names = sorted((p.name for p in Path(site_dir).iterdir() if EPUB_RE.match(p.name)), reverse=True)
    for n in names[keep:]:
        (Path(site_dir) / n).unlink()
    return names[:keep]


def build_feed(base_url, site_dir, names, now, href_suffix="", feed_name="opds.xml"):
    updated = now.isoformat(timespec="seconds")
    feed_href = base_url + feed_name + href_suffix
    entries = ""
    for n in names:
        d = issue_date(n)
        size = (Path(site_dir) / n).stat().st_size
        entries += (
            "<entry><title>Báo sáng %02d/%02d/%d</title><id>urn:uuid:%s</id><updated>%sT04:00:00+07:00</updated>"
            "<dc:language>vi</dc:language><content type=\"text\">Thời tiết, giá vàng, tin AI, châm ngôn.</content>"
            "<link rel=\"http://opds-spec.org/acquisition\" href=%s type=\"application/epub+zip\" length=\"%d\"/>"
            "</entry>"
        ) % (d.day, d.month, d.year, uuid.uuid5(uuid.NAMESPACE_URL, "x3-daily/" + n), d.isoformat(),
             quoteattr(base_url + n + href_suffix), size)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/terms/" '
        'xmlns:opds="http://opds-spec.org/2010/catalog">'
        "<id>urn:x3-daily:bao-sang</id><title>Báo sáng</title><updated>%s</updated>"
        "<author><name>x3-daily</name></author>"
        '<link rel="self" href=%s type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>'
        '<link rel="start" href=%s type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>'
        "%s</feed>\n"
    ) % (escape(updated), quoteattr(feed_href), quoteattr(feed_href), entries)
