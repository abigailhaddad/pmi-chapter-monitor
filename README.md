# PMI Chapter Engagement Monitor

Automated weekly monitoring of ~150 PMI (Project Management Institute) chapter websites, analyzing content for flywheel engagement activity.

## What it does

1. **Scrapes** the front page of every PMI chapter website
2. **Analyzes** content using OpenAI structured outputs against PMI's flywheel framework:
   - **Adoption** — certifications, tools, standards, PMI-branded offerings
   - **Advocacy** — member stories, partnerships, external visibility
   - **Contribution** — volunteer engagement, member-led content, thought leadership
   - **Retention** — engaging, inclusive, value-driven programming
3. **Publishes** a static report site via GitHub Pages
4. **Tracks changes** between runs so only updated content is re-analyzed

## Setup

```bash
uv sync
uv run playwright install chromium
cp .env.example .env  # add your OPENAI_API_KEY
```

## Usage

```bash
# Scrape all chapter front pages
uv run python scrape_frontpages.py --fresh

# Analyze content
uv run python analyze.py

# Only re-analyze chapters with changed content
uv run python analyze.py --diff-only

# Just rebuild CSV from existing scraped data
uv run python scrape_frontpages.py --csv-only
```

## Automation

A GitHub Actions workflow runs every Monday at noon UTC:
1. Scrapes all chapter websites
2. Analyzes content via OpenAI
3. Commits updated data
4. Deploys the report site to GitHub Pages

Set `OPENAI_API_KEY` as a repository secret for this to work.

## Files

| File | Description |
|---|---|
| `pmi_chapters.csv` | Input: 151 chapters with names, locations, and URLs |
| `scrape_frontpages.py` | Scraper with escalating strategies (requests → cloudscraper → playwright) |
| `analyze.py` | Flywheel analysis via OpenAI structured outputs |
| `config.yaml` | Model, concurrency, and analysis prompt configuration |
| `site/` | Static report site (Bootstrap + vanilla JS) |
| `frontpages.csv` | Scraped content summary (checked in) |
| `scrape_chapters.py` | Deep crawl variant (follows internal links, not used in weekly pipeline) |
