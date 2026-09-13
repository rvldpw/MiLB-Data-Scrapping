"""Load only a selected season/league; preserve source columns and missingness."""
from pathlib import Path
import json
import os
import re

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import streamlit as st
from huggingface_hub import HfApi, hf_hub_download

from dashboard.metric_catalog import RAW_FIELDS

ROOT = Path(__file__).resolve().parents[1]
DATASET_ID = os.getenv("HF_REPO_ID", "rvlpw/milb-game-logs")
LEVEL_LABEL = {"A": "Single-A", "A+": "High-A", "AA": "Double-A"}
POSITION_ORDER = ["C", "1B", "2B", "3B", "SS", "OF", "DH", "UT"]
POSITION_GROUP = {p: p for p in POSITION_ORDER} | {"LF": "OF", "CF": "OF", "RF": "OF", "P": "P"}
PATH_PATTERN = re.compile(r"data/season[-=](\d+)/league[-=](\d+)/team[-=](\d+)/(batting|pitching)\.parquet$")


def server_token():
    token = os.getenv("HF_TOKEN")
    if not token:
        try:
            token = st.secrets.get("HF_TOKEN")
        except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
            token = None
    return token


def clean_data(df, kind):
    df = df.copy()
    if df.empty:
        return pd.DataFrame(columns=["season", "team_level", "league_id", "league_name", "player_id", "team_id",
                                     "player_full_name", "team_name", "game_pk", "game_date", "pos_group", "role",
                                     *RAW_FIELDS[kind].values()])
    aliases = {"team_league_id": "league_id", "team_league": "league_name", "team_level_id": "sport_id"}
    for old, new in aliases.items():
        if new not in df and old in df:
            df[new] = df[old]
    required = ["player_id", "team_id", "game_pk", "season", "game_date", "team_level", "league_id"]
    missing = [c for c in required if c not in df]
    if missing:
        raise ValueError("Missing required dataset columns: " + ", ".join(missing))
    def decode(value):
        try:
            result = json.loads(value) if isinstance(value, str) else {}
            return result if isinstance(result, dict) else {}
        except (TypeError, ValueError):
            return {}
    raw = df.get("raw_stats_json", pd.Series("{}", index=df.index)).map(decode)
    for source, column in RAW_FIELDS[kind].items():
        values = df[column] if column in df else pd.Series(np.nan, index=df.index)
        fallback = raw.map(lambda item: item.get(source, np.nan))
        df[column] = values.where(values.notna(), fallback)
        if column != "pitching_IP_str":
            df[column] = pd.to_numeric(df[column], errors="coerce")
    for col in ("player_id", "team_id", "game_pk", "season", "league_id"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    if df[required].isna().any().any():
        raise ValueError("Some rows have invalid game dates or missing identity fields")
    for col, fallback in (("player_full_name", "Unknown player"), ("team_name", "Unknown team"),
                          ("league_name", "Unknown league"), ("player_position", "Unknown")):
        if col not in df:
            df[col] = fallback
        df[col] = df[col].fillna(fallback)
    df["month"] = df["game_date"].dt.strftime("%Y-%m")
    df["pos_group"] = df["player_position"].map(POSITION_GROUP).fillna("UT")
    if kind == "pitching":
        def outs(value):
            try:
                a, _, b = str(value).partition(".")
                return int(a) * 3 + int(b or 0) if b in ("", "0", "1", "2") else np.nan
            except ValueError:
                return np.nan
        df["pitching_outs"] = df["pitching_outs"].fillna(df["pitching_IP_str"].map(outs))
        df["role"] = np.where(df["pitching_GS"].isna(), "Unknown", np.where(df["pitching_GS"] > 0, "SP", "RP"))
    keys = ["game_pk", "team_id", "player_id"]
    if "fetched_at" in df:
        df = df.sort_values("fetched_at", na_position="first")
    return df.drop_duplicates(keys, keep="last").sort_values(["game_date", "game_pk", "player_id"]).reset_index(drop=True)


@st.cache_data(ttl=900, show_spinner=False)
def source_catalog(source, location, token=None):
    if source == "Hugging Face":
        info = HfApi(token=token).repo_info(location, repo_type="dataset")
        revision = info.sha
        files = [f.rfilename for f in info.siblings]
        if "catalog.json" not in files:
            raise ValueError("This dataset has no catalog.json yet. Finish the scanner's first checkpoint, then refresh.")
        file = hf_hub_download(location, "catalog.json", repo_type="dataset", revision=revision, token=token)
        entries = json.loads(Path(file).read_text())
        rows = list(entries.values())
    else:
        revision = "local"
        root = Path(location).expanduser().resolve()
        rows = []
        for path in sorted(root.glob("data/**/*.parquet")):
            match = PATH_PATTERN.search(str(path.relative_to(root)))
            if not match:
                continue
            frame = pq.ParquetFile(path).read(columns=["season", "league_id", "league_name", "team_level", "team_id", "team_name"]).to_pandas()
            if frame.empty:
                continue
            row = frame.iloc[0].to_dict()
            row[match[4]] = str(path.relative_to(root))
            rows.append(row)
    if not rows:
        raise ValueError("No game-log tables found in this source.")
    return pd.DataFrame(rows), revision


@st.cache_data(ttl=900, show_spinner=False, max_entries=12)
def load_partition(source, location, revision, paths, kind, token=None):
    frames = []
    root = Path(location).expanduser().resolve() if source != "Hugging Face" else None
    for relative in sorted(set(paths)):
        if not PATH_PATTERN.fullmatch(relative):
            raise ValueError("The catalog contains an unsupported table path")
        if source == "Hugging Face":
            file = hf_hub_download(location, relative, repo_type="dataset", revision=revision, token=token)
        else:
            file = root / relative
        frames.append(pq.ParquetFile(file).read().to_pandas())
    return clean_data(pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(), kind)
