"""Aggregate counts first, then calculate rates. Unknown values stay unknown.

The rate formulas are written once and run on either a single line (a dict of
scalars) or a whole table at once (a DataFrame with one row per player, split or
rolling window), because `divide` accepts both. That keeps one source of truth
and avoids a per-player Python loop over ~90 columns.
"""
import numpy as np
import pandas as pd

from dashboard.metric_catalog import RAW_FIELDS

WOBA_W = dict(bb=.690, hbp=.722, s1=.888, s2=1.271, s3=1.616, hr=2.101)
WOBA_SCALE = 1.22


def divide(n, d):
    """n / d, but undefined (NaN) unless both are known and the denominator is positive.

    Works on scalars and on aligned Series, so one formula serves a single line
    and a whole grouped table.
    """
    if isinstance(n, pd.Series) or isinstance(d, pd.Series):
        if isinstance(d, pd.Series):
            denominator = d.where(np.isfinite(d) & d.gt(0))
        else:
            denominator = d if pd.notna(d) and np.isfinite(d) and d > 0 else np.nan
        return (n / denominator).replace([np.inf, -np.inf], np.nan)
    return float(n / d) if pd.notna(n) and pd.notna(d) and np.isfinite(n) and np.isfinite(d) and d > 0 else np.nan


def count_columns(kind):
    """Source count columns that can be summed (innings text is not a number)."""
    return [c for c in RAW_FIELDS[kind].values() if c != "pitching_IP_str"]


def total(df, column):
    if df.empty or column not in df:
        return np.nan
    values = pd.to_numeric(df[column], errors="coerce")
    return float(values.sum()) if values.notna().all() else np.nan


def totals(df, kind, by=None, dropna=True):
    """Summed source counts. A total is unknown if any contributing game is missing it.

    `by` groups the rows (a column name) and returns one row per group; without it
    a single dict of scalars comes back.
    """
    columns = count_columns(kind)
    if by is None:
        line = {c.removeprefix(kind + "_"): total(df, c) for c in columns}
        line["G"] = df["game_pk"].nunique() if "game_pk" in df else 0
        return line
    keys = df[by]
    numbers = df.reindex(columns=columns).apply(pd.to_numeric, errors="coerce")
    grouped = numbers.groupby(keys, dropna=dropna, sort=True)
    complete = grouped.count().eq(grouped.size(), axis=0)
    table = grouped.sum(min_count=1).where(complete)
    table.columns = [c.removeprefix(kind + "_") for c in table.columns]
    table["G"] = df.groupby(keys, dropna=dropna, sort=True)["game_pk"].nunique()
    return table


def batting_rates(s):
    h, ab, bb, hbp, sf, so, hr = (s[k] for k in ("H", "AB", "BB", "HBP", "SF", "SO", "HR"))
    s["1B"] = h - s["2B"] - s["3B"] - hr
    s["AVG"] = divide(h, ab)
    s["OBP"] = divide(h + bb + hbp, ab + bb + hbp + sf)
    s["SLG"] = divide(s["TB"], ab)
    s["OPS"] = s["OBP"] + s["SLG"]
    s["ISO"] = s["SLG"] - s["AVG"]
    s["BABIP"] = divide(h - hr, ab - so - hr + sf)
    s["BB_pct"], s["K_pct"] = divide(bb, s["PA"]), divide(so, s["PA"])
    s["SB_pct"] = divide(s["SB"], s["SB"] + s["CS"])
    s["GO/AO"] = divide(s["GO"], s["AO"])
    s["wOBA"] = divide(.690 * (bb - s["IBB"]) + .722 * hbp + .888 * s["1B"]
                         + 1.271 * s["2B"] + 1.616 * s["3B"] + 2.101 * hr,
                         ab + bb - s["IBB"] + sf + hbp)
    s["R_PA"] = divide(s["R"], s["PA"])
    return s


