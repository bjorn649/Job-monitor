#!/usr/bin/env python3
"""
Freelance Job Monitor v3
"""

import json
import os
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s"
)
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
SEEN_FILE = ROOT / "seen_jobs.json"
CONFIG_FILE = ROOT / "config.yaml"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
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


SKIP = [
    "/login", "/register", "/contact",
    "/over-ons", "/about", "javascript:",
    "mailto:", "#",
]


def scrape_all_links(site_name, url, base_url, keywords):
    jobs = []
    try:
        log.info(f"  Fetching {url}")
        resp = SESSION.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        all_links = soup.find_all("a", href=True)
        log.info(f"  Found {len(all_links)} total links")

        seen_urls = set()
        for link in all_links:
            href = link["href"]
            if not href or href == "#":
                continue
            if href.startswith("javascript"):
                continue
            if not href.startswith("http"):
                href = (
                    base_url.rstrip("/")
                    + "/"
                    + href.lstrip("/")
                )

            title = link.get_text(strip=True)
            combined = f"{title} {href}".lower()

            if not has_keyword(combined, keywords):
                continue
            if len(title) < 5:
                slug = href.split("/")[-1]
                title = slug.replace("-", " ").title()
            if href in seen_urls:
                continue
            seen_urls.add(href)

            if any(p in href.lower() for p in SKIP):
                continue

            jobs.append({
                "title": title,
                "url": href,
                "site": site_name,
            })
            log.info(f"    HIT: {title[:80]}")

    except Exception as e:
        log.warning(
            f"  Error scraping {site_name}: {e}"
        )

    log.info(f"  {len(jobs)} job(s) from {site_name}")
    return jobs


def scrape_site(name, base_url, paths, keywords):
    all_jobs = []
    seen_urls = set()
    for kw in keywords:
        for tmpl in paths:
            url = tmpl.replace(
                "{kw}", quote_plus(kw)
            )
            jobs = scrape_all_links(
                name, url, base_url, keywords
            )
            for j in jobs:
                if j["url"] not in seen_urls:
                    seen_urls.add(j["url"])
                    all_jobs.append(j)
    return all_jobs


SITES = {
    "freelance_nl": {
        "name": "Freelance.nl",
        "base": "https://www.freelance.nl",
        "paths": [
            "https://www.freelance.nl"
            "/opdrachten"
            "?query={kw}&sort=date",
        ],
    },
    "malt_nl": {
        "name": "Malt.nl",
        "base": "https://www.malt.nl",
        "paths": [],
    },
    "yacht": {
        "name": "Yacht.nl",
        "base": "https://www.yacht.nl",
        "paths": [
            "https://www.yacht.nl"
            "/vacatures"
            "?query={kw}",
        ],
    },
    "brunel": {
        "name": "Brunel",
        "base": "https://www.brunel.net",
        "paths": [
            "https://www.brunel.net"
            "/nl-nl/vacatures"
            "?query={kw}",
        ],
    },
    "between": {
        "name": "Between.nl",
        "base": "https://www.between.nl",
        "paths": [
            "https://www.between.nl"
            "/opdrachten"
            "?search={kw}",
        ],
    },
    "quest4": {
        "name": "Quest4.nl",
        "base": "https://www.quest4.nl",
        "paths": [
            "https://www.quest4.nl"
            "/opdrachten"
            "?q={kw}",
        ],
    },
    "headfirst": {
        "name": "HeadFirst",
        "base": "https://www.headfirst.group",
        "paths": [
            "https://www.headfirst.group"
            "/opdrachten"
            "?q={kw}",
        ],
    },
    "striive": {
        "name": "Striive",
        "base": "https://www.striive.com",
        "paths": [
            "https://www.striive.com"
            "/opdrachten"
            "?q={kw}",
        ],
    },
    "freep": {
        "name": "Freep.nl",
        "base": "https://www.freep.nl",
        "paths": [],
    },
    "flextender": {
        "name": "Flextender",
        "base": "https://www.flextender.nl",
        "paths": [
            "https://www.flextender.nl"
            "/opdrachten"
            "?q={kw}",
        ],
    },
    "tenderned": {
        "name": "TenderNed",
        "base": "https://www.tenderned.nl",
        "paths": [
            "https://www.tenderned.nl"
            "/aankondigingen/overzicht"
            "/aankondigingen"
            "?q={kw}&sort=date",
        ],
    },
}


