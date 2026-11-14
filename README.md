# MiLB player game logs

Collect individual game performances into a Hugging Face dataset, organized by season, league, and team. Google Sheets and Apps Script are no longer used.

## Daily behavior

On a fresh dataset, the scheduled run processes **one season per UTC day**:

| Successful daily run | Season |
| --- | --- |
| 1 | 2021 |
| 2 | 2022 |
| 3 | 2023 |
| 4 | 2024 |
| 5 | 2025 |
| 6 | 2026, through the completed games available that day |
| Following days | New, missing, changed, and recent 2026 games |

The example assumes startup during 2026. The ending year is read from the current UTC date, not hardcoded. A year is closed only after its last game: the off-season leagues that start in October 2026 play into February 2027, so 2026 keeps being refreshed until 30 days after its last game. The scanner then reconciles 2026 once and starts 2027 on the next daily run, in early March. It waits for actual completed games during the off-season. The same rollover applies every year.

A slow or failed season can take multiple days. Progress is saved every 100 games. The next run resumes that season; it never skips to the next year because of a timeout or failed API request. Running the workflow again on the same UTC day can resume an unfinished season, but cannot advance a second season after one finishes.

## Coverage

- Regular-season and postseason games at Triple-A (11), Double-A (12), High-A (13), Single-A (14), and the off-season leagues (17): the Arizona Fall League, the Dominican, Mexican Pacific, Puerto Rican, Venezuelan and Australian winter leagues, and the Caribbean Series.
- Off-season rows have `team_level` `WIN`. Their `season` is the year the league starts in: the 2025 season runs from October 2025 into February 2026.
- All-Star and exhibition games of those levels. The source lists them only in the off-season leagues, about 26 games in 2021–2026, such as the Fall Stars Game. An All-Star side is stored as a team of its own with only those rows.
- `game_type` tells them apart: `R` is the regular season, `A` an All-Star game, `E` an exhibition, and every other value a postseason round. In the minors the source uses `L` and `W` for league playoffs and `C` for the Triple-A title game. Keep `game_type == "R"` when you need regular-season totals.
- All players with batting or pitching game statistics, including MLB veterans and players who are no longer active. The old current-prospect filter has been removed.
- One row per `(game_pk, team_id, player_id)` in each batting/pitching table. Doubleheaders remain separate games.
- Player name, position, team, opponent, historical league, game date, final team scores, and win/loss/tie.
- Batting: AB, PA, H, HR, RBI, runs, walks, strikeouts, steals, and more.
- Pitching: innings, outs, hits/runs/earned runs allowed, walks, strikeouts, pitches, and decisions when supplied.
- Additional source fields remain available in `raw_stats_json`. Unavailable statistics remain null.

This release replaces the old season-summary workbook and bio/age enrichment with game-log tables. Catchers appear in batting tables with their game position; there is no separate catcher table. It does not collect Rookie leagues or pitch-by-pitch events. The source lists no spring-training games for these levels.

## Upgrading an existing dataset

A dataset built by release 2.0 (Double-A, High-A, Single-A, regular season only) is extended in place. Replace the code and the workflow; nothing is deleted or downloaded again.

- The first run with the wider scope reopens every stored season. `state/index.json` shows them as not final until they are done.
- Each daily run then completes one season, starting with 2021, and fetches only the games that are new: Triple-A, the postseason and the off-season leagues. A dataset covering 2021–2026 is complete again after six daily runs.
- The current season is refreshed again once the earlier seasons are done. Upgrade in the off-season if you can.
- A narrower scope than the stored one is rejected. Use a separate dataset for that.

## Dataset layout

```text
README.md                  # Generated viewer configurations and source information
catalog.json               # Season/league/team names and file paths
state/
  index.json               # Backfill queue, scope, season completion
  2021.json                # Successfully committed games for 2021
data/
  season-2021/
    league-113/
      team-402/
        batting.parquet
        pitching.parquet
```

Numeric IDs keep paths stable. League names and affiliations come from the game's season, including the league naming changes in 2021. The team catalog provides readable names. Each team has two tables for each season/league it appears in.

The folders use `season-2021`, `league-113`, and `team-402` naming so standard Parquet readers do not infer conflicting partition-column types. Every row already contains its season, league ID, and team ID.

