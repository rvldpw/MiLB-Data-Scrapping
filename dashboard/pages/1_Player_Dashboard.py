import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import bio
from assets import player_photo_html, team_logo_html
from data_loader import LEVEL_LABEL, load_data
from metrics import (batting_line, fip, home_away_split, league_batting_context, league_pitching_context,
                      monthly_split, ops_plus, percentile_rank, pitching_line, radar_metrics, rolling_rate,
                      season_split, stat_sheet, wrc_plus)
from ui import inject_mobile_css

st.set_page_config(page_title="Player Analyst Dashboard", page_icon="🧢", layout="wide", initial_sidebar_state="expanded")
inject_mobile_css()
st.title("🧢 Player Analyst Dashboard")

batting, pitching = load_data()

# ============================= sidebar filters ==============================
st.sidebar.header("Filters")
mode = st.sidebar.radio("Player type", ["Hitter", "Pitcher"], horizontal=True)
src = batting if mode == "Hitter" else pitching
kind = "batting" if mode == "Hitter" else "pitching"

all_seasons = sorted(src["season"].unique())
sel_seasons = st.sidebar.multiselect("Season(s)", all_seasons, default=all_seasons)
sel_levels = st.sidebar.multiselect("Level", ["AA", "A+", "A"], default=["AA", "A+", "A"])

pool = src[src["season"].isin(sel_seasons) & src["team_level"].isin(sel_levels)]

team_options = ["All teams"] + sorted(pool["team_name"].unique())
sel_team = st.sidebar.selectbox("Team", team_options)
if sel_team != "All teams":
    pool = pool[pool["team_name"] == sel_team]

if kind == "batting":
    pos_options = [p for p in ["C", "1B", "2B", "3B", "SS", "OF", "DH", "UT"] if p in pool["pos_group"].unique()]
    sel_pos = st.sidebar.multiselect("Position", pos_options, default=pos_options)
    pool = pool[pool["pos_group"].isin(sel_pos)] if sel_pos else pool
else:
    sel_role = st.sidebar.multiselect("Role", ["SP", "RP"], default=["SP", "RP"])
    pool = pool[pool["role"].isin(sel_role)] if sel_role else pool

candidates = pool[["player_id", "player_full_name"]].drop_duplicates()

st.sidebar.caption(f"{len(candidates)} players match the filters above.")

bios_df = pd.DataFrame()
if 0 < len(candidates) <= 300:
    with st.sidebar:
        with st.spinner(f"Checking live MLB status for {len(candidates)} players..."):
            bios_df = bio.get_bios(candidates["player_id"].tolist())
    if not bios_df.empty:
        merged = candidates.merge(bios_df, on="player_id", how="left")
        age_vals = merged["age"].dropna()
        if len(age_vals):
            lo, hi = int(age_vals.min()), int(age_vals.max())
            if lo < hi:
                age_range = st.sidebar.slider("Age", lo, hi, (lo, hi))
                merged = merged[merged["age"].between(*age_range) | merged["age"].isna()]
        status_options = sorted(merged["status"].dropna().unique(), key=lambda s: bio.STATUS_ORDER.index(s) if s in bio.STATUS_ORDER else 99)
        if status_options:
            sel_status = st.sidebar.multiselect("MLB/MiLB status", status_options, default=status_options)
            merged = merged[merged["status"].isin(sel_status) | merged["status"].isna()]
        candidates = merged[["player_id", "player_full_name"]].drop_duplicates()
elif len(candidates) > 300:
    st.sidebar.info("Narrow the filters above (e.g. pick a team) to unlock age/status filtering.")

if candidates.empty:
    st.warning("No players match the current filters.")
    st.stop()

names = candidates.sort_values("player_full_name")["player_full_name"].tolist()
picked_name = st.sidebar.selectbox("Search player", names)
player_id = candidates[candidates["player_full_name"] == picked_name]["player_id"].iloc[0]

