"""Sabermetric formulas, MLB-style, applied to the MiLB game-log columns.

Two things worth knowing before touching this file:

1. wOBA linear weights (wBB/wHBP/w1B/...) are the standard FanGraphs-style
   run-value coefficients. They barely move year to year in the majors and
   there's no MiLB-specific published set, so we use one fixed set for all
   seasons/levels. Everything downstream of wOBA (wRC+, the FIP constant) is
   instead centered on league averages computed straight from this dataset,
   per season + level, so "average" always means "average at that level that
   year" rather than an imported MLB number.
2. Every function takes an already-filtered slice of the batting/pitching
   frame and returns one dict of aggregated stats. Nothing here mutates the
   input.
"""
import numpy as np
import pandas as pd

# ---- batting ---------------------------------------------------------

WOBA_W = dict(bb=0.690, hbp=0.722, s1=0.888, s2=1.271, s3=1.616, hr=2.101)
WOBA_SCALE = 1.22


def _safe_div(n, d):
    return n / d if d else np.nan


def batting_line(df: pd.DataFrame) -> dict:
    g = df.agg({
        "batting_AB": "sum", "batting_H": "sum", "batting_2B": "sum", "batting_3B": "sum",
        "batting_HR": "sum", "batting_BB": "sum", "batting_IBB": "sum", "batting_HBP": "sum",
        "batting_SF": "sum", "batting_SO": "sum", "batting_PA": "sum", "batting_SB": "sum",
        "batting_CS": "sum", "batting_TB": "sum", "batting_R": "sum", "batting_RBI": "sum",
    })
    ab, h, d2, d3, hr = g["batting_AB"], g["batting_H"], g["batting_2B"], g["batting_3B"], g["batting_HR"]
    bb, ibb, hbp, sf, so, pa = (g["batting_BB"], g["batting_IBB"], g["batting_HBP"],
                                 g["batting_SF"], g["batting_SO"], g["batting_PA"])
    tb, sb, cs = g["batting_TB"], g["batting_SB"], g["batting_CS"]
    s1 = h - d2 - d3 - hr
    ubb = bb - ibb

    avg = _safe_div(h, ab)
    obp = _safe_div(h + bb + hbp, ab + bb + hbp + sf)
    slg = _safe_div(tb, ab)
    woba_num = WOBA_W["bb"] * ubb + WOBA_W["hbp"] * hbp + WOBA_W["s1"] * s1 + WOBA_W["s2"] * d2 \
        + WOBA_W["s3"] * d3 + WOBA_W["hr"] * hr
    woba_den = ab + bb - ibb + sf + hbp
    woba = _safe_div(woba_num, woba_den)
    babip = _safe_div(h - hr, ab - so - hr + sf)

    return dict(
        G=df["game_pk"].nunique(), PA=pa, AB=ab, H=h, HR=hr, RBI=g["batting_RBI"], R=g["batting_R"],
        SB=sb, CS=cs, BB=bb, SO=so, AVG=avg, OBP=obp, SLG=slg, OPS=(obp or 0) + (slg or 0),
        ISO=(slg - avg) if pd.notna(slg) and pd.notna(avg) else np.nan,
        BABIP=babip, BB_pct=_safe_div(bb, pa), K_pct=_safe_div(so, pa),
        SB_pct=_safe_div(sb, sb + cs), wOBA=woba,
    )


def league_batting_context(df: pd.DataFrame, keys=("season", "team_level")) -> pd.DataFrame:
    """Per season+level (or season+level+pos_group) league-average slash line & R/PA."""
    rows = []
    for key, sub in df.groupby(list(keys)):
        line = batting_line(sub)
        line.update(dict(zip(keys, key if isinstance(key, tuple) else (key,))))
        line["R_PA"] = _safe_div(sub["batting_R"].sum(), sub["batting_PA"].sum())
        rows.append(line)
    return pd.DataFrame(rows)


def wrc_plus(line: dict, lg_line: dict) -> float:
    """wRC+, no park factor (none is available in this dataset)."""
    if not lg_line.get("wOBA") or pd.isna(line.get("wOBA")) or not line.get("PA"):
        return np.nan
    wraa_pa = (line["wOBA"] - lg_line["wOBA"]) / WOBA_SCALE
    lg_r_pa = lg_line.get("R_PA", np.nan)
    if not lg_r_pa:
        return np.nan
    return round(100 * (wraa_pa + lg_r_pa) / lg_r_pa, 1)