def pitching_rates(s):
    s["IP"] = s["outs"] / 3
    s["ERA"], s["RA9"] = divide(27 * s["ER"], s["outs"]), divide(27 * s["R"], s["outs"])
    s["WHIP"] = divide(3 * (s["H"] + s["BB"]), s["outs"])
    for key, counter in (("K9", "SO"), ("BB9", "BB"), ("HR9", "HR"), ("H9", "H")):
        s[key] = divide(27 * s[counter], s["outs"])
    s["K_pct"], s["BB_pct"] = divide(s["SO"], s["BF"]), divide(s["BB"], s["BF"])
    s["K_BB_pct"] = s["K_pct"] - s["BB_pct"]
    s["Strike_pct"] = divide(s["PI_strikes"], s["PI"])
    s["W_pct"] = divide(s["W"], s["W"] + s["L"])
    s["SO/BB"], s["BB/SO"] = divide(s["SO"], s["BB"]), divide(s["BB"], s["SO"])
    s["BABIP"] = divide(s["H"] - s["HR"], s["AB"] - s["SO"] - s["HR"] + s["SF"])
    s["BA"] = divide(s["H"], s["AB"])
    s["OBP"] = divide(s["H"] + s["BB"] + s["HBP"], s["AB"] + s["BB"] + s["HBP"] + s["SF"])
    s["SLG"] = divide(s["H"] + s["2B"] + 2 * s["3B"] + 3 * s["HR"], s["AB"])
    s["OPS"], s["ISO"] = s["OBP"] + s["SLG"], s["SLG"] - s["BA"]
    s["PI/PA"], s["HR/PA"], s["PI/IP"] = divide(s["PI"], s["BF"]), divide(s["HR"], s["BF"]), divide(s["PI"], s["IP"])
    s["fip_raw"] = divide(13 * s["HR"] + 3 * (s["BB"] + s["HBP"]) - 2 * s["SO"], s["IP"])
    s["fip_const"] = s["ERA"] - s["fip_raw"]
    return s


def rates(s, kind):
    return batting_rates(s) if kind == "batting" else pitching_rates(s)


def batting_line(df):
    return batting_rates(totals(df, "batting"))


def pitching_line(df):
    return pitching_rates(totals(df, "pitching"))


def line_for(df, kind):
    return rates(totals(df, kind), kind)


def table_for(df, kind, by, dropna=True):
    """One line per group, computed for every group at once."""
    return rates(totals(df, kind, by=by, dropna=dropna), kind)


def wrc_plus(line, context):
    return 100 * divide((line["wOBA"] - context.get("wOBA", np.nan)) / WOBA_SCALE
                         + context.get("R_PA", np.nan), context.get("R_PA", np.nan))


def ops_plus(line, context):
    return 100 * (divide(line["OBP"], context.get("OBP", np.nan))
                  + divide(line["SLG"], context.get("SLG", np.nan)) - 1)


def fip(line, context):
    return line["fip_raw"] + context.get("fip_const", np.nan)


def enrich(line, kind, context):
    """Add the league-relative estimates. Works on one line or a whole table."""
    if kind == "batting":
        line["wRC_est"], line["OPS_index"] = wrc_plus(line, context), ops_plus(line, context)
    else:
        line["FIP_est"] = fip(line, context)
    return line


def enriched_line(df, kind, context):
    return enrich(line_for(df, kind), kind, context)


def player_table(df, kind):
    """One row per player, with the identity fields from their latest game."""
    if df.empty:
        return pd.DataFrame(columns=["player_id", "team_id", "Player", "Team", "Position", "Role"])
    table = enrich(table_for(df, kind, "player_id"), kind, line_for(df, kind))
    latest = df.sort_values(["game_date", "game_pk"]).groupby("player_id").tail(1).set_index("player_id")
    table["Player"] = latest["player_full_name"]
    table["Team"] = latest["team_name"]
    table["team_id"] = latest["team_id"]
    table["Position"] = latest["pos_group"] if "pos_group" in latest else "P"
    table["Role"] = latest["role"] if "role" in latest else ""
    return table.reset_index()


