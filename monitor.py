#!/usr/bin/env python3
"""
Freelance Job Monitor
Checks Dutch freelance platforms for Scrum Master / Agile Coach roles.
"""

import json
import os
import hashlib
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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


def matches_keywords(text, keywords):
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def scrape_generic_search(site_name, search_url, link_selector,
                          title_attr="text", base_url="",
                          keywords=None):
    jobs = []
    try:
        log.info(f"  Fetching {search_url}")
        resp = SESSION.get(search_url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.select(link_selector)
        log.info(f"  Found {len(links)} raw links")

        for link in links:
            href = link.get("href", "")
            if not href or href == "#":
                continue
            if not href.startswith("http"):
                href = base_url.rstrip("/") + "/" + href.lstrip("/")

            title = link.get_text(strip=True) if title_attr == "text" else link.get(title_attr, "")
            if not title:
                title = href

            if keywords and not matches_keywords(title, keywords):
                continue

            jobs.append({"title": title, "url": href, "site": site_name})
    except Exception as e:
        log.warning(f"  Error scraping {site_name}: {e}")
    return jobs


def scrape_freelance_nl(keywords):
    all_jobs = []
    for kw in keywords:
        url = f"https://www.freelance.nl/opdrachten?query={quote_plus(kw)}&sort=date"
        jobs = scrape_generic_search("Freelance.nl", url,
            link_selector="a.project-title, a[class*='title'], h2 a, h3 a",
            base_url="https://www.freelance.nl")
        all_jobs.extend(jobs)
    return all_jobs


def scrape_malt_nl(keywords):
    all_jobs = []
    for kw in keywords:
        url = f"https://www.malt.nl/s?q={quote_plus(kw)}"
        jobs = scrape_generic_search("Malt.nl", url,
            link_selector="a[href*='/project/'], a[href*='/profile/']",
            base_url="https://www.malt.nl", keywords=keywords)
        all_jobs.extend(jobs)
    return all_jobs


def scrape_yacht(keywords):
    all_jobs = []
    for kw in keywords:
        url = f"https://www.yacht.nl/vacatures?q={quote_plus(kw)}"
        jobs = scrape_generic_search("Yacht.nl", url,
            link_selector="a[href*='/vacatures/'], a[href*='/vacancy/']",
            base_url="https://www.yacht.nl", keywords=keywords)
        all_jobs.extend(jobs)
    return all_jobs


def scrape_brunel(keywords):
    all_jobs = []
    for kw in keywords:
        url = f"https://www.brunel.net/nl-nl/vacatures?query={quote_plus(kw)}"
        jobs = scrape_generic_search("Brunel", url,
            link_selector="a[href*='/vacatures/'], a[href*='vacancy']",
            base_url="https://www.brunel.net", keywords=keywords)
        all_jobs.extend(jobs)
    return all_jobs


def scrape_between(keywords):
    all_jobs = []
    for kw in keywords:
        url = f"https://www.between.nl/opdrachten?search={quote_plus(kw)}"
        jobs = scrape_generic_search("Between.nl", url,
            link_selector="a[href*='/opdracht'], a[href*='/assignment']",
            base_url="https://www.between.nl", keywords=keywords)
        all_jobs.extend(jobs)
    return all_jobs


def scrape_quest4(keywords):
    all_jobs = []
    for kw in keywords:
        url = f"https://www.quest4.nl/opdrachten?q={quote_plus(kw)}"
        jobs = scrape_generic_search("Quest4.nl", url,
            link_selector="a[href*='/opdracht']",
            base_url="https://www.quest4.nl", keywords=keywords)
        all_jobs.extend(jobs)
    return all_jobs


def scrape_headfirst(keywords):
    all_jobs = []
    for kw in keywords:
        url = f"https://www.headfirst.group/opdrachten?search={quote_plus(kw)}"
        jobs = scrape_generic_search("HeadFirst", url,
            link_selector="a[href*='/opdracht']",
            base_url="https://www.headfirst.group", keywords=keywords)
        all_jobs.extend(jobs)
    return all_jobs


def scrape_striive(keywords):
    all_jobs = []
    for kw in keywords:
        url = f"https://www.striive.com/opdrachten?q={quote_plus(kw)}"
        jobs = scrape_generic_search("Striive", url,
            link_selector="a[href*='/opdracht']",
            base_url="https://www.striive.com", keywords=keywords)
        all_jobs.extend(jobs)
    return all_jobs


def scrape_freep(keywords):
    all_jobs = []
    for kw in keywords:
        url = f"https://www.freep.nl/opdrachten?search={quote_plus(kw)}"
        jobs = scrape_generic_search("Freep.nl", url,
            link_selector="a[href*='/opdracht']",
            base_url="https://www.freep.nl", keywords=keywords)
        all_jobs.extend(jobs)
    return all_jobs


def scrape_flextender(keywords):
    all_jobs = []
    for kw in keywords:
        url = f"https://www.flextender.nl/opdrachten?q={quote_plus(kw)}"
        jobs = scrape_generic_search("Flextender", url,
            link_selector="a[href*='/opdracht']",
            base_url="https://www.flextender.nl", keywords=keywords)
        all_jobs.extend(jobs)
    return all_jobs


def scrape_tenderned(keywords):
    all_jobs = []
    for kw in keywords:
        url = (f"https://www.tenderned.nl/aankondigingen/overzicht/aankondigingen"
               f"?q={quote_plus(kw)}&sort=date")
        jobs = scrape_generic_search("TenderNed", url,
            link_selector="a[href*='/aankondiging']",
            base_url="https://www.tenderned.nl")
        all_jobs.extend(jobs)
    return all_jobs


SCRAPERS = {
    "freelance_nl": scrape_freelance_nl,
    "malt_nl": scrape_malt_nl,
    "yacht": scrape_yacht,
    "brunel": scrape_brunel,
    "between": scrape_between,
    "quest4": scrape_quest4,
    "headfirst": scrape_headfirst,
    "striive": scrape_striive,
    "freep": scrape_freep,
    "flextender": scrape_flextender,
    "tenderned": scrape_tenderned,
}


def send_email(new_jobs, config):
    email_cfg = config["email"]
    sender = os.environ.get("EMAIL_SENDER", email_cfg["sender"])
    password = os.environ.get("EMAIL_PASSWORD", email_cfg["password"])
    recipient = email_cfg["recipient"]
    smtp_host = email_cfg.get("smtp_host", "smtp.gmail.com")
    smtp_port = email_cfg.get("smtp_port", 587)

    now = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M UTC")

    rows = ""
    for j in new_jobs:
        rows += f"""
        <tr>
            <td style="padding:8px; border-bottom:1px solid #eee;">{j['site']}</td>
            <td style="padding:8px; border-bottom:1px solid #eee;">
                <a href="{j['url']}" style="color:#0066cc;">{j['title']}</a>
            </td>
        </tr>"""

    html = f"""
    <html><body style="font-family: Arial, sans-serif; color:#333;">
    <h2 style="color:#0066cc;">🔔 {len(new_jobs)} nieuwe opdracht(en) gevonden</h2>
    <p style="color:#666;">Scan uitgevoerd op {now}</p>
    <table style="border-collapse:collapse; width:100%; max-width:700px;">
        <tr style="background:#f5f5f5;">
            <th style="padding:8px; text-align:left;">Platform</th>
            <th style="padding:8px; text-align:left;">Opdracht</th>
        </tr>
        {rows}
    </table>
    <p style="color:#999; font-size:12px; margin-top:20px;">
        Freelance Job Monitor
    </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔔 {len(new_jobs)} nieuwe freelance opdracht(en) — {now}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        log.info(f"Email sent to {recipient} with {len(new_jobs)} new job(s)")
    except Exception as e:
        log.error(f"Failed to send email: {e}")
        raise


def main():
    config = load_config()
    keywords = config.get("keywords", ["scrum master", "agile coach"])
    enabled_sites = config.get("sites", list(SCRAPERS.keys()))

    log.info(f"Starting scan — keywords: {keywords}")
    log.info(f"Enabled sites: {enabled_sites}")

    seen = load_seen()
    all_new_jobs = []

    for site_key in enabled_sites:
        scraper = SCRAPERS.get(site_key)
        if not scraper:
            log.warning(f"Unknown site key: {site_key}, skipping")
            continue

        log.info(f"Scanning {site_key}...")
        jobs = scraper(keywords)
        log.info(f"  {len(jobs)} matching job(s) from {site_key}")

        for job in jobs:
            jid = job_id(job["url"], job["title"])
            if jid not in seen:
                seen[jid] = {
                    "title": job["title"],
                    "url": job["url"],
                    "site": job["site"],
                    "first_seen": datetime.now(timezone.utc).isoformat(),
                }
                all_new_jobs.append(job)

    log.info(f"Total new jobs found: {len(all_new_jobs)}")

    if all_new_jobs:
        send_email(all_new_jobs, config)
    else:
        log.info("No new jobs — no email sent.")

    cutoff = datetime.now(timezone.utc).timestamp() - (90 * 86400)
    pruned = {}
    for jid, data in seen.items():
        try:
            seen_ts = datetime.fromisoformat(data["first_seen"]).timestamp()
            if seen_ts > cutoff:
                pruned[jid] = data
        except (KeyError, ValueError):
            pruned[jid] = data
    seen = pruned

    save_seen(seen)
    log.info(f"Seen database: {len(seen)} jobs tracked")


if __name__ == "__main__":
    main()
