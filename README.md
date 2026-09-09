# MiLB Prospect Scanner — automated, incremental, Google Sheets-backed

Scans **A / A+ / AA** MiLB levels only, pulls full 2021–current-season stats for
every player still active, splits into **Batter / Pitcher / Catcher**, and keeps a
running Google Sheet up to date automatically via GitHub Actions.

## How the pieces fit together

```
GitHub Actions (cron, daily)
        │
        ▼
   run.py  →  scanner/  (pulls MLB Stats API, computes metrics, splits sheets)
        │
        ├── writes this run's DELTA to output/milb_prospect_scan_delta.xlsx
        │   (uploaded as a workflow artifact — handy for a quick look/download)
        │
        └── pushes rows to Google Sheets via a small Apps Script Web App
            (this is your permanent, cumulative "databank")
```

**The incremental part** (the part you asked about): the Google Sheet remembers
which past seasons it already has fully synced (in a hidden `_SyncState` tab). Every
run:
1. Asks the Sheet which seasons are already marked complete.
2. Skips fetching those entirely — a season before the current calendar year is
   over and won't change again, so once it's synced, it's done for good.
3. Always re-fetches the **current** season only (it's still in progress).
4. Pushes what it fetched (upsert — safe to re-run) and marks any newly-finished
   prior season complete.

Net effect: the **first run ever** does the full 2021–2026 backfill (slow, many API
calls). **Every run after that** only touches the current season — a small fraction
of the work — and the Sheet keeps accumulating the full career history over time.

## One-time setup

### 1. Create the Google Sheet databank
1. Create a new Google Sheet (this becomes your databank — Batter/Pitcher/Catcher
   tabs get created automatically on first sync).
2. In the Sheet: **Extensions → Apps Script**.
3. Delete the default `Code.gs` content and paste in [`apps_script/Code.gs`](apps_script/Code.gs).
4. **Project Settings → Script Properties → Add script property**:
   - Name: `SHARED_SECRET`
   - Value: any long random string (e.g. generate one with `openssl rand -hex 32`)
5. **Deploy → New deployment → type "Web app"**:
   - Execute as: **Me**
   - Who has access: **Anyone**
6. Copy the deployment URL (ends in `/exec`).

### 2. Add GitHub repo secrets
In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**:
- `APPS_SCRIPT_URL` = the `/exec` URL from step 1.6
- `APPS_SCRIPT_SECRET` = the same value you put in `SHARED_SECRET`

### 3. Push this code to the repo
The workflow at [`.github/workflows/milb_scan.yml`](.github/workflows/milb_scan.yml)
is already wired up with:
- `schedule:` — runs daily at 09:00 UTC automatically
- `workflow_dispatch:` — a manual **"Run workflow"** button in the Actions tab, for
  on-demand runs

That's it — no further setup. The first run will take a while (full 2021–2026
backfill across A/A+/AA); check the Actions log to watch progress.

## Running locally (optional)
```bash
pip install -r requirements.txt
export APPS_SCRIPT_URL="https://script.google.com/macros/s/.../exec"
export APPS_SCRIPT_SECRET="your-secret"
python run.py
```
Leave the two env vars unset to skip Sheets sync entirely and just get a local
`output/milb_prospect_scan_delta.xlsx`.

## Forcing a re-pull of a season
Open the Sheet's `_SyncState` tab and either delete that season's row, or set its
`complete` cell to `FALSE`. The next run will re-fetch it in full.

## Project layout
```
run.py                          CLI entry point
scanner/
  config.py                     seasons, levels, active-season definition
  fetch.py                      MLB Stats API session, field maps, row builder
  metrics.py                    derived rate stats (AVG/OBP/ERA/WHIP/etc.)
  sheets_sync.py                talks to the Apps Script web app
  build.py                      orchestrates: decide what's new → pull → split → sync
apps_script/Code.gs             paste into the Google Sheet's Apps Script editor
.github/workflows/milb_scan.yml scheduled + manual trigger
```

## Notes & limitations
- **Source**: public MLB Stats API (`statsapi.mlb.com` + `bdfed.stitch.mlbinfra.com`).
- **Identity is always ID-based, never name-based.** Every row's `player_id` is MLB's
  own permanent Person ID, attached to the stat line by the API itself — name is
  carried alongside it as metadata, never used as a join key anywhere in this
  pipeline (not for the Batter/Pitcher/Catcher split, not for the Sheets upsert key,
  not for the age/bio lookup). Two players sharing a name can never get merged or
  cross-matched.
- **Age** comes from a per-player, ID-keyed lookup (`/api/v1/people/{player_id}`),
  run once per unique active player per run, computed as of July 1st of each row's
  own season. Toggle off with `ENRICH_WITH_BIO=false` if you want a faster run
  without it.
- **"Active"** = has a stat line in the current season at A/A+/AA. Simple, honest
  proxy — not a live roster-status flag.
- **Levels are locked** to A / A+ / AA on purpose.
- **The season window has no hardcoded end year** — it tracks the real calendar
  year, so the scanner keeps rolling forward (2027, 2028, ...) on its own without
  any code changes.
- If a Sheets push fails partway through a run, that run does **not** mark any season
  complete, so the next scheduled run safely retries the full fetch for that run's
  seasons rather than silently losing data.