def percentile_rank(pool, value, lower=False):
    pool = pd.to_numeric(pool, errors="coerce").dropna()
    if len(pool) < 5 or pd.isna(value):
        return np.nan
    rank = 100 * ((pool < value).sum() + .5 * (pool == value).sum()) / len(pool)
    return 100 - rank if lower else rank


def rolling_rate(df, kind, window, metric=None):
    """The metric recalculated from the counts in each trailing window of appearances."""
    metric = metric or ("OPS" if kind == "batting" else "ERA")
    columns = count_columns(kind)
    frames = []
    # Never let a rolling window cross a season or level boundary.
    for _, season in df.groupby(["season", "team_level"], sort=True):
        season = season.sort_values(["game_date", "game_pk"])
        numbers = season.reindex(columns=columns).apply(pd.to_numeric, errors="coerce")
        window_sums = numbers.rolling(window, min_periods=1).sum()
        # A window total is unknown if any appearance inside it is missing that count.
        complete = numbers.notna().rolling(window, min_periods=1).min().eq(1)
        sums = window_sums.where(complete)
        sums.columns = [c.removeprefix(kind + "_") for c in sums.columns]
        sums["G"] = np.minimum(np.arange(len(season)) + 1, window)
        line = rates(sums, kind)
        frames.append(pd.DataFrame({"game_date": season["game_date"].values, "game_pk": season["game_pk"].values,
                                    "value": line[metric].values, "Games in window": line["G"].values,
                                    "metric": metric, "season": season["season"].values}))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["game_date", "game_pk", "value", "Games in window", "metric", "season"])


SPLIT_LABELS = {True: "Home", False: "Away"}


def split_table(df, kind, key):
    table = table_for(df, kind, key, dropna=False)
    labels = table.index.to_series()
    table["Split"] = labels.map(SPLIT_LABELS).fillna("Unknown") if key == "is_home" else labels.astype(str)
    return table.reset_index(drop=True)


def team_table(batting, pitching):
    """One row per team: observed record, runs and the headline batting/pitching rates."""
    games = game_results(batting, pitching)
    if games.empty:
        return pd.DataFrame(columns=["team_id", "Team", "Games", "W", "L", "W_pct", "RS", "RA", "Margin"])
    record = games.groupby("team_id").agg(Team=("team_name", "last"), Games=("game_pk", "nunique"),
                                          W=("result", lambda s: int(s.eq("W").sum())),
                                          L=("result", lambda s: int(s.eq("L").sum())),
                                          RS=("team_score", "sum"), RA=("opponent_score", "sum"))
    record["Margin"] = record["RS"] - record["RA"]
    record["W_pct"] = divide(record["W"], record["W"] + record["L"])
    for source, kind, keys in ((batting, "batting", ["OPS", "AVG", "OBP", "SLG", "HR"]),
                               (pitching, "pitching", ["ERA", "WHIP", "K9", "BB9"])):
        if source.empty:
            continue
        lines = table_for(source, kind, "team_id")
        for key in keys:
            record[key] = lines[key]
    return record.reset_index()


def game_results(batting, pitching):
    cols = ["game_pk", "game_date", "team_id", "team_name", "opponent_name", "team_score", "opponent_score", "result", "is_home"]
    frames = [df.reindex(columns=cols) for df in (batting, pitching) if not df.empty]
    if not frames:
        return pd.DataFrame(columns=cols + ["Margin"])
    games = pd.concat(frames).drop_duplicates(["game_pk", "team_id"]).sort_values(["game_date", "game_pk"])
    games["Margin"] = games["team_score"] - games["opponent_score"]
    return games


PYTHAGOREAN_EXPONENT = 1.83


