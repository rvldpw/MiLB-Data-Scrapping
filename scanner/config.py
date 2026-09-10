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
# Rows per HTTP request. Each push now costs roughly one bulk read + one bulk
# write of the whole existing sheet, regardless of chunk size -- so fewer, larger
# chunks means paying that fixed per-call cost fewer times, not more small calls.
SHEETS_PUSH_CHUNK_SIZE = int(os.environ.get("SHEETS_PUSH_CHUNK_SIZE", "2000"))

# --- Local scratch space (artifacts, run-scoped cache) --------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "cache"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# "Active" = has a stat line in the most recent in-scope season.
ACTIVE_SEASON = SEASON_END

# --- Game-by-game logs -----------------------------------------------------------------
# Separate opt-in pipeline from the season summaries above: same active-player scope,
# but one row per game instead of one row per season. A full 2021-2025 game-by-game
# backfill for every active prospect is thousands of extra API calls, so historical
# seasons are throttled to this many not-yet-synced seasons per run -- the current
# season is always fetched in full every run regardless of this cap. At 1/run, a
# 5-season backfill drains over ~5 daily runs instead of one 90-minute timeout.
GAME_LOG_ENABLED = os.environ.get("GAME_LOG_ENABLED", "true").lower() != "false"
MAX_GAMELOG_SEASONS_PER_RUN = int(os.environ.get("MAX_GAMELOG_SEASONS_PER_RUN", "1"))

# Bio/age enrichment — one extra API call per unique active player, ID-keyed (never
# name-matched). Adds real minutes to a run with thousands of active players, so
# it's toggle-able. Default on since age is core to how you evaluate prospects.
ENRICH_WITH_BIO = os.environ.get("ENRICH_WITH_BIO", "true").lower() != "false"
