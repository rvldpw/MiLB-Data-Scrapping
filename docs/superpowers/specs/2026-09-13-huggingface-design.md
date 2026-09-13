# Hugging Face game-log migration

The user approved replacing Sheets with a season/league/team dataset and requested one season per day from 2021 through the current year, followed by current-season updates and automatic rollover.

## Design decision

Use public schedules and one box-score request per final game. Compared with per-player season endpoints, this captures everyone who played and supports incremental game updates without a roster-history dependency. Keep the original AA/A+/A and regular-season coverage. Remove prospect-only filtering because it would make historical game tables incomplete.

Store two typed Parquet tables per season/league/team. Include player identity, opponent, final scores, mapped game statistics, and raw game-stat JSON. Use historical IDs for paths and a catalog for names. Batting and pitching get separate Hugging Face configurations and per-league subsets.

## Progress and failures

Store small global season state and one game manifest per season in the same Hub repository. Checkpoint up to 100 games atomically with affected tables, catalog, and README. Pin reads to a commit and require that commit as parent on writes. A failed upload cannot advance remote progress.

Select the earliest unfinished season. Complete at most one backfill/finalization per UTC day. A soft runtime budget allows partial seasons to resume; it does not force one season to finish in one day. After initial catch-up, recheck the selected season's schedules and download only missing/changed games and a seven-day recent window. Reconcile the old current year once at rollover, then select the new year. Empty current seasons are valid; empty historical coverage is an error.

## Validation

Test cold start, same-day gate, six-day progression, limited runs, failed fetches/uploads, late suspended games, score corrections, duplicate runs, stable null types, real box-score parsing, and 2027 rollover. Validate public API output locally with a bounded sample. Do not publish or claim an authenticated upload without a configured destination and credentials.
