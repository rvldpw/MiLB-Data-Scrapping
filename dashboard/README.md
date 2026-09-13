# MiLB Analyst Hub

A three-page Streamlit app on top of [`rvlpw/milb-game-logs`](https://huggingface.co/datasets/rvlpw/milb-game-logs):
a **Player Analyst Dashboard**, a **Team Analyst Dashboard**, and a **Trade Simulator**,
with the sabermetric formulas MLB analysts actually use (wOBA, wRC+, OPS+, ISO, BABIP,
FIP, K-BB%, etc.) computed game-by-game so growth/trend analysis is possible.

## Run it

```bash
pip install -r requirements.txt
streamlit run Home.py
```

The dataset is public, so no Hugging Face token is needed. `.streamlit/config.toml`
carries the dark theme — Streamlit picks it up automatically, nothing else to configure.

## Pages

- **Home.py** — dataset overview + a quick top-performers snapshot.
- **pages/1_Player_Dashboard.py** — sidebar filters (season, level, team,
  position/role, then age + live MLB/MiLB status once the pool is small
  enough to check), a scouting radar chart, a full stat sheet (exportable to
  CSV), four growth tabs (rolling form / month-by-month / season-over-season
  / home-away), a per-game distribution histogram, and a **head-to-head
  player comparison** toggle that overlays a second player on the radar and
  stat sheet.
- **pages/2_Team_Dashboard.py** — team offense/pitching lines with a
  **Squad Rating** (0-100, blend of wRC+ and FIP), a **positional need
  finder** (team wRC+ by position vs. league average + a PA-share pie), and
  a rotation-vs-bullpen comparison with an IP-vs-FIP bubble chart. Every
  roster table shows live age/status and exports to CSV.
- **pages/3_Trade_Simulator.py** — pick two teams, pick who each side sends
  away, and see the roster impact instantly: Squad Rating before/after,
  offense/pitching lines before/after, and a positional wRC+ before/after
  chart for both clubs. See "How the trade simulator works" below.

## Files

| File | Purpose |
| --- | --- |
| `data_loader.py` | Pulls the two HF configs (`batting`, `pitching`), dtype cleanup, position-group + SP/RP tagging |
| `metrics.py` | All sabermetric formulas, league benchmarks, percentile ranks, splits, the stat-sheet builder, `simulate_trade()`, and `power_rating()` |
| `bio.py` | Live player status (active in MLB / back in MiLB / injured / released / retired) from the MLB Stats API, disk-cached |
| `assets.py` | Player headshot / team logo `<img>` helpers (MLB Stats API IDs → `midfield.mlbstatic.com`, with an SVG fallback) |
| `ui.py` | The design system — theme CSS, hero banners, stat cards, section headers, scrollable tables, CSV download button |
| `.streamlit/config.toml` | Dark navy + orange theme |
| `Home.py`, `pages/*.py` | The three pages |

## How the trade simulator works

There's no way to project future performance from a box-score dataset, so
the simulator does the honest thing instead: for the players changing
teams, it **relabels which roster their actual games this season count
toward**, then recomputes every downstream metric (wRC+, FIP, Squad Rating,
positional need) from that relabeled data. It answers *"what would each
team's stat line look like if this production had belonged to the other
roster all along"* — a real, defensible before/after comparison — not a
prediction of what either player will do next. It also doesn't model
roster rules, service time, or salary/prospect capital a real front office
would have to weigh.

## Mobile use

All filters live in the sidebar, which Streamlit renders with a built-in
collapse/expand chevron at its top edge — tap it to get the sidebar out of
the way on a phone. The custom roster tables (the ones with inline player
photos) scroll sideways instead of squashing, and stat cards drop to a
2-column grid under ~900px.

## Live player status

Because `player_id` is a real MLB Stats API person ID, the app can ask
`statsapi.mlb.com` directly whether a player is currently on an MLB roster,
back in the minors, hurt, released, or retired — something the game-log
dataset itself has no way to encode. Results are cached to `cache/bios.json`
for 3 days, and a small player pool (a team roster, or a filtered search
result under ~300 players) is fetched concurrently. A very broad, unfiltered
player search skips status/age filtering rather than firing hundreds of
requests at once — narrow the season/level/team/position first.

## Methodology notes

- **wOBA** uses fixed linear weights (FanGraphs-style). **wRC+, OPS+, the
  FIP constant, and Squad Rating** are centered on this dataset's own
  season+level averages, not imported MLB numbers — "100" always means
  "average at that level, that year."
- **No park factors** — none are available in the source data.
- **No birthdate field in the dataset** — age comes from the live MLB Stats
  API bio lookup, not the game logs themselves.
- **Starter/reliever role** is inferred per appearance from `pitching_GS`.
- Missing source stats stay `null` upstream and are excluded from sums,
  per the dataset's own documentation.
