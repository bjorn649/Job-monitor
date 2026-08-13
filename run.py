#!/usr/bin/env python3
"""
Freelance Job Monitor v5 — DuckDuckGo Search
"""

import json
import os
import hashlib
import logging
import time
import random
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse, parse_qs

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
    "Chrome/126.0.0.0 Safari/537.36"
)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": UA,
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
})


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


def ddg_search(query):
    """Search DuckDuckGo HTML version."""
    results = []
    url = "https://html.duckduckgo.com/html/"

    try:
        log.info(f"  DDG: {query}")
        resp = SESSION.post(
            url,
            data={"q": query},
            timeout=30,
        )

        if resp.status_code != 200:
            log.warning(f"  DDG status: {resp.status_code}")
            return results

        soup = BeautifulSoup(resp.text, "html.parser")

        for result in soup.find_all("div", class_="result"):
            a_tag = result.find("a", class_="result__a")
            if not a_tag:
                continue

            href = a_tag.get("href", "")

            if "uddg=" in href:
                parsed = parse_qs(urlparse(href).query)
                if "uddg" in parsed:
                    href = parsed["uddg"][0]

            if not href.startswith("http"):
                continue
            if "duckduckgo.com" in href:
                continue

            title = a_tag.get_text(strip=True)
            if not title or len(title) < 5:
                continue

            results.append({
                "title": title,
                "url": href,
            })

    except Exception as e:
        log.warning(f"  DDG error: {e}")

    log.info(f"  Got {len(results)} results")
    return results


SITE_DOMAINS = {
    "freelance_nl": "freelance.nl",
    "yacht": "yacht.nl",
    "brunel": "brunel.net",
    "between": "between.nl",
    "quest4": "quest4.nl",
    "headfirst": "headfirst.group",
    "striive": "striive.com",
    "flextender": "flextender.nl",
    "tenderned": "tenderned.nl",
    "malt_nl": "malt.nl",
    "freep": "freep.nl",
}


def search_site(domain, keywords):
    """Search DDG for jobs on a specific site."""
    all_jobs = []
    seen_urls = set()

    for kw in keywords:
        query = f"site:{domain} {kw}"
        results = ddg_search(query)

        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_jobs.append({
                    "title": r["title"],
                    "url": r["url"],
                    "site": domain,
                })

        delay = random.uniform(3, 6)
        time.sleep(delay)

    return all_jobs


def create_github_issue(new_jobs):
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")

    if not token or not repo:
        log.error("No token/repo — logging only")
        for j in new_jobs:
            log.info(f"  NEW: [{j['site']}] {j['title']}")
        return

    now = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M UTC")

    body = f"## {len(new_jobs)} nieuwe opdracht(en)\n"
    body += f"*Scan: {now}*\n\n"
    body += "| Platform | Opdracht |\n|---|---|\n"
    for j in new_jobs:
        body += f"| {j['site']} | [{j['title']}]({j['url']}) |\n"
    body += "\n---\n*Freelance Job Monitor*"

    title = f"{len(new_jobs)} nieuwe opdracht(en) — {now}"

    api_url = f"https://api.github.com/repos/{repo}/issues"

    try:
        resp = requests.post(
            api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            json={"title": title, "body": body},
            timeout=30,
        )
        if resp.status_code == 201:
            log.info(f"Issue created: {resp.json().get('html_url', 'OK')}")
        else:
            log.error(f"Issue failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        log.error(f"Error creating issue: {e}")


def main():
    config = load_config()
    keywords = config.get("keywords", ["scrum master", "agile coach"])
    enabled = config.get("sites", list(SITE_DOMAINS.keys()))

    log.info(f"Keywords: {keywords}")
    log.info(f"Sites: {enabled}")

    seen = load_seen()
    all_new = []

    for site_key in enabled:
        domain = SITE_DOMAINS.get(site_key)
        if not domain:
            log.warning(f"Unknown: {site_key}")
            continue

        log.info(f"Scanning {domain}...")
        jobs = search_site(domain, keywords)
        log.info(f"  {len(jobs)} result(s) from {domain}")

        for job in jobs:
            jid = job_id(job["url"], job["title"])
            if jid not in seen:
                seen[jid] = {
                    "title": job["title"],
                    "url": job["url"],
                    "site": job["site"],
                    "first_seen": datetime.now(timezone.utc).isoformat(),
                }
                all_new.append(job)

    log.info(f"Total new: {len(all_new)}")

    if all_new:
        create_github_issue(all_new)
    else:
        log.info("No new jobs.")

    cutoff = datetime.now(timezone.utc).timestamp() - (90 * 86400)
    pruned = {}
    for jid, data in seen.items():
        try:
            ts = datetime.fromisoformat(data["first_seen"]).timestamp()
            if ts > cutoff:
                pruned[jid] = data
        except (KeyError, ValueError):
            pruned[jid] = data
    seen = pruned

    save_seen(seen)
    log.info(f"Database: {len(seen)} jobs tracked")


if __name__ == "__main__":
    main()