def create_github_issue(new_jobs):
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        token = os.environ.get(
            "GITHUB_TOKEN", ""
        )
    repo = os.environ.get(
        "GITHUB_REPOSITORY", ""
    )

    if not token or not repo:
        log.error("No token/repo — logging only")
        for j in new_jobs:
            log.info(
                f"  NEW: [{j['site']}] "
                f"{j['title']} — {j['url']}"
            )
        return

    now = datetime.now(timezone.utc).strftime(
        "%d-%m-%Y %H:%M UTC"
    )

    body = (
        f"## {len(new_jobs)} nieuwe opdracht(en)\n"
        f"*Scan: {now}*\n\n"
        "| Platform | Opdracht |\n|---|---|\n"
    )
    for j in new_jobs:
        body += (
            f"| {j['site']} "
            f"| [{j['title']}]({j['url']}) |\n"
        )
    body += "\n---\n*Freelance Job Monitor*"

    title = (
        f"{len(new_jobs)} nieuwe opdracht(en)"
        f" — {now}"
    )

    api_url = (
        "https://api.github.com"
        f"/repos/{repo}/issues"
    )

    try:
        resp = requests.post(
            api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": (
                    "application/vnd.github+json"
                ),
            },
            json={
                "title": title,
                "body": body,
            },
            timeout=30,
        )
        if resp.status_code == 201:
            issue_url = resp.json().get(
                "html_url", "OK"
            )
            log.info(f"Issue created: {issue_url}")
        else:
            log.error(
                f"Issue failed: "
                f"{resp.status_code} "
                f"{resp.text[:200]}"
            )
    except Exception as e:
        log.error(f"Error creating issue: {e}")


def main():
    config = load_config()
    keywords = config.get(
        "keywords",
        ["scrum master", "agile coach"],
    )
    enabled = config.get(
        "sites", list(SITES.keys())
    )

    log.info(f"Keywords: {keywords}")
    log.info(f"Sites: {enabled}")

    seen = load_seen()
    all_new = []

    for key in enabled:
        cfg = SITES.get(key)
        if not cfg:
            log.warning(f"Unknown: {key}")
            continue

        if not cfg["paths"]:
            log.info(f"Skipping {key} (blocked)")
            continue

        log.info(f"Scanning {key}...")
        jobs = scrape_site(
            cfg["name"],
            cfg["base"],
            cfg["paths"],
            keywords,
        )

        for job in jobs:
            jid = job_id(job["url"], job["title"])
            if jid not in seen:
                seen[jid] = {
                    "title": job["title"],
                    "url": job["url"],
                    "site": job["site"],
                    "first_seen": (
                        datetime.now(timezone.utc)
                        .isoformat()
                    ),
                }
                all_new.append(job)

    log.info(f"Total new: {len(all_new)}")

    if all_new:
        create_github_issue(all_new)
    else:
        log.info("No new jobs.")

    cutoff = (
        datetime.now(timezone.utc).timestamp()
        - (90 * 86400)
    )
    pruned = {}
    for jid, data in seen.items():
        try:
            ts = datetime.fromisoformat(
                data["first_seen"]
            ).timestamp()
            if ts > cutoff:
                pruned[jid] = data
        except (KeyError, ValueError):
            pruned[jid] = data
    seen = pruned

    save_seen(seen)
    log.info(f"Database: {len(seen)} jobs tracked")


if __name__ == "__main__":
    main()
