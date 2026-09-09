"""Orchestrates one end-to-end run: figure out what's new, pull only that, split into
Batter/Pitcher/Catcher, write a local artifact, and sync to the Google Sheets databank.

Incremental strategy
---------------------
The Google Sheet is the source of truth for "what's already been downloaded":
  1. Ask the Sheet which past seasons are already marked complete.
  2. Skip re-fetching those entirely — a season strictly before the current calendar
     year is over and its numbers don't change, so once it's synced, it's done for good.
  3. Always (re-)fetch the current season, since it's still in progress.
  4. Push whatever was fetched this run to the Sheet (upsert, so re-running the same
     season is always safe/idempotent) and mark any freshly-fetched *prior* season
     complete so future runs skip it too.

The local CSV/XLSX this run writes only contains what was actually pulled *this run*
(the delta) — the full career history lives cumulatively in the Google Sheet, built
up across runs. First run ever = full 2021-2026 backfill; every run after that is
just the current season.
"""
import logging

import pandas as pd

from . import config, fetch, metrics, sheets_sync

logger = logging.getLogger("milb_scanner.build")


def determine_seasons_to_fetch(completed_seasons: set[int]) -> list[int]:
    return [
        s for s in range(config.SEASON_START, config.SEASON_END + 1)
        if not config.is_final_season(s) or s not in completed_seasons
    ]


