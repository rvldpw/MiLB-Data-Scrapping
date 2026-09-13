"""Shared filters apply identically to every dashboard page."""
from dataclasses import dataclass
import os
import pandas as pd
import streamlit as st

from dashboard.data_loader import ROOT, DATASET_ID, LEVEL_LABEL, source_catalog, load_partition, server_token
from dashboard.ui import coverage


@dataclass
class Context:
    batting: pd.DataFrame
    pitching: pd.DataFrame
    season: int
    level: str
    league: str
    league_id: int
    source: str
    location: str
    start: object
    end: object
    revision: str

    @property
    def description(self):
        return f"{self.season} · {LEVEL_LABEL.get(self.level, self.level)} · {self.league}"


def load_context():
    with st.sidebar:
        st.markdown("### Your field of view")
        st.caption("Start with a league. Every page follows these filters.")
        source = st.selectbox("Data source", ["Hugging Face", "Included sample", "Local dataset"],
                              index=0, key="data_source")
        if source == "Hugging Face":
            location = st.text_input("Dataset repository", DATASET_ID, key="dataset_repository")
        elif source == "Local dataset":
            location = st.text_input("Dataset folder", os.getenv("MILB_DATA_DIR", str(ROOT / "samples")), key="local_dataset")
        else:
            location = str(ROOT / "samples")
            st.caption("Five real games from 2021. Explore the layout, then connect your dataset.")
        if st.button("Refresh source", width="stretch"):
            source_catalog.clear()
            load_partition.clear()
        try:
            with st.spinner("Reading available leagues…"):
                catalog, revision = source_catalog(source, location, server_token())
        except Exception:
            st.error("Could not read this source. Check the repository or folder and, for a private dataset, the server's HF_TOKEN secret. Then refresh.")
            st.stop()
        seasons = sorted(catalog["season"].dropna().astype(int).unique(), reverse=True)
        season = st.selectbox("Season", seasons, key="scope_season")
        season_catalog = catalog[catalog["season"].astype(int).eq(season)]
        levels = season_catalog.groupby("team_level")["team_id"].nunique().sort_values(ascending=False).index.tolist()
        level = st.selectbox("Level", levels, format_func=lambda x: LEVEL_LABEL.get(x, x), key="scope_level")
        level_catalog = season_catalog[season_catalog["team_level"].eq(level)]
        leagues = level_catalog[["league_id", "league_name"]].drop_duplicates("league_id").sort_values("league_name")
        names = dict(zip(leagues["league_id"].astype(int), leagues["league_name"]))
        lid = st.selectbox("League", list(names), format_func=names.get, key="scope_league")
        chosen = level_catalog[level_catalog["league_id"].astype(int).eq(lid)]
        try:
            with st.spinner("Loading this league's game logs…"):
                frames = []
                for kind in ("batting", "pitching"):
                    paths = tuple(chosen[kind].dropna().unique()) if kind in chosen else ()
                    frames.append(load_partition(source, location, revision, paths, kind, server_token()))
                batting, pitching = frames
        except Exception:
            st.error("This league could not be loaded. Check that its Parquet files match the catalog, then refresh the source.")
            st.stop()
        dates = pd.concat([batting["game_date"], pitching["game_date"]]).dropna()
        if dates.empty:
            st.info("No completed game rows are available for this selection yet.")
            st.stop()
        start, end = dates.min().date(), dates.max().date()
        selected = st.date_input("Game dates", (start, end), min_value=start, max_value=end,
                                 key=f"dates_{source}_{location}_{season}_{level}_{lid}")
        if isinstance(selected, tuple) and len(selected) == 2:
            start, end = selected
        elif isinstance(selected, tuple) and len(selected) == 1:
            st.caption("Select an end date to apply a date range.")
        st.divider()
        st.caption("Benchmarks use this season, league, level and date range. Selecting a player or team does not change the peer group.")
        st.caption("No full-season coverage is assumed. Only downloaded games count.")
    def within(df):
        if df.empty:
            return df
        return df[df["game_date"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()
    return Context(within(batting), within(pitching), int(season), level, names[lid], int(lid), source, location, start, end, revision)


def context_note(ctx):
    both = pd.concat([ctx.batting, ctx.pitching], ignore_index=True)
    games = both["game_pk"].nunique() if not both.empty else 0
    if ctx.source == "Included sample":
        coverage(f"Real sample data · {games} game(s) in this league · {ctx.start:%d %b %Y} to {ctx.end:%d %b %Y}. A format preview, not a complete season or a reliable player ranking.")
    else:
        st.caption(f"{ctx.source} · {games:,} games on file · {ctx.start:%d %b %Y} to {ctx.end:%d %b %Y} · Scope: {ctx.league}")
