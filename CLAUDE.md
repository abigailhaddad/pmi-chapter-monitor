# CLAUDE.md

## Project overview

PMI Chapter Engagement Monitor. Scrapes ~150 PMI chapter websites weekly (front pages + deep crawl up to 50 pages/site), analyzes content against PMI's flywheel framework (Adoption, Advocacy, Contribution, Retention) using OpenAI structured outputs, and generates a static report site.

## Key commands

- `uv sync` — install dependencies
- `uv run python scrape_frontpages.py --fresh` — scrape all chapter front pages
- `uv run python scrape_chapters.py` — deep crawl all sites (up to 50 pages each, depth 2). Takes ~2 hours. Resumable: `scrape_chapters.py 85` starts at index 85
- `uv run python analyze.py` — analyze scraped content (needs OPENAI_API_KEY in .env). Prefers deep crawl data, falls back to front pages
- `uv run python analyze.py --diff-only` — only re-analyze chapters whose content changed

## Architecture

- `scrape_frontpages.py` — scrapes front pages with escalating strategies (requests → cloudscraper → playwright). Outputs `frontpages.json` + `frontpages.csv`.
- `scrape_chapters.py` — deep crawl. Follows internal links up to 50 pages/site, depth 2. Outputs per-chapter JSON to `scraped_data/`. Resumable via start index argument.
- `analyze.py` — sends scraped text to OpenAI with structured output (Pydantic models), classifies findings by flywheel element and suggested CEP action. Uses deep crawl data when available (combines top pages up to 15K chars), falls back to front pages. Tracks content hashes to detect changes between runs.
- `config.yaml` — model selection, concurrency, and the analysis prompt. The prompt is tuned for specificity — it filters out generic "every chapter does this" activities.
- `site/` — static site (Bootstrap 5.3, vanilla JS) that loads `site/data/analysis.json`. Includes filters, flywheel breakdown, notable findings, and gaps.
- `.github/workflows/weekly.yml` — GitHub Actions cron (Monday noon UTC): scrape front pages → deep crawl → analyze → commit data.

## Data flow

1. `pmi_chapters.csv` → `scrape_frontpages.py` → `frontpages.json` + `frontpages.csv`
2. `pmi_chapters.csv` → `scrape_chapters.py` → `scraped_data/*.json`
3. `scraped_data/` + `frontpages.json` → `analyze.py` → `site/data/analysis.json`
4. `site/` → deploy via Vercel/Netlify (not automated yet)

## Notes

- Analysis rotates `analysis.json` → `previous_analysis.json` each run for diff tracking.
- `scraped_data/` and `frontpages.json` are gitignored (large, regenerable).
- `frontpages.csv` and `site/data/analysis.json` are checked in.
- The `OPENAI_API_KEY` secret must be set in GitHub repo settings for Actions to work.
- Deep crawl takes ~2 hours for all 151 sites. If interrupted, resume with `scrape_chapters.py N`.
