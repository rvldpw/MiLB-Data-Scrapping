"""One season per UTC day, with game-level resume and automatic year rollover."""
from datetime import date, timedelta
import hashlib
import json

STATE_VERSION = 1
CLOSE_AFTER_DAYS = 30  # a past season is frozen this long after its last game


def initial_state(settings):
    return {"version": STATE_VERSION, "scope": settings.scope(), "seasons": {},
            "last_backfill_completed_on": None}


def validate_state(state, settings):
    if state.get("version") != STATE_VERSION or not isinstance(state.get("scope"), dict):
        raise ValueError("Dataset state version differs from this scanner; use a separate dataset")
    if not isinstance(state.get("seasons"), dict):
        raise ValueError("Dataset state is malformed")
    for year, record in state["seasons"].items():
        if not str(year).isdigit() or not isinstance(record, dict):
            raise ValueError("Dataset season state is malformed")
        if record.get("final_complete") and not record.get("initialized"):
            raise ValueError("A final season cannot be marked complete without initialization")


def widen_scope(state, wanted):
    """Adopt a configuration that covers more than the stored one; anything else is refused.

    Added levels or game types make every stored season incomplete again. Its per-game progress is
    kept, so the next runs fetch only the games that are new to the scope, one season per UTC day.
    Returns the number of seasons reopened.
    """
    stored, added, removed = state["scope"], set(), set()
    try:
        for key in ("sport_ids", "game_types"):
            added |= set(wanted[key]) - set(stored[key])
            removed |= set(stored[key]) - set(wanted[key])
        later = wanted["start_season"] > stored["start_season"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Dataset state scope is malformed") from exc
    if removed or later:
        raise ValueError("Dataset scope is wider than the configuration; restore START_SEASON, SPORT_IDS "
                         "and GAME_TYPES, or use a separate dataset for a narrower scope")
    state["scope"] = wanted
    if not added:
        return 0
    for record in state["seasons"].values():
        record["initialized"] = record["final_complete"] = False
    return len(state["seasons"])


def choose_season(state, settings, today):
    for year in range(settings.start_season, today.year + 1):
        record = state["seasons"].get(str(year), {})
        if not record.get("initialized") or (year < today.year and not record.get("final_complete")):
            if state.get("last_backfill_completed_on") == today.isoformat():
                return None
            return year
    return today.year if settings.start_season <= today.year else None


def still_played(schedule, season, today):
    """Whether a season has a game ahead of it, or one that is less than CLOSE_AFTER_DAYS old.

    Winter leagues start in October and end in February, so a season is not over when its year is; the
    margin leaves room for a late make-up or an added playoff round before the season is frozen.
    Days after 1 March of the next year do not count: a stray schedule entry cannot hold up the next season.
    """
    last_day = max((g.get("listed_until") or g.get("resumeGameDate") or g["officialDate"] for g in schedule),
                   default="")
    return min(last_day, f"{season + 1}-03-01") > (today - timedelta(days=CLOSE_AFTER_DAYS)).isoformat()


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


def needs_fetch(game, index, today, refresh_days, historical, excluded=None):
    """`excluded` maps a game ID to the signature it had when its box score proved unusable."""
    signature = game_signature(game)
    if excluded and excluded.get(game["gamePk"]) == signature:
        return False  # nothing changed since it failed; a rescheduled or corrected entry is retried
    previous = index.get(str(game["gamePk"]))
    if previous is None or previous["signature"] != signature:
        return True
    if historical:
        return False
    played_on = date.fromisoformat(game.get("resumeGameDate") or game["officialDate"])
    return (played_on >= today - timedelta(days=refresh_days - 1)
            and previous["fetched_on"] != today.isoformat())