# ============================= player data ==============================
pdf_all = src[src["player_id"] == player_id].copy()
pdf = pdf_all[pdf_all["season"].isin(sel_seasons)]
if pdf.empty:
    pdf = pdf_all

latest_row = pdf.sort_values("game_date").iloc[-1]
level = latest_row["team_level"]
lg_ctx_df = (league_batting_context(batting[batting["team_level"] == level]) if kind == "batting"
             else league_pitching_context(pitching[pitching["team_level"] == level]))

player_bio = bio.get_bios([player_id]).iloc[0].to_dict() if True else {}

# --- header card -----------------------------------------------------------
head_l, head_r = st.columns([1, 4])
with head_l:
    st.markdown(player_photo_html(player_id, size=110), unsafe_allow_html=True)
with head_r:
    st.markdown(f"### {picked_name}")
    age_txt = f"Age **{int(player_bio['age'])}**" if pd.notna(player_bio.get("age")) else "Age —"
    status_html = bio.status_badge_html(player_bio.get("status", "Other / Unknown"))
    debut = player_bio.get("debut_date")
    debut_txt = f"MLB debut **{debut}**" if debut else "No MLB debut on record"
    st.markdown(
        f"{team_logo_html(latest_row['team_id'], 26)} **{latest_row['team_name']}** &nbsp;·&nbsp; "
        f"Position: **{latest_row['player_position']}** &nbsp;·&nbsp; Level: **{LEVEL_LABEL.get(level, level)}** "
        f"&nbsp;·&nbsp; {age_txt} &nbsp;·&nbsp; {status_html}",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"{debut_txt} &nbsp;·&nbsp; Seasons in this dataset: **{sorted(pdf_all['season'].unique())[0]}"
        f"–{sorted(pdf_all['season'].unique())[-1]}**"
        + (f" &nbsp;·&nbsp; Currently with **{player_bio['current_team']}**" if player_bio.get("current_team") else ""),
        unsafe_allow_html=True,
    )

st.divider()

# --- headline slash line / pitching line ------------------------------------
if kind == "batting":
    line = batting_line(pdf)
    lg_line = lg_ctx_df[lg_ctx_df["season"] == pdf["season"].max()]
    lg_line = (lg_line.iloc[0].to_dict() if len(lg_line) else lg_ctx_df.iloc[-1].to_dict())
    wrc = wrc_plus(line, lg_line)
    opsp = ops_plus(line, lg_line)

    m = st.columns(4)
    m[0].metric("G", int(line["G"]))
    m[1].metric("AVG / OBP / SLG", f"{line['AVG']:.3f}/{line['OBP']:.3f}/{line['SLG']:.3f}" if pd.notna(line["AVG"]) else "—")
    m[2].metric("OPS", f"{line['OPS']:.3f}" if pd.notna(line["OPS"]) else "—")
    m[3].metric("wRC+", f"{wrc:.0f}" if pd.notna(wrc) else "—", help="100 = league average at this level")
    m2 = st.columns(4)
    m2[0].metric("BB% / K%", f"{100*line['BB_pct']:.1f}% / {100*line['K_pct']:.1f}%")
    m2[1].metric("ISO / BABIP", f"{line['ISO']:.3f} / {line['BABIP']:.3f}" if pd.notna(line["ISO"]) else "—")
    m2[2].metric("OPS+", f"{opsp:.0f}" if pd.notna(opsp) else "—")
    m2[3].metric("HR / RBI / SB", f"{int(line['HR'])}/{int(line['RBI'])}/{int(line['SB'])}")
