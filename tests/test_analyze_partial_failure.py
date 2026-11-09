import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import analyze


def chap(name, status, hash_="h"):
    return {"chapter_name": name, "url": f"https://{name}.example", "status": status,
            "content_hash": hash_, "findings": [{"flywheel_element": "adoption", "suggested_action": "recognize"}] if status == "analyzed" else [],
            "summary": "good" if status == "analyzed" else ""}


class PartialFailure(unittest.TestCase):
    def test_failed_chapter_keeps_previous_good_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            analysis = d / "analysis.json"
            analysis.write_text(json.dumps({"chapters": [chap("a", "analyzed", "old"), chap("b", "analyzed")]}))
            new = [chap("a", "error", "new"), chap("b", "analyzed")]

            async def fake(*args, **kw):
                return new.pop(0)

            chapters = [{"chapter_name": "a", "url": "https://a.example", "text": "t"},
                        {"chapter_name": "b", "url": "https://b.example", "text": "t"}]
            cfg = "model: m\nconcurrency: 2\nprompts:\n  analyze: p\n"
            (d / "config.yaml").write_text(cfg)
            with mock.patch.object(analyze, "DATA_DIR", d), \
                 mock.patch.object(analyze, "ANALYSIS_PATH", analysis), \
                 mock.patch.object(analyze, "PREVIOUS_PATH", d / "previous.json"), \
                 mock.patch.object(analyze, "CONFIG_PATH", d / "config.yaml"), \
                 mock.patch.object(analyze, "load_chapters", return_value=chapters), \
                 mock.patch.object(analyze, "analyze_chapter", fake), \
                 mock.patch.object(analyze, "AsyncOpenAI", mock.Mock()):
                asyncio.run(analyze.run_analysis())
            out = {c["chapter_name"]: c for c in json.loads(analysis.read_text())["chapters"]}
            self.assertEqual(out["a"]["status"], "analyzed")
            self.assertEqual(out["a"]["content_hash"], "old")
            self.assertEqual(out["a"]["summary"], "good")


if __name__ == "__main__":
    unittest.main()
