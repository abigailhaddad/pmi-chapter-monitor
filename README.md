# PMI Chapter Scraper

Scrapes the front pages of ~150 PMI (Project Management Institute) chapter websites and produces a clean CSV.

## Setup

```bash
uv sync
uv run playwright install chromium
```

## Usage

```bash
# Scrape all sites (skips already-scraped ones)
uv run python scrape_frontpages.py

# Re-scrape everything from scratch
uv run python scrape_frontpages.py --fresh

# Just rebuild the CSV from existing scraped data
uv run python scrape_frontpages.py --csv-only
```

## How it works

For each site in `pmi_chapters.csv`, the scraper tries four strategies in order until one succeeds:

1. `requests` with a polite user-agent
2. `requests` with browser-like headers
3. `cloudscraper` (bypasses basic Cloudflare)
4. `playwright` (full headless Chromium)

It extracts the main content area (stripping nav, headers, footers, menus) and saves everything to `frontpages.json`. Then it generates `frontpages.csv` with a clean summary.

## Files

| File | Description |
|---|---|
| `pmi_chapters.csv` | Input: 151 PMI chapters with name, location, and website URL |
| `scrape_frontpages.py` | Main script: scrapes front pages and generates CSV |
| `scrape_chapters.py` | Deep crawl script: follows internal links (up to 200 pages/site, depth 3) |
| `frontpages.csv` | Output: clean CSV with status, title, text length, and content preview |
| `frontpages.json` | Output: full scraped text (gitignored, regenerable) |

## Results

Last run: 149/151 sites scraped successfully. Two sites with persistent SSL issues:
- PMI Northern Louisiana (pminorthernla.org)
- PMI West Texas (pmiwtx.org)
