"""
Test 10: Unified pipeline — loads a single podcast YAML and runs the full flow.

Uses PodcastRunner to orchestrate: filter → processing → output.

For testing, we override the date range to use historical data (2023 SCC)
so results are guaranteed regardless of the current date.

Set your API key before running:
  export OPENAI_API_KEY=sk-...
"""

import sys
import os
import copy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import yaml
from src.runner import PodcastRunner


def test_dry_run():
    """Test that the runner loads and wires everything without calling APIs."""
    print("=" * 60)
    print("DRY RUN — verify YAML loading and handler wiring")
    print("=" * 60)

    podcasts_dir = os.path.join(os.path.dirname(__file__), "..", "podcasts")
    for filename in sorted(os.listdir(podcasts_dir)):
        if not filename.endswith(".yaml"):
            continue
        path = os.path.join(podcasts_dir, filename)
        runner = PodcastRunner.load(path)
        print(f"  {filename}: {runner!r}")
        print(f"    podcast:    {runner.podcast.get('name')}")
        print(f"    has filter: {'filter' in runner._raw}")
        print(f"    has proc:   {'processing' in runner._raw}")
        print(f"    has tts:    {'tts' in runner._raw}")
        print(f"    has tg:     {'telegram' in runner._raw}")
    print()


def test_full_pipeline():
    """Run the SCC roundup with historical dates against live API + LLM."""
    print("=" * 60)
    print("FULL PIPELINE — SCC Roundup (2023 historical data)")
    print("=" * 60)

    path = os.path.join(os.path.dirname(__file__), "..", "podcasts", "scc_weekly_roundup.yaml")
    with open(path, "r") as f:
        config = yaml.safe_load(f)

    # Override to use historical data and limit results for cheap testing
    config["filter"]["date_range"] = {
        "mode": "absolute",
        "start_date": "2023-06-01",
        "end_date": "2023-12-31",
    }
    config["filter"]["max_results"] = 2
    config["filter"]["max_text_chars"] = 3000
    # Skip audio + Telegram for the cheap test run
    config.pop("tts", None)
    config.pop("telegram", None)

    runner = PodcastRunner(config)
    result = runner.run()

    print("\n")
    print("=" * 60)
    print("FINAL OUTPUT")
    print("=" * 60)
    print()
    print(result.get("final", "(no output)"))

    # Clean up dedup state from test
    filter_handler = result.get("_filter_handler")
    if filter_handler:
        filter_handler.reset_processed()


if __name__ == "__main__":
    test_dry_run()

    # Only run full pipeline if API key is set
    if os.environ.get("OPENAI_API_KEY"):
        test_full_pipeline()
    else:
        print("OPENAI_API_KEY not set — skipping full pipeline test.")
        print("Set it with: export OPENAI_API_KEY=sk-...")
