"""
Scrape the front page of every PMI chapter site and produce a clean CSV.

Usage:
    uv run python scrape_frontpages.py           # full run (skips already-scraped)
    uv run python scrape_frontpages.py --fresh    # re-scrape everything from scratch
    uv run python scrape_frontpages.py --csv-only # just rebuild CSV from existing JSON

Escalation per site: requests (polite) → requests (browser headers) → cloudscraper → playwright

Outputs:
    frontpages.json  — raw results with full text
    frontpages.csv   — clean, human-readable summary
"""

import csv
import json
import logging
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

CHAPTERS_CSV = Path("pmi_chapters.csv")
JSON_PATH = Path("frontpages.json")
CSV_PATH = Path("frontpages.csv")
TIMEOUT = 15
DELAY = 0.5

HEADERS_POLITE = {"User-Agent": "PMIChapterScraper/1.0 (research)"}
HEADERS_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------
def extract_main_text(soup: BeautifulSoup) -> str:
    """Extract the main content area, stripping nav/header/footer/menus."""
    # Try to find an explicit main content area first.
    # Be strict: only use it if it has substantial text (> 200 chars).
    candidates = [
        soup.find("main"),
        soup.find("div", role="main"),
        soup.find("div", id=re.compile(r"^(content|main-content|page-content)$", re.I)),
        soup.find("article"),
    ]
    target = None
    for c in candidates:
        if c and len(c.get_text(strip=True)) > 200:
            target = c
            break
    if target is None:
        target = soup.body if soup.body else soup

    # Remove boilerplate elements from our working copy
    for tag in target.find_all(
        ["script", "style", "noscript", "nav", "header", "footer", "iframe"]
    ):
        tag.decompose()

    # Also remove elements that look like menus/sidebars by class/id
    for tag in target.find_all(True):
        if not isinstance(tag, Tag) or tag.attrs is None:
            continue
        classes = " ".join(tag.get("class") or [])
        tag_id = tag.get("id") or ""
        combined = f"{classes} {tag_id}".lower()
        if re.search(r"(menu|sidebar|nav|cookie|popup|modal|banner)", combined):
            tag.decompose()

    text = target.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    # Collapse runs of blank lines
    cleaned = []
    for line in lines:
        if line:
            cleaned.append(line)
        elif cleaned and cleaned[-1] != "":
            cleaned.append("")
    return "\n".join(cleaned).strip()


def extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return ""


def extract(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = extract_title(soup)
    text = extract_main_text(soup)
    return {"title": title, "text": text, "html_length": len(html)}


# ---------------------------------------------------------------------------
# Fetch strategies (escalating)
# ---------------------------------------------------------------------------
def try_requests(url, session, headers):
    try:
        r = session.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
            return r.text
    except Exception:
        pass
    return None


def try_cloudscraper(url):
    try:
        import cloudscraper
        s = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin"}
        )
        r = s.get(url, timeout=TIMEOUT)
        if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
            return r.text
    except Exception:
        pass
    return None


def try_playwright(url):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            html = page.content()
            browser.close()
            return html
    except Exception:
        pass
    return None


def fetch(url, session):
    strategies = [
        ("requests_polite", lambda: try_requests(url, session, HEADERS_POLITE)),
        ("requests_browser", lambda: try_requests(url, session, HEADERS_BROWSER)),
        ("cloudscraper", lambda: try_cloudscraper(url)),
        ("playwright", lambda: try_playwright(url)),
    ]
    for name, fn in strategies:
        html = fn()
        if html and len(html) > 500:
            return html, name
    return None, "all_failed"


# ---------------------------------------------------------------------------
# Scrape all sites → JSON
# ---------------------------------------------------------------------------
def scrape(fresh: bool = False):
    with open(CHAPTERS_CSV) as f:
        chapters = list(csv.DictReader(f))

    if not fresh and JSON_PATH.exists():
        with open(JSON_PATH) as f:
            results = json.load(f)
        done_urls = {r["url"] for r in results}
        log.info(f"Resuming: {len(done_urls)} already done, {len(chapters) - len(done_urls)} remaining")
    else:
        results = []
        done_urls = set()

    session = requests.Session()

    for i, ch in enumerate(chapters):
        url = ch["website_url"]
        name = ch["chapter_name"]

        if url in done_urls:
            continue

        log.info(f"[{i+1}/{len(chapters)}] {name}")
        html, method = fetch(url, session)

        if html:
            info = extract(html)
            results.append({
                "chapter_name": name,
                "state_province": ch["state_province"],
                "country": ch["country"],
                "url": url,
                "method": method,
                "title": info["title"],
                "text": info["text"],
                "html_length": info["html_length"],
                "error": "",
            })
            log.info(f"  OK via {method} — {len(info['text'])} chars")
        else:
            results.append({
                "chapter_name": name,
                "state_province": ch["state_province"],
                "country": ch["country"],
                "url": url,
                "method": "all_failed",
                "title": "",
                "text": "",
                "html_length": 0,
                "error": "all strategies failed",
            })
            log.warning(f"  FAILED")

        # Save after each so we can resume
        with open(JSON_PATH, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        time.sleep(DELAY)

    ok = sum(1 for r in results if not r["error"])
    fail = sum(1 for r in results if r["error"])
    log.info(f"Scrape done: {ok} OK, {fail} failed out of {len(chapters)}")
    return results


# ---------------------------------------------------------------------------
# JSON → clean CSV
# ---------------------------------------------------------------------------
def build_csv(results: list[dict]):
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "chapter_name", "state_province", "country", "url",
            "status", "method", "title", "text_length", "content_preview",
        ])
        for r in results:
            status = "OK" if not r["error"] else "FAILED"
            # First ~300 chars of cleaned text, one line
            preview = r["text"][:300].replace("\n", " | ").replace("\r", "")
            # Collapse multiple pipes
            preview = re.sub(r"(\s*\|\s*)+", " | ", preview).strip(" |")
            writer.writerow([
                r["chapter_name"],
                r.get("state_province", ""),
                r.get("country", ""),
                r["url"],
                status,
                r["method"],
                r["title"],
                len(r["text"]),
                preview,
            ])

    ok = sum(1 for r in results if not r["error"])
    fail = sum(1 for r in results if r["error"])
    log.info(f"Wrote {CSV_PATH}: {len(results)} rows ({ok} OK, {fail} failed)")

    if fail:
        log.info("Failed sites:")
        for r in results:
            if r["error"]:
                log.info(f"  {r['chapter_name']} — {r['url']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    args = set(sys.argv[1:])

    if "--csv-only" in args:
        with open(JSON_PATH) as f:
            results = json.load(f)
        log.info(f"Loaded {len(results)} results from {JSON_PATH}")
    else:
        results = scrape(fresh="--fresh" in args)

    build_csv(results)


if __name__ == "__main__":
    main()