def pull_seasons(seasons: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    batting_frames, pitching_frames = [], []
    for season in seasons:
        for level in config.LEVELS:
            logger.info("Pulling %s %s ...", season, level)
            batting_frames.append(fetch.pull_season_level(season, level, "batting"))
            pitching_frames.append(fetch.pull_season_level(season, level, "pitching"))

    batting_raw = pd.concat(batting_frames, ignore_index=True) if batting_frames else pd.DataFrame()
    pitching_raw = pd.concat(pitching_frames, ignore_index=True) if pitching_frames else pd.DataFrame()
    return batting_raw, pitching_raw


def split_sheets(batting_full: pd.DataFrame, pitching_full: pd.DataFrame):
    if batting_full.empty:
        active_batter_ids, active_pitcher_ids = set(), set()
    else:
        active_batter_ids = set(
            batting_full.loc[batting_full["season"] == config.ACTIVE_SEASON, "player_id"]
        )
    if not pitching_full.empty:
        active_pitcher_ids = set(
            pitching_full.loc[pitching_full["season"] == config.ACTIVE_SEASON, "player_id"]
        )
    else:
        active_pitcher_ids = set()

    batting_active = batting_full[batting_full["player_id"].isin(active_batter_ids)].copy() \
        if not batting_full.empty else batting_full
    pitching_active = pitching_full[pitching_full["player_id"].isin(active_pitcher_ids)].copy() \
        if not pitching_full.empty else pitching_full

    if batting_active.empty:
        sheet_batter, sheet_catcher = batting_active, batting_active
    else:
        is_catcher = batting_active["player_primary_position"] == "C"
        sheet_catcher = batting_active[is_catcher].copy()
        sheet_batter = batting_active[~is_catcher].copy()

    sheet_pitcher = pitching_active

    sort_cols = ["player_full_name", "season", "team_level"]
    for df in (sheet_batter, sheet_catcher, sheet_pitcher):
        if not df.empty:
            df.sort_values(sort_cols, inplace=True)

    return sheet_batter, sheet_pitcher, sheet_catcher


def enrich_with_age(sheet_batter, sheet_pitcher, sheet_catcher):
    """Bio/age lookup, run once against the union of active player IDs across all
    three sheets (never per-row, never per-name) so each unique player is only
    looked up once even if they'd otherwise appear more than once."""
    all_ids = pd.concat([
        sheet_batter["player_id"] if not sheet_batter.empty else pd.Series(dtype="Int64"),
        sheet_pitcher["player_id"] if not sheet_pitcher.empty else pd.Series(dtype="Int64"),
        sheet_catcher["player_id"] if not sheet_catcher.empty else pd.Series(dtype="Int64"),
    ]).dropna().unique().tolist()

    if not all_ids:
        return sheet_batter, sheet_pitcher, sheet_catcher

    logger.info("Fetching bio/age for %s unique active players...", len(all_ids))
    bios = fetch.fetch_player_bios(all_ids)

    return (
        metrics.add_age(sheet_batter, bios),
        metrics.add_age(sheet_pitcher, bios),
        metrics.add_age(sheet_catcher, bios),
    )


def filter_out_mlb_debuted(sheet_batter, sheet_pitcher, sheet_catcher):
    """Drop any player who already has an mlb_debut_date -- i.e. has appeared in a
    real MLB game at some point (current call-up, rehab assignment, or a past
    debut). These aren't prospects anymore and would distort the databank if left
    in, even though their stat line at AA/A+/A is otherwise valid. Requires bio
    enrichment to have run first (mlb_debut_date only exists after enrich_with_age);
    no-ops safely if that column isn't present, e.g. ENRICH_WITH_BIO=false."""
    def _drop_debuted(df):
        if df.empty or "mlb_debut_date" not in df.columns:
            return df
        before = len(df)
        out = df[df["mlb_debut_date"].isna()].copy()
        dropped = before - len(out)
        if dropped:
            logger.info("Filtered out %s row(s) belonging to already-debuted MLB players", dropped)
        return out

    return _drop_debuted(sheet_batter), _drop_debuted(sheet_pitcher), _drop_debuted(sheet_catcher)


def write_local_artifact(sheet_batter, sheet_pitcher, sheet_catcher) -> None:
    out_file = config.OUTPUT_DIR / "milb_prospect_scan_delta.xlsx"
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        (sheet_batter if not sheet_batter.empty else pd.DataFrame()).to_excel(
            writer, sheet_name="Batter", index=False)
        (sheet_pitcher if not sheet_pitcher.empty else pd.DataFrame()).to_excel(
            writer, sheet_name="Pitcher", index=False)
        (sheet_catcher if not sheet_catcher.empty else pd.DataFrame()).to_excel(
            writer, sheet_name="Catcher", index=False)
    logger.info("Local delta artifact written to %s", out_file.resolve())


def run() -> None:
    completed_seasons = sheets_sync.get_completed_seasons()
    logger.info("Seasons already marked complete in the databank: %s", sorted(completed_seasons))

    seasons_to_fetch = determine_seasons_to_fetch(completed_seasons)
    freshly_final_seasons = [s for s in seasons_to_fetch if config.is_final_season(s)]
    logger.info(
        "This run will fetch seasons %s (skipping %s already-complete seasons)",
        seasons_to_fetch, sorted(completed_seasons & set(range(config.SEASON_START, config.SEASON_END + 1))),
    )

    if not seasons_to_fetch:
        logger.info("Nothing to do — everything is already synced.")
        return

    batting_raw, pitching_raw = pull_seasons(seasons_to_fetch)
    batting_full = metrics.add_batting_rates(batting_raw)
    pitching_full = metrics.add_pitching_rates(pitching_raw)

    sheet_batter, sheet_pitcher, sheet_catcher = split_sheets(batting_full, pitching_full)

    if config.ENRICH_WITH_BIO:
        sheet_batter, sheet_pitcher, sheet_catcher = enrich_with_age(
            sheet_batter, sheet_pitcher, sheet_catcher
        )
        sheet_batter, sheet_pitcher, sheet_catcher = filter_out_mlb_debuted(
            sheet_batter, sheet_pitcher, sheet_catcher
        )

    logger.info(
        "This run's delta -> Batter: %s rows | Pitcher: %s rows | Catcher: %s rows",
        len(sheet_batter), len(sheet_pitcher), len(sheet_catcher),
    )

    write_local_artifact(sheet_batter, sheet_pitcher, sheet_catcher)

    ok = True
    ok &= sheets_sync.push_rows("Batter", sheet_batter)
    ok &= sheets_sync.push_rows("Pitcher", sheet_pitcher)
    ok &= sheets_sync.push_rows("Catcher", sheet_catcher)

    if not ok:
        logger.warning(
            "One or more Sheets pushes failed — the local artifact still has this "
            "run's data, but the databank may be out of sync. Not marking any season "
            "complete this run, so the next run will retry the full fetch."
        )
        return

    for season in freshly_final_seasons:
        sheets_sync.mark_season_complete(season)

    logger.info("Run complete.")
