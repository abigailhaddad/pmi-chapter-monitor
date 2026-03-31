# PMI Chapter Engagement Monitor

Automated weekly monitoring of ~150 PMI (Project Management Institute) chapter websites, analyzing content for flywheel engagement activity.

## What it does

1. **Scrapes** every PMI chapter website — front pages first, then a deep crawl following internal links (up to 50 pages per site, depth 2)
2. **Analyzes** content using OpenAI structured outputs against PMI's flywheel framework:
   - **Adoption** — certifications, tools, standards, PMI-branded offerings
   - **Advocacy** — member stories, partnerships, external visibility
   - **Contribution** — volunteer engagement, member-led content, thought leadership
   - **Retention** — engaging, inclusive, value-driven programming
3. **Generates** a static report site with per-chapter findings, cross-chapter patterns, and gaps
4. **Tracks changes** between runs — content hashes detect what changed, `--diff-only` re-analyzes only updated chapters

The analysis prioritizes specific, distinctive activities over generic ones. Every PMI chapter "hosts events" — the monitor looks for what makes each chapter's approach noteworthy.

## Setup

```bash
uv sync
uv run playwright install chromium
```

Add your OpenAI key to `.env`:
```
OPENAI_API_KEY=sk-...
```

## Usage

```bash
# Full pipeline: scrape front pages → deep crawl → analyze
uv run python scrape_frontpages.py --fresh
uv run python scrape_chapters.py
uv run python analyze.py

# Only re-analyze chapters whose content changed since last run
uv run python analyze.py --diff-only

# Resume a deep crawl from site N (e.g. if interrupted)
uv run python scrape_chapters.py 85

# Just rebuild the front pages CSV from existing JSON
uv run python scrape_frontpages.py --csv-only
```

## Automation

A GitHub Actions workflow runs every Monday at noon UTC:
1. Scrapes all chapter front pages
2. Deep crawls all sites (up to 50 pages each)
3. Analyzes content via OpenAI
4. Commits updated data back to the repo

Set `OPENAI_API_KEY` as a repository secret in Settings → Secrets → Actions.

## Scraping strategy

Both scrapers try four strategies in order per site, escalating when blocked:

1. `requests` with a polite user-agent
2. `requests` with browser-like headers
3. `cloudscraper` (bypasses basic Cloudflare)
4. `playwright` (full headless Chromium)

The deep crawl locks in whichever strategy worked for the first page of a site, then uses it for all subsequent pages.

## Files

| File | Description |
|---|---|
| `pmi_chapters.csv` | Input: 151 chapters with names, locations, and URLs |
| `scrape_frontpages.py` | Front page scraper — one page per site, outputs `frontpages.json` + `frontpages.csv` |
| `scrape_chapters.py` | Deep crawl — follows internal links, up to 50 pages/site at depth 2, outputs per-chapter JSON to `scraped_data/` |
| `analyze.py` | Flywheel analysis via OpenAI structured outputs. Uses deep crawl data when available, falls back to front pages |
| `config.yaml` | Model, concurrency, and analysis prompt |
| `site/` | Static report site (Bootstrap 5.3 + vanilla JS), loads `site/data/analysis.json` |
| `frontpages.csv` | Front page scrape summary (checked in for quick reference) |

## Data flow

```
pmi_chapters.csv
    ↓
scrape_frontpages.py → frontpages.json + frontpages.csv
scrape_chapters.py   → scraped_data/*.json
    ↓
analyze.py → site/data/analysis.json
             site/data/previous_analysis.json (rotated each run)
    ↓
site/ → deploy wherever (Vercel, Netlify, etc.)
```
