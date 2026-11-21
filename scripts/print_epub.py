"""Print the text of an EPUB, page by page in spine order, with a heading per page.

Usage: python scripts/print_epub.py <file.epub>
Stdlib only. Meant for reading the morning brief in a terminal or a Claude session.
"""
import posixpath
import re
import sys
import zipfile
from html import unescape
from xml.etree import ElementTree as ET

NS_C = "{urn:oasis:names:tc:opendocument:xmlns:container}"
NS_O = "{http://www.idpf.org/2007/opf}"
NS_N = "{http://www.daisy.org/z3986/2005/ncx/}"


def _text(xhtml):
    s = re.sub(r"(?is)<(script|style).*?</\1>", "", xhtml)
    s = re.sub(r"(?i)</(p|h[1-6]|li|div|tr|table)>|<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</t[dh]>", "\t", s)
    s = unescape(re.sub(r"<[^>]+>", "", s))
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in s.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def main(path):
    with zipfile.ZipFile(path) as z:
        rootfile = ET.fromstring(z.read("META-INF/container.xml")).find(".//%srootfile" % NS_C).get("full-path")
        opf = ET.fromstring(z.read(rootfile))
        base = posixpath.dirname(rootfile)
        manifest = {i.get("id"): i.get("href") for i in opf.iter(NS_O + "item")}
        labels = {}
        ncx_href = manifest.get("ncx")
        if ncx_href:
            ncx = ET.fromstring(z.read(posixpath.join(base, ncx_href)))
            for p in ncx.iter(NS_N + "navPoint"):
                src = p.find(NS_N + "content").get("src").split("#")[0]
                labels[src] = p.find(NS_N + "navLabel/" + NS_N + "text").text
        for ref in opf.iter(NS_O + "itemref"):
            href = manifest[ref.get("idref")]
            body = z.read(posixpath.join(base, href)).decode("utf-8")
            print("=" * 8, labels.get(href, href), "(%s)" % href, "=" * 8)
            print(_text(body))
            print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
