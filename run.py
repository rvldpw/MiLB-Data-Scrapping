#!/usr/bin/env python3
"""Entry point: `python run.py`.

Locally: exports Batter/Pitcher/Catcher into ./output/milb_prospect_scan_delta.xlsx.
If APPS_SCRIPT_URL and APPS_SCRIPT_SECRET are set (as GitHub Actions secrets, or in
your local shell), also syncs to the Google Sheets databank and skips any season
already marked complete there.
"""
import logging
import sys

from scanner import build, config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("milb_scanner")


def main() -> int:
    logger.info(
        "Seasons in scope: %s-%s | Levels: %s | Sheets sync: %s",
        config.SEASON_START, config.SEASON_END, list(config.LEVELS),
        "ON" if config.SHEETS_SYNC_ENABLED else "OFF (no APPS_SCRIPT_URL/SECRET set)",
    )
    try:
        build.run()
    except Exception:
        logger.exception("Run failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
