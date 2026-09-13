import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from assets import team_logo_html
from data_loader import LEVEL_LABEL, POSITION_ORDER, load_data
from metrics import (batting_line, fip, league_batting_context, league_pitching_context,
                      ops_plus, pitching_line, power_rating, simulate_trade, wrc_plus)
from ui import BAD, GOOD, hero, inject_mobile_css, section, stat_cards

st.set_page_config(page_title="Trade Simulator", page_icon="🔁", layout="wide", initial_sidebar_state="expanded")
inject_mobile_css()
hero("🔁", "Trade Simulator",
     "Swap real players between two rosters and see the impact instantly — offense, pitching, and "
     "positional needs, before vs. after. Uses each player's actual games this season, so it's asking "
     "'what if this production had belonged to the other roster', not projecting anything new.")

batting, pitching = load_data()

# --- sidebar: season/level + the two clubs -----------------------------------
st.sidebar.header("Set up the trade")
season = st.sidebar.selectbox("Season", sorted(batting["season"].unique(), reverse=True))
level = st.sidebar.selectbox("Level", ["AA", "A+", "A"], format_func=lambda x: f"{x} — {LEVEL_LABEL.get(x, x)}")
bpool = batting[(batting["season"] == season) & (batting["team_level"] == level)].copy()
ppool = pitching[(pitching["season"] == season) & (pitching["team_level"] == level)].copy()
team_names = sorted(bpool["team_name"].unique())
if len(team_names) < 2:
    st.warning("Not enough teams at that season/level to run a trade.")
    st.stop()

team_a = st.sidebar.selectbox("Team A", team_names, index=0)
team_b = st.sidebar.selectbox("Team B", [t for t in team_names if t != team_a], index=0)


def roster_options(team):
    opts = {}
    bt = bpool[bpool["team_name"] == team]
    for pid, sub in bt.groupby("player_id"):
        line = batting_line(sub)
        label = f"{sub['player_full_name'].iloc[-1]} — {sub['player_position'].iloc[-1]} ({int(line['PA'])} PA)"
        opts[label] = pid
    pt = ppool[ppool["team_name"] == team]
    for pid, sub in pt.groupby("player_id"):
        line = pitching_line(sub)
        label = f"{sub['player_full_name'].iloc[-1]} — P ({line['IP']:.1f} IP)"
        opts[label] = pid
    return dict(sorted(opts.items()))


opts_a = roster_options(team_a)
opts_b = roster_options(team_b)

st.sidebar.markdown(f"**{team_a} sends away:**")
a_send_labels = st.sidebar.multiselect(" ", list(opts_a.keys()), key="a_send", label_visibility="collapsed")
st.sidebar.markdown(f"**{team_b} sends away:**")
b_send_labels = st.sidebar.multiselect(" ", list(opts_b.keys()), key="b_send", label_visibility="collapsed")

a_out = {opts_a[l] for l in a_send_labels}
b_out = {opts_b[l] for l in b_send_labels}
run = st.sidebar.button("⚡ Simulate trade", type="primary", use_container_width=True, disabled=not (a_out or b_out))

if not (a_out or b_out):
    st.info("Pick at least one player from either side in the sidebar, then hit **Simulate trade**.")
    st.stop()
if not run and "trade_ran" not in st.session_state:
    st.info("Players selected — click **Simulate trade** in the sidebar to see the impact.")
    st.stop()
if run:
    st.session_state["trade_ran"] = True

# --- run the simulation -------------------------------------------------
sim_b = simulate_trade(bpool, team_a, team_b, a_out, b_out)
sim_p = simulate_trade(ppool, team_a, team_b, a_out, b_out)

lg_bat = league_batting_context(bpool).iloc[0].to_dict()
lg_pit = league_pitching_context(ppool).iloc[0].to_dict()
lg_pos = league_batting_context(bpool, keys=("team_level", "pos_group"))


def team_snapshot(bcol, pcol, team):
    bl = batting_line(bpool[bpool[bcol] == team] if bcol == "team_name" else sim_b[sim_b[bcol] == team])
    pl = pitching_line(ppool[ppool[pcol] == team] if pcol == "team_name" else sim_p[sim_p[pcol] == team])
    wrc = wrc_plus(bl, lg_bat)
    ftr = fip(pl, lg_pit)
    return dict(bl=bl, pl=pl, wrc=wrc, fip=ftr, rating=power_rating(wrc, ftr))


