"""A daily run advances one season, or refreshes the current season."""
from datetime import datetime, timezone
import logging
import time

from .dataset import dataset_card, merge_games
from .fetch import FetchError
from .game_log import parse_boxscore
from .state import (initial_state, validate_state, widen_scope, choose_season, still_played,
                    game_signature, needs_fetch)
from .storage import read_json, json_bytes

log = logging.getLogger(__name__)


class IncompleteRun(RuntimeError):
    pass


def run(settings, client, store, now=None):
    started = time.monotonic()
    now = now or datetime.now(timezone.utc)
    today, stamp = now.date(), now.isoformat()
    state = read_json(store, "state/index.json", initial_state(settings))
    validate_state(state, settings)
    scope = settings.scope()
    if state["scope"] != scope:
        log.warning("Stored scope widened to %s; %s stored seasons reopened for the added games",
                    scope, widen_scope(state, scope))
    season = choose_season(state, settings, today)
    if season is None:
        return {"status": "waiting", "message": "Next season starts on the next UTC day", "games_fetched": 0}
    record = state["seasons"].setdefault(str(season), {})
    index_path = f"state/{season}.json"
    game_index = read_json(store, index_path, {})
    catalog = read_json(store, "catalog.json", {})
    if record.get("stored_games", 0) > 0 and not game_index:
        raise ValueError(f"Missing game progress in {index_path}; restore it before continuing")
    for entry in game_index.values():
        if not isinstance(entry, dict) or not {"signature", "fetched_on", "paths"} <= entry.keys():
            raise ValueError(f"Malformed progress in {index_path}")
    schedule = client.schedule(season)
    # A past year is closed only some weeks after its last game; until then it is refreshed like the
    # current season.
    historical = season < today.year and not still_played(schedule, season, today)
    log.info("Selected %s (%s)", season, "backfill/finalization" if historical else "season in play")
    final_games = [g for g in schedule if g["status"].get("abstractGameState") == "Final"
                   and g["officialDate"] <= today.isoformat()]
    if historical:
        missing_levels = set(settings.sport_ids) - {g["sport_id"] for g in final_games}
        if missing_levels:
            raise IncompleteRun(f"No completed games returned for {season}, sport IDs {sorted(missing_levels)}; not marking complete")
    excluded_games = dict(record.get("excluded_games", {}))
    unusable = {int(pk): entry.get("signature") for pk, entry in excluded_games.items()}
    targets = [g for g in final_games
               if needs_fetch(g, game_index, today, settings.refresh_days, historical, unusable)]
    log.info("%s final games; %s need box scores", len(final_games), len(targets))
    batch, metadata, failures, newly_excluded = [], {}, [], {}
    fetched, attempted, limited, excluded_this_run = 0, 0, False, 0

    def checkpoint(complete=False):
        nonlocal batch, metadata, newly_excluded
        files = merge_games(store, batch, game_index)
        for result in batch:
            game_index[str(result.game_pk)] = metadata[str(result.game_pk)]
            catalog.update(result.catalog)
            excluded_games.pop(str(result.game_pk), None)  # a once-unusable game that now has data
        excluded_games.update(newly_excluded)
        record.update({"last_attempt_on": today.isoformat(), "stored_games": len(game_index),
                       "scheduled_final_games": len(final_games), "last_run_errors": failures,
                       "excluded_games": excluded_games, "updated_at": stamp})
        if complete:
            was_complete = record.get("initialized") and (not historical or record.get("final_complete"))
            record.update({"initialized": True, "final_complete": historical,
                           "last_success_on": today.isoformat()})
            if not was_complete:
                state["last_backfill_completed_on"] = today.isoformat()
        files.update({"state/index.json": json_bytes(state), index_path: json_bytes(game_index),
                      "catalog.json": json_bytes(catalog), "README.md": dataset_card(catalog)})
        store.commit(files, f"MiLB {season}: {'complete snapshot' if complete else 'checkpoint'} ({len(game_index)} games)")
        log.info("Committed %s games; %s total stored for %s", len(batch), len(game_index), season)
        batch, metadata, newly_excluded = [], {}, {}

    for game in targets:
        if ((settings.max_games and attempted >= settings.max_games)
                or time.monotonic() - started >= settings.max_run_minutes * 60):
            limited = True
            break
        attempted += 1
        try:
            result = parse_boxscore(game, client.boxscore(game["gamePk"]), stamp)
        except FetchError as exc:
            failures.append({"game_pk": game["gamePk"], "error": str(exc)})
            log.error("Game %s failed (retryable): %s", game["gamePk"], exc)
            continue
        except ValueError as exc:
            # parse_boxscore raises ValueError only for a game whose own schedule/box-score
            # entry is missing required data (e.g. a cancelled or postponed game that MLB's
            # feed marks "Final" with no score). Retrying the same entry never fixes it, so
            # record it once with its signature rather than blocking the season; a postponed
            # game is fetched again when its schedule entry changes (state.needs_fetch).
            newly_excluded[str(game["gamePk"])] = {"error": str(exc), "excluded_on": today.isoformat(),
                                                   "signature": game_signature(game)}
            excluded_this_run += 1
            log.warning("Game %s excluded until its schedule entry changes (source data gap): %s", game["gamePk"], exc)
            continue
        batch.append(result)
        metadata[str(result.game_pk)] = {"signature": game_signature(game), "fetched_on": today.isoformat(),
                                         "paths": sorted(result.tables)}
        fetched += 1
        if len(batch) >= settings.checkpoint_games:
            checkpoint()
    complete = not limited and not failures
    # Avoid an empty off-season commit on every run after initialization.
    if batch or newly_excluded or targets or not record.get("initialized") or (historical and not record.get("final_complete")):
        checkpoint(complete=complete)
    summary = {"season": season, "status": "complete" if complete else "partial",
               "games_fetched": fetched, "stored_games": len(game_index),
               "scheduled_final_games": len(final_games), "failures": len(failures),
               "excluded_games": len(excluded_games)}
    if failures:
        log.warning("%s games failed for %s; successful games saved, retry next run", len(failures), season)
    if excluded_this_run:
        log.warning("%s games excluded for %s this run (%s excluded in total)",
                    excluded_this_run, season, len(excluded_games))
    return summary
