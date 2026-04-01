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
- **Which AI model to use:** Also in `config.yaml`. Currently `gpt-4.1-mini` (~$1-2 per run). Switch to `gpt-4.1` for better quality at higher cost.

## Running this on your own (optional)

To take ownership of this pipeline, you need three things: a GitHub repo, an OpenAI API key, and a Netlify site.

### 1. Fork this repo

Click "Fork" on GitHub (or copy it to your own org).

### 2. Add three secrets to GitHub

Go to **Settings > Secrets and variables > Actions** and add:

| Secret | Where to get it |
|---|---|
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) (~$1-2/run) |
| `NETLIFY_AUTH_TOKEN` | [Netlify personal access tokens](https://app.netlify.com/user/applications#personal-access-tokens) |
| `NETLIFY_SITE_ID` | Your Netlify project settings > General > Site ID |

### 3. Create a Netlify site

On [app.netlify.com](https://app.netlify.com): **Add new site > Import an existing project**, connect your repo, set publish directory to `site`, no build command needed.

### 4. Turn on weekly runs

Once the secrets are in place, the pipeline runs automatically every Monday at noon UTC. You can also trigger it manually from the **Actions** tab. A full run takes ~2.5 hours (most of that is crawling 151 sites).
