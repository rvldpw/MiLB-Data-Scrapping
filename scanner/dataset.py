"""Replace each refreshed game's rows in the affected team tables."""
from collections import defaultdict
from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq

from .schema import schema_for


def merge_games(store, batch, game_index):
    replacements, incoming = defaultdict(set), defaultdict(list)
    known_paths = {path for entry in game_index.values() for path in entry.get("paths", [])}
    for result in batch:
        previous = game_index.get(str(result.game_pk), {})
        for path in set(previous.get("paths", [])) | result.tables.keys():
            replacements[path].add(result.game_pk)
        for path, rows in result.tables.items():
            incoming[path].extend(rows)
    files = {}
    for path, game_ids in replacements.items():
        raw = store.read(path)
        if raw is None and path in known_paths:
            raise ValueError(f"Table {path} is missing but progress says it exists; restore it before continuing")
        rows = pq.ParquetFile(BytesIO(raw)).read().to_pylist() if raw is not None else []
        rows = [row for row in rows if row["game_pk"] not in game_ids] + incoming[path]
        unique = {}
        for row in rows:
            key = (row["game_pk"], row["team_id"], row["player_id"])
            if key in unique:
                raise ValueError(f"Duplicate player/game row in {path}: {key}")
            unique[key] = row
        rows.sort(key=lambda row: (row["game_date"], row["game_pk"], row["player_id"]))
        kind = path.rsplit("/", 1)[-1].removesuffix(".parquet")
        buffer = BytesIO()
        pq.write_table(pa.Table.from_pylist(rows, schema=schema_for(kind)), buffer, compression="zstd")
        files[path] = buffer.getvalue()
    return files


def dataset_card(catalog):
    leagues = sorted({int(row["league_id"]) for row in catalog.values()})
    lines = ["---", "language:", "- en", "tags:", "- baseball", "- milb"]
    if leagues:
        lines.append("configs:")
        for kind in ("batting", "pitching"):
            lines += [f"- config_name: {kind}"]
            if kind == "batting":
                lines.append("  default: true")
            lines += ["  data_files:", "  - split: train", f'    path: "data/season-*/league-*/team-*/{kind}.parquet"']
            for league in leagues:
                lines += [f"- config_name: league-{league}-{kind}", "  data_files:", "  - split: train",
                          f'    path: "data/season-*/league-{league}/team-*/{kind}.parquet"']
    lines += ["---", "", "# MiLB player game logs", "",
              "One row per player, game, team, and statistic group. Regular-season games at AA, High-A, and Single-A, subject to configured coverage.",
              "", "Source: [MLB Stats API](https://statsapi.mlb.com). Data is extracted from box-score `stats`, never `seasonStats`.",
              "Missing statistics are null. `pitching_IP_str` uses baseball notation; use `pitching_outs` for arithmetic.",
              "", "Files are grouped by season, historical league ID, and team ID. `catalog.json` maps IDs to names and table paths.",
              "The `train` split is a loading convention; no training/test split has been applied.",
              "", "`state/index.json` records season completion; partially backfilled seasons can be visible.",
              "`state/SEASON.json` records the games successfully stored. Current-season games are refreshed incrementally.",
              "Player coverage includes everyone with a game stat line, including MLB veterans and players no longer active.",
              "", "Historical seasons are frozen after completion. Late corrections outside the configured recent-game window may require an explicit re-fetch.",
              "", "## League names by season", "", "| Season | League ID | League | Level |", "| --- | --- | --- | --- |"]
    names = {(r["season"], r["league_id"], r["league_name"], r["team_level"]) for r in catalog.values()}
    lines += [f"| {season} | {lid} | {name} | {level} |" for season, lid, name, level in sorted(names)]
    return ("\n".join(lines) + "\n").encode()
