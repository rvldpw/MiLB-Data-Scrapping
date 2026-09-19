import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import charts, bio, news
from dashboard.assets import player_photo_url, team_logo_html
from dashboard.context import context_note
from dashboard.data_loader import POSITION_ORDER, LEVEL_LABEL
from dashboard.metrics import line_for, enriched_line, player_table, game_results, split_table
from dashboard.ui import plain, pretty, jump_to_player, hero, identity, section, stat_cards, league_delta, chart, brief, fmt, download_button, stat_sheet, news_list, ACCENT, BAD, MUTED

ctx = st.session_state["_context"]
hero("Team room", "Record, roster and pitching staff for one club.")
context_note(ctx)
both = pd.concat([ctx.batting, ctx.pitching], ignore_index=True)
teams = dict(both[["team_id", "team_name"]].drop_duplicates("team_id").itertuples(index=False, name=None))
if not teams:
    st.info("No games in this date range.")
    st.stop()
tid = st.selectbox("Choose a team", sorted(teams, key=teams.get), format_func=teams.get, key="team_pick")
bteam = ctx.batting[ctx.batting["team_id"].eq(tid)]
pteam = ctx.pitching[ctx.pitching["team_id"].eq(tid)]
games = game_results(bteam, pteam)
bc, pc = line_for(ctx.batting, "batting"), line_for(ctx.pitching, "pitching")
bl, pl = enriched_line(bteam, "batting", bc), enriched_line(pteam, "pitching", pc)
wins, losses, ties = (int(games["result"].eq(v).sum()) for v in ("W", "L", "T"))
margin = games["Margin"].sum(min_count=len(games))
identity(teams[tid], team_logo_html(tid, 84), [
    ("Level", f"{LEVEL_LABEL.get(ctx.level, ctx.level)} · {ctx.league}"), ("Seasons", ctx.period),
    ("Games on file", f"{len(games)}")])
