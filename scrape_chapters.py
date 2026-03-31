"""
Scrape all PMI chapter websites with progressive escalation.

Strategy (per site):
  1. requests + BeautifulSoup (fast, polite)
  2. requests with browser-like headers + retries
  3. cloudscraper (bypasses basic Cloudflare)
  4. playwright (full headless browser)

For each site we crawl internal links up to a configurable depth/max-pages,
saving all page text content to a per-chapter JSON file.
"""

import csv
import json
import hashlib
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OUTPUT_DIR = Path("scraped_data")
CSV_PATH = Path("pmi_chapters.csv")
MAX_PAGES_PER_SITE = 50
MAX_DEPTH = 2
REQUEST_TIMEOUT = 15
DELAY_BETWEEN_REQUESTS = 1.0  # seconds, be polite
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

HEADERS_POLITE = {"User-Agent": "PMIChapterScraper/1.0 (research)"}
HEADERS_BROWSER = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@dataclass
class PageResult:
    url: str
    title: str
    text: str
    links_found: int
    method: str  # which strategy succeeded


@dataclass
class SiteResult:
    chapter_name: str
    base_url: str
    pages: list[PageResult] = field(default_factory=list)
    method_used: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------
def normalise_url(url: str) -> str:
    """Strip fragments and trailing slashes for dedup."""
    p = urlparse(url)
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme, p.netloc, path, p.params, p.query, ""))


def is_same_domain(url: str, base_domain: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc == base_domain or parsed.netloc == ""


def should_skip_url(url: str) -> bool:
    """Skip non-page resources."""
    skip_extensions = {
        ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".gz", ".tar", ".mp4", ".mp3", ".avi", ".mov",
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".css", ".js", ".ico", ".woff", ".woff2", ".ttf", ".eot",
    }
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in skip_extensions)


def extract_links(soup: BeautifulSoup, base_url: str, base_domain: str) -> list[str]:
    """Pull same-domain links from parsed HTML."""
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = urljoin(base_url, href)
        if not is_same_domain(absolute, base_domain):
            continue
        if should_skip_url(absolute):
            continue
        links.append(normalise_url(absolute))
    return links


def extract_text(soup: BeautifulSoup) -> str:
    """Get visible text, cleaned up."""
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # collapse whitespace
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def extract_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return ""


# ---------------------------------------------------------------------------
# Fetching strategies
# ---------------------------------------------------------------------------
def fetch_with_requests(url: str, session: requests.Session, headers: dict) -> str | None:
    """Returns HTML string or None."""
    try:
        resp = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
            return resp.text
    except requests.RequestException:
        pass
    return None


def fetch_with_cloudscraper(url: str) -> str | None:
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        resp = scraper.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
            return resp.text
    except Exception:
        pass
    return None


def fetch_with_playwright(url: str) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="networkidle", timeout=30000)
            html = page.content()
            browser.close()
            return html
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# The escalation chain for a single page fetch
# ---------------------------------------------------------------------------
STRATEGIES = [
    ("requests_polite", lambda url, sess: fetch_with_requests(url, sess, HEADERS_POLITE)),
    ("requests_browser", lambda url, sess: fetch_with_requests(url, sess, HEADERS_BROWSER)),
    ("cloudscraper", lambda url, _sess: fetch_with_cloudscraper(url)),
    ("playwright", lambda url, _sess: fetch_with_playwright(url)),
]


def fetch_page(url: str, session: requests.Session) -> tuple[str | None, str]:
    """Try each strategy in order. Returns (html, method_name)."""
    for name, fn in STRATEGIES:
        html = fn(url, session)
        if html and len(html) > 500:  # reject near-empty responses
            return html, name
    return None, "all_failed"


# ---------------------------------------------------------------------------
# Crawl one site
# ---------------------------------------------------------------------------
def crawl_site(chapter_name: str, base_url: str) -> SiteResult:
    result = SiteResult(chapter_name=chapter_name, base_url=base_url)
    base_domain = urlparse(base_url).netloc
    session = requests.Session()

    visited: set[str] = set()
    # (url, depth)
    queue: list[tuple[str, int]] = [(normalise_url(base_url), 0)]
    winning_method = ""

    while queue and len(result.pages) < MAX_PAGES_PER_SITE:
        url, depth = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        html, method = fetch_page(url, session)
        if html is None:
            if len(result.pages) == 0:
                # First page failed with all strategies — record error
                result.error = f"Could not fetch {url} with any strategy"
                log.warning(f"  SKIP {chapter_name}: {result.error}")
                return result
            continue

        # On first success, lock in the winning strategy to avoid
        # escalating on every single page
        if not winning_method:
            winning_method = method
            result.method_used = method
            log.info(f"  {chapter_name}: locked strategy={method}")

        soup = BeautifulSoup(html, "html.parser")
        title = extract_title(soup)
        text = extract_text(soup)
        links = extract_links(soup, url, base_domain)

        result.pages.append(PageResult(
            url=url, title=title, text=text,
            links_found=len(links), method=method,
        ))

        # Enqueue new links if within depth
        if depth < MAX_DEPTH:
            for link in links:
                if link not in visited:
                    queue.append((link, depth + 1))

        time.sleep(DELAY_BETWEEN_REQUESTS)

    if not winning_method:
        result.error = "No pages fetched"

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def load_chapters(csv_path: Path) -> list[dict]:
    with open(csv_path) as f:
        return list(csv.DictReader(f))


def save_result(result: SiteResult, output_dir: Path):
    slug = re.sub(r"[^a-z0-9]+", "_", result.chapter_name.lower()).strip("_")
    path = output_dir / f"{slug}.json"
    data = {
        "chapter_name": result.chapter_name,
        "base_url": result.base_url,
        "method_used": result.method_used,
        "error": result.error,
        "pages_scraped": len(result.pages),
        "pages": [asdict(p) for p in result.pages],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    chapters = load_chapters(CSV_PATH)

    # Allow passing a start index to resume: python scrape_chapters.py 50
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    log.info(f"Loaded {len(chapters)} chapters, starting at index {start}")

    summary = {"ok": 0, "fail": 0, "methods": {}}

    for i, ch in enumerate(chapters[start:], start=start):
        name = ch["chapter_name"]
        url = ch["website_url"]
        log.info(f"[{i+1}/{len(chapters)}] {name} — {url}")

        result = crawl_site(name, url)
        save_result(result, OUTPUT_DIR)

        if result.error:
            summary["fail"] += 1
            log.warning(f"  FAILED: {result.error}")
        else:
            summary["ok"] += 1
            m = result.method_used
            summary["methods"][m] = summary["methods"].get(m, 0) + 1
            log.info(f"  OK: {len(result.pages)} pages via {m}")

    log.info(f"\nDone. OK={summary['ok']} FAIL={summary['fail']}")
    log.info(f"Methods: {summary['methods']}")

    # Write summary
    with open(OUTPUT_DIR / "_summary.json", "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
