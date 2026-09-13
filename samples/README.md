# Real sample game logs

These are **five games only**, downloaded from the public MLB Stats API on 2026-09-13. They demonstrate the output format and do not represent a complete season.

| Level | Game IDs | Batting + pitching rows |
| --- | --- | --- |
| AA | 645343 | 25 |
| High-A | 642623, 642668, 642738 | 79 |
| Single-A | 647848 | 27 |

There are 131 player-stat rows in 20 team/group Parquet files. Each row includes its original box-score `source_url` and extraction timestamp. The samples have no sync-state files and are not imported into the production backfill.

The directory layout matches the generated dataset: `data/season-2021/league-ID/team-ID/batting.parquet` and `pitching.parquet`. Read a downloaded file with `pyarrow.parquet.read_table(path)` or another standard Parquet reader.
