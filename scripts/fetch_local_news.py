#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

URL = "https://www.infranken.de/lk/bamberg/"
OUT = "local-news.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; KitchenDashboard/1.0; +https://github.com/)"
}

def clean_text(text):
    return re.sub(r"\s+", " ", (text or "")).strip()

def likely_article(title, href):
    if not title or len(title) < 22:
        return False
    low = title.lower()
    blocked = (
        "mehr anzeigen", "weitere artikel", "mehr nachrichten", "mehr ft anzeigen",
        "newsletter", "podcast", "ticketshop", "jobs in", "immobilien",
        "partnersuche", "veranstaltungskalender", "tankpreise im raum bamberg"
    )
    if any(x in low for x in blocked):
        return False

    host = urlparse(href).netloc.lower()
    return host.endswith("infranken.de") or host.endswith("fraenkischertag.de")

def source_name(href):
    host = urlparse(href).netloc.lower()
    if "fraenkischertag.de" in host:
        return "Fränkischer Tag"
    return "inFranken · Bamberg"

def score(item):
    s = 0
    if item["source"] == "Fränkischer Tag":
        s += 20
    title_low = item["title"].lower()
    if "bamberg" in title_low or "bamberger" in title_low:
        s += 8
    for place in ("bischberg", "hallstadt", "hirschaid", "gaustadt", "scheßlitz",
                  "schlüsselfeld", "memmelsdorf", "buttenheim", "viereth", "strullendorf"):
        if place in title_low:
            s += 5
    s -= item["order"] * 0.02
    return s

def main():
    r = requests.get(URL, headers=HEADERS, timeout=25)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    candidates = []
    seen_links = set()
    seen_titles = set()

    for order, a in enumerate(soup.find_all("a", href=True)):
        title = clean_text(a.get_text(" ", strip=True))
        href = urljoin(URL, a["href"])

        if not likely_article(title, href):
            continue

        # Avoid navigation/category pages
        path = urlparse(href).path.lower()
        if path.rstrip("/") in (
            "/lk/bamberg", "/lk/bamberg/uebersicht", "/ort/bamberg"
        ):
            continue

        key_title = title.lower()
        if href in seen_links or key_title in seen_titles:
            continue

        seen_links.add(href)
        seen_titles.add(key_title)

        candidates.append({
            "title": title,
            "link": href,
            "source": source_name(href),
            "order": order
        })

    candidates.sort(key=score, reverse=True)

    # Aim for a useful mix: up to 3 FT + at least 2 local inFranken if available
    ft = [x for x in candidates if x["source"] == "Fränkischer Tag"][:3]
    inf = [x for x in candidates if x["source"] != "Fränkischer Tag"][:5]

    selected = []
    for item in ft:
        selected.append(item)
    for item in inf:
        if len(selected) >= 5:
            break
        selected.append(item)

    # Fallback to any candidates if the source mix is sparse
    if len(selected) < 5:
        for item in candidates:
            if item not in selected:
                selected.append(item)
            if len(selected) >= 5:
                break

    for item in selected:
        item.pop("order", None)
        item["time"] = ""

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_page": URL,
        "items": selected[:5]
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(payload['items'])} items to {OUT}")
    for item in payload["items"]:
        print(f"- [{item['source']}] {item['title']}")

if __name__ == "__main__":
    main()
