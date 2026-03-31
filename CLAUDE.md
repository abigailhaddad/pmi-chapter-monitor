# CLAUDE.md

## Project overview

Scraper for PMI chapter websites. The input is `pmi_chapters.csv` (151 chapters with URLs). The main script is `scrape_frontpages.py` which fetches front pages and outputs `frontpages.csv` + `frontpages.json`.

## Key commands

- `uv sync` — install dependencies
- `uv run python scrape_frontpages.py` — scrape (resumes from where it left off)
- `uv run python scrape_frontpages.py --fresh` — full re-scrape
- `uv run python scrape_frontpages.py --csv-only` — regenerate CSV from JSON

## Architecture

- `scrape_frontpages.py` — front page scraper with escalating fetch strategies (requests → cloudscraper → playwright). Outputs JSON (full text) and CSV (summary).
- `scrape_chapters.py` — deep crawl variant that follows internal links up to depth 3 / 200 pages per site. Outputs per-chapter JSON files to `scraped_data/`.
- `pmi_chapters.csv` — source of truth for chapter names and URLs.

## Notes

- `frontpages.json` and `scraped_data/` are gitignored (large, regenerable).
- `frontpages.csv` is checked in so people can review without re-scraping.
- Playwright needs `uv run playwright install chromium` after first `uv sync`.
