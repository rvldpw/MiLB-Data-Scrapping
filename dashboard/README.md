# MiLB Analyst Hub — redesigned Streamlit dashboard

An interactive workspace for scouts, coaches and player analysts, built around player game logs. The scanner and its daily backfill workflow are unchanged by this dashboard release.

## Run locally

Use Python 3.11 or 3.12. From the repository root:

```sh
python -m pip install -r dashboard/requirements.txt
python -m streamlit run dashboard/Home.py
```

The app opens with the included five real sample games. The coverage banner makes this explicit. For a full dataset, select **Hugging Face** in the sidebar and enter your dataset repository ID. The default repository is `rvlpw/milb-game-logs`. No Google Sheets connection is needed.

For Streamlit Community Cloud, select `dashboard/Home.py` as the entrypoint. Install `dashboard/requirements.txt`. Use the repository's light `.streamlit/config.toml`. Private datasets require a read token in Streamlit secrets:

```toml
HF_TOKEN = "your-read-token"
```

Keep secrets out of Git. You can also configure environment variables `HF_TOKEN`, `HF_REPO_ID`, and `DASHBOARD_SOURCE=hub`. Local dataset mode expects a folder containing `data/season-YYYY/league-ID/team-ID/{batting,pitching}.parquet`. Hugging Face mode also requires the scanner's `catalog.json`.

## Pages

- **Overview:** league performance landscape, opportunity filters, sortable leaderboards, coverage and downloads.
- **Player lab:** searchable player IDs, team and position/role filters, rolling performance, same-league percentiles, individual game inspection, month/home-away/team splits, player comparisons, full metrics and a downloadable report with notes.
- **Team room:** observed results and run margins, a positional batting map, historical roster production, starting/relief pitching splits and all team metrics.
- **Roster scenarios:** two-way reassignment of recorded player production, showing before/after rates and opportunity totals. This is a historical replay, not a player valuation or a forecast.
- **Metric guide:** plain-language definitions, formulas, direction of interpretation, source columns and a per-column completeness audit.

All pages share season, level, league and date filters. A team/player selection does not shrink the league benchmark. Hugging Face reads are pinned to the catalog revision and only the selected league's batting and pitching files are downloaded. Refresh clears cached source data; switching filters does not require loading every season.

## Metric integrity

The dashboard retains all 38 batting and 54 pitching source fields from the original scraper's metric mapping. It recovers mapped values from `raw_stats_json` where available, preserves additional source columns, and exposes raw rows for download. Unavailable fields remain visible as N/A; the dashboard cannot recreate observations absent from both the columns and raw source JSON.

Rates are computed from summed counts, not averages of game percentages. Missing inputs make the affected aggregate unavailable, including partially missing counts. Pitching rates use recorded outs; 5.2 innings means 17 outs. Game results are deduplicated by game and team. Player selection and scenarios use IDs, not name matching.

Percentiles require at least five players with valid values and use midranks for ties. Minimum PA/IP controls help users inspect sample size; no percentile is presented as a scouting grade. Trend windows display the actual number of available appearances and do not cross season/level boundaries.

wOBA uses fixed illustrative weights. Estimated wRC, OPS index and FIP are explicitly labeled estimates, benchmarked to loaded data, without park adjustment. They are not official FanGraphs season metrics. Consult the in-app guide for formulas. The positional map measures batting production at listed positions; it is not a defensive skill assessment. Current bio lookup is optional and separate from historical game data; unknown activity status is never guessed to be a release.

## Validation

```sh
python -m pip install pytest
python -m pytest dashboard/tests -q
```

The dashboard suite covers weighted rates, missingness, pitching arithmetic, complete field recovery, percentile ties, conservative status, unique game counts, scenario conservation, all five page renders and interactive pitching/scenario flows. Existing root-level scraper tests are outside this dashboard suite.

Design uses native Streamlit navigation and accessible controls, a light neutral/green palette, responsive metric strips, interactive Plotly charts and chart PNG downloads. CSV exports retain underlying metrics; they do not replace Hugging Face storage.
