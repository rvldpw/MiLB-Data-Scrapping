import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import charts, bio, news
from dashboard.assets import player_photo_url, team_logo_html, team_logo_url
from dashboard.context import context_note
from dashboard.data_loader import POSITION_ORDER
from dashboard.metrics import line_for, enriched_line, player_table, game_results, split_table
from dashboard.ui import hero, identity, section, stat_cards, chart, brief, fmt, download_button, stat_sheet, news_list, ACCENT, BAD, MUTED, LINE

ctx = st.session_state["_context"]
hero("Team room", "See the roster as a whole.", "Connect the team's results with the players, positions and appearances behind them.")
context_note(ctx)
both = pd.concat([ctx.batting, ctx.pitching], ignore_index=True)
teams = dict(both[["team_id", "team_name"]].drop_duplicates("team_id").itertuples(index=False, name=None))
if not teams:
    st.info("No teams have games in this date range.")
    st.stop()
tid = st.selectbox("Choose a team", sorted(teams, key=teams.get), format_func=teams.get, key="team_pick")
bteam = ctx.batting[ctx.batting["team_id"].eq(tid)]
pteam = ctx.pitching[ctx.pitching["team_id"].eq(tid)]
games = game_results(bteam, pteam)
bc, pc = line_for(ctx.batting, "batting"), line_for(ctx.pitching, "pitching")
bl, pl = enriched_line(bteam, "batting", bc), enriched_line(pteam, "pitching", pc)
wins, losses, ties = (int(games["result"].eq(v).sum()) for v in ("W", "L", "T"))
margin = games["Margin"].sum(min_count=len(games))
identity(teams[tid], f"{ctx.description} · {len(games)} downloaded games", f"{wins}–{losses}", team_logo_html(tid, 72))
stat_cards([
    {"label": "Observed record", "value": f"{wins}–{losses}", "sub": f"{ties} ties · not the official season record"},
    {"label": "Run differential", "value": f"{margin:+.0f}" if pd.notna(margin) else "N/A", "sub": "Runs scored minus runs allowed"},
    {"label": "Team OPS", "value": fmt(bl['OPS'], 'OPS'), "sub": f"Loaded cohort {fmt(bc['OPS'],'OPS')}"},
    {"label": "Staff ERA", "value": fmt(pl['ERA'], 'ERA'), "sub": f"Loaded cohort {fmt(pc['ERA'],'ERA')}"},
])
tabs = st.tabs(["Team picture", "Roster", "Pitching staff", "Game results", "News", "All team metrics"])
with tabs[0]:
    a, b = st.columns([1.25, 1], gap="large")
    with a:
        section("", "Offense around the field", "OPS by recorded position. This measures batting production, not defensive quality or roster depth.")
        positions = []
        for pos in POSITION_ORDER:
            team_pos = bteam[bteam["pos_group"].eq(pos)] if not bteam.empty else bteam
            peer_pos = ctx.batting[ctx.batting["pos_group"].eq(pos)]
            team_line, peer_line = line_for(team_pos, "batting"), line_for(peer_pos, "batting")
            positions.append({"Position": pos, "PA": team_line["PA"], "OPS": team_line["OPS"], "Cohort OPS": peer_line["OPS"], "Gap": team_line["OPS"] - peer_line["OPS"]})
        positional = pd.DataFrame(positions)
        locations = {"C": (0, -13), "1B": (45, 40), "2B": (25, 82), "SS": (-25, 82), "3B": (-45, 40), "OF": (0, 125), "DH": (82, 10), "UT": (-82, 10)}
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[0, 48, 0, -48, 0], y=[0,48,96,48,0], fill="toself", fillcolor="#e7eee4", line=dict(color="#c7d8c8",width=2), mode="lines", hoverinfo="skip", showlegend=False))
        for _, row in positional.iterrows():
            x, y = locations[row["Position"]]
            color = ACCENT if pd.notna(row["Gap"]) and row["Gap"] >= 0 else BAD if pd.notna(row["Gap"]) else MUTED
            fig.add_trace(go.Scatter(x=[x],y=[y],mode="markers+text",marker=dict(size=56,color="#ffffff",line=dict(color=color,width=2)),
                                     text=[row["Position"]],textposition="middle center",textfont=dict(color=color,size=13), showlegend=False,
                                     hovertemplate=f"{row['Position']}<br>OPS {fmt(row['OPS'],'OPS')}<br>{fmt(row['PA'],'PA')} PA<br>Cohort OPS {fmt(row['Cohort OPS'],'OPS')}<extra></extra>"))
            fig.add_annotation(x=x,y=y-19,text=fmt(row["OPS"],"OPS"),showarrow=False,font=dict(size=12,color=color))
        charts.style(fig, 390)
        fig.update_xaxes(visible=False,range=[-120,120],fixedrange=True)
        fig.update_yaxes(visible=False,range=[-48,157],fixedrange=True)
        chart(fig,"team_field")
        st.caption("Green: at/above the position's cohort OPS. Rust: below. Gray: unavailable. Position is the box-score label, not innings spent defending there.")
    with b:
        section("", "Where to look next", "Start with evidence, then check the size and quality of the sample.")
        qualified = positional[positional["PA"].ge(50) & positional["Gap"].notna()]
        if qualified.empty:
            brief("More context before a roster verdict", "No position has 50 recorded plate appearances in this selection. The field view shows the results, but the sample does not support calling a position a strength or a roster need.")
        else:
            weakest = qualified.sort_values("Gap").iloc[0]
            brief(f"Review the {weakest['Position']} production", f"OPS is {fmt(weakest['OPS'],'OPS')} across {fmt(weakest['PA'],'PA')} PA, versus {fmt(weakest['Cohort OPS'],'OPS')} for the loaded position cohort. Check the players and matchups behind the gap.")
        brief("Keep run prevention separate", f"The staff has a {fmt(pl['ERA'],'ERA')} ERA and a {fmt(pl['K_BB_pct'],'K_BB_pct')} strikeout-minus-walk rate. Use the staff tab to separate starting and relief appearances.")
        brief("Use the roster as an index", "Sort the roster by opportunities first. Open a player report to inspect the individual games before forming a conclusion.")
    st.dataframe(positional.rename(columns={"Gap":"OPS gap"}).round(3),hide_index=True,width="stretch")

