# PMI Chapter Engagement Monitor

Automated weekly monitoring of ~150 PMI chapter websites, analyzing content against PMI's flywheel framework (Adoption, Advocacy, Contribution, Retention).

## What it does

Every week, this pipeline:

1. **Scrapes** 151 PMI chapter websites — front pages, then a deep crawl following internal links (up to 50 pages per site)
2. **Analyzes** scraped content using OpenAI structured outputs, classifying findings by flywheel element and recommending CEP actions (amplify, recognize, replicate, follow up)
3. **Generates** a static report site with per-chapter findings, cross-chapter patterns, and gap identification
4. **Tracks changes** between runs so only updated content is re-analyzed

The analysis is tuned for specificity. Every chapter "hosts events" — the monitor surfaces what's *distinctive*: named programs, specific partnerships, innovative approaches.

## Current results

From the most recent run across 151 chapters:

- **89 chapters** with distinctive findings, **60 chapters** flagged as opportunities for CEP outreach
- **299 specific findings** (not generic "promotes certifications" — real programs and initiatives)
- **10 amplify-worthy** activities across the network, e.g.:
  - PMI Alamo's "Project Management as a Life Skill" secondary school outreach program
  - PMI Mile Hi's Project Management Day of Service (PMDoS) pairing volunteer PMs with nonprofits
  - PMI SF Bay Area's "PMs for Good" sustainability-focused meetup group
  - PMI Central Mass's structured 6-month mentoring program (20 PDUs, $100)
- All findings verified against source text — no hallucinations

## What's ready to go

The pipeline works end-to-end and is ready to run as a weekly automated job. To make it live, two things are needed:

### 1. GitHub Actions (automated weekly runs)

Already configured in `.github/workflows/weekly.yml`. Just needs:

- **Add the `OPENAI_API_KEY` secret** to the repo: Settings → Secrets and variables → Actions → New repository secret
- The workflow runs every Monday at noon UTC (or trigger manually via Actions → Run workflow)
- Each run scrapes all sites, analyzes content, and commits updated data back to the repo

### 2. Static report site (optional)

The `site/` folder contains a ready-to-deploy Bootstrap report with:
- Flywheel activity breakdown
- Notable findings with CEP action recommendations
- Filterable chapter list (by flywheel element, action, location, search)
- Cross-chapter patterns and gaps

Deploy options:
- **Netlify**: connect the repo, set publish directory to `site/`, no build command needed
- **Vercel**: same — point at `site/`, static deployment
- **Or just browse `site/data/analysis.json` directly** — the data is self-contained

## Setup (for local runs)

```bash
uv sync
uv run playwright install chromium
```

Add your OpenAI key to `.env`:
```
OPENAI_API_KEY=sk-...
```

```bash
# Full pipeline
uv run python scrape_frontpages.py --fresh
uv run python scrape_chapters.py
uv run python analyze.py

# Only re-analyze chapters whose content changed
uv run python analyze.py --diff-only

# Resume a deep crawl if interrupted
uv run python scrape_chapters.py 85
```

## How the scraping works

Both scrapers try four strategies per site, escalating when blocked:

1. `requests` with a polite user-agent
2. `requests` with browser-like headers
3. `cloudscraper` (bypasses basic Cloudflare)
4. `playwright` (full headless Chromium)

149/151 sites scrape successfully. The deep crawl takes ~2 hours for all sites.

## Files

| File | Description |
|---|---|
| `pmi_chapters.csv` | 151 chapters with names, locations, and URLs |
| `scrape_frontpages.py` | Front page scraper (fast, ~5 min for all sites) |
| `scrape_chapters.py` | Deep crawl (up to 50 pages/site, ~2 hours total) |
| `analyze.py` | Flywheel analysis via OpenAI structured outputs |
| `config.yaml` | Model, concurrency, and the analysis prompt |
| `site/` | Static report site |
| `site/data/analysis.json` | Analysis output (checked in) |
| `frontpages.csv` | Front page scrape summary (checked in) |

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
site/ → Netlify / Vercel / browse locally
```
