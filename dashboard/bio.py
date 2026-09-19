"""Where is each player today? Answered from the MLB Stats API.

`player_id` in the game logs is the real MLB person ID, so no name matching is
needed. For every player we resolve the *current team*, then map that team to
its level (MLB, Triple-A, Double-A, High-A, Single-A, Rookie) with the API's own
team list. That is the reliable signal: the API's per-player `active` flag is
often False for minor leaguers who are on a roster, so it is not used.

A player with no current team is reported as "No team", never guessed to be
released or retired. Roster status (injured list, restricted, etc.) is read from
the current team's full roster when the API supplies it.

Everything is cached on disk (people for 3 days, team list and rosters for 1
day) and fetched in bulk and in parallel, so filtering a whole league is one
short wait the first time.
"""
import json
import time
from html import escape
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from requests.adapters import HTTPAdapter, Retry

CACHE_DIR = Path(__file__).with_name("cache")
PEOPLE_TTL = 3 * 24 * 3600
TEAM_TTL = 24 * 3600
BATCH = 100
API = "https://statsapi.mlb.com/api/v1"

# MLB Stats API sport ids -> the labels used everywhere in the dashboard.
LEVEL_BY_SPORT = {1: "MLB", 11: "Triple-A", 12: "Double-A", 13: "High-A", 14: "Single-A", 16: "Rookie / complex"}
LEVEL_ORDER = ["MLB", "Triple-A", "Double-A", "High-A", "Single-A", "Rookie / complex", "Other league", "No team", "Unknown"]
# How the scanner labels its own levels.
DATA_LEVEL = {"AAA": "Triple-A", "AA": "Double-A", "A+": "High-A", "A": "Single-A", "R": "Rookie / complex"}
STATES = ["Active", "Injured list", "Restricted list", "Suspended", "Development list"]

# Level chips: (background, text). Soft tints, all >= 4.5:1 contrast.
LEVEL_COLOR = {
    "MLB": ("#1f4e8c", "#ffffff"), "Triple-A": ("#dce8fa", "#173f75"), "Double-A": ("#d5f0e0", "#0d6a3b"),
    "High-A": ("#fff0c2", "#7a5200"), "Single-A": ("#fde0cf", "#a03e0c"), "Rookie / complex": ("#e7ece4", "#3f4f45"),
    "Other league": ("#eef1ec", "#55645a"), "No team": ("#eef1ec", "#55645a"), "Unknown": ("#eef1ec", "#55645a"),
}


COLUMNS = ["player_id", "age", "birth_date", "debut_date", "current_team", "team_id", "current_org", "current_level", "sport_id",
           "position", "height", "height_cm", "weight_lb", "weight_kg", "bats", "throws", "birthplace", "fetched_at"]


def _read(name):
    try:
        return json.loads((CACHE_DIR / name).read_text())
    except Exception:
        return {}


def _write(name, data):
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        (CACHE_DIR / name).write_text(json.dumps(data))
    except Exception:
        pass  # best effort: a failed write only means a re-fetch later


# One pooled session: the API rate-limits bursts, so retry a few times before giving up.
SESSION = requests.Session()
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=.6, respect_retry_after_header=True,
                                                       status_forcelist=(429, 500, 502, 503, 504))))