with tabs[1]:
    section("", "Who contributed", "Players who appeared for this team in the selected games — not a verified current roster.")
    group = st.segmented_control("Roster group", ["Batters", "Pitchers"], default="Batters", key="team_roster_kind")
    kind = "pitching" if group == "Pitchers" else "batting"
    rows = player_table(pteam if kind == "pitching" else bteam, kind)
    search = st.text_input("Search roster", key="team_roster_search", placeholder="Player name")
    if rows.empty:
        st.info("No appearances in this group.")
    else:
        if search:
            rows = rows[rows["Player"].str.contains(search,case=False,regex=False)]
        status_key = f"roster_bio_{tid}_{kind}"
        bcol, _ = st.columns([2, 3])
        with bcol:
            if st.button(f"Check live status for these {len(rows)} players", key=f"roster_status_{tid}_{kind}"):
                with st.spinner("Checking the MLB player record for each roster spot…"):
                    st.session_state[status_key] = bio.get_bios(rows["player_id"].tolist())
        cols = ["player_id","Player","Position","G","PA","AVG","OBP","SLG","OPS","HR","BB_pct","K_pct"] if kind == "batting" else ["player_id","Player","Role","G","GS","IP","ERA","WHIP","K9","BB9","K_BB_pct"]
        shown=rows.reindex(columns=cols).copy()
        shown.insert(0, "Photo", shown["player_id"].map(player_photo_url))
        if status_key in st.session_state:
            statuses = st.session_state[status_key][["player_id", "age", "status"]].rename(columns={"age": "Age", "status": "Status"})
            shown = shown.merge(statuses, on="player_id", how="left")
        for key in shown:
            if key not in ("Player","Position","Role","Photo","player_id","Status"):
                shown[key]=shown[key].map(lambda v,k=key:fmt(v,k))
        shown_cols = [c for c in shown.columns if c != "player_id"]
        st.dataframe(shown,hide_index=True,width="stretch",height=400, column_order=shown_cols,
                     column_config={"Photo": st.column_config.ImageColumn("")})
        st.caption("Status is a live MLB Stats API lookup (Active – MLB, Active – MiLB / still developing, Injured List, Free agent / released, Retired) — separate from the game logs above.")
        download_button(rows,f"team_{tid}_{kind}_roster.csv","Download roster metrics","team_roster_export")

with tabs[2]:
    section("", "Starting and relief appearances", "Roles describe the individual appearance. A pitcher can contribute to both groups.")
    if pteam.empty:
        st.info("No pitching appearances are available.")
    else:
        roles=split_table(pteam,"pitching","role")
        chart(charts.split_bars(roles,"ERA"),"staff_roles")
        shown=roles[["Split","G","GS","IP","ERA","WHIP","K9","BB9","K_BB_pct"]].copy()
        shown["IP"]=shown["IP"].map(lambda v:fmt(v,"IP"))
        st.dataframe(shown,hide_index=True,width="stretch")
        brief("A workload question", "Review pitches and innings alongside the role. Box-score workload is descriptive; it cannot diagnose fatigue or establish a safe pitching limit.")

with tabs[3]:
    section("", "One result per team game", "Scores are deduplicated so a game is never counted once per player.")
    fig=go.Figure(go.Bar(x=games["game_date"].dt.strftime("%d %b")+" · "+games["game_pk"].astype(str), y=games["Margin"],
                        marker_color=[ACCENT if x>=0 else BAD for x in games["Margin"].fillna(0)],
                        hovertemplate="%{x}<br>Run differential: %{y:+}<extra></extra>"))
    fig.add_hline(y=0,line_color=MUTED)
    fig.update_yaxes(title="Runs scored − runs allowed")
    chart(charts.style(fig,330),"team_results")
    st.dataframe(games,hide_index=True,width="stretch")
    download_button(games,f"team_{tid}_results.csv","Download game results","team_results_export")

with tabs[4]:
    section("", "Recent coverage", f"News search for \"{teams[tid]}\", via Google News — indexes ESPN, SB Nation, MiLB.com and local beat writers, not one site.")
    if st.button("Load recent news", key=f"team_news_{tid}"):
        with st.spinner("Searching for recent coverage…"):
            st.session_state[f"team_news_result_{tid}"] = news.fetch_news(f"{teams[tid]} baseball")
    if f"team_news_result_{tid}" in st.session_state:
        news_list(st.session_state[f"team_news_result_{tid}"])
    else:
        st.caption("Not loaded yet — click above.")

with tabs[5]:
    for title, line, context, kind in (("Batting",bl,bc,"batting"),("Pitching",pl,pc,"pitching")):
        section("",title,"Rates use aggregate counts; unavailable fields remain visible.")
        sheet=stat_sheet(line,context,kind)
        st.dataframe(sheet,hide_index=True,width="stretch",height=330)
        download_button(sheet,f"team_{tid}_{kind}_metrics.csv",f"Download {kind} metric sheet",f"team_all_{kind}")
