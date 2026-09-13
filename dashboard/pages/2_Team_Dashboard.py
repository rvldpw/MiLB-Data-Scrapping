import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

import bio
from assets import player_photo_html, team_logo_html
from data_loader import LEVEL_LABEL, POSITION_ORDER, load_data
from metrics import (batting_line, fip, league_batting_context, league_pitching_context,
                      ops_plus, pitching_line, stat_sheet, wrc_plus)
from ui import inject_mobile_css

st.set_page_config(page_title="Team Analyst Dashboard", page_icon="🏟️", layout="wide", initial_sidebar_state="expanded")
inject_mobile_css()
st.title("🏟️ Team Analyst Dashboard")

batting, pitching = load_data()

# --- sidebar: pick season / level / team --------------------------------------
st.sidebar.header("Filters")
season = st.sidebar.selectbox("Season", sorted(batting["season"].unique(), reverse=True))
level = st.sidebar.selectbox("Level", ["AA", "A+", "A"], format_func=lambda x: f"{x} — {LEVEL_LABEL.get(x, x)}")
bpool = batting[(batting["season"] == season) & (batting["team_level"] == level)]
ppool = pitching[(pitching["season"] == season) & (pitching["team_level"] == level)]
team_names = sorted(bpool["team_name"].unique())
if not team_names:
    st.warning("No teams at that season/level.")
    st.stop()
team_name = st.sidebar.selectbox("Team", team_names)

bteam = bpool[bpool["team_name"] == team_name]
pteam = ppool[ppool["team_name"] == team_name]
team_id = bteam["team_id"].iloc[0] if len(bteam) else pteam["team_id"].iloc[0]

# roster bios (small set - a team roster - so a threaded fetch is fast) -------
roster_ids = pd.concat([bteam["player_id"], pteam["player_id"]]).unique().tolist()
with st.sidebar:
    with st.spinner(f"Checking live status for {len(roster_ids)} roster players..."):
        roster_bios = bio.get_bios(roster_ids)

st.sidebar.subheader("Roster table filters")
status_opts = sorted(roster_bios["status"].dropna().unique(), key=lambda s: bio.STATUS_ORDER.index(s) if s in bio.STATUS_ORDER else 99) if not roster_bios.empty else []
sel_status = st.sidebar.multiselect("Status (roster tables below)", status_opts, default=status_opts) if status_opts else []
age_vals = roster_bios["age"].dropna() if not roster_bios.empty else pd.Series(dtype=float)
sel_age = None
if len(age_vals) and age_vals.min() < age_vals.max():
    sel_age = st.sidebar.slider("Age (roster tables below)", int(age_vals.min()), int(age_vals.max()),
                                 (int(age_vals.min()), int(age_vals.max())))


def _apply_roster_filters(ids):
    """Keep a player id unless bios data says it fails the sidebar status/age filters."""
    if roster_bios.empty:
        return ids
    b = roster_bios.set_index("player_id")
    out = []
    for pid in ids:
        row = b.loc[pid] if pid in b.index else None
        if row is None:
            out.append(pid); continue
        if sel_status and pd.notna(row.get("status")) and row["status"] not in sel_status:
            continue
        if sel_age and pd.notna(row.get("age")) and not (sel_age[0] <= row["age"] <= sel_age[1]):
            continue
        out.append(pid)
    return out


def _bio_cell(pid):
    if roster_bios.empty or pid not in roster_bios["player_id"].values:
        return "", ""
    row = roster_bios[roster_bios["player_id"] == pid].iloc[0]
    age_txt = f"{int(row['age'])}" if pd.notna(row["age"]) else "—"
    return age_txt, bio.status_badge_html(row.get("status", "Other / Unknown"))


# --- header + record ---------------------------------------------------------
games = pd.concat([bteam[["game_pk", "game_date", "win", "team_score", "opponent_score"]],
                    pteam[["game_pk", "game_date", "win", "team_score", "opponent_score"]]]).drop_duplicates("game_pk")
games = games.sort_values("game_date")
wins, losses = int(games["win"].sum()), int((games["win"] == 0).sum())