def expected_win_pct(scored, allowed):
    """Share of games a team with these runs usually wins (Pythagorean expectation)."""
    return divide(scored ** PYTHAGOREAN_EXPONENT, scored ** PYTHAGOREAN_EXPONENT + allowed ** PYTHAGOREAN_EXPONENT)


def record_table(games, by):
    """Wins, losses and runs for each value of `by`: a label for every game, or one label for all of them."""
    table = games.assign(Split=by, W=games["result"].eq("W"), L=games["result"].eq("L")).groupby("Split", sort=False).agg(
        G=("game_pk", "nunique"), W=("W", "sum"), L=("L", "sum"), RS=("team_score", "sum"), RA=("opponent_score", "sum"))
    table[["W", "L"]] = table[["W", "L"]].astype(int)
    table["W_pct"] = divide(table["W"], table["W"] + table["L"])
    table["Margin"] = table["RS"] - table["RA"]
    return table.reset_index()


def record_splits(games):
    """One club's record at home and away, in close games and blowouts, and month by month."""
    games = games.sort_values(["game_date", "game_pk"])
    gap = games["Margin"].abs()
    parts = [record_table(games[games["is_home"].eq(home)], name) for home, name in ((True, "Home"), (False, "Away"))]
    parts += [record_table(games[gap.eq(1)], "One-run games"), record_table(games[gap.ge(5)], "Decided by 5+")]
    months = games["game_date"].dt.strftime("%b %Y" if games["game_date"].dt.year.nunique() > 1 else "%b")
    return pd.concat([p for p in parts if not p.empty] + [record_table(games, months)], ignore_index=True)


def standings_path(games):
    """Games above .500 after every decided game, per team: the shape of each club's season."""
    played = games[games["result"].isin(["W", "L"])].sort_values(["game_date", "game_pk"])
    step = played["result"].eq("W").astype(int) * 2 - 1
    return played.assign(Over=step.groupby(played["team_id"]).cumsum(), Game=played.groupby("team_id").cumcount() + 1)


def league_by_month(batting, pitching):
    """The league month by month: runs per team game and the pooled batting rates."""
    games = game_results(batting, pitching)
    if games.empty or batting.empty:
        return pd.DataFrame(columns=["Month", "Games", "R_G", "HR_G", "OPS", "K_pct", "BB_pct"])
    table = table_for(batting, "batting", "month")
    scores = games.groupby(games["game_date"].dt.strftime("%Y-%m"))["team_score"]
    table["R_G"], table["Games"] = scores.mean(), scores.size()
    table["HR_G"] = divide(table["HR"], table["Games"])
    stamps = pd.to_datetime(table.index + "-01")
    table["Month"] = stamps.strftime("%b %Y" if stamps.year.nunique() > 1 else "%b")
    return table.reset_index(drop=True)


def run_lengths(flags):
    """(longest run of True, run of True at the end)."""
    best = current = 0
    for flag in flags:
        current = current + 1 if flag else 0
        best = max(best, current)
    return best, current


def batting_streaks(df):
    """Hitting and on-base streaks from one player's games; empty when a count is missing."""
    need = ["batting_AB", "batting_PA", "batting_H", "batting_BB", "batting_HBP"]
    if df.empty or any(c not in df for c in need) or df[need].isna().any().any():
        return {}
    games = df.sort_values(["game_date", "game_pk"])
    official = games[games["batting_AB"] > 0]  # a game without an at-bat neither extends nor ends a hitting streak
    faced = games[games["batting_PA"] > 0]
    hit_best, hit_now = run_lengths(official["batting_H"] > 0)
    on_best, on_now = run_lengths((faced["batting_H"] + faced["batting_BB"] + faced["batting_HBP"]) > 0)
    return {"hit_best": hit_best, "hit_now": hit_now, "on_best": on_best, "on_now": on_now,
            "hit_share": divide(int((official["batting_H"] > 0).sum()), len(official)),
            "multi_hit": int((official["batting_H"] >= 2).sum()), "games": len(official)}


