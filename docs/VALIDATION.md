# Validation — 2026-11-15

## Automated checks

`python -m pytest tests -q`: **43 scanner tests passed**. `python -m pytest dashboard/tests -q`: **29 dashboard tests passed**.

Scanner coverage includes six daily backfill runs, the same-day gate, game-count and runtime limits, failed API requests, failed uploads, checkpoint resume, current-season refresh, old suspended games, the 2027 rollover, scoring corrections, doubleheaders, stable nullable Parquet types, missing state/data detection, and guarded atomic Hub commits.

New in 2.1:

- Triple-A, postseason, All-Star and off-season rows keep their level and `game_type`; schedule requests ask for and keep only the configured game types.
- A wider scope reopens finished seasons and fetches only the new games; a narrower one is refused.
- A postponed game is collected once it is made up; an exclusion recorded by release 2.0 is checked once more.
- Missed runs: a job that was off from August to the next May completes the old year (postseason included) and then the new one; a year that was never run is scraped before the current one.
- A season that plays into the next calendar year stays open on 1 January, keeps its refresh window, is frozen 30 days after its last game, and the next year starts the day after. A stray scheduled game cannot keep it open past March. A suspended game listed again on a later day keeps its season open (real client and run together).

Hub read tests distinguish a confirmed missing remote file from a network/cache failure, preventing a temporary outage from resetting the backfill state.

The real box-score fixture for game 750975 verifies that extracted player hits/runs match team game totals and that unused players' season totals do not become game rows. An additional regression verifies ordinary Parquet readers can open the downloaded team files without partition-type conflicts.

## Live public API checks

2026-11-14 and 2026-11-15, release 2.1:

- Game types in the 2024 and 2025 schedules: Triple-A returns `R`, `W` (5 games) and `C` (1 game); Double-A, High-A and Single-A return `R`, `L` and `W`. One request with `gameTypes=R,F,D,L,W,C,P` returns all of them.
- Upgrade rehearsal with real box scores: a finished local dataset holding only Double-A `W` games for 2024–2026 (24 games) was switched to four levels and `L,W,C`. Three daily runs reopened one season each and fetched 179 new games (64, 57 and 58). None of the 24 stored games was downloaded again. No failures and no exclusions. Each Triple-A title game put its two teams in their own league tables.
- 45 Triple-A regular-season box scores from 2024, and 12 from 2026 through `run.py --local-dir`, were stored without errors.
- Off-season leagues (sport ID 17): 138 box scores from 2021 and 2025 were parsed, four from every league and round — Arizona Fall League, Dominican, Mexican Pacific, Puerto Rican, Venezuelan and Australian leagues, Caribbean Series. 137 were stored; the other one is a cancelled game.
- Off-season calendars: every schedule entry of a season carries its start year, including the games played in January and February. Seasons 2021–2025 end between 3 and 10 February and have no unfinished entries left. On the real 2025 schedule the scanner keeps the season open through 8 March 2026 and closes it on 9 March, 30 days after its last game; the 2025 Double-A season is closed on 1 January. A real suspended game (851559, 21 October 2026, listed again under 16 November) is picked up by its later listing.
- Off-season rehearsal: 25 league-final games of the 2025 off-season were added to a finished Double-A dataset in one run, stored under season 2025 with 2026 game dates, and nothing already stored was downloaded again. A second run stored 42 regular-season games and excluded three: two cancelled and one postponed Fall League game of 11 October 2025.
- All-Star and exhibition games: the 2021–2026 schedules of all five levels list 26 of them, all in the off-season leagues, and no spring-training or intrasquad games. The 22 already played were parsed and stored (Fall Stars Games, league All-Star games, exhibition series); two more were cancelled and two are not played yet.
- Every dashboard page was rendered in batting and pitching mode on the deployed dataset and on a local off-season dataset without an error. The new views (league spread, monthly trends, club season paths, expected wins, record by situation, playing-time charts, form, streaks, game scores, out profile, similar players) were looked at in a real browser at desktop and phone width; a scan found no wrapped or cut-off card titles, figures or header values, and no sideways page scroll.
- In a real browser the dashboard sidebar was checked at desktop width and the page at phone width: the Games choices are stacked and aligned, the scope bar names the kind of games shown, and the Fall Stars Game appears only under Exhibition.
- The dashboard was driven on those local datasets: Triple-A and the off-season leagues appear as levels, the Games filter returned 546 regular-season, 68 postseason and 614 combined batting rows for the 2024 International League, and every page rendered.
- Make-up games: 70 games in the 2026 Double-A schedule were first listed as postponed without a score and later played under the same game ID. This is the case the exclusion fix covers.
- The deployed dataset's state was read, not written: 2021–2026 are complete under the 2.0 scope, and all 461 excluded games are cancelled games without a score.

2026-09-13, release 2.0:

- Full 2021 regular-season schedules for sport IDs 12, 13, and 14 returned 1,800 unique final games each, totaling 5,400 after deduplicating resumed schedule entries.
- Five distinct 2021 box scores were fetched and saved locally: 645343 (AA), 642623/642668/642738 (High-A), and 647848 (Single-A).
- The resulting sample has 131 player-stat rows across 20 team/group files. Every sample file was reopened using the default PyArrow Parquet reader.
- All limited live runs retained the season as incomplete rather than advancing the backfill.

## Integration checks

The GitHub workflow YAML parses correctly. The installed Hugging Face client exposes the commit-parent guard and upload-operation interfaces used by the code. Dataset-card YAML produces separate batting/pitching and league configurations.

Release 2.1 validated locally with Python 3.13.9, PyArrow 21.0.0, huggingface_hub 1.22.0, requests 2.34.2, and pytest 9.0.3. Release 2.0 was validated with Python 3.12.14, PyArrow 23.0.1, huggingface_hub 1.31.0, and pytest 9.1.1.

## Not yet exercised

No authenticated Hugging Face upload, GitHub Actions deployment, or upgrade of the deployed dataset was performed. Those require the destination repository and write token. The full Triple-A, postseason and off-season backfill for 2021–2026 was not run; the rehearsals used small real samples and do not prove every historical box score is available. No season has yet crossed a real 1 January under this release; that path is covered by tests and by the real 2025 schedule only. The scanner reports and retries missing data rather than silently marking it complete.

References for the integration design: [Hugging Face uploads](https://huggingface.co/docs/huggingface_hub/en/guides/upload), [dataset viewer configuration](https://huggingface.co/docs/hub/datasets-manual-configuration), and [GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
