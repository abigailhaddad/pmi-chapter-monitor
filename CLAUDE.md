# CLAUDE.md

## Project overview

PMI Chapter Engagement Monitor. Scrapes ~150 PMI chapter websites weekly, analyzes content against PMI's flywheel framework (Adoption, Advocacy, Contribution, Retention) using OpenAI structured outputs, and publishes a static report site via GitHub Pages.

## Key commands

- `uv sync` — install dependencies
- `uv run python scrape_frontpages.py --fresh` — scrape all chapter front pages
- `uv run python analyze.py` — analyze scraped content (needs OPENAI_API_KEY in .env)
- `uv run python analyze.py --diff-only` — only re-analyze chapters whose content changed

## Architecture

- `scrape_frontpages.py` — scrapes front pages with escalating strategies (requests → cloudscraper → playwright). Outputs `frontpages.json` + `frontpages.csv`.
- `analyze.py` — sends scraped text to OpenAI with structured output (Pydantic models), classifies findings by flywheel element and suggested CEP action. Tracks content hashes to detect changes between runs.
- `config.yaml` — model selection, concurrency, and the analysis prompt.
- `site/` — static site (Bootstrap 5.3, vanilla JS) that loads `site/data/analysis.json`.
- `.github/workflows/weekly.yml` — GitHub Actions cron (Monday noon UTC): scrape → analyze → commit data → deploy Pages.

## Data flow

1. `pmi_chapters.csv` → `scrape_frontpages.py` → `frontpages.json` + `frontpages.csv`
2. `frontpages.json` → `analyze.py` → `site/data/analysis.json`
3. `site/` → GitHub Pages

## Notes

- `scrape_chapters.py` is the deep-crawl variant (follows links, up to 200 pages/site). Not used in the weekly pipeline yet.
- Analysis rotates `analysis.json` → `previous_analysis.json` each run for diff tracking.
- The `OPENAI_API_KEY` secret must be set in GitHub repo settings for Actions to work.
