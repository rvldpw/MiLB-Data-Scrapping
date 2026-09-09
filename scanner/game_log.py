"""Game-by-game log sync -- a separate pipeline from the season-summary one in
build.py, but the same shape: ask the Sheet what's already synced, skip it, pull
the rest, push, mark complete.

Scope is deliberately narrower than the season pipeline: only players who are
*active this season* (the same set build.py already narrowed the summary sheets
down to), and only the exact (player_id, season, team_level) combinations their
season stat lines actually show -- never a blind player x season x level
cross-product. That's still thousands of extra API calls for a multi-year
backfill, so historical (final) seasons are throttled to
config.MAX_GAMELOG_SEASONS_PER_RUN per run; the current season is always pulled
in full every run, since that's the one that actually needs to stay fresh.

Targets come from `sheets_sync.get_season_level_rows()` -- i.e. what's already on
the "Batter"/"Pitcher"/"Catcher" tabs in the Sheet -- rather than from this run's
own batting_full/pitching_full, because once a season is marked complete in the
season-summary pipeline it's never re-fetched, so this run's in-memory data alone
would never cover the full 2021+ history.
"""
import logging

import pandas as pd

from . import config, fetch, sheets_sync

logger = logging.getLogger("milb_scanner.game_log")

SHEET_NAMES = {"batting": "BatterGameLog", "pitching": "PitcherGameLog"}


def _seasons_to_backfill(available_seasons: set[int], completed: set[int]) -> list[int]:
    """Historical (final) seasons not yet synced, capped per run. Current/future
    seasons are handled separately below and always included in full."""
    pending = sorted(s for s in available_seasons if config.is_final_season(s) and s not in completed)
    return pending[: config.MAX_GAMELOG_SEASONS_PER_RUN]


def _targets(season_rows: pd.DataFrame, active_ids: set[int],
             seasons_in_scope: set[int]) -> list[tuple[int, int, str]]:
    if season_rows.empty or not active_ids or not seasons_in_scope:
        return []
    subset = season_rows[
        season_rows["player_id"].isin(active_ids) & season_rows["season"].isin(seasons_in_scope)
    ]
    return list(subset.drop_duplicates().itertuples(index=False, name=None))


def _sync_one(stats_type: str, season_rows: pd.DataFrame, active_ids: set[int]) -> None:
    if season_rows.empty or not active_ids:
        return

    kind = f"gamelog_{stats_type}"
    completed = sheets_sync.get_completed_seasons(kind=kind)
    available_seasons = {int(s) for s in season_rows["season"].unique().tolist()}
    current_seasons = {s for s in available_seasons if not config.is_final_season(s)}
    backfill_seasons = _seasons_to_backfill(available_seasons, completed)
    seasons_in_scope = current_seasons | set(backfill_seasons)

    logger.info(
        "Game logs (%s): %s season(s) already complete, backfilling %s this run, "
        "plus current season(s) %s",
        stats_type, sorted(completed), backfill_seasons, sorted(current_seasons),
    )

    targets = _targets(season_rows, active_ids, seasons_in_scope)
    if not targets:
        logger.info("Game logs (%s): nothing to fetch this run.", stats_type)
        return

    logger.info("Game logs (%s): fetching %s (player, season, level) combos...", stats_type, len(targets))
    log_df = fetch.fetch_game_logs(targets, stats_type)
    logger.info("Game logs (%s): pulled %s game rows.", stats_type, len(log_df))

    ok = sheets_sync.push_rows(SHEET_NAMES[stats_type], log_df)
    if not ok:
        logger.warning(
            "Game logs (%s): one or more Sheets pushes failed -- not marking any "
            "season complete, next run will retry.", stats_type,
        )
        return

    for season in backfill_seasons:
        sheets_sync.mark_season_complete(season, kind=kind)


def run(active_batter_ids: set[int], active_pitcher_ids: set[int]) -> None:
    if not config.GAME_LOG_ENABLED or not config.SHEETS_SYNC_ENABLED:
        return

    batter_rows = pd.concat([
        sheets_sync.get_season_level_rows("Batter"),
        sheets_sync.get_season_level_rows("Catcher"),
    ], ignore_index=True)
    pitcher_rows = sheets_sync.get_season_level_rows("Pitcher")

    _sync_one("batting", batter_rows, active_batter_ids)
    _sync_one("pitching", pitcher_rows, active_pitcher_ids)
