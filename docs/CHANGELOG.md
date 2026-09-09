# Game-by-game log update

This adds a second, independent sync pipeline for per-game stat lines (instead of
per-season totals), so you can look at streaks/form instead of just cumulative
numbers. It sits alongside the existing season-summary pipeline and doesn't
change how that one behaves.

## Folder map (what's new vs. what changed)

```
milb_automation/
├── apps_script/
│   └── Code.gs              CHANGED — new "kind" param on state/mark_complete,
│                             new "season_rows" read action, per-sheet upsert key
├── scanner/
│   ├── build.py              CHANGED — calls game_log.run() after season sync
│   ├── config.py             CHANGED — GAME_LOG_ENABLED, MAX_GAMELOG_SEASONS_PER_RUN
│   ├── fetch.py               CHANGED — fetch_player_game_log(), fetch_game_logs()
│   ├── sheets_sync.py         CHANGED — get_completed_seasons(kind=...),
│   │                           get_season_level_rows(), mark_season_complete(kind=...)
│   ├── game_log.py           NEW — orchestrates the game-log pipeline end to end
│   └── metrics.py            unchanged
├── run.py                    unchanged
├── requirements.txt          unchanged
├── docs/                     NEW — this file, plus DEPLOY.md and SCANNER_GUIDE.md
└── .github/workflows/
    └── milb_scan.yml         CHANGED (optional) — MAX_GAMELOG_SEASONS_PER_RUN env var
```

## Deploy steps

1. **Apps Script first.** Open the Google Sheet → Extensions → Apps Script.
   Replace `Code.gs` with the new version. Then **Deploy → Manage deployments →
   Edit (pencil icon) → New version → Deploy**. This keeps the same `/exec` URL,
   so you don't need to touch the `APPS_SCRIPT_URL` GitHub secret.
   (If you instead create a brand-new deployment, you'll get a new URL and *do*
   need to update the secret.)

2. **Push the Python changes** (`fetch.py`, `sheets_sync.py`, `config.py`,
   `build.py`, `game_log.py`) to your repo's `main` branch.

3. **Trigger a fresh run** — Actions tab → "MiLB Prospect Scan" → Run workflow
   (not "re-run failed jobs", so it checks out `main` clean).

## What happens on the sheet

Two new tabs get auto-created the same way `Batter`/`Pitcher`/`Catcher` already
do — no manual setup:

- **`BatterGameLog`** — one row per (player, game) for every batter/catcher
  active this season, keyed by `player_id` + `season` + `game_pk`.
- **`PitcherGameLog`** — same, for pitchers.

Plus two internal bookkeeping tabs (don't edit by hand, same as `_SyncState`):
`_SyncState_gamelog_batting` and `_SyncState_gamelog_pitching`.

## Pacing

Full 2021-2025 game-by-game history for ~4,000+ active players is thousands of
extra API calls — too much for one 90-minute run. So it backfills **one**
not-yet-synced historical season per day (oldest first), while the current
season's games are always refreshed in full every run. Expect the full backfill
to take about 5 daily runs to complete; after that, every run is fast (just the
current season's new/updated games).

To backfill faster, set a GitHub Actions secret/env var
`MAX_GAMELOG_SEASONS_PER_RUN` to something higher than the default `1` — just
weigh that against the 90-minute job timeout.

## Do you need to clear anything in the Sheet first?

No. Every push you've had so far failed before it ever reached the Sheet (the
NaN/Infinity JSON bug), so the Sheet is still completely empty — there's nothing
to delete. Going forward, this is all additive and idempotent:

- `Batter`/`Pitcher`/`Catcher` (season summaries) are untouched by this update.
- `BatterGameLog`/`PitcherGameLog` are brand-new tabs, so nothing to conflict with.
- Every row write is an upsert (existing key = overwrite, new key = append), so
  re-running the same day/season twice is always safe.

If you ever *do* want to force a re-pull of something later, you can manually
edit the relevant `_SyncState*` tab (set a season's `complete` flag to `FALSE`,
or delete that row) and the next run will re-fetch it.
