"""Daily quote from quotes.txt (`text | author` per line)."""
from datetime import date


def load(path):
    quotes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        text, sep, by = line.rpartition("|")
        if not sep:
            text, by = line, ""
        quotes.append({"text": text.strip(), "by": by.strip()})
    return quotes


def pick(quotes, day):
    """Stable for a given date: same day, same quote; consecutive days rotate."""
    if not quotes:
        return None
    q = quotes[day.toordinal() % len(quotes)]
    return {"text": q["text"], "by": q["by"]} if q["by"] else {"text": q["text"]}