def game_score(df):
    """Bill James game score for each pitching appearance: 50 is an average start, 90 is dominant."""
    outs = df["pitching_outs"]
    return (50 + outs + 2 * (outs // 3 - 4).clip(lower=0) + df["pitching_SO"] - 2 * df["pitching_H"]
            - 4 * df["pitching_ER"] - 2 * (df["pitching_R"] - df["pitching_ER"]) - df["pitching_BB"])


def start_summary(df):
    """One pitcher's starts: how many, how many were quality starts, and the game scores."""
    starts = df[df["pitching_GS"].fillna(0) > 0] if "pitching_GS" in df else df.iloc[:0]
    if starts.empty:
        return {}
    score = game_score(starts)
    quality = (starts["pitching_outs"] >= 18) & (starts["pitching_ER"] <= 3)
    return {"starts": len(starts), "quality": int(quality.sum()), "score_avg": float(score.mean()) if score.notna().all() else np.nan,
            "score_best": float(score.max()) if score.notna().any() else np.nan,
            "outs_avg": float(starts["pitching_outs"].mean()) if starts["pitching_outs"].notna().all() else np.nan}


SIMILAR_KEYS = {"batting": ["K_pct", "BB_pct", "ISO", "AVG"], "pitching": ["K_pct", "BB_pct", "HR9", "BABIP"]}


def similar_players(population, player_id, kind, count=5):
    """The players whose rates sit closest to this one's, in standard deviations across the group.

    Match is 100 for identical rates and 0 for a pair as far apart as two typical players.
    """
    keys = SIMILAR_KEYS[kind]
    table = population.dropna(subset=keys).set_index("player_id")
    if player_id not in table.index or len(table) < 6:
        return table.iloc[:0].assign(Match=[]).reset_index()
    spread = table[keys].std(ddof=0).replace(0, np.nan)
    scaled = ((table[keys] - table[keys].mean()) / spread).fillna(0)
    distance = np.sqrt(((scaled - scaled.loc[player_id]) ** 2).sum(axis=1)).drop(player_id)
    typical = np.sqrt(2 * len(keys))  # expected distance between two independent standardised players
    nearest = distance.nsmallest(count)
    return table.loc[nearest.index].assign(Match=(100 * (1 - nearest / typical)).clip(lower=0)).reset_index()


def season_path(df, kind, points=24):
    """Each player's season-to-date OPS (or ERA) after every game, thinned to at most `points` values."""
    if df.empty:
        return pd.Series(dtype=object)
    columns = count_columns(kind)
    ordered = df.sort_values(["game_date", "game_pk"])
    numbers = ordered.reindex(columns=columns).apply(pd.to_numeric, errors="coerce").fillna(0)
    running = numbers.groupby(ordered["player_id"]).cumsum()
    running.columns = [c.removeprefix(kind + "_") for c in running.columns]
    running["G"] = 1
    value = rates(running, kind)["OPS" if kind == "batting" else "ERA"]
    # The first games swing wildly: start the line once there is something to read.
    value = value.where(running["PA"] >= 20 if kind == "batting" else running["outs"] >= 15)
    def thin(series):
        values = series.dropna().tolist()
        step = max(1, -(-len(values) // points))
        return values[::-1][::step][::-1]  # keep the latest game
    return value.groupby(ordered["player_id"]).apply(thin)


def simulate_trade(df, team_a, team_b, a_out, b_out):
    out = df.copy()
    destination = out["team_id"].copy()
    a_mask = out["team_id"].eq(team_a) & out["player_id"].isin(a_out)
    b_mask = out["team_id"].eq(team_b) & out["player_id"].isin(b_out)
    out["scenario_team_id"] = destination.mask(a_mask, team_b).mask(b_mask, team_a)
    return out


def innings_text(outs):
    if pd.isna(outs):
        return "N/A"
    return f"{int(outs) // 3}.{int(outs) % 3}"
