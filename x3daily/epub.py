"""Build the daily EPUB ("Báo sáng") with zipfile only. EPUB 2 layout: OPF + NCX, one TOC entry per file.

Gold history is written as plain lines, not a <table>: CrossVi flattens tables and
prints "Tab Row N, Cell M:" before each cell.
The EPUB never contains calendar data.
"""
import uuid
import zipfile
from xml.sax.saxutils import escape, quoteattr

from .config import GOLD_TABLE_DAYS
from .gold import to_million_per_luong
from .vi import fmt_date_long, fmt_decimal

CSS = "body{line-height:1.5}h1{font-size:1.4em}h2{font-size:1.15em}p{margin:0.4em 0}.small{font-size:0.85em}"


def _page(title, body):
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="vi"><head><title>%s</title>'
        '<link rel="stylesheet" type="text/css" href="style.css"/></head><body>%s</body></html>\n'
    ) % (escape(title), body)


def _weather_page(day, weather):
    body = "<h1>Báo sáng</h1><p>%s</p><h2>Thời tiết</h2>" % escape(fmt_date_long(day))
    if weather:
        body += "".join("<p><b>%s</b>: %s, %s</p>" % (escape(w["city"]), escape(w["now"]), escape(w["range"]))
                        for w in weather)
    else:
        body += "<p>Không có dữ liệu thời tiết.</p>"
    return _page("Thời tiết", body)


def _gold_page(day, price, hist, block):
    body = "<h1>Giá vàng nhẫn 9999</h1>"
    if price:
        body += "<p>Hôm nay: mua <b>%s</b>, bán <b>%s</b> (triệu đồng/lượng).</p>" % (block["buy"], block["sell"])
        chg = [("1 tháng", "d1m"), ("3 tháng", "d3m"), ("1 năm", "d1y")]
        parts = ["%s %s" % (label, block[k]) for label, k in chg if k in block]
        if parts:
            body += "<p>So với: %s.</p>" % escape("; ".join(parts))
    else:
        body += "<p>Không có giá hôm nay.</p>"
    rows = sorted((d for d in hist if (day - d).days < GOLD_TABLE_DAYS and d <= day), reverse=True)
    if rows:
        body += "<h2>%d ngày gần nhất</h2>" % GOLD_TABLE_DAYS
        for d in rows:
            p = hist[d]
            body += "<p>%02d/%02d: mua %s, bán %s</p>" % (
                d.day, d.month, fmt_decimal(to_million_per_luong(p.buy)), fmt_decimal(to_million_per_luong(p.sell)))
    return _page("Giá vàng", body)


def _news_page(news):
    body = "<h1>Tin AI</h1>"
    if not news:
        body += "<p>Không có tin mới trong 24 giờ qua.</p>"
    for item, title, summary, translated in news:
        body += "<h2>%s%s</h2>" % (escape(title), "" if translated else " (chưa dịch)")
        if summary:
            body += "<p>%s</p>" % escape(summary)
        body += '<p class="small">%s. <a href=%s>%s</a></p>' % (
            escape(item.source), quoteattr(item.link), escape(item.link))
    return _page("Tin AI", body)


def _quote_page(quote):
    body = "<h1>Châm ngôn</h1>"
    if quote:
        body += "<p>%s</p>" % escape(quote["text"])
        if quote.get("by"):
            body += "<p>— %s</p>" % escape(quote["by"])
    return _page("Châm ngôn", body)


def build(path, day, weather, price, hist, gold_block, news, quote):
    """Write the EPUB to `path`. `news` is a list of (Item, title, summary, translated)."""
    pages = [
        ("thoi-tiet.xhtml", "Thời tiết", _weather_page(day, weather)),
        ("vang.xhtml", "Giá vàng", _gold_page(day, price, hist, gold_block)),
        ("tin-ai.xhtml", "Tin AI", _news_page(news)),
        ("cham-ngon.xhtml", "Châm ngôn", _quote_page(quote)),
    ]
    title = "Báo sáng %02d/%02d/%d" % (day.day, day.month, day.year)
    uid = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "x3-daily/" + day.isoformat()))
    manifest = "".join('<item id="p%d" href="%s" media-type="application/xhtml+xml"/>' % (i, f)
                       for i, (f, _, _) in enumerate(pages))
    spine = "".join('<itemref idref="p%d"/>' % i for i in range(len(pages)))
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uid">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>%s</dc:title><dc:language>vi</dc:language><dc:identifier id=\"uid\">%s</dc:identifier>"
        "<dc:creator>x3-daily</dc:creator><dc:date>%s</dc:date></metadata>"
        '<manifest><item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
        '<item id="css" href="style.css" media-type="text/css"/>%s</manifest>'
        '<spine toc="ncx">%s</spine></package>\n'
    ) % (escape(title), uid, day.isoformat(), manifest, spine)
    points = "".join(
        '<navPoint id="n%d" playOrder="%d"><navLabel><text>%s</text></navLabel><content src="%s"/></navPoint>'
        % (i, i + 1, escape(label), f) for i, (f, label, _) in enumerate(pages))
    ncx = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head>'
        '<meta name="dtb:uid" content="%s"/><meta name="dtb:depth" content="1"/>'
        '<meta name="dtb:totalPageCount" content="0"/><meta name="dtb:maxPageNumber" content="0"/></head>'
        "<docTitle><text>%s</text></docTitle><navMap>%s</navMap></ncx>\n"
    ) % (uid, escape(title), points)
    container = (
        '<?xml version="1.0"?>\n<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
        "</rootfiles></container>\n"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for name, data in [("META-INF/container.xml", container), ("OEBPS/content.opf", opf),
                           ("OEBPS/toc.ncx", ncx), ("OEBPS/style.css", CSS)] + \
                          [("OEBPS/" + f, html) for f, _, html in pages]:
            z.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