hc1, hc2 = st.columns([1, 5])
with hc1:
    st.markdown(team_logo_html(team_id, 90), unsafe_allow_html=True)
with hc2:
    st.markdown(f"### {team_name}")
    st.markdown(f"**{season} {LEVEL_LABEL.get(level, level)}** &nbsp;·&nbsp; Record: **{wins}-{losses}** "
                f"({100*wins/max(wins+losses,1):.1f}% win rate) &nbsp;·&nbsp; Games on file: **{len(games)}**")

if len(games) > 1:
    games["cum_win_pct"] = games["win"].expanding().mean()
    fig = px.line(games, x="game_date", y="cum_win_pct", title="Cumulative win% over the season")
    fig.add_hline(y=0.5, line_dash="dot", opacity=0.5)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- team offense / pitching summary ------------------------------------------
lg_bat_ctx = league_batting_context(bpool).iloc[0].to_dict()
lg_pit_ctx = league_pitching_context(ppool).iloc[0].to_dict()
team_bat_line = batting_line(bteam)
team_pit_line = pitching_line(pteam)
team_wrc = wrc_plus(team_bat_line, lg_bat_ctx)
team_ops_plus = ops_plus(team_bat_line, lg_bat_ctx)
team_fip = fip(team_pit_line, lg_pit_ctx)

oc, pc = st.columns(2)
with oc:
    st.subheader("Offense")
    m = st.columns(2)
    m[0].metric("Team AVG/OBP/SLG", f"{team_bat_line['AVG']:.3f}/{team_bat_line['OBP']:.3f}/{team_bat_line['SLG']:.3f}")
    m[1].metric("Team wRC+", f"{team_wrc:.0f}" if pd.notna(team_wrc) else "—",
                delta=f"{team_wrc-100:.0f} vs lg avg" if pd.notna(team_wrc) else None)
    m2 = st.columns(2)
    m2[0].metric("Team OPS+", f"{team_ops_plus:.0f}" if pd.notna(team_ops_plus) else "—")
    m2[1].metric("BB% / K%", f"{100*team_bat_line['BB_pct']:.1f}% / {100*team_bat_line['K_pct']:.1f}%")
    with st.expander("Full offense stat sheet"):
        st.dataframe(stat_sheet(team_bat_line, lg_bat_ctx, "batting"), hide_index=True, use_container_width=True)
with pc:
    st.subheader("Pitching")
    m = st.columns(2)
    m[0].metric("Team ERA", f"{team_pit_line['ERA']:.2f}" if pd.notna(team_pit_line["ERA"]) else "—")
    m[1].metric("Team FIP", f"{team_fip:.2f}" if pd.notna(team_fip) else "—",
                delta=f"{lg_pit_ctx['ERA']-team_fip:.2f} vs lg ERA" if pd.notna(team_fip) else None)
    m2 = st.columns(2)
    m2[0].metric("WHIP", f"{team_pit_line['WHIP']:.2f}" if pd.notna(team_pit_line["WHIP"]) else "—")
    m2[1].metric("K-BB%", f"{100*(team_pit_line['K_pct']-team_pit_line['BB_pct']):.1f}%")
    with st.expander("Full pitching stat sheet"):
        st.dataframe(stat_sheet(team_pit_line, lg_pit_ctx, "pitching"), hide_index=True, use_container_width=True)

st.divider()

# --- positional need finder --------------------------------------------------
st.subheader("🧭 Positional need finder")
st.caption(
    "Team wRC+ at each position, benchmarked against every other team at the same level and season. "
    "Bars below 100 are the roster's soft spots; pick one below to see exactly who is producing (or not)."
)

lg_pos_ctx = league_batting_context(bpool, keys=("team_level", "pos_group"))
pos_rows = []
for pos in POSITION_ORDER:
    sub = bteam[bteam["pos_group"] == pos]
    if sub.empty:
        continue
    line = batting_line(sub)
    lg_row = lg_pos_ctx[lg_pos_ctx["pos_group"] == pos]
    if lg_row.empty or not line["PA"]:
        continue
    wrc = wrc_plus(line, lg_row.iloc[0].to_dict())
    pos_rows.append(dict(Position=pos, PA=int(line["PA"]), **{"wRC+": wrc}))
