"""All MLB Stats API access lives here.

One shared session with bounded retries and a real timeout on every call. Every
request is built from two fixed, hardcoded hosts plus validated parameters — never
from unvalidated user input. Responses are parsed strictly as JSON; anything that
doesn't look right is logged and skipped rather than raised, so one bad team/season
never kills a run.
"""
import json
import logging
import time
from typing import Optional

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config

logger = logging.getLogger("milb_scanner.fetch")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _build_session() -> requests.Session:
    session = requests.Session()
    retry_cfg = Retry(
        total=config.MAX_RETRIES,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_cfg)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": _USER_AGENT, "Accept": "application/json"})
    return session


SESSION = _build_session()


def safe_get_json(url: str) -> Optional[dict]:
    try:
        resp = SESSION.get(url, timeout=config.REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("Request failed: %s (%s)", url, exc)
        return None

    time.sleep(config.RATE_LIMIT_DELAY)

    if resp.status_code != 200:
        logger.warning("HTTP %s for %s", resp.status_code, url)
        return None
    try:
        return resp.json()
    except ValueError:
        logger.warning("Non-JSON response for %s", url)
        return None


def _validate_season(season: int) -> None:
    if not (2005 <= season <= config.SEASON_END):
        raise ValueError(f"season {season} out of supported range (2005-{config.SEASON_END})")


def _validate_level(level: str) -> int:
    if level not in config.LEVELS:
        raise ValueError(f"level must be one of {list(config.LEVELS)}, got {level!r}")
    return config.LEVELS[level]


def get_teams_for_level(season: int, level: str) -> list[int]:
    """Team IDs playing at `level` in `season`. Cached for the duration of this run."""
    _validate_season(season)
    level_id = _validate_level(level)

    cache_file = config.CACHE_DIR / f"teams_{season}.json"
    if cache_file.exists():
        all_teams = json.loads(cache_file.read_text())
    else:
        data = safe_get_json(f"{config.STATS_API_HOST}/api/v1/teams?season={season}")
        all_teams = data.get("teams", []) if data else []
        cache_file.write_text(json.dumps(all_teams))

    return [t["id"] for t in all_teams if t.get("sport", {}).get("id") == level_id]


# --- Field maps: raw MLB Stats API key -> clean output column name -------------------
BATTING_FIELD_MAP = {
    "gamesPlayed": "G", "plateAppearances": "batting_PA", "atBats": "batting_AB",
    "hits": "batting_H", "doubles": "batting_2B", "triples": "batting_3B",
    "homeRuns": "batting_HR", "rbi": "batting_RBI", "runs": "batting_R",
    "stolenBases": "batting_SB", "caughtStealing": "batting_CS",
    "baseOnBalls": "batting_BB", "intentionalWalks": "batting_IBB",
    "strikeOuts": "batting_SO", "totalBases": "batting_TB",
    "gidpOpp": "batting_GiDP_Opp", "groundIntoDoublePlay": "batting_GiDP",
    "sacBunts": "batting_SH", "sacFlies": "batting_SF", "hitByPitch": "batting_HBP",
    "extraBaseHits": "batting_XBH", "groundOuts": "batting_GO", "airOuts": "batting_AO",
    "flyOuts": "batting_FO", "popOuts": "batting_PO", "lineOuts": "batting_LO",
    "catchersInterference": "batting_CI", "leftOnBase": "batting_LOB",
    "groundHits": "batting_ground_hits", "flyHits": "batting_fly_hits",
    "popHits": "batting_pop_hits", "lineHits": "batting_line_hits",
    "numberOfPitches": "batting_pitches_faced", "totalSwings": "batting_swings",
    "swingAndMisses": "batting_whiffs", "ballsInPlay": "batting_balls_in_play",
    "reachedOnError": "batting_reached_on_error", "walkOffs": "batting_walkoffs",
}

PITCHING_FIELD_MAP = {
    "wins": "pitching_W", "losses": "pitching_L", "gamesPitched": "pitching_G",
    "gamesStarted": "pitching_GS", "gamesFinished": "pitching_GF",
    "completeGames": "pitching_CG", "qualityStarts": "pitching_QS",
    "shutouts": "pitching_SHO", "saveOpportunities": "pitching_SVO",
    "saves": "pitching_SV", "holds": "pitching_HLD", "blownSaves": "pitching_BS",
    "inningsPitched": "pitching_IP_str", "outs": "pitching_outs",
    "battersFaced": "pitching_BF", "atBats": "pitching_AB", "runs": "pitching_R",
    "hits": "pitching_H", "doubles": "pitching_2B", "triples": "pitching_3B",
    "earnedRuns": "pitching_ER", "homeRuns": "pitching_HR", "totalBases": "pitching_TB",
    "baseOnBalls": "pitching_BB", "intentionalWalks": "pitching_IBB",
    "strikeOuts": "pitching_SO", "hitByPitch": "pitching_HBP", "balks": "pitching_BK",
    "groundIntoDoublePlay": "pitching_GiDP", "gidpOpp": "pitching_GiDP_Opp",
    "catchersInterference": "pitching_CI", "inheritedRunners": "pitching_IR",
    "inheritedRunnersScored": "pitching_IRS", "bequeathedRunners": "pitching_BqR",
    "bequeathedRunnersScored": "pitching_BqRS", "runSupport": "pitching_RS",
    "sacFlies": "pitching_SF", "stolenBases": "pitching_SB",
    "caughtStealing": "pitching_CS", "pickoffs": "pitching_PK",
    "flyHits": "pitching_FH", "popHits": "pitching_PH", "lineHits": "pitching_LH",
    "flyOuts": "pitching_FO", "groundOuts": "pitching_GO", "airOuts": "pitching_AO",
    "popOuts": "pitching_pop_outs", "lineOuts": "pitching_line_outs",
    "numberOfPitches": "pitching_PI", "totalSwings": "pitching_total_swings",
    "swingAndMisses": "pitching_swing_and_misses", "ballsInPlay": "pitching_balls_in_play",
    "strikes": "pitching_PI_strikes", "wildPitches": "pitching_WP",
}


def _build_row(stat_line: dict, field_map: dict, season: int, team_id: int,
               level: str) -> dict:
    row = {
        "season": season,
        "team_id": team_id,
        "team_abv": stat_line.get("teamAbbrev"),
        "team_name": stat_line.get("teamName"),
        "team_league_id": stat_line.get("leagueId"),
        "team_league": stat_line.get("leagueName"),
        "team_level": level,
        "team_level_id": config.LEVELS[level],
        "player_id": stat_line.get("playerId"),
        "player_full_name": stat_line.get("playerFullName"),
        "player_first_name": stat_line.get("playerFirstName"),
        "player_last_name": stat_line.get("playerLastName"),
        "player_use_name": stat_line.get("playerUseName"),
        "player_initial_name": stat_line.get("playerInitLastName"),
    }
    primary_pos = stat_line.get("primaryPositionAbbrev")
    full_pos = stat_line.get("positionAbbrev")
    row["player_primary_position"] = primary_pos
    row["player_position"] = (
        primary_pos if primary_pos == full_pos else f"{primary_pos}/{full_pos}"
    )
    for raw_key, out_col in field_map.items():
        row[out_col] = stat_line.get(raw_key)
    return row


def _fetch_team_season_stats(season: int, level: str, team_id: int,
                              stats_type: str) -> pd.DataFrame:
    group = "hitting" if stats_type == "batting" else "pitching"
    level_id = config.LEVELS[level]
    url = (
        f"{config.BDFED_HOST}/bdfed/stats/player"
        f"?stitch_env=prod&season={season}&sportId={level_id}&teamId={team_id}"
        f"&stats=season&group={group}&gameType=R&limit=100&offset=0&playerPool=ALL"
    )
    data = safe_get_json(url)
    if not data or not data.get("stats"):
        return pd.DataFrame()

    field_map = BATTING_FIELD_MAP if stats_type == "batting" else PITCHING_FIELD_MAP
    rows = [_build_row(line, field_map, season, team_id, level) for line in data["stats"]]
    return pd.DataFrame(rows)


def pull_season_level(season: int, level: str, stats_type: str) -> pd.DataFrame:
    """Pull every team's stat lines for one (season, level, stats_type). No caching
    across runs here — the "don't re-download finished seasons" decision is made one
    layer up, before this function is even called (see scanner.build)."""
    _validate_season(season)
    _validate_level(level)
    if stats_type not in ("batting", "pitching"):
        raise ValueError("stats_type must be 'batting' or 'pitching'")

    team_ids = get_teams_for_level(season, level)
    frames = []
    for team_id in team_ids:
        try:
            frames.append(_fetch_team_season_stats(season, level, team_id, stats_type))
        except Exception as exc:  # noqa: BLE001 - keep the run alive on bad team data
            logger.warning("Skipped team %s (%s %s): %s", team_id, season, level, exc)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def fetch_player_bio(player_id: int) -> dict:
    """One lookup, keyed strictly by the numeric MLB person ID — the exact same
    `player_id` that came attached to the stat line in `_build_row`. Never matched
    or re-matched by name, so a common name (there are multiple "Jose Rodriguez"s
    in the minors at any given time) can't get paired with the wrong bio."""
    data = safe_get_json(f"{config.STATS_API_HOST}/api/v1/people/{player_id}")
    person = (data.get("people") or [{}])[0] if data else {}
    return {
        "player_id": player_id,
        "birth_date": person.get("birthDate"),
        "height": person.get("height"),
        "weight": person.get("weight"),
        "bats": (person.get("batSide") or {}).get("code"),
        "throws": (person.get("pitchHand") or {}).get("code"),
        "mlb_debut_date": person.get("mlbDebutDate"),
        "birth_country": person.get("birthCountry"),
    }


def fetch_player_bios(player_ids: list[int]) -> pd.DataFrame:
    """Bio lookup for a batch of unique player IDs. One API call per player, each
    one an independent ID-keyed request — no batching-by-name, no fuzzy matching."""
    if not player_ids:
        return pd.DataFrame(columns=[
            "player_id", "birth_date", "height", "weight", "bats", "throws",
            "mlb_debut_date", "birth_country",
        ])
    rows = []
    for i, pid in enumerate(player_ids, start=1):
        rows.append(fetch_player_bio(pid))
        if i % 200 == 0:
            logger.info("Fetched bios for %s/%s active players", i, len(player_ids))
    return pd.DataFrame(rows)