else:
    line = pitching_line(pdf)
    lg_line = lg_ctx_df[lg_ctx_df["season"] == pdf["season"].max()]
    lg_line = (lg_line.iloc[0].to_dict() if len(lg_line) else lg_ctx_df.iloc[-1].to_dict())
    fip_val = fip(line, lg_line)

    m = st.columns(4)
    m[0].metric("G (GS)", f"{int(line['G'])} ({int(line['GS'])})")
    m[1].metric("IP", f"{line['IP']:.1f}")
    m[2].metric("ERA / FIP", f"{line['ERA']:.2f} / {fip_val:.2f}" if pd.notna(line["ERA"]) else "—")
    m[3].metric("WHIP", f"{line['WHIP']:.2f}" if pd.notna(line["WHIP"]) else "—")
    m2 = st.columns(4)
    m2[0].metric("K/9 / BB/9", f"{line['K9']:.1f} / {line['BB9']:.1f}" if pd.notna(line["K9"]) else "—")
    m2[1].metric("K-BB%", f"{100*(line['K_pct']-line['BB_pct']):.1f}%")
    m2[2].metric("HR/9", f"{line['HR9']:.2f}" if pd.notna(line["HR9"]) else "—")
    m2[3].metric("W-L (SV)", f"{int(line['W'])}-{int(line['L'])} ({int(line['SV'])})")

st.caption(f"Rates benchmarked against the {int(lg_line.get('season', pdf['season'].max()))} {LEVEL_LABEL.get(level, level)} league average.")

st.divider()

# --- scouting radar + full stat sheet ---------------------------------------
r1, r2 = st.columns([1, 1])
with r1:
    st.subheader("🎯 Scouting radar")
    st.caption("Each axis is a percentile (0-100) vs. every player at this level in the selected season(s).")
    # Compute every candidate's line once (not once per axis) then derive all percentiles from it.
    pop_lines = []
    min_sample = "PA" if kind == "batting" else "IP"
    for pid, g in pool.groupby("player_id"):
        ln = batting_line(g) if kind == "batting" else pitching_line(g)
        pop_lines.append(ln)
    pop_df = pd.DataFrame(pop_lines)
    if not pop_df.empty:
        pop_df = pop_df[pop_df[min_sample] >= (10 if kind == "batting" else 3)]
    if kind == "pitching" and not pop_df.empty:
        pop_df["K_BB_pct"] = pop_df["K_pct"] - pop_df["BB_pct"]

    axes, vals = [], []
    for label, key, invert in radar_metrics(kind):
        col = "K_BB_pct" if key is None else key
        v = (line["K_pct"] - line["BB_pct"]) if key is None else line[key]
        pct = percentile_rank(pop_df[col], v) if not pop_df.empty and col in pop_df else np.nan
        pct = 100 - pct if invert and pd.notna(pct) else pct
        axes.append(label)
        vals.append(pct if pd.notna(pct) else 50)
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=vals + [vals[0]], theta=axes + [axes[0]], fill="toself", name=picked_name))
    fig.add_trace(go.Scatterpolar(r=[50] * (len(axes) + 1), theta=axes + [axes[0]], line=dict(dash="dot"), name="League avg"))
    fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100], visible=True)), showlegend=True,
                       margin=dict(l=30, r=30, t=20, b=20), height=380)
    st.plotly_chart(fig, use_container_width=True)

with r2:
    st.subheader("📋 Full stat sheet")
    st.dataframe(stat_sheet(line, lg_line, kind), hide_index=True, use_container_width=True, height=380)

st.divider()

# --- growth / trend section -------------------------------------------------
st.subheader("📈 Growth & form")
tab1, tab2, tab3, tab4 = st.tabs(["Rolling form", "Month by month", "Season over season", "Home vs. away"])