pos_df = pd.DataFrame(pos_rows)

if pos_df.empty:
    st.info("Not enough plate appearances by position for this team yet.")
else:
    pos_df["Need"] = np.where(pos_df["wRC+"] < 90, "Needs improvement",
                        np.where(pos_df["wRC+"] < 100, "Below average", "Strength"))
    color_map = {"Needs improvement": "#ef4444", "Below average": "#f59e0b", "Strength": "#22c55e"}

    chart_col, pie_col = st.columns([2, 1])
    with chart_col:
        fig = px.bar(pos_df, x="Position", y="wRC+", color="Need", color_discrete_map=color_map,
                     category_orders={"Position": POSITION_ORDER}, text="wRC+")
        fig.add_hline(y=100, line_dash="dot", annotation_text="league avg (100)")
        fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    with pie_col:
        fig2 = px.pie(pos_df, names="Position", values="PA", title="Share of team PA by position", hole=0.4)
        st.plotly_chart(fig2, use_container_width=True)

    weak_spots = pos_df[pos_df["wRC+"] < 100].sort_values("wRC+")
    if weak_spots.empty:
        st.success("Every position is producing at or above league average — no clear hole on this roster.")
    else:
        pick = st.selectbox("See who's driving the number at a position", weak_spots["Position"].tolist())
        roster_at_pos = bteam[bteam["pos_group"] == pick]
        lg_row = lg_pos_ctx[lg_pos_ctx["pos_group"] == pick].iloc[0].to_dict()
        impact_rows = []
        for pid, sub in roster_at_pos.groupby("player_id"):
            if pid not in _apply_roster_filters([pid]):
                continue
            line = batting_line(sub)
            if not line["PA"]:
                continue
            age_txt, status_html = _bio_cell(pid)
            impact_rows.append(dict(
                player_id=pid, Player=sub["player_full_name"].iloc[-1], age=age_txt, status=status_html,
                PA=int(line["PA"]), AVG=round(line["AVG"], 3) if pd.notna(line["AVG"]) else None,
                OPS=round(line["OPS"], 3) if pd.notna(line["OPS"]) else None,
                wrc=wrc_plus(line, lg_row),
            ))
        impact_df = pd.DataFrame(impact_rows).sort_values("PA", ascending=False)
        if impact_df.empty:
            st.info("No players at this position pass the roster filters in the sidebar.")
        else:
            rows_html = "".join(
                f"<tr><td>{player_photo_html(r.player_id, 42)}</td><td>{r.Player}</td><td>{r.age}</td>"
                f"<td>{r.status}</td><td>{r.PA}</td><td>{r.AVG}</td><td>{r.OPS}</td>"
                f"<td style='color:{'#ef4444' if pd.notna(r.wrc) and r.wrc < 100 else '#22c55e'}'><b>"
                f"{r.wrc:.0f}</b></td></tr>"
                for r in impact_df.itertuples(index=False)
            )
            st.markdown(
                "<div class='scroll-table'><table><tr><th></th><th>Player</th><th>Age</th><th>Status</th>"
                f"<th>PA</th><th>AVG</th><th>OPS</th><th>wRC+</th></tr>{rows_html}</table></div>",
                unsafe_allow_html=True,
            )
        st.caption(f"Most-used player at {pick} carries the sample; a low wRC+ next to a high PA count is the real drag on the position.")

st.divider()

# --- rotation vs bullpen strength ---------------------------------------------
st.subheader("⚾ Rotation vs. bullpen strength")
st.caption("Starters and relievers benchmarked separately, since their run environments differ.")

role_rows = []
for role in ["SP", "RP"]:
    sub = pteam[pteam["role"] == role]
    if sub.empty:
        continue
    line = pitching_line(sub)
    lg_role = league_pitching_context(ppool[ppool["role"] == role])
    lg_role = lg_role.iloc[0].to_dict() if len(lg_role) else lg_pit_ctx
    role_rows.append(dict(Role="Rotation" if role == "SP" else "Bullpen", IP=round(line["IP"], 1),
                           ERA=round(line["ERA"], 2) if pd.notna(line["ERA"]) else None,
                           FIP=fip(line, lg_role), **{"lg avg FIP": round(lg_role.get("ERA", np.nan), 2)}))
