#!/usr/bin/env python
"""
Run a podcast pipeline from its YAML file.

  python run.py podcasts/scc_weekly_roundup.yaml            # full run
  python run.py podcasts/scc_weekly_roundup.yaml --no-send  # skip Telegram
  python run.py podcasts/scc_weekly_roundup.yaml --test     # 2 old cases, no Telegram, no dedup
  python run.py --all                                       # run every podcast in podcasts/
"""

import argparse
import glob
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.runner import PodcastRunner  # noqa: E402


def run_one(path: str, no_send: bool, test: bool) -> None:
    with open(path) as f:
        config = yaml.safe_load(f)

    if test:
        # Cheap, repeatable: two Supreme Court cases from 2023, no delivery
        config["filter"]["date_range"] = {"mode": "absolute", "start_date": "2023-06-01", "end_date": "2023-12-31"}
        config["filter"]["max_results"] = 2
        config.pop("telegram", None)
    elif no_send:
        config.pop("telegram", None)

    result = PodcastRunner(config).run()

    if test and result.get("_filter_handler"):
        result["_filter_handler"].reset_processed()

    print("\nDigest:\n")
    print(result.get("final", "(no output)"))
    if result.get("audio_path"):
        print(f"\nAudio: {result['audio_path']}")


def main() -> None:
    p = argparse.ArgumentParser(description="Run a Voice of the Courts podcast.")
    p.add_argument("yaml", nargs="?", help="podcast YAML, e.g. podcasts/scc_weekly_roundup.yaml")
    p.add_argument("--all", action="store_true", help="run every YAML in podcasts/")
    p.add_argument("--no-send", action="store_true", help="skip the Telegram stage")
    p.add_argument("--test", action="store_true", help="use 2 old cases, skip Telegram, do not mark cases processed")
    args = p.parse_args()

    if args.all:
        paths = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "podcasts", "*.yaml")))
    elif args.yaml:
        paths = [args.yaml]
    else:
        p.error("give a YAML path or --all")

    for path in paths:
        run_one(path, args.no_send, args.test)


if __name__ == "__main__":
    main()