Hugging Face stores Parquet files and provides dataset viewing; this is not a live SQL database. Batting and pitching have separate dataset configurations because their schemas differ. Each league also has its own configurations, such as `league-113-batting`.

## Setup

See [deployment instructions](docs/DEPLOY.md). In brief:

1. Put this project at the root of your GitHub repository, including `.github/workflows`.
2. Add repository variable `HF_REPO_ID` with `your-username/milb-game-logs`.
3. Add repository secret `HF_TOKEN` with a Hugging Face token allowed to write to that dataset.
4. Open **Actions → MiLB daily game logs → Run workflow**.

The workflow is configured for daily runs at **09:00 UTC / 16:00 WIB**. Hugging Face holds the persistent data and checkpoints; a fresh GitHub runner does not restart the backfill. A newly created dataset is private by default.

## Local preview

Python 3.12 is used in CI.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py --local-dir local-data --max-games 3
```

This makes real public MLB requests, writes local Parquet files, and makes no Hugging Face writes. Repeat to resume. Use a different directory with `--start-season 2024` to preview a different season. Local progress is independent of the deployed dataset. `--max-games` limits attempted box scores, not the number of schedule requests or output rows.

Set `SPORT_IDS` or `GAME_TYPES` to preview a smaller scope, for example Triple-A only:

```bash
SPORT_IDS=11 python run.py --local-dir aaa-preview --max-games 3
```

## Download by league or team

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="your-username/milb-game-logs",
    repo_type="dataset",
    allow_patterns=["data/season-2026/league-113/**/*.parquet", "catalog.json"],
    local_dir="eastern-league-2026",
)
```

For one team, use `data/season-2026/league-113/team-402/*.parquet`. For all seasons of a league, use `data/season-*/league-113/**/*.parquet`. Authenticate locally with `hf auth login` to access a private dataset.

To load a league as a table with the optional `datasets` library:

```python
from datasets import load_dataset

batting = load_dataset(
    "your-username/milb-game-logs",
    name="league-113-batting",
    split="train",
    token=True,  # use your saved token for a private dataset
)
```

`train` is only a dataset loading convention here. No machine-learning split has been applied. Do not sum `pitching_IP_str` as decimal numbers: `5.2` means five innings and two outs. Sum `pitching_outs` instead.

## Missed runs

Nothing has to be re-run by hand after a gap.

- Every run compares the whole schedule of its year with what is stored and fetches every finished game that is missing, however old.
- A year that was left unfinished, for example because nobody ran the job through the off-season, is completed first. A year that was never run is scraped before the current one. One year per UTC day, oldest first.
- GitHub pauses scheduled workflows in a public repository after [60 days without repository activity](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows). Open **Actions → MiLB daily game logs → Enable workflow**; the next run catches up as described above.

## Reliability and limitations

The schedule is rechecked for the selected season, while box scores are fetched only for missing games, changed schedule metadata/scores, and completed games in the last seven days. This catches delayed and resumed games even when their original dates are older. Historical seasons are frozen after successful completion. Corrections outside the refresh window that do not change schedule metadata require a deliberate re-fetch; see [the scanner guide](docs/SCANNER_GUIDE.md).

Data files and checkpoint state are published in the same Hugging Face commit. A concurrent update causes the commit to fail rather than overwrite another writer's progress. Only affected team tables are downloaded and rewritten. Interrupted uploads resume from the last committed batch. Missing final box scores fail visibly instead of silently marking a season complete. A cancelled or postponed game has no box score: it is listed under `excluded_games` in `state/index.json` and fetched as soon as its schedule entry changes, for example when it is made up.

The API is an external dependency; source coverage and future schema changes can affect a run. A final game with unavailable box-score data blocks that season until the source recovers or the issue is investigated. A full production backfill and authenticated Hub upload require your configured repository and token.

## Tests

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests -q
```

Tests cover scheduling, year rollover, resume after failures, duplicate/correction handling, Triple-A and postseason rows, the in-place scope upgrade, make-up games, stable Parquet schemas, and a captured real MiLB box score. The dashboard has its own packages and tests: see [dashboard/README.md](dashboard/README.md).

The [samples directory](samples/README.md) includes five real 2021 games from Double-A, High-A, and Single-A. See [validation results](docs/VALIDATION.md) for what has been tested and what still requires deployment credentials.
