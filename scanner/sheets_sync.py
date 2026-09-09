"""Client for the Google Apps Script web app that acts as the Google Sheets databank.

Design: the Sheet is the single source of truth for "what's already been synced."
Before pulling anything from the MLB Stats API, we ask the Apps Script which past
seasons are already marked complete and skip re-fetching those entirely. After a
successful pull, we push the new/updated rows and mark any freshly-fetched prior
season as complete (the current season is never marked complete — it's always
re-fetched, since it's still in progress).

If APPS_SCRIPT_URL / APPS_SCRIPT_SECRET aren't set, sync is a no-op and the run falls
back to local CSV/XLSX output only — this module never raises on a missing config,
only on a config that's set but broken (so misconfiguration is loud, not silent).
"""
import logging
import math

import pandas as pd
import requests

from . import config

logger = logging.getLogger("milb_scanner.sheets_sync")


def get_completed_seasons(kind: str = "season") -> set[int]:
    """Seasons the Sheet already has fully synced for the given `kind`. `kind`
    keeps independent pipelines (season summaries vs. game logs) from stepping on
    each other's completion state -- each gets its own `_SyncState*` tab on the
    Apps Script side. Empty set if sync is disabled or nothing's marked yet."""
    if not config.SHEETS_SYNC_ENABLED:
        return set()

    try:
        resp = requests.get(
            config.APPS_SCRIPT_URL,
            params={"action": "state", "secret": config.APPS_SCRIPT_SECRET, "kind": kind},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Could not read sync state (%s) from Sheets, assuming nothing synced: %s", kind, exc)
        return set()

    return {int(s) for s in data.get("completed_seasons", [])}


def get_season_level_rows(sheet_name: str) -> pd.DataFrame:
    """Distinct (player_id, season, team_level) triples already written to
    `sheet_name`. This is how the game-log pipeline finds targets across every
    season ever synced -- not just what the current run happened to (re)fetch,
    since already-complete seasons aren't re-pulled from the API anymore."""
    if not config.SHEETS_SYNC_ENABLED:
        return pd.DataFrame(columns=["player_id", "season", "team_level"])

    try:
        resp = requests.get(
            config.APPS_SCRIPT_URL,
            params={"action": "season_rows", "secret": config.APPS_SCRIPT_SECRET, "sheet": sheet_name},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Could not read season rows from '%s': %s", sheet_name, exc)
        return pd.DataFrame(columns=["player_id", "season", "team_level"])

    return pd.DataFrame(data.get("rows", []), columns=["player_id", "season", "team_level"])


def _post(payload: dict) -> bool:
    try:
        resp = requests.post(config.APPS_SCRIPT_URL, json=payload, timeout=60)
        resp.raise_for_status()
        body = resp.json()
        if not body.get("ok", False):
            logger.warning("Apps Script rejected request: %s", body.get("error"))
            return False
        return True
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Sheets sync request failed: %s", exc)
        return False


def push_rows(sheet_name: str, df: pd.DataFrame) -> bool:
    """Upsert `df` into the given sheet tab, keyed by (player_id, season, team_id).
    Sent in chunks so no single request is too large for Apps Script to handle
    comfortably. Returns True only if every chunk succeeded."""
    if not config.SHEETS_SYNC_ENABLED or df.empty:
        return True

    clean = df.replace([float("inf"), float("-inf")], pd.NA)
    records = clean.astype(object).where(pd.notnull(clean), None).to_dict(orient="records")
    chunk_size = config.SHEETS_PUSH_CHUNK_SIZE
    n_chunks = math.ceil(len(records) / chunk_size)
    all_ok = True

    for i in range(n_chunks):
        chunk = records[i * chunk_size: (i + 1) * chunk_size]
        ok = _post({
            "secret": config.APPS_SCRIPT_SECRET,
            "action": "sync_rows",
            "sheet": sheet_name,
            "rows": chunk,
        })
        all_ok = all_ok and ok
        logger.info(
            "Pushed %s/%s rows to '%s' (chunk %s/%s) -> %s",
            len(chunk), len(records), sheet_name, i + 1, n_chunks,
            "ok" if ok else "FAILED",
        )

    return all_ok


def mark_season_complete(season: int, kind: str = "season") -> bool:
    if not config.SHEETS_SYNC_ENABLED:
        return True
    ok = _post({
        "secret": config.APPS_SCRIPT_SECRET,
        "action": "mark_complete",
        "season": season,
        "kind": kind,
    })
    logger.info("Marked season %s (%s) complete -> %s", season, kind, "ok" if ok else "FAILED")
    return ok
