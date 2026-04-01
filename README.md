# PMI Chapter Engagement Monitor

Monitors ~150 PMI chapter websites, uses AI to find noteworthy activities, and publishes a filterable report.

**Live site:** [pmi-chapter-monitor.netlify.app](https://pmi-chapter-monitor.netlify.app)

## How it works

1. Scrapes 151 PMI chapter websites (front pages + up to 50 internal pages each)
2. An AI model (OpenAI) identifies **specific, distinctive activities** — not generic stuff every chapter does
3. Classifies each finding by flywheel element (Adoption, Advocacy, Contribution, Retention) and recommends an action (amplify, recognize, replicate, follow up)

Each finding includes the **original text from the chapter's website** and a **link to the source page**, so you can click through and verify it. Findings that are new since the last run are tagged with a "New" badge.

The site is live now with data from a manual run. It **can be set up to run automatically every week** — see below.

## What you can customize

- **What the AI looks for:** Edit [`config.yaml`](config.yaml) — the prompt is plain English. You can do this directly on GitHub (click the file, then the pencil icon).
- **Which chapters to monitor:** Edit [`pmi_chapters.csv`](pmi_chapters.csv) — add or remove rows.
- **Which AI model to use:** Also in `config.yaml`. Currently `gpt-5.4-mini` (~$1-2 per run). Switch to `gpt-5.4` for better quality at higher cost.

## Running this on your own (optional)

To take ownership of this pipeline, you need an OpenAI API key and someone with light technical skills to set it up. Here's what's involved:

1. **Fork this repo** — click "Fork" on GitHub to copy it to your own account
2. **Get an OpenAI API key** — sign up at [platform.openai.com](https://platform.openai.com), create an API key, and add it as a secret in your repo's GitHub settings. This is what powers the AI analysis (~$1-2 per run).
3. **Set up the website** — the report site is hosted on Netlify (a free website hosting service). Someone needs to create a Netlify account, connect it to the repo, and add the Netlify credentials to GitHub as well.
4. **Turn on weekly runs** — once the above is done, the pipeline runs automatically every Monday. You can also trigger it manually anytime from the GitHub Actions tab.

A full run takes ~2.5 hours (most of that is crawling 151 sites). The detailed setup steps are in the repo's GitHub Action config (`.github/workflows/weekly.yml`).
