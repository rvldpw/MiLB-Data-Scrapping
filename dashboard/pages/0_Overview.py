import pandas as pd
import streamlit as st

from dashboard.assets import player_photo_url, team_logo_url
from dashboard.context import context_note
from dashboard import charts
from dashboard.metrics import player_table, line_for, game_results
from dashboard.ui import hero, section, stat_cards, brief, chart, fmt, download_button

ctx = st.session_state["_context"]
hero("League intelligence", "Your league. In focus.", "Find performances worth a closer look, then dig into the evidence.")
context_note(ctx)
both = pd.concat([ctx.batting, ctx.pitching], ignore_index=True)
stat_cards([
    {"label": "Games on file", "value": f"{both['game_pk'].nunique():,}", "sub": "Unique games, not player rows"},
    {"label": "Players observed", "value": f"{both['player_id'].nunique():,}", "sub": "Batting and pitching appearances"},
    {"label": "Teams represented", "value": f"{both['team_id'].nunique():,}", "sub": ctx.league},
    {"label": "Latest game", "value": ctx.end.strftime("%d %b"), "sub": f"{ctx.season} · {ctx.level}"},
])
mode = st.segmented_control("Explore the league", ["Batting", "Pitching"], default="Batting", key="overview_kind")
kind = "pitching" if mode == "Pitching" else "batting"
src = ctx.batting if kind == "batting" else ctx.pitching
if src.empty:
    st.info("No appearances in this group for the selected dates. Choose another group or date range.")
    st.stop()
players = player_table(src, kind)
sample_key = "PA" if kind == "batting" else "IP"
minimum = st.number_input("Minimum plate appearances" if kind == "batting" else "Minimum innings",
                          min_value=0, value=0 if ctx.source == "Included sample" else 100 if kind == "batting" else 20,
                          step=5, key=f"overview_min_{kind}", help="An exploration threshold, not an official qualification rule.")
qualified = players[players[sample_key].ge(minimum)].copy()
left, right = st.columns([1.65, 1], gap="large")
with left:
    section("", "The performance landscape", "Each dot is a player. Larger dots mean more opportunities. Dashed lines mark player medians.")
    if qualified.empty:
        st.info("No players meet this minimum yet. Lower it to explore the available sample.")
    else:
        chart(charts.scatter_field(qualified, kind), "overview_landscape")
        st.caption("Look toward the upper left: more power with fewer strikeouts." if kind == "batting" else "Look toward the upper left: more strikeouts with fewer walks.")
with right:
    section("", "Put the numbers in context", ctx.description)
    pooled = line_for(src, kind)
    if kind == "batting":
        brief("Reaching base", f"The loaded cohort has an on-base percentage of {fmt(pooled['OBP'], 'OBP')}. Compare players within this league and date range before comparing across levels.")
        brief("Power and contact", "The chart separates extra-base production from strikeouts. A high-power result with only a few at-bats is a reason to watch, not a finished scouting grade.")
    else:
        brief("Strikeouts and walks", f"The loaded cohort strikes out {fmt(pooled['K_pct'], 'K_pct')} of batters and walks {fmt(pooled['BB_pct'], 'BB_pct')}. Compare the two together; ERA alone leaves out part of the story.")
        brief("Results versus process", "A low ERA can coexist with walks or low strikeouts. Use the player lab to inspect outings, workload and recent direction.")
    if st.button("Explore a player", type="primary", width="stretch"):
        st.session_state["player_kind"] = "Batting" if kind == "batting" else "Pitching"
        st.switch_page("pages/1_Player_Dashboard.py")

section("", "The shortlist starts here", "Sortable results from the loaded games — not prospect grades or projections.")
metric_options = ["OPS", "OBP", "ISO", "HR", "BB_pct", "K_pct"] if kind == "batting" else ["ERA", "WHIP", "K_BB_pct", "K9", "BB9"]
sort_key = st.selectbox("Order by", metric_options, key=f"overview_sort_{kind}")
ascending = sort_key in ("ERA", "WHIP", "BB9") or (sort_key == "K_pct" and kind == "batting")
ranked = qualified.sort_values(sort_key, ascending=ascending, na_position="last")
cols = ["player_id", "team_id", "Player", "Team", "G", "PA", "AVG", "OBP", "SLG", "OPS", "HR", "BB_pct", "K_pct"] if kind == "batting" else ["player_id", "team_id", "Player", "Team", "G", "IP", "ERA", "WHIP", "K9", "BB9", "K_BB_pct"]
display = ranked.reindex(columns=cols).copy()
display.insert(0, "Photo", display["player_id"].map(player_photo_url))
display.insert(3, "Logo", display["team_id"].map(team_logo_url))
for key in display.columns:
    if key not in ("Player", "Team", "Photo", "Logo", "player_id", "team_id"):
        display[key] = display[key].map(lambda v, k=key: fmt(v, k))
display = display.rename(columns={"K_pct": "K%", "BB_pct": "BB%", "K_BB_pct": "K−BB%"})
shown_cols = [c for c in display.columns if c not in ("player_id", "team_id")]
st.dataframe(display.head(50), hide_index=True, width="stretch", height=350, column_order=shown_cols,
             column_config={"Photo": st.column_config.ImageColumn(""), "Logo": st.column_config.ImageColumn("")})
download_button(ranked, f"{ctx.season}_{ctx.league_id}_{kind}_leaderboard.csv", "Download full leaderboard", "overview_export")

with st.expander("What is included in this snapshot?"):
    st.write("Every view uses downloaded completed games. A team or player may have additional games that are not yet in this dataset.")
    st.write(f"Source: {ctx.location}. Batting rows: {len(ctx.batting):,}. Pitching rows: {len(ctx.pitching):,}.")
    st.write("Use the Metric guide for formulas, missing-data coverage, and the difference between a recorded statistic and an estimate.")