def positional_lines(df, col, team):
    rows = []
    for pos in POSITION_ORDER:
        sub = df[(df[col] == team) & (df["pos_group"] == pos)]
        if sub.empty:
            continue
        line = batting_line(sub)
        lg_row = lg_pos[lg_pos["pos_group"] == pos]
        if lg_row.empty or not line["PA"]:
            continue
        rows.append(dict(Position=pos, **{"wRC+": wrc_plus(line, lg_row.iloc[0].to_dict())}))
    return pd.DataFrame(rows)


before_a = team_snapshot("team_name", "team_name", team_a)
after_a = team_snapshot("team_name_sim", "team_name_sim", team_a)
before_b = team_snapshot("team_name", "team_name", team_b)
after_b = team_snapshot("team_name_sim", "team_name_sim", team_b)

# --- headline: squad rating before/after --------------------------------
section("⚖️", "Trade impact — squad rating")
c1, c2 = st.columns(2)
for col, team, before, after, tid in [
    (c1, team_a, before_a, after_a, bpool[bpool["team_name"] == team_a]["team_id"].iloc[0]),
    (c2, team_b, before_b, after_b, bpool[bpool["team_name"] == team_b]["team_id"].iloc[0]),
]:
    with col:
        delta = (after["rating"] - before["rating"]) if pd.notna(after["rating"]) and pd.notna(before["rating"]) else np.nan
        color = GOOD if pd.notna(delta) and delta >= 0 else BAD
        st.markdown(
            f"<div class='player-card'>{team_logo_html(tid, 60)}<div>"
            f"<p class='player-name' style='font-size:1.15rem'>{team}</p>"
            f"<div class='player-meta'>Before <b>{before['rating']:.0f}</b> → After <b>{after['rating']:.0f}</b> "
            f"<span style='color:{color};font-weight:700'>({delta:+.1f})</span></div></div></div>"
            if pd.notna(before["rating"]) and pd.notna(after["rating"]) else "",
            unsafe_allow_html=True,
        )
        stat_cards([
            {"label": "wRC+", "value": f"{after['wrc']:.0f}" if pd.notna(after["wrc"]) else "—",
             "sub": f"was {before['wrc']:.0f}" if pd.notna(before["wrc"]) else None},
            {"label": "FIP", "value": f"{after['fip']:.2f}" if pd.notna(after["fip"]) else "—",
             "sub": f"was {before['fip']:.2f}" if pd.notna(before["fip"]) else None},
        ], cols=2)

st.divider()

# --- positional need before vs after -------------------------------------
section("🧭", "Positional wRC+ — before vs. after")
pc1, pc2 = st.columns(2)
for col, team in [(pc1, team_a), (pc2, team_b)]:
    with col:
        st.markdown(f"**{team}**")
        pb = positional_lines(bpool, "team_name", team)
        pa = positional_lines(sim_b, "team_name_sim", team)
        pb["When"], pa["When"] = "Before", "After"
        merged = pd.concat([pb, pa])
        if merged.empty:
            st.info("No positional data.")
            continue
        fig = px.bar(merged, x="Position", y="wRC+", color="When", barmode="group",
                     category_orders={"Position": POSITION_ORDER, "When": ["Before", "After"]},
                     color_discrete_sequence=["#8b96ad", "#f97316"])
        fig.add_hline(y=100, line_dash="dot", opacity=0.5)
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#e5e9f0", height=340)
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- the trade itself, laid out ------------------------------------------
section("📋", "The trade")
t1, t2, t3 = st.columns([5, 1, 5])
with t1:
    st.markdown(f"**{team_a} sends:**")
    if a_send_labels:
        for l in a_send_labels:
            st.markdown(f"<span class='chip'>{l.split(' — ')[0]}</span>", unsafe_allow_html=True)
    else:
        st.caption("Nothing")
with t2:
    st.markdown("<div class='vs-divider'>🔁</div>", unsafe_allow_html=True)
with t3:
    st.markdown(f"**{team_b} sends:**")
    if b_send_labels:
        for l in b_send_labels:
            st.markdown(f"<span class='chip'>{l.split(' — ')[0]}</span>", unsafe_allow_html=True)
    else:
        st.caption("Nothing")

st.caption(
    "Methodology: this replays each traded player's actual games this season as if they'd been on the new "
    "roster all along, then recomputes wRC+/FIP/Squad Rating from that combined line — it is not a projection "
    "of future performance, park/league adjustments are already baked into wRC+/FIP the same way they are "
    "elsewhere in this app, and it ignores roster/service-time rules a real front office would have to work around."
)
