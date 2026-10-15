#!/usr/bin/env python3
"""Fetch public RSS feeds into a static JSON cache for the GitHub Pages site."""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "news.json"
USER_AGENT = "DeKoderDigitalNews/1.0 (+https://ytforestarmy.github.io/dekoderdigital/)"
DEFAULT_IMAGE = "https://images.unsplash.com/photo-1504711432869-efd597cdd045?auto=format&fit=crop&w=900&q=80"

FEEDS = [
    ("India", "Google News India", "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"),
    ("India", "BBC News", "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml"),
    ("India", "NDTV", "https://feeds.feedburner.com/ndtvnews-top-stories"),
    ("India", "The Hindu", "https://www.thehindu.com/news/national/feeder/default.rss"),
    ("India", "Indian Express", "https://indianexpress.com/section/india/feed/"),
    ("World", "Google News World", "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en"),
    ("World", "BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("World", "The Guardian World", "https://www.theguardian.com/world/rss"),
]


def text(value: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def child_value(item: ET.Element, names: tuple[str, ...]) -> str:
    for child in item:
        tag = child.tag.rsplit("}", 1)[-1].lower()
        if tag in names and child.text:
            return text(child.text)
    return ""


def image_from(item: ET.Element, description: str) -> str:
    for child in item.iter():
        tag = child.tag.rsplit("}", 1)[-1].lower()
        if tag in {"thumbnail", "content", "enclosure"}:
            url = child.attrib.get("url") or child.attrib.get("href") or child.attrib.get("resource")
            if url and url.startswith(("http://", "https://")):
                return url
    match = re.search(r'<img[^>]+(?:src|url)=["\']([^"\']+)', description, re.I)
    return match.group(1) if match else DEFAULT_IMAGE


def clean_title(title: str, source: str) -> str:
    suffix = f" - {source}"
    return title[:-len(suffix)].strip() if title.endswith(suffix) else title


def fetch_feed(region: str, source: str, url: str) -> list[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())
    articles: list[dict] = []
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1].lower() not in {"item", "entry"}:
            continue
        title = child_value(item, ("title",))
        link = child_value(item, ("link",))
        if not link:
            for child in item:
                if child.tag.rsplit("}", 1)[-1].lower() == "link":
                    link = child.attrib.get("href", "")
                    break
        description = child_value(item, ("description", "summary", "content", "encoded"))
        published = child_value(item, ("pubdate", "published", "updated", "date"))
        if title and link.startswith(("http://", "https://")):
            articles.append({
                "title": clean_title(title, source),
                "source": source,
                "link": link,
                "image": image_from(item, description),
                "region": region,
                "published": published,
            })
    return articles[:30]


def main() -> int:
    articles: list[dict] = []
    failures: list[str] = []
    for region, source, url in FEEDS:
        try:
            articles.extend(fetch_feed(region, source, url))
        except Exception as exc:  # Keep other publishers available if one feed changes.
            failures.append(f"{source}: {exc}")
    unique: dict[str, dict] = {}
    for article in articles:
        key = article["link"]
        if key not in unique:
            unique[key] = article
    result = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "articles": list(unique.values())[:200],
        "feedErrors": failures,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if result["articles"] or not OUTPUT.exists():
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Fetched {len(result['articles'])} articles from {len(FEEDS) - len(failures)}/{len(FEEDS)} feeds")
    if failures:
        print("Feed warnings:", *failures, sep="\n- ", file=sys.stderr)
    return 0 if result["articles"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
