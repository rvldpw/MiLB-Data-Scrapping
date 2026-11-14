"""Public MLB schedule and box-score access; failures must never mean no data."""
import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)
HOST = "https://statsapi.mlb.com"


class FetchError(RuntimeError):
    pass


class MLBClient:
    def __init__(self, settings):
        self.settings = settings
        self.session = requests.Session()
        retries = Retry(total=settings.retries, backoff_factor=1,
                        status_forcelist=[429, 500, 502, 503, 504],
                        allowed_methods=["GET"], respect_retry_after_header=True)
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.headers.update({"Accept": "application/json", "User-Agent": "MiLB-Game-Logs/2.0"})

    def get(self, path, params=None):
        try:
            response = self.session.get(HOST + path, params=params,
                                        timeout=self.settings.request_timeout)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or "messageNumber" in data:
                raise ValueError("Unexpected MLB response")
            return data
        except (requests.RequestException, ValueError) as exc:
            raise FetchError(f"MLB request failed: {path}: {exc}") from exc
        finally:
            time.sleep(self.settings.request_delay)

    def schedule(self, season):
        games, types = {}, self.settings.game_types
        wanted = ",".join(types)
        for sport_id in self.settings.sport_ids:
            data = self.get("/api/v1/schedule", {
                "sportId": sport_id, "season": season, "gameTypes": wanted, "hydrate": "team",
            })
            if not isinstance(data.get("dates"), list) or "totalGames" not in data:
                raise FetchError(f"Incomplete schedule response for {season}, sport {sport_id}")
            returned = 0
            for day in data["dates"]:
                if not isinstance(day.get("games"), list):
                    raise FetchError("Schedule date is missing its game list")
                for game in day["games"]:
                    returned += 1
                    if game.get("gameType") not in types or int(game.get("season", 0)) != season:
                        continue
                    if not game.get("gamePk") or not game.get("officialDate") or not game.get("status"):
                        raise FetchError("Schedule game is missing its ID, date, or status")
                    key = str(game["gamePk"])
                    previous = games.get(key)
                    # A postponed or suspended game is listed again on the day it will be played: keep the
                    # last day it appears under (a game waiting to be resumed carries no other sign of it).
                    listed = max(day.get("date") or "", game.get("resumeGameDate") or "", game["officialDate"],
                                 previous["listed_until"] if previous else "")
                    if previous is None or game["status"].get("abstractGameState") == "Final":
                        games[key] = dict(game, sport_id=sport_id)
                    games[key]["listed_until"] = listed
            if returned != data["totalGames"]:
                raise FetchError(f"Truncated schedule: expected {data['totalGames']}, received {returned}")
            log.info("Schedule %s sport %s: %s entries", season, sport_id, returned)
        return sorted(games.values(), key=lambda g: (g["officialDate"], g["gamePk"]))

    def boxscore(self, game_pk):
        return self.get(f"/api/v1/game/{int(game_pk)}/boxscore")
