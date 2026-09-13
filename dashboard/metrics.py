"""Aggregate counts first, then calculate rates. Unknown values stay unknown."""
import numpy as np
import pandas as pd

from dashboard.metric_catalog import RAW_FIELDS

WOBA_W = dict(bb=.690, hbp=.722, s1=.888, s2=1.271, s3=1.616, hr=2.101)
WOBA_SCALE = 1.22


def divide(n, d):
    return float(n / d) if pd.notna(n) and pd.notna(d) and np.isfinite(n) and np.isfinite(d) and d > 0 else np.nan


def total(df, column):
    if df.empty or column not in df:
        return np.nan
    values = pd.to_numeric(df[column], errors="coerce")
    return float(values.sum()) if values.notna().all() else np.nan


def batting_line(df):
    s = {c.removeprefix("batting_"): total(df, c) for c in RAW_FIELDS["batting"].values()}
    h, ab, bb, hbp, sf, so, hr = (s[k] for k in ("H", "AB", "BB", "HBP", "SF", "SO", "HR"))
    s["G"] = df["game_pk"].nunique() if "game_pk" in df else 0
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


def pitching_line(df):
    s = {c.removeprefix("pitching_"): total(df, c) for c in RAW_FIELDS["pitching"].values() if c != "pitching_IP_str"}
    s["G"] = df["game_pk"].nunique() if "game_pk" in df else 0
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


def line_for(df, kind):
    return batting_line(df) if kind == "batting" else pitching_line(df)


def wrc_plus(line, context):
    return 100 * divide((line.get("wOBA", np.nan) - context.get("wOBA", np.nan)) / WOBA_SCALE
                         + context.get("R_PA", np.nan), context.get("R_PA", np.nan))


def ops_plus(line, context):
    return 100 * (divide(line.get("OBP", np.nan), context.get("OBP", np.nan))
                  + divide(line.get("SLG", np.nan), context.get("SLG", np.nan)) - 1)


def fip(line, context):
    return line.get("fip_raw", np.nan) + context.get("fip_const", np.nan)


def enriched_line(df, kind, context):
    result = line_for(df, kind)
    if kind == "batting":
        result.update(wRC_est=wrc_plus(result, context), OPS_index=ops_plus(result, context))
    else:
        result["FIP_est"] = fip(result, context)
    return result


def player_table(df, kind):
    context = line_for(df, kind)
    rows = []
    for pid, sub in df.groupby("player_id", sort=False):
        latest = sub.sort_values(["game_date", "game_pk"]).iloc[-1]
        row = enriched_line(sub, kind, context)
        row.update(player_id=pid, team_id=latest.get("team_id"), Player=latest["player_full_name"], Team=latest["team_name"],
                   Position=latest.get("pos_group", "P"), Role=latest.get("role", ""))
        rows.append(row)
    return pd.DataFrame(rows)


def percentile_rank(pool, value, lower=False):
    pool = pd.to_numeric(pool, errors="coerce").dropna()
    if len(pool) < 5 or pd.isna(value):
        return np.nan
    rank = 100 * ((pool < value).sum() + .5 * (pool == value).sum()) / len(pool)
    return 100 - rank if lower else rank


def rolling_rate(df, kind, window, metric=None):
    metric = metric or ("OPS" if kind == "batting" else "ERA")
    rows = []
    # Never let a rolling window cross a season or level boundary.
    for _, season in df.groupby(["season", "team_level"], sort=True):
        season = season.sort_values(["game_date", "game_pk"]).reset_index(drop=True)
        for i in range(len(season)):
            sub = season.iloc[max(0, i - window + 1):i + 1]
            rows.append({"game_date": season.iloc[i]["game_date"], "game_pk": season.iloc[i]["game_pk"],
                         "value": line_for(sub, kind).get(metric, np.nan), "Games in window": len(sub),
                         "metric": metric, "season": season.iloc[i]["season"]})
    return pd.DataFrame(rows)


def split_table(df, kind, key):
    rows = []
    for value, sub in df.groupby(key, dropna=False, sort=True):
        row = line_for(sub, kind)
        row["Split"] = ("Unknown" if pd.isna(value) else ("Home" if value else "Away")) if key == "is_home" else str(value)
        rows.append(row)
    return pd.DataFrame(rows)


def game_results(batting, pitching):
    cols = ["game_pk", "game_date", "team_id", "team_name", "opponent_name", "team_score", "opponent_score", "result"]
    frames = [df.reindex(columns=cols) for df in (batting, pitching) if not df.empty]
    if not frames:
        return pd.DataFrame(columns=cols + ["Margin"])
    games = pd.concat(frames).drop_duplicates(["game_pk", "team_id"]).sort_values(["game_date", "game_pk"])
    games["Margin"] = games["team_score"] - games["opponent_score"]
    return games


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
