#!/usr/bin/env python3
"""Daily Hugging Face sync, or an isolated local preview with --local-dir."""
import argparse
from dataclasses import replace
import json
import logging
import os
from pathlib import Path

from scanner.build import run
from scanner.config import Settings
from scanner.fetch import MLBClient
from scanner.storage import HubStore, LocalStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-dir", type=Path, help="Write here instead of Hugging Face; keeps its own progress")
    parser.add_argument("--max-games", type=int, help="Limit box-score attempts this run; leave the season incomplete")
    parser.add_argument("--start-season", type=int, help="Initial season for a NEW dataset (default 2021)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    try:
        settings = Settings.from_env()
        if args.max_games is not None:
            settings = replace(settings, max_games=args.max_games)
        if args.start_season is not None:
            settings = replace(settings, start_season=args.start_season)
        store = LocalStore(args.local_dir) if args.local_dir else HubStore(
            os.getenv("HF_REPO_ID"), os.getenv("HF_TOKEN"),
            private=os.getenv("HF_PRIVATE", "true").lower() != "false")
        summary = run(settings, MLBClient(settings), store)
        output = Path("output")
        output.mkdir(exist_ok=True)
        (output / "run-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        logging.info("Result: %s", summary)
        if os.getenv("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as file:
                file.write("## MiLB game logs\n\n```json\n" + json.dumps(summary, indent=2) + "\n```\n")
        return 0
    except Exception:
        logging.exception("Run failed; next run resumes from the last successful checkpoint")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
