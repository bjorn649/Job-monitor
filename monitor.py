#!/usr/bin/env python3
"""
Freelance Job Monitor v3 — betere scraping + API-based issues
"""

import json
import os
import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
SEEN_FILE = ROOT / "seen_jobs.json"
CONFIG_FILE = ROOT / "config.yaml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_seen():
    if SEEN_FILE.exists():
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, indent=2, ensure_ascii=False)


def job_id(url, title):
    raw = f"{url.strip().lower()}|{title.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def has_keyword(text, keywords):
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def scrape_all_links(site_name, url, base_url, keywords):
    """Broad approach: grab ALL links from the page, keep those with a keyword in title or URL."""
    jobs = []
    try:
        log.info(f"  Fetching {url}")
        resp = SESSION.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        all_links = soup.find_all("a", href=True)
        log.info(f"  Found {len(all_links)} total links on page")

        seen_urls = set()
        for link in all_links:
            href = link["href"]
            if not href or href == "#" or href.startswith("javascript"):
                continue
            if not href.startswith("http"):
                href = base_url.rstrip("/") + "/" + href.lstrip("/")

            title = link.get_text(strip=True)
            combined = f"{title} {href}".lower()

            if not has_keyword(combined, keywords):
                continue
            if len(title) < 5:
                title = href.split("/")[-1].replace("-", " ").title()
            if href in seen_urls:
                continue
            seen_urls.add(href)

            # Skip obvious navigation links
            skip_patterns = ["/login", "/register", "/contact", "/over-ons", "/about", "javascript:", "mailto:", "#"]
            if any(p in href.lower() for p in skip_patterns):
                continue

            jobs.append({"title": title, "url": href, "site": site_name})
            log.info(f"    HIT: {title[:80]} -> {href[:100]}")

    except Exception as e:
        log.warning(f"  Error scraping {site_name}: {e}")

    log.info(f"  {len(jobs)} job(s) found on {site_name}")
    return jobs


def scrape_site(site_name, base_url, search_paths, keywords):
    """Scrape a site using keyword-based search URLs."""
    all_jobs = []
    seen_urls = set()
    for kw in keywords:
        for path_template in search_paths:
            url = path_template.format(kw=quote_plus(kw))
            jobs = scrape_all_links(site_name, url, base_url, keywords)
            for j in jobs:
                if j["url"] not in seen_urls:
                    seen_urls.add(j["url"])
                    all_jobs.append(j)
    return all_jobs


# Site configurations: name, base_url, search URL templates
SITE_CONFIGS = {
    "freelance_nl": {
        "name": "Freelance.nl",
        "base_url": "https://www.freelance.nl",
        "search_paths": [
            "https://www.freelance.nl/opdrachten?query={kw}&sort=date",
        ],
    },
    "malt_nl": {
        "name": "Malt.nl",
        "base_url": "https://www.malt.nl",
        "search_paths": [],  # 403 blocked
    },
    "yacht": {
        "name": "Yacht.nl",
        "base_url": "https://www.yacht.nl",
        "search_paths": [
            "https://www.yacht.nl/vacatures?query={k
