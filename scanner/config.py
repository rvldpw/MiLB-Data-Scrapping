"""Shared configuration for the MiLB prospect scanner.

Nothing here talks to the network — safe to import anywhere.
"""
import os
from datetime import datetime
from pathlib import Path

# --- Season window ------------------------------------------------------------------
# SEASON_END tracks the real calendar year on purpose (no hardcoded ceiling) — this
# is what lets the scanner roll forward into 2027, 2028, etc. on its own. The season
# that's "current" (always re-fetched, never marked complete) is whatever
# SEASON_END resolves to on the day the workflow runs.
SEASON_START = 2021
CURRENT_YEAR = datetime.now().year
SEASON_END = CURRENT_YEAR

# --- Levels in scope (MLB Stats API "sport" ids) --------------------------------------
# Locked to A / A+ / AA on purpose. Do not add AAA (11), A- (15), Rookie (16), Winter (17).
LEVELS: dict[str, int] = {
    "AA": 12,
    "A+": 13,
    "A": 14,
}

# A season is "final" (safe to skip re-fetching forever, once synced) once it's a
# full prior calendar year. The current calendar year's season is always re-fetched,
# since it's still in progress / stats can still change.
def is_final_season(season: int) -> bool:
    return season < CURRENT_YEAR

# --- Networking (MLB Stats API) -------------------------------------------------------
REQUEST_TIMEOUT = 20
RATE_LIMIT_DELAY = 0.12
MAX_RETRIES = 5
STATS_API_HOST = "https://statsapi.mlb.com"
BDFED_HOST = "https://bdfed.stitch.mlbinfra.com"

# --- Google Sheets "databank" (Apps Script Web App) ------------------------------------
APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL", "")
APPS_SCRIPT_SECRET = os.environ.get("APPS_SCRIPT_SECRET", "")
SHEETS_SYNC_ENABLED = bool(APPS_SCRIPT_URL and APPS_SCRIPT_SECRET)
SHEETS_PUSH_CHUNK_SIZE = 300  # rows per HTTP request, keeps Apps Script fast per call

# --- Local scratch space (artifacts, run-scoped cache) --------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "cache"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# "Active" = has a stat line in the most recent in-scope season.
ACTIVE_SEASON = SEASON_END

# Bio/age enrichment — one extra API call per unique active player, ID-keyed (never
# name-matched). Adds real minutes to a run with thousands of active players, so
# it's toggle-able. Default on since age is core to how you evaluate prospects.
ENRICH_WITH_BIO = os.environ.get("ENRICH_WITH_BIO", "true").lower() != "false"
