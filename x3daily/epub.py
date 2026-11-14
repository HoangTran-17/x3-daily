"""Build the daily EPUB ("Báo sáng") with zipfile only. EPUB 2 layout: OPF + NCX, one TOC entry per file.

Gold points are written as plain lines, not a <table>: CrossVi flattens tables and
prints "Tab Row N, Cell M:" before each cell. Each point fits one line on the X3 screen.
The EPUB never contains calendar data.
"""
import uuid
import zipfile
from xml.sax.saxutils import escape

from .config import GOLD_EPUB_PERIODS
from .gold import change_vs, reference, to_million_per_luong
from .vi import fmt_date_long, fmt_decimal

# CrossVi already adds half a line after each block (extra paragraph spacing), so the
# EPUB adds no margins of its own. text-align:left stops justify from stretching short lines.
CSS = ("h1{font-size:1.3em;margin:0 0 0.3em}h2{font-size:1.1em;margin:0.6em 0 0.2em}"
       "p{margin:0;text-indent:0;text-align:left}")


def _page(title, body):
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="vi"><head><title>%s</title>'
        '<link rel="stylesheet" type="text/css" href="style.css"/></head><body>%s</body></html>\n'
    ) % (escape(title), body)


def _weather_html(day, weather):
    body = "<h1>Báo sáng</h1><p>%s</p><h2>Thời tiết</h2>" % escape(fmt_date_long(day))
    if weather:
        body += "".join("<p><b>%s</b>: %s, %s</p>" % (escape(w["city"]), escape(w["now"]), escape(w["range"]))
                        for w in weather)
    else:
        body += "<p>Không có dữ liệu thời tiết.</p>"
    return body


def _gold_html(day, price, hist, block):
    body = "<h2>Giá vàng nhẫn 9999</h2>"
    if price:
        body += "<p>Hôm nay: mua <b>%s</b>, bán <b>%s</b> (triệu/lượng)</p>" % (block["buy"], block["sell"])
    else:
        body += "<p>Không có giá hôm nay.</p>"
    body += "<h2>So với trước (% giá bán)</h2>" if price else "<h2>So với trước</h2>"
    for label, days, tol in GOLD_EPUB_PERIODS:
        ref = reference(hist, day, days, tol)
        if ref is None:
            body += "<p>%s: chưa có</p>" % escape(label)
            continue
        d, p = ref
        line = "%s (%02d/%02d): mua %s, bán %s" % (
            label, d.day, d.month, fmt_decimal(to_million_per_luong(p.buy)), fmt_decimal(to_million_per_luong(p.sell)))
        if price:
            line += ", %s" % change_vs(hist, day, days, price.sell, tol)
        body += "<p>%s</p>" % escape(line)
    return body


def _today_page(day, weather, price, hist, block):
    return _page("Thời tiết, giá vàng", _weather_html(day, weather) + _gold_html(day, price, hist, block))


def _news_page(news):
    body = "<h1>Tin AI</h1>"
    if not news:
        body += "<p>Không có tin mới trong 24 giờ qua.</p>"
    for item, title, summary, translated in news:
        body += "<h2>%s%s</h2>" % (escape(title), "" if translated else " (chưa dịch)")
        # The X3 cannot open links and long URLs overflow the line, so only the source name is shown.
        body += "<p>%s(%s)</p>" % (escape(summary) + " " if summary else "", escape(item.source))
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
        ("hom-nay.xhtml", "Thời tiết, giá vàng", _today_page(day, weather, price, hist, gold_block)),
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
