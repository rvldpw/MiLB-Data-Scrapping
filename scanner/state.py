"""One season per UTC day, with game-level resume and automatic year rollover."""
from datetime import date, timedelta
import hashlib
import json

STATE_VERSION = 1


def initial_state(settings):
    return {"version": STATE_VERSION, "scope": settings.scope(), "seasons": {},
            "last_backfill_completed_on": None}


def validate_state(state, settings):
    if state.get("version") != STATE_VERSION or state.get("scope") != settings.scope():
        raise ValueError("Dataset state version/scope differs from configuration; use a separate dataset for a new scope")
    if not isinstance(state.get("seasons"), dict):
        raise ValueError("Dataset state is malformed")
    for year, record in state["seasons"].items():
        if not str(year).isdigit() or not isinstance(record, dict):
            raise ValueError("Dataset season state is malformed")
        if record.get("final_complete") and not record.get("initialized"):
            raise ValueError("A final season cannot be marked complete without initialization")


def choose_season(state, settings, today):
    for year in range(settings.start_season, today.year + 1):
        record = state["seasons"].get(str(year), {})
        if not record.get("initialized") or (year < today.year and not record.get("final_complete")):
            if state.get("last_backfill_completed_on") == today.isoformat():
                return None
            return year
    return today.year if settings.start_season <= today.year else None


def game_signature(game):
    relevant = {k: game.get(k) for k in
                ("officialDate", "gameDate", "resumeGameDate", "resumeDate", "gameNumber", "gameType", "status")}
    relevant["teams"] = {
        side: {"id": game["teams"][side]["team"]["id"],
               "league": game["teams"][side]["team"].get("league"),
               "score": game["teams"][side].get("score")}
        for side in ("home", "away")
    }
    return hashlib.sha256(json.dumps(relevant, sort_keys=True).encode()).hexdigest()


def needs_fetch(game, index, today, refresh_days, historical):
    previous = index.get(str(game["gamePk"]))
    if previous is None or previous["signature"] != game_signature(game):
        return True
    if historical:
        return False
    played_on = date.fromisoformat(game.get("resumeGameDate") or game["officialDate"])
    return (played_on >= today - timedelta(days=refresh_days - 1)
            and previous["fetched_on"] != today.isoformat())