stat_cards([
    {"label": "Record in this view", "value": f"{wins}–{losses}", "sub": f"{ties} ties · not the official season record"},
    {"label": "Runs scored minus allowed", "value": f"{margin:+.0f}" if pd.notna(margin) else "N/A",
     "delta": None if pd.isna(margin) else ("outscoring opponents" if margin > 0 else "outscored" if margin < 0 else "level",
                                            "good" if margin > 0 else "bad" if margin < 0 else None)},
    {"label": "Team hitting (OPS)", "value": fmt(bl['OPS'], 'OPS'), "delta": league_delta(bl.get('OPS'), bc.get('OPS'), 'OPS', 'batting'),
     "sub": f"League {fmt(bc['OPS'],'OPS')}"},
    {"label": "Staff runs per 9 (ERA)", "value": fmt(pl['ERA'], 'ERA'), "delta": league_delta(pl.get('ERA'), pc.get('ERA'), 'ERA', 'pitching'),
     "sub": f"League {fmt(pc['ERA'],'ERA')}"},
])
tabs = st.tabs(["Team picture", "Roster", "Pitching staff", "Game results", "News", "All team metrics"])
with tabs[0]:
    a, b = st.columns([1.25, 1], gap="large")
    with a:
        section("Offense by position", "OPS by listed position. This is hitting only, not defense.")
        positions = []
        for pos in POSITION_ORDER:
            team_pos = bteam[bteam["pos_group"].eq(pos)] if not bteam.empty else bteam
            peer_pos = ctx.batting[ctx.batting["pos_group"].eq(pos)]
            team_line, peer_line = line_for(team_pos, "batting"), line_for(peer_pos, "batting")
            positions.append({"Position": pos, "PA": team_line["PA"], "OPS": team_line["OPS"], "League OPS": peer_line["OPS"], "Gap": team_line["OPS"] - peer_line["OPS"]})
        positional = pd.DataFrame(positions)
        locations = {"C": (0, -13), "1B": (45, 40), "2B": (25, 82), "SS": (-25, 82), "3B": (-45, 40), "OF": (0, 125), "DH": (82, 10), "UT": (-82, 10)}
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[0, 48, 0, -48, 0], y=[0,48,96,48,0], fill="toself", fillcolor="#fbe3d0", line=dict(color="#f0bf9c",width=2), mode="lines", hoverinfo="skip", showlegend=False))
        for _, row in positional.iterrows():
            x, y = locations[row["Position"]]
            color = ACCENT if pd.notna(row["Gap"]) and row["Gap"] >= 0 else BAD if pd.notna(row["Gap"]) else MUTED
            fig.add_trace(go.Scatter(x=[x],y=[y],mode="markers+text",marker=dict(size=56,color="#ffffff",line=dict(color=color,width=2)),
                                     text=[row["Position"]],textposition="middle center",textfont=dict(color=color,size=13), showlegend=False,
                                     hovertemplate=f"{row['Position']}<br>OPS {fmt(row['OPS'],'OPS')}<br>{fmt(row['PA'],'PA')} PA<br>League OPS {fmt(row['League OPS'],'OPS')}<extra></extra>"))
            fig.add_annotation(x=x,y=y-26,text=fmt(row["OPS"],"OPS"),showarrow=False,font=dict(size=12,color=color))
        charts.style(fig, 390)
        fig.update_layout(plot_bgcolor="#d7eedd")
        fig.update_xaxes(visible=False,range=[-120,120],fixedrange=True)
        fig.update_yaxes(visible=False,range=[-48,157],fixedrange=True)
        chart(fig,"team_field")
        st.caption("Green: at or above the league OPS for that position. Orange: below. Grey: no data. Position is the box-score label.")
    with b:
        section("By position", "Team OPS against the league at each spot.")
        st.dataframe(pd.DataFrame({"Position": positional["Position"], "PA": positional["PA"].map(lambda v: fmt(v, "PA")), "OPS": positional["OPS"].map(lambda v: fmt(v, "OPS")),
                                   "League OPS": positional["League OPS"].map(lambda v: fmt(v, "OPS")),
                                   "Difference": positional["Gap"].map(lambda v: "N/A" if pd.isna(v) else f"{v:+.3f}")}),hide_index=True,width="stretch")

with tabs[1]:
    section("Roster", "Everyone who played for this club in the selected games. Level now shows where they are today.")
    group = st.segmented_control("Roster group", ["Batters", "Pitchers"], default="Batters", key="team_roster_kind")
    kind = "pitching" if group == "Pitchers" else "batting"
    rows = player_table(pteam if kind == "pitching" else bteam, kind)
    search = st.text_input("Search roster", key="team_roster_search", placeholder="Player name")
    if rows.empty:
        st.info("No appearances in this group.")
    else:
        if search:
            rows = rows[rows["Player"].str.contains(search,case=False,regex=False)]
        with st.spinner("Checking where these players are today…"):
            now = bio.get_bios(rows["player_id"].tolist(), with_roster=False).set_index("player_id")
        rows = rows.assign(Now=rows["player_id"].map(now["current_level"]), Org=rows["player_id"].map(now["current_org"]),
                           Age=rows["player_id"].map(now["age"]))
        present = [x for x in bio.LEVEL_ORDER if x in set(rows["Now"])]
        wanted = st.multiselect("Where they are today", present, default=present, key=f"team_roster_now_{tid}_{kind}",
                                help="Current level from the MLB Stats API. Remove a level to hide those players.")
        rows = rows[rows["Now"].isin(wanted)]
        cols = ["player_id","Player","Now","Org","Age","Position","G","PA","AVG","OBP","SLG","OPS","HR","BB_pct","K_pct"] if kind == "batting" else ["player_id","Player","Now","Org","Age","Role","G","GS","IP","ERA","WHIP","K9","BB9","K_BB_pct"]
        shown=rows.reindex(columns=cols).copy()
        shown.insert(0, "Photo", shown["player_id"].map(player_photo_url))
        for key in shown:
            if key not in ("Player","Position","Role","Photo","player_id","Now","Org"):
                shown[key]=shown[key].map(lambda v,k=key:fmt(v,k))
        shown = plain(shown).rename(columns={"Now": "Level now"})
        st.dataframe(shown, hide_index=True, width="stretch", height=400,
                     column_order=[c for c in shown.columns if c != "player_id"],
                     column_config={"Photo": st.column_config.ImageColumn("")})
        jump_to_player({int(p): n for p, n in zip(rows["player_id"], rows["Player"])},
                       f"team_jump_{tid}_{kind}", kind, "Open one of these players")
        st.caption("Level now is the level of the player's team today. \"Other league\" is independent, foreign or winter ball. \"No team\" means no club on file. It does not confirm a release or retirement.")
        download_button(rows,f"team_{tid}_{kind}_roster.csv","Download roster metrics","team_roster_export")