def ops_plus(line: dict, lg_line: dict) -> float:
    if not lg_line.get("OBP") or not lg_line.get("SLG") or pd.isna(line.get("OBP")):
        return np.nan
    return round(100 * (line["OBP"] / lg_line["OBP"] + line["SLG"] / lg_line["SLG"] - 1), 1)


# ---- pitching ----------------------------------------------------------

def pitching_line(df: pd.DataFrame) -> dict:
    g = df.agg({
        "pitching_outs": "sum", "pitching_H": "sum", "pitching_R": "sum", "pitching_ER": "sum",
        "pitching_HR": "sum", "pitching_BB": "sum", "pitching_HBP": "sum", "pitching_SO": "sum",
        "pitching_BF": "sum", "pitching_PI": "sum", "pitching_PI_strikes": "sum",
        "pitching_W": "sum", "pitching_L": "sum", "pitching_SV": "sum", "pitching_HLD": "sum",
    })
    ip = g["pitching_outs"] / 3.0
    bf = g["pitching_BF"]
    era = _safe_div(g["pitching_ER"] * 9, ip)
    whip = _safe_div(g["pitching_BB"] + g["pitching_H"], ip)
    return dict(
        G=df["game_pk"].nunique(), GS=int((df["pitching_GS"].fillna(0) > 0).sum()), IP=ip,
        H=g["pitching_H"], R=g["pitching_R"], ER=g["pitching_ER"], HR=g["pitching_HR"],
        BB=g["pitching_BB"], SO=g["pitching_SO"], HBP=g["pitching_HBP"], BF=bf,
        W=g["pitching_W"], L=g["pitching_L"], SV=g["pitching_SV"], HLD=g["pitching_HLD"],
        ERA=era, WHIP=whip, K9=_safe_div(g["pitching_SO"] * 9, ip), BB9=_safe_div(g["pitching_BB"] * 9, ip),
        HR9=_safe_div(g["pitching_HR"] * 9, ip), K_pct=_safe_div(g["pitching_SO"], bf),
        BB_pct=_safe_div(g["pitching_BB"], bf), Strike_pct=_safe_div(g["pitching_PI_strikes"], g["pitching_PI"]),
    )


def league_pitching_context(df: pd.DataFrame, keys=("season", "team_level")) -> pd.DataFrame:
    rows = []
    for key, sub in df.groupby(list(keys)):
        line = pitching_line(sub)
        line.update(dict(zip(keys, key if isinstance(key, tuple) else (key,))))
        rows.append(line)
    out = pd.DataFrame(rows)
    out["fip_const"] = out["ERA"] - (13 * out["HR"] + 3 * (out["BB"] + out["HBP"]) - 2 * out["SO"]) / out["IP"]
    return out


def fip(line: dict, lg_line: dict) -> float:
    if not line.get("IP"):
        return np.nan
    raw = (13 * line["HR"] + 3 * (line["BB"] + line["HBP"]) - 2 * line["SO"]) / line["IP"]
    return round(raw + lg_line.get("fip_const", 3.10), 2)


# ---- shared -------------------------------------------------------------

