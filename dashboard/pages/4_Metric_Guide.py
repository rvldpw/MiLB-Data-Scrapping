import pandas as pd
import streamlit as st

from dashboard.context import context_note
from dashboard.glossary import METRICS, keys_for, label, definition, direction
from dashboard.metric_catalog import RAW_FIELDS
from dashboard.metrics import line_for, enriched_line
from dashboard.ui import hero, section, brief, stat_cards, download_button

ctx=st.session_state["_context"]
hero("Metric guide", "Understand the number. Then use it.", "A plain-English field guide, the formulas behind the charts, and an honest account of what this dataset contains.")
context_note(ctx)
mode=st.segmented_control("Metric group",["Batting","Pitching"],default="Batting",key="guide_kind")
kind="pitching" if mode=="Pitching" else "batting"
src=ctx.batting if kind=="batting" else ctx.pitching
query=st.text_input("Search a metric or concept",placeholder="Try on-base, walks, ERA, whiffs…",key="guide_search")
rows=[]
for key in keys_for(kind):
    source_col=next((c for c in RAW_FIELDS[kind].values() if c.removeprefix(kind+"_")==key),None)
    rows.append({"Metric":label(key),"Code":key,"Meaning":definition(key,kind),
                 "Calculation":("Convert total outs to whole innings plus remaining outs (.1 or .2)." if key == "IP_str" else "Count unique game IDs." if key == "G" else METRICS[key][2] if key in METRICS else "Sum recorded game counts; incomplete counts stay unavailable."),
                 "Direction":direction(key,kind),"Source column":source_col or "Calculated from game counts"})
guide=pd.DataFrame(rows)
visible=guide[guide.astype(str).apply(lambda col:col.str.contains(query,case=False,regex=False)).any(axis=1)] if query else guide
st.dataframe(visible,hide_index=True,width="stretch",height=440)
download_button(guide,f"{kind}_metric_dictionary.csv","Download metric dictionary","guide_download")
section("","What is actually available?","An unavailable field remains visible. It is never a zero by default.")
coverage=[]
for source,col in RAW_FIELDS[kind].items():
    available=int(src[col].notna().sum()) if col in src else 0
    coverage.append({"Metric":label(col.removeprefix(kind+"_")),"Column":col,"Rows with a value":available,"Rows in selection":len(src),
                     "Coverage":available/len(src) if len(src) else 0,"Status":"Complete" if len(src) and available==len(src) else "Partial" if available else "Not supplied"})
coverage_df=pd.DataFrame(coverage)
stat_cards([{"label":"Original source metrics","value":len(coverage_df),"sub":"Every original column retained"},
            {"label":"Complete in this selection","value":int(coverage_df['Status'].eq('Complete').sum()),"sub":"Available in every loaded row"},
            {"label":"Missing or partial","value":int(coverage_df['Status'].ne('Complete').sum()),"sub":"Not enough data for a full total"}],cols=3)
st.dataframe(coverage_df,hide_index=True,width="stretch",height=330,column_config={"Coverage":st.column_config.ProgressColumn("Rows available",min_value=0,max_value=1,format="percent")})
download_button(coverage_df,f"{kind}_coverage.csv","Download availability report","coverage_download")
with st.expander("Inspect all source columns, including additional fields"):
    st.dataframe(src,hide_index=True,width="stretch",height=350)
    download_button(src,f"{ctx.season}_{ctx.league_id}_{kind}_all_fields.csv","Download full selected dataset","all_fields_download")
section("","The rules behind the analysis")
a,b=st.columns(2,gap="large")
with a:
    brief("A fair frame of reference","Benchmarks are pooled rates for the loaded season, league, level and date range. They are not automatically the official full-league averages. Player percentiles compare individual player rates and use tied midranks.")
    brief("Counts first, rates second","We add hits and at-bats, then calculate batting average. We do not average game batting averages. Pitching arithmetic uses outs; 5.2 displayed innings means five innings and two outs.")
with b:
    brief("Estimates are labeled","Estimated wOBA and the run-creation index use fixed weights. The OPS index has no park adjustment. FIP uses a constant calculated from the loaded cohort. None should be represented as an official adjusted statistic.")
    brief("No invented scouting grades","Box scores cannot measure command, defensive range, exit velocity, spin, pitch shape, injury risk or trade value. We show observed production and suggest questions for further review.")
st.markdown("Sources: [MLB statistic glossary](https://www.mlb.com/glossary) · [FanGraphs wOBA methodology](https://library.fangraphs.com/offense/woba/) · [FanGraphs wRC methodology](https://library.fangraphs.com/offense/wrc/)")
