"""Loads the rvlpw/milb-game-logs dataset and does light, one-time cleanup.

Kept deliberately simple: pull the two pre-built HF configs (batting, pitching),
convert to pandas, fix dtypes, tag a position group + pitcher role. Everything
else (rate stats, benchmarks) lives in metrics.py and is computed on demand
from these two frames.
"""
import numpy as np
import pandas as pd
import streamlit as st

DATASET_ID = "rvlpw/milb-game-logs"

# Collapse raw MLB position codes into the groups a scouting report actually uses.
POSITION_GROUP = {
    "C": "C", "1B": "1B", "2B": "2B", "3B": "3B", "SS": "SS",
    "LF": "OF", "CF": "OF", "RF": "OF", "OF": "OF",
    "DH": "DH", "P": "P",
}
POSITION_ORDER = ["C", "1B", "2B", "3B", "SS", "OF", "DH"]
LEVEL_ORDER = ["A", "A+", "AA"]
LEVEL_LABEL = {"A": "Single-A", "A+": "High-A", "AA": "Double-A"}


def _clean_common(df: pd.DataFrame) -> pd.DataFrame:
    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    df["month"] = df["game_date"].dt.to_period("M").astype(str)
    df["win"] = np.where(df["result"] == "W", 1, np.where(df["result"] == "L", 0, np.nan))
    df["team_level"] = df["team_level"].replace({"A-": "A"})
    return df


@st.cache_data(show_spinner="Pulling MiLB game logs from Hugging Face...", ttl=6 * 3600)
def load_data():
    from datasets import load_dataset

    batting = load_dataset(DATASET_ID, "batting", split="train").to_pandas()
    pitching = load_dataset(DATASET_ID, "pitching", split="train").to_pandas()

    batting = _clean_common(batting)
    batting["pos_group"] = batting["player_position"].map(POSITION_GROUP).fillna("UT")

    pitching = _clean_common(pitching)
    pitching["IP"] = pitching["pitching_outs"] / 3.0
    # A player is treated as a "starter" for a given appearance if he started it.
    pitching["role"] = np.where(pitching["pitching_GS"].fillna(0) > 0, "SP", "RP")

    return batting, pitching


@st.cache_data(show_spinner=False)
def season_levels(batting: pd.DataFrame, pitching: pd.DataFrame):
    """All (season, level) combos present, sorted, for sidebar filters."""
    cols = ["season", "team_level"]
    combo = pd.concat([batting[cols], pitching[cols]]).drop_duplicates()
    combo["level_rank"] = combo["team_level"].apply(
        lambda x: LEVEL_ORDER.index(x) if x in LEVEL_ORDER else 99
    )
    combo = combo.sort_values(["season", "level_rank"])
    return list(combo["season"].unique()), combo