def rolling_rate(df: pd.DataFrame, kind: str, window: int) -> pd.DataFrame:
    """Trailing-N-game rolling rate stat, one row per game, for a trend line."""
    df = df.sort_values("game_date")
    if kind == "batting":
        cols = ["batting_AB", "batting_H", "batting_BB", "batting_IBB", "batting_HBP",
                "batting_SF", "batting_2B", "batting_3B", "batting_HR", "batting_TB", "batting_PA"]
        roll = df[cols].rolling(window, min_periods=max(3, window // 3)).sum()
        s1 = roll["batting_H"] - roll["batting_2B"] - roll["batting_3B"] - roll["batting_HR"]
        ubb = roll["batting_BB"] - roll["batting_IBB"]
        num = (WOBA_W["bb"] * ubb + WOBA_W["hbp"] * roll["batting_HBP"] + WOBA_W["s1"] * s1
               + WOBA_W["s2"] * roll["batting_2B"] + WOBA_W["s3"] * roll["batting_3B"] + WOBA_W["hr"] * roll["batting_HR"])
        den = roll["batting_AB"] + roll["batting_BB"] - roll["batting_IBB"] + roll["batting_SF"] + roll["batting_HBP"]
        out = pd.DataFrame({"game_date": df["game_date"], "value": num / den})
        out["metric"] = f"Rolling {window}-game wOBA"
    else:
        cols = ["pitching_outs", "pitching_ER", "pitching_H", "pitching_BB", "pitching_HR", "pitching_SO"]
        roll = df[cols].rolling(window, min_periods=max(3, window // 3)).sum()
        ip = roll["pitching_outs"] / 3.0
        out = pd.DataFrame({"game_date": df["game_date"], "value": roll["pitching_ER"] * 9 / ip})
        out["metric"] = f"Rolling {window}-game ERA"
    return out.dropna()


def monthly_split(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    rows = []
    for month, sub in df.groupby("month"):
        line = batting_line(sub) if kind == "batting" else pitching_line(sub)
        line["month"] = month
        rows.append(line)
    return pd.DataFrame(rows).sort_values("month")


def season_split(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    rows = []
    for season, sub in df.groupby("season"):
        line = batting_line(sub) if kind == "batting" else pitching_line(sub)
        line["season"] = season
        rows.append(line)
    return pd.DataFrame(rows).sort_values("season")


def home_away_split(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    rows = []
    for is_home, sub in df.groupby("is_home"):
        line = batting_line(sub) if kind == "batting" else pitching_line(sub)
        line["split"] = "Home" if is_home else "Away"
        rows.append(line)
    return pd.DataFrame(rows)


def percentile_rank(pool: pd.Series, value) -> float:
    """Where `value` sits (0-100) inside `pool`. Used to turn a raw rate stat
    into something comparable across metrics for a radar chart."""
    s = pool.dropna()
    if value is None or pd.isna(value) or s.empty:
        return np.nan
    return round(100 * (s <= value).sum() / len(s), 1)


# label, dict key, format string, higher_is_better (for coloring deltas)
BATTING_SHEET = [
    ("G", "G", "{:.0f}", True), ("PA", "PA", "{:.0f}", True), ("AB", "AB", "{:.0f}", True),
    ("AVG", "AVG", "{:.3f}", True), ("OBP", "OBP", "{:.3f}", True), ("SLG", "SLG", "{:.3f}", True),
    ("OPS", "OPS", "{:.3f}", True), ("ISO", "ISO", "{:.3f}", True), ("BABIP", "BABIP", "{:.3f}", True),
    ("wOBA", "wOBA", "{:.3f}", True), ("BB%", "BB_pct", "{:.1%}", True), ("K%", "K_pct", "{:.1%}", False),
    ("SB%", "SB_pct", "{:.1%}", True), ("HR", "HR", "{:.0f}", True), ("RBI", "RBI", "{:.0f}", True),
    ("R", "R", "{:.0f}", True), ("SB", "SB", "{:.0f}", True), ("CS", "CS", "{:.0f}", False),
]
PITCHING_SHEET = [
    ("G", "G", "{:.0f}", True), ("GS", "GS", "{:.0f}", True), ("IP", "IP", "{:.1f}", True),
    ("ERA", "ERA", "{:.2f}", False), ("WHIP", "WHIP", "{:.2f}", False), ("K/9", "K9", "{:.1f}", True),
    ("BB/9", "BB9", "{:.1f}", False), ("HR/9", "HR9", "{:.2f}", False), ("K%", "K_pct", "{:.1%}", True),
    ("BB%", "BB_pct", "{:.1%}", False), ("Strike%", "Strike_pct", "{:.1%}", True),
    ("W", "W", "{:.0f}", True), ("L", "L", "{:.0f}", False), ("SV", "SV", "{:.0f}", True),
    ("HLD", "HLD", "{:.0f}", True),
]


def stat_sheet(line: dict, lg_line: dict, kind: str) -> pd.DataFrame:
    """Every computed metric, side by side with the season+level average -
    the 'not just the headline averages' full detail table."""
    spec = BATTING_SHEET if kind == "batting" else PITCHING_SHEET
    rows = []
    for label, key, fmt, _ in spec:
        v, lv = line.get(key), lg_line.get(key)
        rows.append({
            "Metric": label,
            "Value": fmt.format(v) if pd.notna(v) else "—",
            "League Avg": fmt.format(lv) if pd.notna(lv) else "—",
        })
    return pd.DataFrame(rows)


def radar_metrics(kind: str):
    """(label, key, invert) tuples used to build the scouting-radar chart -
    a compact 6-axis view of where a player ranks vs. the field."""
    if kind == "batting":
        return [("AVG", "AVG", False), ("OBP", "OBP", False), ("SLG", "SLG", False),
                ("BB%", "BB_pct", False), ("K%", "K_pct", True), ("SB%", "SB_pct", False)]
    return [("K/9", "K9", False), ("BB/9", "BB9", True), ("HR/9", "HR9", True),
            ("WHIP", "WHIP", True), ("Strike%", "Strike_pct", False), ("K-BB%", None, False)]
