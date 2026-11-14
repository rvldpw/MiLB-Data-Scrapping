# Changelog

## 2.1 — Triple-A, postseason and off-season leagues

- Added Triple-A (sport ID 11) and postseason games; `game_type` separates them from the regular season.
- Added the off-season leagues (sport ID 17, `team_level` `WIN`): Arizona Fall League, the Caribbean and Australian winter leagues, the Caribbean Series.
- A year now stays open until its last game instead of closing on 1 January, because those leagues play into February.
- Added All-Star and exhibition games (`game_type` `A` and `E`); with them every game the source lists for these levels is collected.
- An existing dataset is extended in place: a wider scope reopens stored seasons and fetches only the new games.
- Fixed: a postponed game stayed excluded forever, so its make-up was never collected. Exclusions now end when the schedule entry changes.
- Fixed: `python -m pytest` failed on a leftover test of the old Google Sheets pipeline. Removed it with the two unused modules it needed; added the missing `.gitignore`.
- Dashboard: Triple-A and off-season levels, and a Games filter (Regular, Postseason, Exhibition, All) that shows the kinds a league has.
- Dashboard fixed: sidebar titles and labels were near-white on a white sidebar; the sidebar now has the dark background its text was styled for.
- Dashboard analysis: league spread and monthly trends, club season paths, expected wins and luck, record by situation, playing-time charts, player form, streaks, game scores, out profile and most similar players.
- Dashboard layout: short one-line card titles, compact table headers with the full name on hover, tidy label-value rows on phones, readable page links in the sidebar.

## 2.0 — Hugging Face game logs

- Replaced Google Sheets/Apps Script and the season-summary XLSX pipeline with Parquet game logs on Hugging Face.
- Added league/team partitions, human-readable catalog, and separate batting/pitching viewer configurations.
- Switched to schedule discovery and actual box-score `stats`; preserved extra fields as JSON.
- Added final game scores and all historical participants, removing current-active and MLB-debut exclusions.
- Added daily sequential season backfill from 2021, game checkpoints, current-year refresh, and automatic year rollover.
- Added atomic data/state commits, concurrent-write protection, explicit failures, local preview, and regression tests.
