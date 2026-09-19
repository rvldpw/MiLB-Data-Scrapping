# Farmboard

Streamlit dashboard for MiLB player game logs. It reads the data the scanner produces and adds a season and date filter, a "where is the player today" filter, player and team pages, and a roster what-if page.

## Run locally

Python 3.11 or 3.12. From the repository root:

```sh
python -m pip install -r dashboard/requirements.txt
python -m streamlit run dashboard/Home.py
```

The app starts on the Hugging Face dataset (`rvlpw/milb-game-logs` by default). Under **Data source** in the sidebar you can switch to the five included sample games or to a local folder. A local folder needs `data/season-YYYY/league-ID/team-ID/{batting,pitching}.parquet`. The Hugging Face dataset also needs the scanner's `catalog.json`.

On Streamlit Community Cloud, use `dashboard/Home.py` as the entrypoint and `dashboard/requirements.txt` for packages. A private dataset needs a read token in secrets:

```toml
HF_TOKEN = "your-read-token"
```

`HF_TOKEN`, `HF_REPO_ID` and `DASHBOARD_SOURCE=hub` also work as environment variables. Keep tokens out of Git.

## Filters

The sidebar filters apply to every page.

- **From / To season.** Pick different seasons to cover several years, for example 2021 to 2023. Rates and peer averages then pool all of them.
- **Level and league.**
- **Players.** Everyone who played, only those still at this level today, only those who moved up, or any levels you pick.
- **Exact dates.** Narrows the chosen seasons to a start and end date.

## Where a player is today

Level now comes from the MLB Stats API, not from the game logs. The player's current team is matched to a level: MLB, Triple-A, Double-A, High-A, Single-A, Rookie / complex. "Other league" is independent, foreign or winter ball. "No team" means the API lists no club. It is not treated as a release or retirement. Injured list and similar roster status is shown when the team's roster lists it.

Lookups are cached in `dashboard/cache/` (people for 3 days, teams and rosters for 1 day). The folder is ignored by Git.

## Pages

- **Overview.** Player leaderboard (ranked, with each player's level today), league averages, a scatter of all players, and a team table with records and run differences. Under the leaderboard, *Open one of these players* jumps straight to that player's page.
- **Player lab.** One player: trend, peer percentiles, game log, splits, comparison, news, full metric sheet and a downloadable report.
- **Team room.** Record, offense by position, roster, starters vs. relievers, results. The roster has the same *Open one of these players* jump.
- **Roster scenarios.** Move players between two teams and compare the totals. It replays recorded stats and predicts nothing.
- **Analyst guide.** A beginner's path into the job: how to read a minor-league player, the level ladder and typical ages, which metrics to learn first, how much data a rate needs before it means anything, mistakes to avoid, the full metric dictionary, data coverage and the rules behind every figure.

## Performance

Rates for every player, split and rolling window are computed for all groups at once rather than one player at a time, so a full league table builds in well under a second. Player level lookups are cached in memory for the session as well as on disk, and MLB Stats API calls retry on rate limits.

## What readers never see

Plumbing columns (the raw source JSON, the fetch URL and timestamp, internal intermediate values) are stripped from every on-screen table. Metrics are shown by their conventional code, never an internal key.

## Data handling

- All 38 batting and 54 pitching fields from the scanner are kept. Values missing from a column are filled from `raw_stats_json` when present. Anything still missing shows as N/A, never zero.
- Rates come from summed counts, not averages of game rates. Innings are counted in outs (5.2 innings is 17 outs).
- Games are counted once per game and team. Players are matched by ID, not name.
- Percentiles need at least five players and use the middle rank for ties.
- wOBA uses fixed weights. Estimated wRC, the OPS index and FIP are estimates without park adjustment, and are labeled that way.
- The position map shows hitting by listed position, not defense.

## Tests

```sh
python -m pip install pytest
python -m pytest dashboard/tests -q
```
