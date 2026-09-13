# MiLB Analyst Hub

A two-page Streamlit app built on top of [`rvlpw/milb-game-logs`](https://huggingface.co/datasets/rvlpw/milb-game-logs):
a **Player Analyst Dashboard** and a **Team Analyst Dashboard**, both with the
sabermetric formulas MLB analysts actually use (wOBA, wRC+, OPS+, ISO, BABIP,
FIP, K-BB%, etc.), applied game-by-game so growth/trend charts are possible.

## Run it

```bash
pip install -r requirements.txt
streamlit run Home.py
```

The dataset is public, so no Hugging Face token is needed. The first load
pulls the full dataset (~11 MB, ~277k rows) and is cached for 6 hours
(`st.cache_data`), so subsequent interactions are instant.

## Pages

- **Home.py** — dataset overview + a quick top-performers snapshot.
- **pages/1_Player_Dashboard.py** — sidebar filters (season, level, team,
  position/role, then age + live MLB/MiLB status once the pool is small
  enough to check), then for the selected player: a scouting radar chart
  (percentile vs. the filtered pool), a full stat sheet, and four growth
  tabs — rolling form, month-by-month, season-over-season, home/away — plus
  a per-game distribution histogram so you're not just looking at averages.
- **pages/2_Team_Dashboard.py** — sidebar season/level/team pickers, team
  offense/pitching lines with full stat-sheet expanders, a **positional need
  finder** (team wRC+ by position vs. league average, plus a PA-share pie),
  and a rotation-vs-bullpen comparison with an IP-vs-FIP bubble chart for
  every arm on the staff. Every roster drill-down table shows each player's
  live age and MLB/MiLB status, and can be filtered by both in the sidebar.

## Files

| File | Purpose |
| --- | --- |
| `data_loader.py` | Pulls the two HF configs (`batting`, `pitching`), light dtype cleanup, position-group + SP/RP tagging |
| `metrics.py` | All sabermetric formulas + league-average benchmarks, percentile ranks, home/away splits, and the full stat-sheet table |
| `bio.py` | Live player status (active in MLB / back in MiLB / injured / released / retired) from the MLB Stats API, disk-cached |
| `assets.py` | Player headshot / team logo `<img>` helpers (MLB Stats API IDs → `midfield.mlbstatic.com`, with an inline SVG fallback) |
| `ui.py` | Mobile CSS (scrollable custom tables, tighter phone padding) |
| `Home.py`, `pages/*.py` | The Streamlit pages |

## Mobile use

All filters live in the sidebar, which Streamlit already renders with a
built-in collapse/expand chevron at its top edge — tap it to get the sidebar
out of the way on a phone, tap again to bring back the filters. The custom
roster tables (the ones with inline player photos) scroll sideways instead
of squashing on a narrow screen, and the headline metric rows are capped at
4 across so they stack cleanly.

## Live player status

Because `player_id` is a real MLB Stats API person ID, the app can ask
`statsapi.mlb.com` directly whether that player is currently on an MLB
roster, back in the minors, hurt, released, or retired — something the
game-log dataset itself has no way to encode (it only has box-score rows).
Results are cached to `cache/bios.json` for 3 days, and a small player pool
(a team roster, or a filtered search result under ~300 players) is fetched
concurrently so it doesn't feel slow. If a very broad, unfiltered player
search is left open, status/age filtering is skipped rather than firing
hundreds of requests at once — narrow the season/level/team/position first.

## Methodology notes (read this before trusting a number)

- **player_id / team_id are real MLB Stats API IDs**, so headshots and team
  logos load straight off MLB's own CDN — no separate image dataset needed.
  If a given ID has no photo on file (common for org-only staff or very old
  rows), the `<img onerror>` fallback swaps in a generic silhouette/shield so
  nothing ever renders broken.
- **wOBA** uses fixed linear weights (FanGraphs-style; these barely move
  year to year in the majors and there's no published MiLB-specific set).
  **wRC+, OPS+, and the FIP constant** are instead centered on this
  dataset's own season+level averages, not imported MLB numbers — so "100"
  always means "average at that level, that year," which is the more
  honest comparison for MiLB.
- **No park factors** — none are available in the source data, so wRC+/OPS+
  here are park-neutral approximations, same as most public MiLB tools.
- **No birthdate field** — age-relative-to-level (a staple of real prospect
  writeups) isn't possible from this dataset alone. Growth is read off
  rolling in-season form, month splits, and season-over-season trend instead.
- **Starter/reliever role** is inferred per appearance from `pitching_GS`
  (started that game = SP for that game), not a fixed season-long label,
  since some arms swing between roles.
- Rows with missing source stats stay `null` upstream and are excluded from
  the relevant sums, per the dataset's own documentation — nothing here
  coerces a missing stat to zero.
