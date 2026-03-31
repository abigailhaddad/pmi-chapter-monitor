"""
Analyze scraped PMI chapter content against the flywheel framework.

Usage:
    uv run python analyze.py              # analyze all chapters
    uv run python analyze.py --diff-only  # only report new/changed content

Reads:  frontpages.json (scraped content)
Writes: site/data/analysis.json (current analysis)
        site/data/previous_analysis.json (rotated from prior run)
"""

import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum

import yaml
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DATA_DIR = Path("site/data")
SCRAPED_PATH = Path("frontpages.json")
ANALYSIS_PATH = DATA_DIR / "analysis.json"
PREVIOUS_PATH = DATA_DIR / "previous_analysis.json"
CONFIG_PATH = Path("config.yaml")


# ---------------------------------------------------------------------------
# Pydantic models for structured output
# ---------------------------------------------------------------------------
class FlywheelElement(str, Enum):
    adoption = "adoption"
    advocacy = "advocacy"
    contribution = "contribution"
    retention = "retention"


class CEPAction(str, Enum):
    amplify = "amplify"
    recognize = "recognize"
    follow_up = "follow_up"
    replicate = "replicate"
    no_action = "no_action"


class Finding(BaseModel):
    activity: str
    flywheel_element: FlywheelElement
    why_it_matters: str
    suggested_action: CEPAction


class ChapterAnalysis(BaseModel):
    findings: list[Finding]
    summary: str


# ---------------------------------------------------------------------------
# Content hashing for diff tracking
# ---------------------------------------------------------------------------
def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def load_previous_hashes() -> dict[str, str]:
    """Load content hashes from the previous analysis run."""
    if not PREVIOUS_PATH.exists():
        return {}
    with open(PREVIOUS_PATH) as f:
        prev = json.load(f)
    return {ch["url"]: ch.get("content_hash", "") for ch in prev.get("chapters", [])}


# ---------------------------------------------------------------------------
# LLM analysis
# ---------------------------------------------------------------------------
async def analyze_chapter(
    client: AsyncOpenAI,
    model: str,
    system_prompt: str,
    chapter: dict,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Analyze a single chapter's content."""
    async with semaphore:
        text = chapter["text"]
        if not text or len(text) < 50:
            return {
                "chapter_name": chapter["chapter_name"],
                "state_province": chapter.get("state_province", ""),
                "country": chapter.get("country", ""),
                "url": chapter["url"],
                "content_hash": content_hash(text or ""),
                "status": "skipped",
                "reason": "insufficient content",
                "findings": [],
                "summary": "",
            }

        user_msg = (
            f"Chapter: {chapter['chapter_name']}\n"
            f"URL: {chapter['url']}\n\n"
            f"Website content:\n{text[:8000]}"
        )

        try:
            resp = await client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                response_format=ChapterAnalysis,
            )
            analysis = resp.choices[0].message.parsed
            log.info(
                f"  {chapter['chapter_name']}: "
                f"{len(analysis.findings)} findings"
            )
            return {
                "chapter_name": chapter["chapter_name"],
                "state_province": chapter.get("state_province", ""),
                "country": chapter.get("country", ""),
                "url": chapter["url"],
                "content_hash": content_hash(text),
                "status": "analyzed",
                "findings": [f.model_dump() for f in analysis.findings],
                "summary": analysis.summary,
            }
        except Exception as e:
            log.error(f"  {chapter['chapter_name']}: {e}")
            return {
                "chapter_name": chapter["chapter_name"],
                "state_province": chapter.get("state_province", ""),
                "country": chapter.get("country", ""),
                "url": chapter["url"],
                "content_hash": content_hash(text),
                "status": "error",
                "reason": str(e)[:200],
                "findings": [],
                "summary": "",
            }


async def run_analysis(diff_only: bool = False):
    config = yaml.safe_load(open(CONFIG_PATH))
    model = config["model"]
    concurrency = config["concurrency"]
    system_prompt = config["prompts"]["analyze"]

    with open(SCRAPED_PATH) as f:
        chapters = json.load(f)

    # Filter to only changed content if diff mode
    prev_hashes = load_previous_hashes()
    if diff_only and prev_hashes:
        original_count = len(chapters)
        chapters = [
            ch for ch in chapters
            if content_hash(ch.get("text", "")) != prev_hashes.get(ch["url"], "")
        ]
        log.info(
            f"Diff mode: {len(chapters)} changed out of {original_count}"
        )
    else:
        log.info(f"Full analysis: {len(chapters)} chapters")

    client = AsyncOpenAI()
    semaphore = asyncio.Semaphore(concurrency)

    tasks = [
        analyze_chapter(client, model, system_prompt, ch, semaphore)
        for ch in chapters
    ]
    results = await asyncio.gather(*tasks)

    # If diff mode, merge with previous results for unchanged chapters
    if diff_only and PREVIOUS_PATH.exists():
        with open(PREVIOUS_PATH) as f:
            prev = json.load(f)
        prev_by_url = {ch["url"]: ch for ch in prev.get("chapters", [])}
        changed_urls = {r["url"] for r in results}
        for url, prev_ch in prev_by_url.items():
            if url not in changed_urls:
                prev_ch["status"] = "unchanged"
                results.append(prev_ch)

    # Sort by chapter name
    results.sort(key=lambda r: r["chapter_name"])

    # Build cross-chapter patterns
    patterns = build_patterns(results)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_chapters": len(results),
        "analyzed": sum(1 for r in results if r["status"] == "analyzed"),
        "unchanged": sum(1 for r in results if r["status"] == "unchanged"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "errors": sum(1 for r in results if r["status"] == "error"),
        "patterns": patterns,
        "chapters": results,
    }

    # Rotate current → previous
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if ANALYSIS_PATH.exists():
        ANALYSIS_PATH.rename(PREVIOUS_PATH)

    with open(ANALYSIS_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    log.info(
        f"Done: {output['analyzed']} analyzed, "
        f"{output['unchanged']} unchanged, "
        f"{output['skipped']} skipped, "
        f"{output['errors']} errors"
    )
    log.info(f"Output: {ANALYSIS_PATH}")


def build_patterns(results: list[dict]) -> dict:
    """Identify cross-chapter patterns."""
    flywheel_counts = {"adoption": 0, "advocacy": 0, "contribution": 0, "retention": 0}
    action_counts = {}
    chapters_with_findings = 0
    chapters_without = 0
    all_findings = []

    for r in results:
        if r["status"] != "analyzed":
            continue
        if r["findings"]:
            chapters_with_findings += 1
            for f in r["findings"]:
                flywheel_counts[f["flywheel_element"]] += 1
                action_counts[f["suggested_action"]] = action_counts.get(f["suggested_action"], 0) + 1
                all_findings.append({**f, "chapter": r["chapter_name"]})
        else:
            chapters_without += 1

    # Top findings worth amplifying/replicating
    notable = [
        f for f in all_findings
        if f["suggested_action"] in ("amplify", "replicate", "recognize")
    ]

    return {
        "flywheel_counts": flywheel_counts,
        "action_counts": action_counts,
        "chapters_with_findings": chapters_with_findings,
        "chapters_without_findings": chapters_without,
        "notable_findings": notable[:20],
    }


def main():
    diff_only = "--diff-only" in sys.argv
    asyncio.run(run_analysis(diff_only=diff_only))


if __name__ == "__main__":
    main()
