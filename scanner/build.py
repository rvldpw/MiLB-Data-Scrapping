"""A daily run advances one season, or refreshes the current season."""
from datetime import datetime, timezone
import logging
import time

from .dataset import dataset_card, merge_games
from .fetch import FetchError
from .game_log import parse_boxscore
from .state import initial_state, validate_state, choose_season, game_signature, needs_fetch
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
    season = choose_season(state, settings, today)
    if season is None:
        return {"status": "waiting", "message": "Next season starts on the next UTC day", "games_fetched": 0}
    historical = season < today.year
    record = state["seasons"].setdefault(str(season), {})
    index_path = f"state/{season}.json"
    game_index = read_json(store, index_path, {})
    catalog = read_json(store, "catalog.json", {})
    if record.get("stored_games", 0) > 0 and not game_index:
        raise ValueError(f"Missing game progress in {index_path}; restore it before continuing")
    for entry in game_index.values():
        if not isinstance(entry, dict) or not {"signature", "fetched_on", "paths"} <= entry.keys():
            raise ValueError(f"Malformed progress in {index_path}")
    log.info("Selected %s (%s)", season, "backfill/finalization" if historical else "current season")
    schedule = client.schedule(season)
    final_games = [g for g in schedule if g["status"].get("abstractGameState") == "Final"
                   and g["officialDate"] <= today.isoformat()]
    if historical:
        missing_levels = set(settings.sport_ids) - {g["sport_id"] for g in final_games}
        if missing_levels:
            raise IncompleteRun(f"No completed games returned for {season}, sport IDs {sorted(missing_levels)}; not marking complete")
    targets = [g for g in final_games if needs_fetch(g, game_index, today, settings.refresh_days, historical)]
    log.info("%s final games; %s need box scores", len(final_games), len(targets))
    batch, metadata, failures = [], {}, []
    fetched, attempted, limited = 0, 0, False

    def checkpoint(complete=False):
        nonlocal batch, metadata
        files = merge_games(store, batch, game_index)
        for result in batch:
            game_index[str(result.game_pk)] = metadata[str(result.game_pk)]
            catalog.update(result.catalog)
        record.update({"last_attempt_on": today.isoformat(), "stored_games": len(game_index),
                       "scheduled_final_games": len(final_games), "last_run_errors": failures,
                       "updated_at": stamp})
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
        batch, metadata = [], {}

    for game in targets:
        if ((settings.max_games and attempted >= settings.max_games)
                or time.monotonic() - started >= settings.max_run_minutes * 60):
            limited = True
            break
        attempted += 1
        try:
            result = parse_boxscore(game, client.boxscore(game["gamePk"]), stamp)
        except (FetchError, ValueError, KeyError, TypeError) as exc:
            failures.append({"game_pk": game["gamePk"], "error": str(exc)})
            log.error("Game %s failed: %s", game["gamePk"], exc)
            continue
        batch.append(result)
        metadata[str(result.game_pk)] = {"signature": game_signature(game), "fetched_on": today.isoformat(),
                                         "paths": sorted(result.tables)}
        fetched += 1
        if len(batch) >= settings.checkpoint_games:
            checkpoint()
    complete = not limited and not failures
    # Avoid an empty off-season commit on every run after initialization.
    if batch or targets or not record.get("initialized") or (historical and not record.get("final_complete")):
        checkpoint(complete=complete)
    summary = {"season": season, "status": "complete" if complete else "partial",
               "games_fetched": fetched, "stored_games": len(game_index),
               "scheduled_final_games": len(final_games), "failures": len(failures)}
    if failures:
        log.warning("%s games failed for %s; successful games saved, retry next run", len(failures), season)
    return summary
