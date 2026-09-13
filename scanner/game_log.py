"""Extract actual game statistics; never read the box score's seasonStats."""
from dataclasses import dataclass

from .config import LEVELS
from .schema import stats_columns


@dataclass
class GameRows:
    game_pk: int
    tables: dict[str, list[dict]]
    catalog: dict[str, dict]


def partition_path(season, league_id, team_id, kind):
    return f"data/season-{int(season)}/league-{int(league_id)}/team-{int(team_id)}/{kind}.parquet"


def parse_boxscore(game, box, fetched_at):
    tables, catalog = {}, {}
    pk, season = int(game["gamePk"]), int(game["season"])
    for side, other in (("home", "away"), ("away", "home")):
        team_box = box.get("teams", {}).get(side, {})
        scheduled = game["teams"][side]
        opponent = game["teams"][other]
        team = scheduled["team"]
        league = team.get("league") or team_box.get("team", {}).get("league", {})
        sport_id = int(team.get("sport", {}).get("id", game["sport_id"]))
        if sport_id not in LEVELS or not league.get("id") or not league.get("name"):
            raise ValueError(f"Game {pk}: missing or unsupported league/level metadata")
        if team_box.get("team", {}).get("id") != team["id"]:
            raise ValueError(f"Game {pk}: schedule/box-score team mismatch")
        if not isinstance(team_box.get("players"), dict) or not team_box["players"]:
            raise ValueError(f"Game {pk}: missing player statistics")
        for score in (scheduled.get("score"), opponent.get("score")):
            if not isinstance(score, int):
                raise ValueError(f"Game {pk}: final score unavailable")
        base = {
            "season": season, "league_id": int(league["id"]), "league_name": league["name"],
            "sport_id": sport_id, "team_level": LEVELS[sport_id],
            "team_id": int(team["id"]), "team_name": team["name"],
            "opponent_id": int(opponent["team"]["id"]), "opponent_name": opponent["team"]["name"],
            "game_pk": pk, "game_date": game["officialDate"], "game_datetime": game.get("gameDate"),
            "resume_date": game.get("resumeGameDate"), "game_number": game.get("gameNumber", 1),
            "game_type": game["gameType"], "is_home": side == "home",
            "team_score": scheduled["score"], "opponent_score": opponent["score"],
            "result": "W" if scheduled["score"] > opponent["score"] else
                      "L" if scheduled["score"] < opponent["score"] else "T",
            "source_url": f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore", "fetched_at": fetched_at,
        }
        catalog_key = f"{season}/{league['id']}/{team['id']}"
        catalog[catalog_key] = {k: base[k] for k in
                                ("season", "league_id", "league_name", "sport_id", "team_level", "team_id", "team_name")}
        for kind, participant_key in (("batting", "batters"), ("pitching", "pitchers")):
            rows = []
            for player in team_box["players"].values():
                stats = player.get("stats", {}).get(kind)
                if not stats:
                    continue
                person = player.get("person", {})
                if not person.get("id") or not person.get("fullName"):
                    raise ValueError(f"Game {pk}: player identity missing")
                row = dict(base, player_id=int(person["id"]), player_full_name=person["fullName"],
                           player_position=player.get("position", {}).get("abbreviation"))
                row.update(stats_columns(kind, stats))
                rows.append(row)
            if not rows:
                raise ValueError(f"Game {pk}: no {kind} rows for {side} team")
            expected = set(team_box.get(participant_key, []))
            if kind == "batting":
                # MLB's batters list also includes pitchers who never batted.
                expected -= set(team_box.get("pitchers", []))
            actual = {r["player_id"] for r in rows}
            if len(actual) != len(rows) or expected - actual:
                raise ValueError(f"Game {pk}: incomplete/duplicate {kind} player rows")
            if kind == "batting":
                totals = team_box.get("teamStats", {}).get("batting", {})
                for source_key, column in (("hits", "batting_H"), ("runs", "batting_R"), ("atBats", "batting_AB")):
                    if totals.get(source_key) is not None and all(r[column] is not None for r in rows):
                        if sum(r[column] for r in rows) != totals[source_key]:
                            raise ValueError(f"Game {pk}: player {source_key} do not match team total")
            path = partition_path(season, league["id"], team["id"], kind)
            tables[path] = rows
            catalog[catalog_key][kind] = path
    return GameRows(pk, tables, catalog)
