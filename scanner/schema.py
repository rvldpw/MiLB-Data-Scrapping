"""Stable Parquet schemas. Missing source statistics stay null, not zero."""
import json

import pyarrow as pa

BATTING_FIELDS = {
    "gamesPlayed": "G", "plateAppearances": "batting_PA", "atBats": "batting_AB",
    "runs": "batting_R", "hits": "batting_H", "doubles": "batting_2B",
    "triples": "batting_3B", "homeRuns": "batting_HR", "rbi": "batting_RBI",
    "baseOnBalls": "batting_BB", "intentionalWalks": "batting_IBB",
    "strikeOuts": "batting_SO", "hitByPitch": "batting_HBP",
    "stolenBases": "batting_SB", "caughtStealing": "batting_CS",
    "totalBases": "batting_TB", "sacBunts": "batting_SH", "sacFlies": "batting_SF",
    "groundIntoDoublePlay": "batting_GiDP", "leftOnBase": "batting_LOB",
    "groundOuts": "batting_GO", "airOuts": "batting_AO",
    "numberOfPitches": "batting_pitches_faced",
}
PITCHING_FIELDS = {
    "gamesPitched": "pitching_G", "gamesStarted": "pitching_GS",
    "inningsPitched": "pitching_IP_str", "outs": "pitching_outs",
    "hits": "pitching_H", "runs": "pitching_R", "earnedRuns": "pitching_ER",
    "homeRuns": "pitching_HR", "baseOnBalls": "pitching_BB",
    "intentionalWalks": "pitching_IBB", "strikeOuts": "pitching_SO",
    "hitByPitch": "pitching_HBP", "battersFaced": "pitching_BF",
    "atBats": "pitching_AB", "numberOfPitches": "pitching_PI", "strikes": "pitching_PI_strikes",
    "wins": "pitching_W", "losses": "pitching_L", "saves": "pitching_SV",
    "holds": "pitching_HLD", "blownSaves": "pitching_BS",
    "wildPitches": "pitching_WP", "balks": "pitching_BK",
    "inheritedRunners": "pitching_IR", "inheritedRunnersScored": "pitching_IRS",
}
FIELD_MAPS = {"batting": BATTING_FIELDS, "pitching": PITCHING_FIELDS}
COMMON = [
    ("season", pa.int64()), ("league_id", pa.int64()), ("league_name", pa.string()),
    ("sport_id", pa.int64()), ("team_level", pa.string()),
    ("team_id", pa.int64()), ("team_name", pa.string()),
    ("opponent_id", pa.int64()), ("opponent_name", pa.string()),
    ("player_id", pa.int64()), ("player_full_name", pa.string()),
    ("player_position", pa.string()), ("game_pk", pa.int64()),
    ("game_date", pa.string()), ("game_datetime", pa.string()),
    ("resume_date", pa.string()), ("game_number", pa.int64()),
    ("game_type", pa.string()), ("is_home", pa.bool_()),
    ("team_score", pa.int64()), ("opponent_score", pa.int64()),
    ("result", pa.string()), ("source_url", pa.string()),
    ("fetched_at", pa.string()), ("raw_stats_json", pa.string()),
]


def schema_for(kind):
    return pa.schema(COMMON + [
        (name, pa.string() if name == "pitching_IP_str" else pa.int64())
        for name in FIELD_MAPS[kind].values()
    ])


def stats_columns(kind, stats):
    row = {column: stats.get(key) for key, column in FIELD_MAPS[kind].items()}
    if kind == "pitching" and row["pitching_outs"] is None and stats.get("inningsPitched") is not None:
        whole, _, partial = str(stats["inningsPitched"]).partition(".")
        if partial not in ("", "0", "1", "2"):
            raise ValueError(f"Invalid baseball innings: {stats['inningsPitched']}")
        row["pitching_outs"] = int(whole) * 3 + int(partial or 0)
    row["raw_stats_json"] = json.dumps(stats, sort_keys=True, separators=(",", ":"))
    return row