def _get(path, **params):
    r = SESSION.get(f"{API}/{path}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _season():
    return date.today().year


def team_map():
    """{team_id: [sport_id, org_name]} for MLB and every affiliated level."""
    cached = _read("teams.json")
    if cached.get("season") == _season() and time.time() - cached.get("at", 0) < TEAM_TTL and cached.get("teams"):
        return cached["teams"]
    teams = {}
    for season in (_season(), _season() - 1):  # early in a year the new season may not be listed yet
        for t in _get("teams", sportIds=",".join(map(str, LEVEL_BY_SPORT)), season=season).get("teams", []):
            org = t["name"] if t["sport"]["id"] == 1 else t.get("parentOrgName") or t["name"]
            teams.setdefault(str(t["id"]), [t["sport"]["id"], org])
        if teams:
            break
    if not teams:
        raise ValueError("MLB team list is empty")
    _write("teams.json", {"season": _season(), "at": time.time(), "teams": teams})
    return teams


def _height_to_cm(height):
    try:
        feet, inches = str(height).replace('"', "").split("'")
        return round((int(feet) * 12 + int(inches)) * 2.54)
    except Exception:
        return None


def _state(code, description):
    code = (code or "").upper()
    if code == "A":
        return "Active"
    if code == "DEV":
        return "Development list"
    if code.startswith("D") or code.startswith("IL"):
        return "Injured list"
    if code in ("RST", "BRV", "PL", "FAM", "PAT"):
        return "Restricted list"
    if code.startswith("SUS"):
        return "Suspended"
    return description or None


def _level(team_id, teams):
    if not team_id:
        return None, "No team", None
    hit = teams.get(str(team_id))
    if not hit:
        return None, "Other league", None
    return hit[0], LEVEL_BY_SPORT.get(hit[0], "Other league"), hit[1]


def _person_row(p, teams):
    team = p.get("currentTeam") or {}
    sport_id, level, org = _level(team.get("id"), teams)
    weight = p.get("weight")
    return dict(
        player_id=int(p["id"]), age=p.get("currentAge"), birth_date=p.get("birthDate"), debut_date=p.get("mlbDebutDate"),
        current_team=team.get("name"), team_id=team.get("id"), current_org=org, current_level=level, sport_id=sport_id,
        position=(p.get("primaryPosition") or {}).get("abbreviation"),
        height=p.get("height"), height_cm=_height_to_cm(p.get("height")), weight_lb=weight,
        weight_kg=round(weight * 0.453592) if weight else None,
        bats=(p.get("batSide") or {}).get("description"), throws=(p.get("pitchHand") or {}).get("description"),
        birthplace=", ".join(x for x in (p.get("birthCity"), p.get("birthStateProvince") or p.get("birthCountry")) if x),
        fetched_at=time.time(),
    )


def _fetch_people(ids, teams):
    data = _get("people", personIds=",".join(map(str, ids)), hydrate="currentTeam")
    return [_person_row(p, teams) for p in data.get("people", [])]


def _roster_states(team_ids):
    """{player_id: state} from each team's full roster. Best effort."""
    cache = _read("rosters.json")
    now = time.time()
    fresh = {t: v for t, v in cache.items() if now - v.get("at", 0) < TEAM_TTL}

    def fetch(tid):
        try:
            roster = _get(f"teams/{tid}/roster", rosterType="fullRoster", season=_season()).get("roster", [])
            return tid, {"at": now, "players": {str(r["person"]["id"]): _state(r["status"].get("code"), r["status"].get("description")) for r in roster}}
        except Exception:
            return tid, None
    todo = [str(t) for t in team_ids if str(t) not in fresh]
    if todo:
        with ThreadPoolExecutor(max_workers=16) as pool:
            for tid, value in pool.map(fetch, todo):
                if value is not None:
                    fresh[tid] = value
        _write("rosters.json", fresh)
    return {pid: state for tid in map(str, team_ids) for pid, state in fresh.get(tid, {}).get("players", {}).items()}


def _lookup(player_ids, max_workers=6, with_roster=True):
    """One row per requested player_id (always)."""
    ids = sorted({int(x) for x in player_ids})
    cache = _read("bios.json")
    now = time.time()
    missing = [i for i in ids if str(i) not in cache or now - cache[str(i)].get("fetched_at", 0) > PEOPLE_TTL]
    if missing:
        try:
            teams = team_map()
            batches = [missing[i:i + BATCH] for i in range(0, len(missing), BATCH)]
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                for rows in pool.map(lambda b: _safe(_fetch_people, b, teams), batches):
                    for row in rows:
                        cache[str(row["player_id"])] = row
            _write("bios.json", cache)
        except Exception:
            pass  # players we could not resolve fall through to "Unknown" below
    rows = [cache.get(str(i)) or dict(player_id=i, current_level="Unknown", sport_id=None, team_id=None) for i in ids]
    frame = pd.DataFrame(rows, columns=COLUMNS) if not rows else pd.DataFrame(rows).reindex(columns=COLUMNS)
    frame["roster_status"] = None
    if with_roster and not frame.empty:
        try:
            states = _roster_states(frame["team_id"].dropna().astype(int).unique())
            frame["roster_status"] = frame["player_id"].astype(str).map(states)
        except Exception:
            pass
    return frame


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return []


def level_rank(level):
    return LEVEL_ORDER.index(level) if level in LEVEL_ORDER else len(LEVEL_ORDER)


def pool_ids(bios, mode, level, picked=()):
    """Player ids allowed by the 'where are they now' filter.

    mode: 'same' = still at `level`, 'up' = moved above it, 'pick' = any of `picked`.
    """
    now = bios["current_level"]
    if mode == "same":
        keep = now.eq(level)
    elif mode == "up":
        keep = now.map(level_rank).lt(level_rank(level)) & now.isin(list(LEVEL_BY_SPORT.values()))
    else:
        keep = now.isin(list(picked))
    return set(bios.loc[keep, "player_id"].astype(int))


def level_chip_html(level, state=None):
    bg, fg = LEVEL_COLOR.get(level, LEVEL_COLOR["Unknown"])
    extra = f" · {escape(state)}" if isinstance(state, str) and state != "Active" else ""
    return f"<span class='lvl' style='background:{bg};color:{fg}'>{escape(level)}{extra}</span>"


@st.cache_data(ttl=900, show_spinner=False, max_entries=32)
def _cached_lookup(ids, with_roster):
    return _lookup(ids, with_roster=with_roster)


def get_bios(player_ids, with_roster=True):
    """Bios for these players, reusing this session's lookups before touching disk or the network."""
    return _cached_lookup(tuple(sorted({int(x) for x in player_ids})), with_roster)
