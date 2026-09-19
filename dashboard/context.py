"""Shared filters apply identically to every dashboard page."""
from dataclasses import dataclass
import os
import pandas as pd
import streamlit as st

from dashboard import bio
from dashboard.data_loader import ROOT, DATASET_ID, LEVEL_LABEL, source_catalog, load_partition, server_token
from dashboard.ui import coverage, scope_bar


@dataclass
class Context:
    batting: pd.DataFrame
    pitching: pd.DataFrame
    seasons: tuple
    level: str
    league: str
    league_id: int
    source: str
    location: str
    start: object
    end: object
    revision: str
    pool: str = "Everyone who played"

    @property
    def multi_season(self):
        return self.seasons[0] != self.seasons[1]

    @property
    def period(self):
        return f"{self.seasons[0]}–{self.seasons[1]}" if self.multi_season else str(self.seasons[0])

    @property
    def tag(self):
        """Filename-safe period, e.g. 2021-2023."""
        return self.period.replace("–", "-")

    @property
    def description(self):
        return f"{self.period} · {LEVEL_LABEL.get(self.level, self.level)} · {self.league}"


def load_context():
    with st.sidebar:
        st.markdown("### Filters")
        scope_box = st.container()
        source_box = st.expander("Data source", expanded=False)
        with source_box:
            source = st.selectbox("Source", ["Hugging Face", "Included sample", "Local dataset"],
                                  index=0, key="data_source")
            if source == "Hugging Face":
                location = st.text_input("Dataset repository", DATASET_ID, key="dataset_repository")
            elif source == "Local dataset":
                location = st.text_input("Dataset folder", os.getenv("MILB_DATA_DIR", str(ROOT / "samples")), key="local_dataset")
            else:
                location = str(ROOT / "samples")
                st.caption("Five real games from 2021, for a look at the layout.")
            if st.button("Refresh source", width="stretch"):
                source_catalog.clear()
                load_partition.clear()
        try:
            with st.spinner("Reading available leagues…"):
                catalog, revision = source_catalog(source, location, server_token())
        except Exception:
            st.error("Could not read this source. Check the repository or folder under Data source (a private dataset needs the HF_TOKEN secret), then refresh.")
            st.stop()
        with scope_box:
            seasons = sorted(catalog["season"].dropna().astype(int).unique())
            if len(seasons) > 1:
                first, last = st.columns(2)
                lo = first.selectbox("From season", seasons, index=len(seasons) - 1, key="scope_from",
                                     help="Set different From and To seasons to cover several years.")
                later = [x for x in seasons if x >= lo]
                hi = last.selectbox("To season", later, index=len(later) - 1, key="scope_to")
            else:
                lo = hi = seasons[0]
                st.caption(f"Season: {lo} (the only one in this source)")
            in_range = catalog[catalog["season"].astype(int).between(lo, hi)]
            levels = in_range.groupby("team_level")["team_id"].nunique().sort_values(ascending=False).index.tolist()
            level = st.selectbox("Level", levels, format_func=lambda x: LEVEL_LABEL.get(x, x), key="scope_level")
            level_catalog = in_range[in_range["team_level"].eq(level)]
            leagues = level_catalog.sort_values("season")[["league_id", "league_name"]].drop_duplicates("league_id", keep="last").sort_values("league_name")
            names = dict(zip(leagues["league_id"].astype(int), leagues["league_name"]))
            lid = st.selectbox("League", list(names), format_func=names.get, key="scope_league")
            chosen = level_catalog[level_catalog["league_id"].astype(int).eq(lid)]
            try:
                with st.spinner("Loading game logs…"):
                    frames = []
                    for kind in ("batting", "pitching"):
                        paths = tuple(chosen[kind].dropna().unique()) if kind in chosen else ()
                        frames.append(load_partition(source, location, revision, paths, kind, server_token()))
                    batting, pitching = frames
            except Exception:
                st.error("This league could not be loaded. Check that its Parquet files match the catalog, then refresh the source.")
                st.stop()
            pool = "Everyone who played"
            here = bio.DATA_LEVEL.get(level, LEVEL_LABEL.get(level, level))
            choice = st.selectbox("Players", ["Everyone who played", f"Still at {here} today", "Moved up to a higher level", "Pick current levels…"],
                                  key="scope_pool", help="Based on each player's team today (MLB Stats API).")
            if choice != "Everyone who played":
                everyone = pd.concat([batting["player_id"], pitching["player_id"]]).dropna().astype(int).unique()
                with st.spinner("Checking where players are today…"):
                    bios = bio.get_bios(everyone, with_roster=False)
                unknown = int(bios["current_level"].eq("Unknown").sum())
                if unknown > len(bios) * .3:
                    st.warning("Could not reach the MLB Stats API. Players are not filtered.")
                else:
                    picked = ()
                    if choice.startswith("Pick"):
                        picked = st.multiselect("Current level", [x for x in bio.LEVEL_ORDER if x != "Unknown"], default=[here], key="scope_pool_levels")
                    mode = "same" if choice.startswith("Still") else "up" if choice.startswith("Moved") else "pick"
                    keep = bio.pool_ids(bios, mode, here, picked)
                    batting, pitching = batting[batting["player_id"].isin(keep)], pitching[pitching["player_id"].isin(keep)]
                    pool = {"same": choice, "up": f"Moved above {here}", "pick": "Now at " + (", ".join(picked) or "no level")}[mode]
                    if unknown:
                        st.caption(f"{unknown} player(s) not found in the MLB Stats API were left out.")
            dates = pd.concat([batting["game_date"], pitching["game_date"]]).dropna()
            if dates.empty:
                st.info("No games match these filters.")
                st.stop()
            start, end = dates.min().date(), dates.max().date()
            with st.expander("Exact dates", expanded=False):
                selected = st.date_input("Game dates", (start, end), min_value=start, max_value=end,
                                         key=f"dates_{source}_{location}_{lo}_{hi}_{level}_{lid}",
                                         help="Defaults to every game in the chosen seasons.")
                if isinstance(selected, tuple) and len(selected) == 2:
                    start, end = selected
                else:
                    st.caption("Pick an end date.")
            st.caption("All pages use these filters. League averages and peers come from this group.")
    def within(df):
        if df.empty:
            return df
        return df[df["game_date"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()
    return Context(within(batting), within(pitching), (int(lo), int(hi)), level, names[lid], int(lid), source, location, start, end, revision, pool)


def context_note(ctx):
    items = [("Seasons", ctx.period), ("Level", LEVEL_LABEL.get(ctx.level, ctx.level)), ("League", ctx.league),
             ("Dates", f"{ctx.start:%d %b %Y} – {ctx.end:%d %b %Y}")]
    if ctx.pool != "Everyone who played":
        items.append(("Players", ctx.pool))
    scope_bar(items)
    if ctx.source == "Included sample":
        coverage("Sample data: a handful of real games, not a full season.")
    if ctx.multi_season:
        st.caption("Several seasons selected. League averages and peers pool all of them.")
