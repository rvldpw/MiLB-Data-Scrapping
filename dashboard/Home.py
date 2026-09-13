import pandas as pd
import streamlit as st

from data_loader import LEVEL_LABEL, load_data
from metrics import batting_line, fip, league_batting_context, league_pitching_context, pitching_line, wrc_plus
from ui import inject_mobile_css

st.set_page_config(page_title="MiLB Analyst Hub", page_icon="⚾", layout="wide", initial_sidebar_state="expanded")
inject_mobile_css()

st.title("⚾ MiLB Analyst Hub")
st.caption(
    "A scouting-department-style read on the MiLB game-log dataset — player development, "
    "team roster strength, and where a club's biggest positional or rotation gaps sit. "
    "Use the arrow at the top of the sidebar to collapse it on a small screen."
)

with st.spinner("Loading dataset..."):
    batting, pitching = load_data()

st.sidebar.header("Filters")
level = st.sidebar.selectbox("Level (league snapshot below)", ["AA", "A+", "A"], key="home_level")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Seasons covered", f"{batting['season'].min()}–{batting['season'].max()}")
c2.metric("Player-games (batting)", f"{len(batting):,}")
c3.metric("Player-games (pitching)", f"{len(pitching):,}")
c4.metric("Unique players", f"{pd.concat([batting['player_id'], pitching['player_id']]).nunique():,}")
c5.metric("Unique teams", f"{pd.concat([batting['team_id'], pitching['team_id']]).nunique():,}")

st.divider()
st.subheader("What's in here")
left, right = st.columns(2)
with left:
    st.page_link("pages/1_Player_Dashboard.py", label="Open the Player Analyst Dashboard", icon="🧢")
    st.markdown(
        "- Full slash line + **wOBA, wRC+/OPS+, ISO, BABIP, BB%/K%** for hitters\n"
        "- **ERA, FIP, WHIP, K-BB%** and strike-throwing rates for pitchers\n"
        "- Rolling-window form, month splits, home/away splits, and season-over-season growth\n"
        "- A live **MLB status badge** — active in the majors, back in MiLB, hurt, released, retired\n"
        "- Filter the whole player pool by level, team, position, age, and status before you search"
    )
with right:
    st.page_link("pages/2_Team_Dashboard.py", label="Open the Team Analyst Dashboard", icon="🏟️")
    st.markdown(
        "- Team record, run environment, and roster-wide offense/pitching lines\n"
        "- **Positional need finder** — every spot on the field vs. the league average at that level\n"
        "- Rotation vs. bullpen strength, with the specific players driving each number\n"
        "- Roster tables filterable by position, age, and live MLB/MiLB status"
    )

st.divider()
st.subheader(f"League snapshot — most recent season on file, {LEVEL_LABEL.get(level, level)}")
latest_season = int(batting["season"].max())
bsub = batting[(batting["season"] == latest_season) & (batting["team_level"] == level)]
psub = pitching[(pitching["season"] == latest_season) & (pitching["team_level"] == level)]

colA, colB = st.columns(2)
with colA:
    st.markdown(f"**Top wRC+ hitters — {latest_season} {LEVEL_LABEL.get(level, level)}** (min 150 PA)")
    lg_ctx = league_batting_context(bsub).iloc[0].to_dict() if len(bsub) else {}
    rows = []
    for pid, sub in bsub.groupby("player_id"):
        line = batting_line(sub)
        if not line["PA"] or line["PA"] < 150:
            continue
        rows.append(dict(
            Player=sub["player_full_name"].iloc[-1], Team=sub["team_name"].iloc[-1],
            PA=int(line["PA"]), AVG=round(line["AVG"], 3), OPS=round(line["OPS"], 3),
            **{"wRC+": wrc_plus(line, lg_ctx)},
        ))
    if rows:
        top_bat = pd.DataFrame(rows).sort_values("wRC+", ascending=False).head(10)
        st.dataframe(top_bat, hide_index=True, use_container_width=True)
    else:
        st.info("No hitters clear the 150 PA minimum for this season/level yet.")

with colB:
    st.markdown(f"**Best FIP pitchers — {latest_season} {LEVEL_LABEL.get(level, level)}** (min 30 IP)")
    lg_pctx = league_pitching_context(psub).iloc[0].to_dict() if len(psub) else {}
    rows = []
    for pid, sub in psub.groupby("player_id"):
        line = pitching_line(sub)
        if not line["IP"] or line["IP"] < 30:
            continue
        rows.append(dict(
            Player=sub["player_full_name"].iloc[-1], Team=sub["team_name"].iloc[-1],
            IP=round(line["IP"], 1), ERA=round(line["ERA"], 2) if pd.notna(line["ERA"]) else None,
            FIP=fip(line, lg_pctx), **{"K-BB%": round(100 * (line["K_pct"] - line["BB_pct"]), 1)},
        ))
    if rows:
        top_pit = pd.DataFrame(rows).sort_values("FIP").head(10)
        st.dataframe(top_pit, hide_index=True, use_container_width=True)
    else:
        st.info("No pitchers clear the 30 IP minimum for this season/level yet.")

st.caption(
    "Data: [rvlpw/milb-game-logs](https://huggingface.co/datasets/rvlpw/milb-game-logs) via the MLB Stats API. "
    "wOBA/wRC+/FIP use standard linear-weight formulas, benchmarked against this dataset's own season+level "
    "averages rather than imported MLB constants. Player status badges on the other two pages come from a live "
    "lookup against the MLB Stats API (cached locally so it isn't refetched every run)."
)
