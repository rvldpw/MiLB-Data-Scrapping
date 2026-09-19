import pandas as pd
import streamlit as st

from dashboard import bio
from dashboard.assets import player_photo_url, team_logo_url
from dashboard.context import context_note
from dashboard import charts
from dashboard.glossary import label
from dashboard.metrics import player_table, line_for, team_table
from dashboard.ui import plain, hero, section, stat_cards, chart, fmt, download_button, jump_to_player

ctx = st.session_state["_context"]
hero("Overview", "League leaders and averages, with where each player is now.")
context_note(ctx)
both = pd.concat([ctx.batting, ctx.pitching], ignore_index=True)
pick, floor_col, _ = st.columns([1, 1, 2], gap="medium", vertical_alignment="bottom")
with pick:
    mode = st.segmented_control("Show", ["Batting", "Pitching"], default="Batting", key="overview_kind")
kind = "pitching" if mode == "Pitching" else "batting"
src = ctx.batting if kind == "batting" else ctx.pitching
if src.empty:
    st.info("No appearances in this group for these dates.")
    st.stop()
players = player_table(src, kind)
sample_key = "PA" if kind == "batting" else "IP"
with floor_col:
    minimum = st.number_input("Min. plate appearances" if kind == "batting" else "Min. innings",
                              min_value=0, value=0 if ctx.source == "Included sample" else 100 if kind == "batting" else 20,
                              step=5, key=f"overview_min_{kind}", help="Hides small samples. Not an official qualifying rule.")
pooled = line_for(src, kind)
stat_cards([
    {"label": "Games", "value": f"{both['game_pk'].nunique():,}", "sub": "Unique games on file"},
    {"label": "Players", "value": f"{src['player_id'].nunique():,}", "sub": "Batters" if kind == "batting" else "Pitchers"},
    {"label": "Teams", "value": f"{src['team_id'].nunique():,}", "sub": ctx.league},
    {"label": "League overall hitting" if kind == "batting" else "League runs per 9", "value": fmt(pooled["OPS"] if kind == "batting" else pooled["ERA"], "OPS" if kind == "batting" else "ERA"),
     "sub": "On-base % plus slugging %" if kind == "batting" else "Runs allowed per 9 innings"},
])
qualified = players[players[sample_key].ge(minimum)].copy()
unit = "plate appearances" if kind == "batting" else "innings"
if qualified.empty and not players.empty:
    st.warning(f"No player reaches {minimum:,} {unit} in this selection. The most by anyone is "
               f"{fmt(players[sample_key].max(), sample_key)}, so lower the minimum above to see them.")
left, right = st.columns([1.65, 1], gap="large")
with left:
    section("Power vs. strikeouts" if kind == "batting" else "Strikeouts vs. walks", "One dot per player. Bigger dots have more playing time. Dotted lines are the medians.")
    if not qualified.empty:
        chart(charts.scatter_field(qualified, kind), "overview_landscape")
        st.caption("Upper left is best: more power, fewer strikeouts." if kind == "batting" else "Upper left is best: more strikeouts, fewer walks.")
with right:
    section("League averages", ctx.description)
    keys = ["AVG", "OBP", "SLG", "OPS", "BB_pct", "K_pct"] if kind == "batting" else ["ERA", "WHIP", "K9", "BB9", "K_pct", "BB_pct"]
    st.dataframe(pd.DataFrame({"Metric": [label(k) for k in keys], "League": [fmt(pooled[k], k) for k in keys]}), hide_index=True, width="stretch")

section("Player leaderboard", "Sorted from the games on file. \"Level now\" is where the player is today.")
metric_options = ["OPS", "OBP", "ISO", "HR", "BB_pct", "K_pct"] if kind == "batting" else ["ERA", "WHIP", "K_BB_pct", "K9", "BB9"]
order_col, size_col, _ = st.columns([1, 1, 2], gap="medium")
with order_col:
    sort_key = st.selectbox("Sort by", metric_options, format_func=label, key=f"overview_sort_{kind}")
