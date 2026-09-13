# Deploy to GitHub Actions and Hugging Face

## 1. Install the updated project

Copy the contents of this project to the root of your GitHub repository. Include hidden `.github` and `.gitignore` files. Replace the old scanner files and workflow. Remove old `apps_script/Code.gs`, `scanner/sheets_sync.py`, `scanner/metrics.py`, and `tests/test_offline.py` if you copy over an existing checkout; they are not part of this release.

The old Google Sheet can remain as an archive. Its data is not imported: the new dataset starts fresh with actual game logs. The old `APPS_SCRIPT_URL` and `APPS_SCRIPT_SECRET` secrets are unused and can be removed.

## 2. Configure Hugging Face

Choose a dataset name such as `your-username/milb-game-logs`. Use a dedicated dataset repository because the scanner maintains its README, catalog, data paths, and state files.

Create a Hugging Face token with write access to that repository. You can pre-create a private dataset and scope the token to it. Alternatively, a token with repository-creation permission can let the scanner create the dataset. Newly created datasets are private by default; the scanner does not change the visibility of an existing repository.

In GitHub **Settings → Secrets and variables → Actions**:

| Type | Name | Value |
| --- | --- | --- |
| Repository variable | `HF_REPO_ID` | `your-username/milb-game-logs` |
| Repository secret | `HF_TOKEN` | Your Hugging Face write token |

Never put the token in source code, this README, or a workflow's plain-text environment values.

## 3. Start the schedule

Open **Actions → MiLB daily game logs → Run workflow**. Inspect logs and `state/index.json` on Hugging Face. After one season finishes, another run on the same UTC day waits; the following day's run selects the next season.

The checked-in workflow requests one run every day at 09:00 UTC (16:00 WIB), on the repository's default branch. This schedule becomes active only after you put the workflow in your GitHub repository and enable Actions. Scheduled GitHub jobs can be delayed; see [GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

No Codex reminder, Google Sheet, Apps Script deployment, or always-on computer is required. Ensure the GitHub account has enough Actions usage for the initial backfill and the Hugging Face account has enough storage for the dataset.

## 4. Check completion

- Hugging Face `state/index.json`: `initialized` means all final games returned by the last successful snapshot were fetched; `final_complete` freezes a past year.
- `state/2021.json`: one entry per successfully stored game, including fetch date and table paths.
- `catalog.json`: readable season/league/team mapping.
- GitHub logs: selected season, pending games, checkpoint commits, and any errors.
- GitHub job summary: fetched/stored game counts for successful or deliberately limited runs.

For a failed run, the job is red and successful checkpoints remain available. Re-run to resume. Do not delete the state directory to fix a temporary network error.
