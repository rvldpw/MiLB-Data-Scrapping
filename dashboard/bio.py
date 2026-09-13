"""Live player status, straight from the MLB Stats API (the same `player_id`
already in the game logs is a real MLB person ID, so no matching/guessing is
needed). Answers exactly the question "is this guy still active in MLB, back
down in MiLB, released, hurt, retired?" - none of which the game-log dataset
itself can tell you, since it only has box-score rows.

Results are cached to a small JSON file on disk (a person's org/roster status
doesn't change minute to minute) so repeat sessions don't re-fetch everyone,
and a ThreadPoolExecutor fans batch lookups out concurrently so filtering a
30-40 man roster feels instant after the first fetch.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

CACHE_FILE = Path(__file__).with_name("cache") / "bios.json"
STALE_SECONDS = 3 * 24 * 3600  # 3 days
API = "https://statsapi.mlb.com/api/v1/people/{}?hydrate=currentTeam,status"

STATUS_ORDER = ["Active – MLB", "Active – MiLB", "Injured List", "Restricted / Suspended",
                "Free Agent / Released", "Retired", "Other / Unknown"]
STATUS_COLOR = {
    "Active – MLB": "#22c55e", "Active – MiLB": "#3b82f6", "Injured List": "#f59e0b",
    "Restricted / Suspended": "#f97316", "Free Agent / Released": "#94a3b8",
    "Retired": "#64748b", "Other / Unknown": "#64748b",
}


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    try:
        CACHE_FILE.parent.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache))
    except Exception:
        pass  # best-effort; a failed write just means we re-fetch next time


def _bucket(active: bool, sport_id, roster_status: str) -> str:
    rs = (roster_status or "").lower()
    if "injured" in rs or rs.startswith("il") or "day-to-day" in rs:
        return "Injured List"
    if "restrict" in rs or "suspend" in rs or "bereavement" in rs or "paternity" in rs:
        return "Restricted / Suspended"
    if "retired" in rs:
        return "Retired"
    if active and sport_id == 1:
        return "Active – MLB"
    if active and sport_id in {11, 12, 13, 14, 16}:
        return "Active – MiLB"
    if "free agent" in rs or "released" in rs:
        return "Free Agent / Released"
    return "Other / Unknown"


def _height_to_cm(height: str):
    """MLB Stats API returns height as e.g. \"6' 2\\\"\" - convert to whole cm."""
    if not height:
        return None
    try:
        feet, inches = height.replace('"', "").split("'")
        total_inches = int(feet.strip()) * 12 + int(inches.strip())
        return round(total_inches * 2.54)
    except Exception:
        return None


def _fetch_one(player_id: int) -> dict:
    try:
        r = requests.get(API.format(int(player_id)), timeout=6)
        r.raise_for_status()
        people = r.json().get("people") or []
        if not people:
            raise ValueError("no person")
        p = people[0]
        team = p.get("currentTeam") or {}
        sport = team.get("sport") or {}
        roster_status = (p.get("status") or {}).get("description")
        active = bool(p.get("active"))
        birthplace = ", ".join(x for x in (p.get("birthCity"), p.get("birthStateProvince") or p.get("birthCountry")) if x)
        row = dict(
            player_id=int(player_id), age=p.get("currentAge"), birth_date=p.get("birthDate"),
            debut_date=p.get("mlbDebutDate"), last_played=p.get("lastPlayedDate"),
            active=active, current_team=team.get("name"), sport_id=sport.get("id"),
            roster_status=roster_status, height=p.get("height"), height_cm=_height_to_cm(p.get("height")),
            weight_lb=p.get("weight"), weight_kg=round(p["weight"] * 0.453592) if p.get("weight") else None,
            bats=(p.get("batSide") or {}).get("description"), throws=(p.get("pitchHand") or {}).get("description"),
            birthplace=birthplace, fetched_at=time.time(),
        )
        row["status"] = _bucket(active, sport.get("id"), roster_status)
    except Exception:
        row = dict(player_id=int(player_id), age=None, birth_date=None, debut_date=None,
                   last_played=None, active=None, current_team=None, sport_id=None,
                   roster_status=None, height=None, height_cm=None, weight_lb=None, weight_kg=None,
                   bats=None, throws=None, birthplace=None, status="Other / Unknown", fetched_at=time.time())
    return row


def get_bios(player_ids, max_workers: int = 10, progress=None) -> pd.DataFrame:
    """Return a bio/status row per player_id, hitting the network only for
    ids that are missing from the cache or stale. `progress`, if given, is a
    Streamlit progress bar/callable updated as fetches complete.
    """
    ids = sorted({int(x) for x in player_ids})
    cache = _load_cache()
    now = time.time()
    missing = [pid for pid in ids if str(pid) not in cache
               or now - cache[str(pid)].get("fetched_at", 0) > STALE_SECONDS]

    if missing:
        done = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_fetch_one, pid): pid for pid in missing}
            for fut in as_completed(futures):
                row = fut.result()
                cache[str(row["player_id"])] = row
                done += 1
                if progress is not None:
                    progress(done / len(missing))
        _save_cache(cache)

    rows = [cache[str(pid)] for pid in ids if str(pid) in cache]
    return pd.DataFrame(rows)


def status_badge_html(status: str) -> str:
    color = STATUS_COLOR.get(status, "#64748b")
    return (f"<span style='background:{color}22;color:{color};border:1px solid {color};"
            f"padding:2px 10px;border-radius:12px;font-size:0.85em;font-weight:600'>{status}</span>")
