#!/usr/bin/env python3
"""
Freelance Job Monitor v4 — Google Search approach
"""

import json
import os
import hashlib
import logging
import time
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

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


def clean_google_url(href):
    """Extract real URL from Google redirect."""
    if "/url?" in href:
        parsed = parse_qs(urlparse(href).query)
        if "q" in parsed:
            return parsed["q"][0]
        if "url" in parsed:
            return parsed["url"][0]
    if href.startswith("http") and "google" not in href:
        return href
    return None


def google_search(query, num_results=10):
    """Search Google and return list of {title, url}."""
    results = []
    params = {
        "q": query,
        "num": num_results,
        "hl": "nl",
        "gl": "nl",
    }

    try:
        url = "https://www.google.com/search"
        log.info(f"  Google: {query}")
        resp = SESSION.get(
            url, params=params, timeout=30
        )

        if resp.status_code == 429:
            log.warning("  Google rate limited (429)")
            return results
        if resp.status_code != 200:
            log.warning(
                f"  Google status: {resp.status_code}"
            )
            return results

        soup = BeautifulSoup(resp.text, "html.parser")

        for div in soup.find_all("div", class_="g"):
            a_tag = div.find("a", href=True)
            if not a_tag:
                continue

            href = clean_google_url(a_tag["href"])
            if not href:
                continue

            h3 = a_tag.find("h3")
            if h3:
                title = h3.get_text(strip=True)
            else:
                title = a_tag.get_text(strip=True)

            if not title or len(title) < 5:
                continue

            results.append({
                "title": title,
                "url": href,
            })

        if not results:
            for a_tag in soup.find_all("a", href=True):
                href = clean_google_url(a_tag["href"])
                if not href:
                    continue
                if "google" in href:
                    continue

                h3 = a_tag.find("h3")
                if not h3:
                    continue
                title = h3.get_text(strip=True)
                if not title or len(title) < 5:
                    continue

                results.append({
                    "title": title,
                    "url": href,
                })

    except Exception as e:
        log.warning(f"  Google error: {e}")

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


def search_site(site_key, domain, keywords):
    """Search Google for jobs on a specific site."""
    all_jobs = []
    seen_urls = set()

    for kw in keywords:
        query = f'site:{domain} "{kw}"'
        results = google_search(query)

        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_jobs.append({
                    "title": r["title"],
                    "url": r["url"],
                    "site": domain,
                })

        delay = random.uniform(2, 5)
        time.sleep(delay)

    return all_jobs


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
        "sites", list(SITE_DOMAINS.keys())
    )

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
        jobs = search_site(
            site_key, domain, keywords
        )
        log.info(
            f"  {len(jobs)} result(s) from {domain}"
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