with tabs[2]:
    section("Starters vs. relievers", "Each appearance counts as a start or relief outing. One pitcher can be in both.")
    if pteam.empty:
        st.info("No pitching appearances.")
    else:
        roles=split_table(pteam,"pitching","role")
        chart(charts.split_bars(roles,"ERA"),"staff_roles")
        st.dataframe(pretty(roles[["Split","G","GS","IP","ERA","WHIP","K9","BB9","K_BB_pct"]]),hide_index=True,width="stretch")

with tabs[3]:
    section("Results", "One row per game.")
    ordered = games.sort_values(["game_date", "game_pk"]).reset_index(drop=True)
    fig=go.Figure(go.Bar(x=list(ordered.index), y=ordered["Margin"],
                        marker_color=[ACCENT if x>=0 else BAD for x in ordered["Margin"].fillna(0)],
                        customdata=ordered["game_date"].dt.strftime("%d %b %Y") + " · vs " + ordered["opponent_name"].fillna("?").astype(str),
                        hovertemplate="%{customdata}<br>Runs scored minus allowed: %{y:+}<extra></extra>"))
    fig.add_hline(y=0,line_color=MUTED)
    fig.update_yaxes(title="Runs scored − runs allowed")
    charts.date_axis(fig, ordered["game_date"])
    chart(charts.style(fig,330),"team_results")
    results_table = pd.DataFrame({"Date": ordered["game_date"].dt.strftime("%d %b %Y"), "Opponent": ordered["opponent_name"], "Result": ordered["result"],
                                  "Score": ordered["team_score"].astype("Int64").astype(str) + "–" + ordered["opponent_score"].astype("Int64").astype(str),
                                  "Margin": ordered["Margin"].map(lambda v: "N/A" if pd.isna(v) else f"{v:+.0f}"), "Game ID": ordered["game_pk"].astype(str)}).iloc[::-1]
    st.dataframe(results_table,hide_index=True,width="stretch",height=380)
    download_button(games,f"team_{tid}_results.csv","Download game results","team_results_export")

with tabs[4]:
    section("Recent coverage", f"News search for \"{teams[tid]}\", from Google News (ESPN, SB Nation, MiLB.com, local writers).")
    if st.button("Load recent news", key=f"team_news_{tid}"):
        with st.spinner("Searching for recent coverage…"):
            st.session_state[f"team_news_result_{tid}"] = news.fetch_news(f"{teams[tid]} baseball")
    if f"team_news_result_{tid}" in st.session_state:
        news_list(st.session_state[f"team_news_result_{tid}"])
    else:
        st.caption("Click the button to search.")

with tabs[5]:
    for title, line, context, kind in (("Batting",bl,bc,"batting"),("Pitching",pl,pc,"pitching")):
        section(title,"Rates come from summed counts. Fields with no data stay listed.")
        sheet=stat_sheet(line,context,kind)
        st.dataframe(sheet,hide_index=True,width="stretch",height=330)
        download_button(sheet,f"team_{tid}_{kind}_metrics.csv",f"Download {kind} metric sheet",f"team_all_{kind}")