with tab1:
    window = st.slider("Trailing-game window", 5, 30, 15)
    roll = rolling_rate(pdf, kind, window)
    if roll.empty:
        st.info("Not enough games yet for a rolling window this wide.")
    else:
        fig = px.line(roll, x="game_date", y="value", title=roll["metric"].iloc[0])
        lg_val = lg_line["wOBA"] if kind == "batting" else lg_line["ERA"]
        fig.add_hline(y=lg_val, line_dash="dot", annotation_text="league avg", opacity=0.6)
        if kind == "pitching":
            fig.update_yaxes(autorange="reversed", title="ERA (lower is better)")
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    ms = monthly_split(pdf, kind)
    if kind == "batting":
        fig = px.bar(ms, x="month", y="wOBA", title="wOBA by month")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(
            ms[["month", "G", "PA", "AVG", "OBP", "SLG", "wOBA", "BB_pct", "K_pct"]]
            .round(3).rename(columns={"BB_pct": "BB%", "K_pct": "K%"}),
            hide_index=True, use_container_width=True,
        )
    else:
        fig = px.bar(ms, x="month", y="ERA", title="ERA by month")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(
            ms[["month", "G", "IP", "ERA", "WHIP", "K9", "BB9"]].round(2),
            hide_index=True, use_container_width=True,
        )

with tab3:
    ss = season_split(pdf_all, kind)  # full career on file, not just the season filter
    if len(ss) < 2:
        st.info("Only one season on file for this player — nothing to compare yet.")
    else:
        y = "wOBA" if kind == "batting" else "ERA"
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ss["season"], y=ss[y], mode="lines+markers", name=y))
        fig.update_layout(title=f"Career {y} trend across seasons on file", xaxis_title="Season", yaxis_title=y)
        if kind == "pitching":
            fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)
        cols = (["season", "G", "PA", "AVG", "OBP", "SLG", "wOBA", "ISO", "BB_pct", "K_pct"] if kind == "batting"
                else ["season", "G", "IP", "ERA", "WHIP", "K9", "BB9", "K_pct", "BB_pct"])
        st.dataframe(ss[cols].round(3), hide_index=True, use_container_width=True)

with tab4:
    ha = home_away_split(pdf, kind)
    if ha.empty:
        st.info("No home/away data for this selection.")
    else:
        y = "OPS" if kind == "batting" else "ERA"
        fig = px.bar(ha, x="split", y=y, color="split", title=f"{y}: home vs. away")
        st.plotly_chart(fig, use_container_width=True)
        cols = (["split", "G", "PA", "AVG", "OBP", "SLG", "OPS"] if kind == "batting"
                else ["split", "G", "IP", "ERA", "WHIP", "K9", "BB9"])
        st.dataframe(ha[cols].round(3), hide_index=True, use_container_width=True)

st.divider()

# --- per-game distribution, not just the average ----------------------------
st.subheader("📊 Per-game distribution")
st.caption("The averages above hide the spread — this is the actual game-to-game shape behind them.")
if kind == "batting":
    dist_metric = st.selectbox("Metric", ["Hits per game", "Total bases per game", "Strikeouts per game"])
    colmap = {"Hits per game": "batting_H", "Total bases per game": "batting_TB", "Strikeouts per game": "batting_SO"}
else:
    dist_metric = st.selectbox("Metric", ["Earned runs per outing", "Strikeouts per outing", "Walks per outing"])
    colmap = {"Earned runs per outing": "pitching_ER", "Strikeouts per outing": "pitching_SO", "Walks per outing": "pitching_BB"}
per_game = pdf.groupby("game_pk")[colmap[dist_metric]].sum()
if per_game.empty:
    st.info("No games to chart.")
else:
    fig = px.histogram(per_game, nbins=int(per_game.max()) + 2 if per_game.max() < 15 else 15, title=dist_metric)
    fig.add_vline(x=per_game.mean(), line_dash="dot", annotation_text=f"avg {per_game.mean():.2f}")
    fig.update_layout(showlegend=False, xaxis_title=dist_metric, yaxis_title="Games")
    st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Age and MLB/MiLB status come from a live MLB Stats API lookup on the player's real MLB ID, cached locally. "
    "wOBA/wRC+/FIP are centered on this dataset's own season+level averages — see the Home page for the full methodology note."
)
