# Changelog

## 2.0 — Hugging Face game logs

- Replaced Google Sheets/Apps Script and the season-summary XLSX pipeline with Parquet game logs on Hugging Face.
- Added league/team partitions, human-readable catalog, and separate batting/pitching viewer configurations.
- Switched to schedule discovery and actual box-score `stats`; preserved extra fields as JSON.
- Added final game scores and all historical participants, removing current-active and MLB-debut exclusions.
- Added daily sequential season backfill from 2021, game checkpoints, current-year refresh, and automatic year rollover.
- Added atomic data/state commits, concurrent-write protection, explicit failures, local preview, and regression tests.
