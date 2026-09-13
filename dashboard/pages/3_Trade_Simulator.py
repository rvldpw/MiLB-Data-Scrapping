import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import charts
from dashboard.assets import team_logo_html
from dashboard.context import context_note
from dashboard.metrics import enriched_line, line_for, simulate_trade
from dashboard.ui import hero, section, brief, stat_cards, fmt, chart, download_button, ACCENT, BLUE, e

ctx=st.session_state["_context"]
hero("Roster scenarios", "Ask a better what-if.", "Move observed player production between two teams and see which numbers change.")
context_note(ctx)
brief("Historical replay, not a trade valuation", "This scenario reallocates recorded batting and pitching lines. It does not predict future wins, estimate player value, apply park factors, or evaluate contracts and roster rules.")
all_rows=pd.concat([ctx.batting,ctx.pitching],ignore_index=True)
teams=dict(all_rows[["team_id","team_name"]].drop_duplicates("team_id").itertuples(index=False,name=None))
if len(teams)<2:
    st.info("Choose a league and date range containing at least two teams.")
    st.stop()
a,b=st.columns(2,gap="large")
with a:
    team_a=st.selectbox("Team A",sorted(teams,key=teams.get),format_func=teams.get,key="scenario_a")
with b:
    team_b=st.selectbox("Team B",[t for t in sorted(teams,key=teams.get) if t!=team_a],format_func=teams.get,key="scenario_b")
def options(team):
    df=all_rows[all_rows["team_id"].eq(team)]
    players=df[["player_id","player_full_name"]].drop_duplicates("player_id")
    return dict(players.itertuples(index=False,name=None))
opta,optb=options(team_a),options(team_b)
with a:
    a_out=st.multiselect("Players Team A sends",sorted(opta,key=opta.get),format_func=lambda p:f"{opta[p]} · ID {p}",key=f"send_a_{team_a}_{team_b}")
with b:
    b_out=st.multiselect("Players Team B sends",sorted(optb,key=optb.get),format_func=lambda p:f"{optb[p]} · ID {p}",key=f"send_b_{team_a}_{team_b}")
if set(a_out)&set(b_out):
    st.error("The same player appears in both selected team histories. Choose a single direction for that player.")
    st.stop()
signature=json.dumps([ctx.description,str(ctx.start),str(ctx.end),ctx.revision,int(team_a),int(team_b),[int(p) for p in sorted(a_out)],[int(p) for p in sorted(b_out)]])
if st.button("Run roster scenario",type="primary",disabled=not(a_out or b_out)):
    st.session_state["scenario_ran"]=signature
if st.session_state.get("scenario_ran")!=signature:
    st.info("Select players and run the scenario. Changing the teams, players or data scope requires a new run.")
    st.stop()
sim_b=simulate_trade(ctx.batting,team_a,team_b,set(a_out),set(b_out))
sim_p=simulate_trade(ctx.pitching,team_a,team_b,set(a_out),set(b_out))
bc,pc=line_for(ctx.batting,"batting"),line_for(ctx.pitching,"pitching")
def snapshot(team,after):
    b=sim_b[sim_b["scenario_team_id"].eq(team)] if after else ctx.batting[ctx.batting["team_id"].eq(team)]
    p=sim_p[sim_p["scenario_team_id"].eq(team)] if after else ctx.pitching[ctx.pitching["team_id"].eq(team)]
    return enriched_line(b,"batting",bc),enriched_line(p,"pitching",pc)
section("","What changes","A before/after of aggregate production. Opportunity totals change too, so this is not equal-playing-time analysis.")
records=[]
for col,team in ((a,team_a),(b,team_b)):
    before_b,before_p=snapshot(team,False)
    after_b,after_p=snapshot(team,True)
    st.markdown(f"<h3 style='display:flex;align-items:center;gap:.6rem;margin-bottom:.3rem'>{team_logo_html(team, 36)}{e(teams[team])}</h3>", unsafe_allow_html=True)
    stat_cards([{"label":"OPS after","value":fmt(after_b["OPS"],"OPS"),"sub":f"Before {fmt(before_b['OPS'],'OPS')}"},
                {"label":"ERA after","value":fmt(after_p["ERA"],"ERA"),"sub":f"Before {fmt(before_p['ERA'],'ERA')}"},
                {"label":"PA moved into mix","value":fmt(after_b["PA"]-before_b["PA"],"PA"),"sub":"Net change in recorded opportunities"},
                {"label":"Innings after","value":fmt(after_p["IP"],"IP"),"sub":f"Before {fmt(before_p['IP'],'IP')}"}])
    for key in ("PA","AVG","OBP","SLG","OPS","HR","wRC_est"):
        records.append({"Team":teams[team],"Group":"Batting","Metric":key,"Before":before_b.get(key),"After":after_b.get(key)})
    for key in ("IP","ERA","WHIP","K9","BB9","K_BB_pct","FIP_est"):
        records.append({"Team":teams[team],"Group":"Pitching","Metric":key,"Before":before_p.get(key),"After":after_p.get(key)})
    chart(charts.compare_dots(before_b,after_b,["Before","After"],["AVG","OBP","SLG"]),f"scenario_chart_{team}")
results=pd.DataFrame(records)
results["Change"]=results["After"]-results["Before"]
shown=results.copy()
for column in ("Before","After"):
    shown[column]=shown.apply(lambda r:fmt(r[column],r["Metric"]),axis=1)
st.dataframe(shown,hide_index=True,width="stretch")
download_button(results,"roster_scenario.csv","Download before / after metrics","scenario_download")
st.caption("Two-way players move their selected-team batting and pitching production together. No observed team win/loss record is reassigned.")
