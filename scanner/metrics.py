"""Derived sabermetrics. Pure functions — no network, safe to unit test directly."""
import numpy as np
import pandas as pd


def add_batting_rates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    df = df.copy()
    ab, pa, tb = df["batting_AB"], df["batting_PA"], df["batting_TB"]
    h, bb, hbp, sf, so, hr = (
        df["batting_H"], df["batting_BB"], df["batting_HBP"],
        df["batting_SF"], df["batting_SO"], df["batting_HR"],
    )

    df["batting_AVG"] = np.where(ab > 0, (h / ab).round(3), np.nan)

    obp_den = ab + bb + hbp + sf
    df["batting_OBP"] = np.where(obp_den > 0, ((bb + hbp + sf) / obp_den).round(3), np.nan)

    df["batting_SLG"] = np.where(ab > 0, (tb / ab).round(3), np.nan)
    df["batting_OPS"] = (df["batting_OBP"].fillna(0) + df["batting_SLG"].fillna(0)).round(3)
    df["batting_ISO"] = np.where(ab > 0, ((tb - h) / ab).round(3), np.nan)

    babip_den = ab - so - hr + sf
    df["batting_BABiP"] = np.where(babip_den > 0, ((h - hr) / babip_den).round(3), np.nan)

    df["batting_K%"] = np.where(pa > 0, (so / pa).round(3), np.nan)
    df["batting_BB%"] = np.where(pa > 0, (bb / pa).round(3), np.nan)

    ao = df["batting_AO"]
    df["batting_GO/AO"] = np.where(ao > 0, (df["batting_GO"] / ao).round(3), np.nan)

    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    return df


def add_pitching_rates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    df = df.copy()
    df["pitching_IP"] = (df["pitching_outs"] / 3).round(3)
    ip, er, r, bb, h, so, ab, hr, bf, pi = (
        df["pitching_IP"], df["pitching_ER"], df["pitching_R"], df["pitching_BB"],
        df["pitching_H"], df["pitching_SO"], df["pitching_AB"], df["pitching_HR"],
        df["pitching_BF"], df["pitching_PI"],
    )
    w, losses, sf = df["pitching_W"], df["pitching_L"], df["pitching_SF"]

    decisions = w + losses
    df["pitching_W%"] = np.where(decisions > 0, (w / decisions).round(3), np.nan)
    df["pitching_ERA"] = np.where(ip > 0, (9 * er / ip).round(3), np.nan)
    df["pitching_RA9"] = np.where(ip > 0, (9 * r / ip).round(3), np.nan)
    df["pitching_WHIP"] = np.where(ip > 0, ((bb + h) / ip).round(3), np.nan)
    df["pitching_H/9"] = np.where(ip > 0, (9 * h / ip).round(3), np.nan)
    df["pitching_HR/9"] = np.where(ip > 0, (9 * hr / ip).round(3), np.nan)
    df["pitching_BB/9"] = np.where(ip > 0, (9 * bb / ip).round(3), np.nan)
    df["pitching_SO/9"] = np.where(ip > 0, (9 * so / ip).round(3), np.nan)
    df["pitching_SO/BB"] = np.where(bb > 0, (so / bb).round(3), np.nan)
    df["pitching_BB/SO"] = np.where(so > 0, (bb / so).round(3), np.nan)

    babip_den = ab - so - hr - sf
    df["pitching_BABiP"] = np.where(babip_den > 0, ((h - hr) / babip_den).round(3), np.nan)
    df["pitching_BA"] = np.where(ab > 0, (h / ab).round(3), np.nan)

    obp_den = ab + bb + df["pitching_HBP"] + sf
    df["pitching_OBP"] = np.where(
        obp_den > 0, ((h + bb + df["pitching_HBP"]) / obp_den).round(3), np.nan
    )
    df["pitching_SLG"] = np.where(
        ab > 0,
        ((h + df["pitching_2B"] * 2 + df["pitching_3B"] * 3 + hr * 4) / ab).round(3),
        np.nan,
    )
    df["pitching_OPS"] = (df["pitching_OBP"].fillna(0) + df["pitching_SLG"].fillna(0)).round(3)
    df["pitching_ISO"] = (df["pitching_SLG"].fillna(0) - df["pitching_BA"].fillna(0)).round(3)

    df["pitching_SO%"] = np.where(bf > 0, (so / bf).round(3), np.nan)
    df["pitching_BB%"] = np.where(bf > 0, (bb / bf).round(3), np.nan)
    df["pitching_PI/PA"] = np.where(bf > 0, (pi / bf).round(3), np.nan)
    df["pitching_HR/PA"] = np.where(bf > 0, (hr / bf).round(3), np.nan)
    df["pitching_PI/IP"] = np.where(ip > 0, (pi / ip).round(3), np.nan)

    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    return df


def add_age(df: pd.DataFrame, bios: pd.DataFrame) -> pd.DataFrame:
    """Attach birth date / bats / throws / debut / age, merged strictly on the
    numeric player_id — never on name. Age is computed per row as of July 1st of
    that row's own season, so a player's career table shows their age at each
    season they actually played, not just their current age."""
    if df.empty or bios.empty:
        return df.copy()

    merged = df.merge(bios, on="player_id", how="left", validate="many_to_one")
    birth = pd.to_datetime(merged["birth_date"], errors="coerce")
    season_mid = pd.to_datetime(
        merged["season"].astype("Int64").astype(str) + "-07-01", errors="coerce"
    )
    merged["age_as_of_season"] = ((season_mid - birth).dt.days / 365.25).round(1)
    return merged