with size_col:
    top = st.selectbox("Show", [25, 50, 100, 250], index=1, key=f"overview_top_{kind}", format_func=lambda n: f"Top {n}")
ascending = sort_key in ("ERA", "WHIP", "BB9") or (sort_key == "K_pct" and kind == "batting")
ranked = qualified.sort_values(sort_key, ascending=ascending, na_position="last")
cols = ["player_id", "team_id", "Player", "Team", "G", "PA", "AVG", "OBP", "SLG", "OPS", "HR", "BB_pct", "K_pct"] if kind == "batting" else ["player_id", "team_id", "Player", "Team", "G", "IP", "ERA", "WHIP", "K9", "BB9", "K_BB_pct"]
shown = ranked.reindex(columns=cols).head(top).copy()
now = bio.get_bios(shown["player_id"], with_roster=False).set_index("player_id")
for key in shown.columns:
    if key not in ("Player", "Team", "player_id", "team_id"):
        shown[key] = shown[key].map(lambda v, k=key: fmt(v, k))
shown.insert(0, "#", range(1, len(shown) + 1))
shown.insert(1, "Photo", shown["player_id"].map(player_photo_url))
shown.insert(4, "Logo", shown["team_id"].map(team_logo_url))
shown.insert(6, "Level now", shown["player_id"].map(now["current_level"]))
shown.insert(7, "Org today", shown["player_id"].map(now["current_org"]))
shown = plain(shown)
st.dataframe(shown, hide_index=True, width="stretch", height=460,
             column_order=[c for c in shown.columns if c not in ("player_id", "team_id")],
             column_config={"Photo": st.column_config.ImageColumn(""), "Logo": st.column_config.ImageColumn(""),
                            "#": st.column_config.NumberColumn(width="small")})
jump_to_player({int(r.player_id): f"{i}. {r.Player} · {r.Team}" for i, r in enumerate(shown.itertuples(), 1)},
               f"overview_jump_{kind}", kind, "Open one of these players")
download_button(ranked, f"{ctx.tag}_{ctx.league_id}_{kind}_leaderboard.csv", "Download full leaderboard", "overview_export")

section("Teams", "Every club in this league over the selected games.")
teams = team_table(ctx.batting, ctx.pitching)
if teams.empty:
    st.info("No team results in this selection.")
else:
    team_cols = ["Team", "Games", "W", "L", "W_pct", "RS", "RA", "Margin", "OPS", "ERA", "WHIP"]
    board = teams.sort_values("W_pct", ascending=False, na_position="last").reindex(columns=["team_id", *team_cols])
    for key in team_cols[1:]:
        board[key] = board[key].map(lambda v, k=key: fmt(v, k))
    board.insert(1, "Logo", board["team_id"].map(team_logo_url))
    board = board.rename(columns={"W_pct": "Win %", "RS": "Runs scored", "RA": "Runs allowed",
                                  "Margin": "Run difference", "RS": "Runs scored", "OPS": "Team hitting (OPS)", "ERA": "Staff runs per 9 (ERA)",
                                  "WHIP": "Baserunners per inning"})
    st.dataframe(board, hide_index=True, width="stretch",
                 column_order=[c for c in board.columns if c != "team_id"],
                 column_config={"Logo": st.column_config.ImageColumn("")})
    download_button(teams, f"{ctx.tag}_{ctx.league_id}_teams.csv", "Download team table", "overview_teams_export")

with st.expander("What is in this data"):
    st.write("Only games in this dataset are counted. A team or player may have played more.")
    st.write(f"Source: {ctx.location}. Batting rows: {len(ctx.batting):,}. Pitching rows: {len(ctx.pitching):,}.")
    st.write("New to this? The Analyst guide page explains which numbers to trust and how to read a player.")
