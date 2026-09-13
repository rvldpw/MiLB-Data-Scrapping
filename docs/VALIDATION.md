# Validation — 2026-09-13

## Automated checks

`python -m pytest -q`: **30 tests passed**.

Coverage includes six daily backfill runs, the same-day gate, game-count and runtime limits, failed API requests, failed uploads, checkpoint resume, current-season refresh, old suspended games, the 2027 rollover, scoring corrections, doubleheaders, stable nullable Parquet types, missing state/data detection, and guarded atomic Hub commits.

Hub read tests distinguish a confirmed missing remote file from a network/cache failure, preventing a temporary outage from resetting the backfill state.

The real box-score fixture for game 750975 verifies that extracted player hits/runs match team game totals and that unused players' season totals do not become game rows. An additional regression verifies ordinary Parquet readers can open the downloaded team files without partition-type conflicts.

## Live public API checks

- Full 2021 regular-season schedules for sport IDs 12, 13, and 14 returned 1,800 unique final games each, totaling 5,400 after deduplicating resumed schedule entries.
- Five distinct 2021 box scores were fetched and saved locally: 645343 (AA), 642623/642668/642738 (High-A), and 647848 (Single-A).
- The resulting sample has 131 player-stat rows across 20 team/group files. Every sample file was reopened using the default PyArrow Parquet reader.
- All limited live runs retained the season as incomplete rather than advancing the backfill.

## Integration checks

Both GitHub workflow YAML files parse correctly. The installed Hugging Face client exposes the commit-parent guard and upload-operation interfaces used by the code. Dataset-card YAML produces separate batting/pitching and league configurations.

Validated locally with Python 3.12.14, PyArrow 23.0.1, huggingface_hub 1.31.0, requests 2.34.2, and pytest 9.1.1.

## Not yet exercised

No authenticated Hugging Face upload, GitHub Actions deployment, or full six-season backfill was performed. Those require the user's destination repository and write token. Live source verification used small historical samples; it does not prove every historical box score is available. The scanner reports and retries missing data rather than silently marking it complete.

References for the integration design: [Hugging Face uploads](https://huggingface.co/docs/huggingface_hub/en/guides/upload), [dataset viewer configuration](https://huggingface.co/docs/hub/datasets-manual-configuration), and [GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