role_df = pd.DataFrame(role_rows)
if not role_df.empty:
    st.dataframe(role_df, hide_index=True, use_container_width=True)

    # bubble chart: every arm on the staff, IP vs FIP, sized by appearances
    bubble_rows = []
    for role_code, role_label in [("SP", "Rotation"), ("RP", "Bullpen")]:
        sub_role = pteam[pteam["role"] == role_code]
        lg_role_ctx = league_pitching_context(ppool[ppool["role"] == role_code])
        lg_role_ctx = lg_role_ctx.iloc[0].to_dict() if len(lg_role_ctx) else lg_pit_ctx
        for pid, sub in sub_role.groupby("player_id"):
            ln = pitching_line(sub)
            if not ln["IP"]:
                continue
            bubble_rows.append(dict(Player=sub["player_full_name"].iloc[-1], Role=role_label,
                                     IP=ln["IP"], FIP=fip(ln, lg_role_ctx), G=ln["G"]))
    bubble_df = pd.DataFrame(bubble_rows)
    if not bubble_df.empty:
        fig = px.scatter(bubble_df, x="IP", y="FIP", size="G", color="Role", hover_name="Player",
                          title="Every arm on the staff — IP vs. FIP (bubble size = appearances)")
        fig.add_hline(y=lg_pit_ctx.get("ERA", np.nan), line_dash="dot", annotation_text="league avg FIP≈ERA")
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

    weak_role = role_df.sort_values("FIP", ascending=False).iloc[0]
    role_code = "SP" if weak_role["Role"] == "Rotation" else "RP"
    st.markdown(f"**{weak_role['Role']} is the softer half of the staff by FIP.** Individual arms below:")
    roster_role = pteam[pteam["role"] == role_code]
    lg_role_ctx = league_pitching_context(ppool[ppool["role"] == role_code])
    lg_role_ctx = lg_role_ctx.iloc[0].to_dict() if len(lg_role_ctx) else lg_pit_ctx
    prows = []
    for pid, sub in roster_role.groupby("player_id"):
        if pid not in _apply_roster_filters([pid]):
            continue
        line = pitching_line(sub)
        if not line["IP"]:
            continue
        age_txt, status_html = _bio_cell(pid)
        prows.append(dict(player_id=pid, Player=sub["player_full_name"].iloc[-1], age=age_txt, status=status_html,
                           IP=round(line["IP"], 1), ERA=round(line["ERA"], 2) if pd.notna(line["ERA"]) else None,
                           FIP=fip(line, lg_role_ctx), kbb=round(100*(line["K_pct"]-line["BB_pct"]), 1)))
    prows_df = pd.DataFrame(prows).sort_values("IP", ascending=False)
    if prows_df.empty:
        st.info("No pitchers in this role pass the roster filters in the sidebar.")
    else:
        rows_html = "".join(
            f"<tr><td>{player_photo_html(r.player_id, 42)}</td><td>{r.Player}</td><td>{r.age}</td>"
            f"<td>{r.status}</td><td>{r.IP}</td><td>{r.ERA}</td>"
            f"<td style='color:{'#ef4444' if pd.notna(r.FIP) and r.FIP > lg_role_ctx.get('ERA', 4) else '#22c55e'}'>"
            f"<b>{r.FIP}</b></td><td>{r.kbb}</td></tr>"
            for r in prows_df.itertuples(index=False)
        )
        st.markdown(
            "<div class='scroll-table'><table><tr><th></th><th>Player</th><th>Age</th><th>Status</th>"
            f"<th>IP</th><th>ERA</th><th>FIP</th><th>K-BB%</th></tr>{rows_html}</table></div>",
            unsafe_allow_html=True,
        )
else:
    st.info("No pitching innings logged for this team in the selection.")

st.caption("Age and status columns come from a live MLB Stats API lookup on each player's real MLB ID, cached locally.")
