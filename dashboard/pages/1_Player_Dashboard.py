import pandas as pd
import streamlit as st

from dashboard import charts, bio, news
from dashboard.assets import player_photo_html, player_photo_url
from dashboard.context import context_note
from dashboard.glossary import label
from dashboard.metrics import line_for, enriched_line, player_table, rolling_rate, split_table
from dashboard.ui import hero, section, identity, stat_cards, brief, chart, fmt, sample_note, metric_help, stat_sheet, download_button, news_list

ctx = st.session_state["_context"]
hero("Player lab", "From the box score to the bigger picture.", "Inspect performance, compare the right peers, and keep the sample size in view.")
context_note(ctx)
mode = st.segmented_control("Player group", ["Batting", "Pitching"], default="Batting", key="player_kind")
kind = "pitching" if mode == "Pitching" else "batting"
src = ctx.batting if kind == "batting" else ctx.pitching
if src.empty:
    st.info("No player appearances match this group and date range.")
    st.stop()
controls = st.columns([1.4, 1, 1], gap="medium")
team_labels = dict(src[["team_id", "team_name"]].drop_duplicates("team_id").itertuples(index=False, name=None))
with controls[1]:
    selected_team = st.selectbox("Team", [None, *sorted(team_labels, key=team_labels.get)], format_func=lambda t: "All teams" if t is None else team_labels[t], key=f"player_team_{kind}")
pool = src if selected_team is None else src[src["team_id"].eq(selected_team)]
with controls[2]:
    filter_col = "pos_group" if kind == "batting" else "role"
    options = sorted(pool[filter_col].dropna().unique())
    position = st.selectbox("Position" if kind == "batting" else "Appearance role", ["All", *options], key=f"player_position_{kind}")
    if position != "All":
        pool = pool[pool[filter_col].eq(position)]
if pool.empty:
    st.info("No players match those filters. Choose another team or position.")
    st.stop()
people = pool.sort_values(["game_date", "game_pk"])[["player_id", "player_full_name"]].drop_duplicates("player_id", keep="last")
names = dict(people.itertuples(index=False, name=None))
with controls[0]:
    pid = st.selectbox("Search player", sorted(names, key=names.get), format_func=lambda p: f"{names[p]} · ID {p}", key=f"player_pick_{kind}")
pdf = pool[pool["player_id"].eq(pid)].copy()
latest = pdf.iloc[-1]
cohort = line_for(src, kind)
line = enriched_line(pdf, kind, cohort)
population = player_table(src, kind)
player_bio = bio.get_bios([pid]).iloc[0].to_dict()
identity(names[pid], f"{latest['team_name']} · {latest['player_position']} · {ctx.description}", f"{int(line['G']):02d} G",
         player_photo_html(pid, 72), bio.status_badge_html(player_bio.get("status", "Other / Unknown")))
st.caption("Status is a live MLB Stats API lookup, separate from the game logs — 'Active – MiLB' means still developing with a minor-league affiliate; 'Active – MLB' means on a major-league roster today.")
sample_note(line, kind)
headline = ["OPS", "OBP", "ISO", "K_pct"] if kind == "batting" else ["ERA", "WHIP", "K_BB_pct", "IP"]
stat_cards([{"label": label(k), "value": fmt(line[k], k), "sub": (f"Cohort {fmt(cohort.get(k), k)}" if k != "IP" else "Baseball notation · .2 = two outs")} for k in headline])
metric_help(headline, kind)

tabs = st.tabs(["Performance", "Game log", "Splits & development", "Compare", "News", "All metrics & report"])
with tabs[0]:
    a, b = st.columns([1.5, 1], gap="large")
    with a:
        section("", "Recent direction", "Rates are recalculated from the counts inside each trailing window.")
        opts = ["OPS", "OBP", "ISO", "K_pct", "wOBA"] if kind == "batting" else ["ERA", "WHIP", "K_BB_pct", "K9", "BB9"]
        sub = st.columns([1, 1])
        with sub[0]:
            metric = st.selectbox("Trend metric", opts, format_func=label, key=f"trend_metric_{kind}")
        with sub[1]:
            window = st.select_slider("Trailing appearances", options=[1, 3, 5, 10, 15, 30], value=10, key=f"trend_window_{kind}")
        rolling = rolling_rate(pdf, kind, window, metric)
        chart(charts.trend(rolling, metric, cohort.get(metric)), "player_trend")
        st.caption(f"{min(window, len(pdf))} of {window} appearances available in the latest window. Hover for the actual window size. This view does not infer growth from one game.")
    with b:
        section("", "The peer comparison", "Same season, league and dates. Higher bars always mean a more favorable result.")
        min_sample = st.number_input("Peer minimum PA" if kind == "batting" else "Peer minimum IP", min_value=0, value=0 if ctx.source == "Included sample" else 100 if kind == "batting" else 20, step=5, key=f"peer_min_{kind}")
        eligible = population[population["PA" if kind == "batting" else "IP"].ge(min_sample)]
        fig, count = charts.percentile_bars(line, eligible, kind)
        if count:
            chart(fig, "player_percentiles")
            st.caption(f"{len(eligible)} comparison players. Equal results share a midrank. These are statistical percentiles, not scouting grades.")
        else:
            st.info("At least five peers with available values are needed to show a percentile. Lower the threshold or widen the dates.")
    section("", "Questions to take to the field", "Data-led prompts for a scout or coach; video and firsthand observation still matter.")
    if kind == "batting":
        brief("Approach at the plate", f"Walk rate: {fmt(line['BB_pct'], 'BB_pct')}; strikeout rate: {fmt(line['K_pct'], 'K_pct')}. Review whether swing decisions and two-strike execution support these results. Pitch locations and swing decisions are not measured by these box scores.")
        brief("Contact with impact", f"Extra-base power (ISO): {fmt(line['ISO'], 'ISO')}. Inspect the game log to see whether production is spread across games. Exit velocity and launch angle are not available here.")
    else:
        brief("Command and missed bats", f"Strikeout minus walk rate: {fmt(line['K_BB_pct'], 'K_BB_pct')}. Review strike throwing, count leverage and pitch execution on video. This is not a direct measure of command or pitch quality.")
        brief("Workload context", f"{fmt(line['IP'], 'IP')} innings in {int(line['G'])} appearances. Compare starts and relief appearances separately. The data alone cannot establish fatigue or injury risk.")

with tabs[1]:
    section("", "Every game behind the summary", "Select a game to inspect its complete source row. Doubleheaders remain separate by game ID.")
    counters = {"Hits": "batting_H", "Total bases": "batting_TB", "Strikeouts": "batting_SO", "Home runs": "batting_HR"} if kind == "batting" else {"Strikeouts": "pitching_SO", "Earned runs": "pitching_ER", "Walks": "pitching_BB", "Pitches": "pitching_PI"}
    selected = st.selectbox("Game-by-game metric", list(counters), key=f"game_metric_{kind}")
    chart(charts.game_bars(pdf, counters[selected], selected), "player_games")
    keycols = [c for c in ["game_date", "game_pk", "team_name", "opponent_name", "result", "team_score", "opponent_score", *counters.values()] if c in pdf]
    st.dataframe(pdf[keycols].sort_values("game_date", ascending=False), hide_index=True, width="stretch")
    options = pdf["game_pk"].drop_duplicates().tolist()
    game_labels = {row["game_pk"]: f"{row['game_date']:%d %b %Y} · {row.get('opponent_name', 'opponent unknown')} · Game {row['game_pk']}" for _, row in pdf.iterrows()}
    game = st.selectbox("Inspect one game", options, format_func=game_labels.get, key=f"game_detail_{kind}")
    with st.expander("All fields for the selected game"):
        st.dataframe(pdf[pdf["game_pk"].eq(game)].T.rename(columns=lambda _: "Source value").astype(str), width="stretch")
    download_button(pdf, f"player_{pid}_{ctx.season}_{kind}_games.csv", "Download every game field", f"games_export_{kind}")

with tabs[2]:
    section("", "Find the context behind a change", "All splits retain your league, team, position and date filters.")
    split_options = {"Month": "month", "Home / away": "is_home", "Team": "team_name"}
    if kind == "pitching":
        split_options["Starter / reliever"] = "role"
    split_name = st.selectbox("Split by", list(split_options), key=f"split_by_{kind}")
    key = split_options[split_name]
    if key in pdf:
        splits = split_table(pdf, kind, key)
        metric = "OPS" if kind == "batting" else "ERA"
        chart(charts.split_bars(splits, metric), "player_splits")
        st.dataframe(splits[["Split", "G", "PA", "AVG", "OBP", "SLG", "OPS", "BB_pct", "K_pct"]] if kind == "batting" else splits[["Split", "G", "IP", "ERA", "WHIP", "K9", "BB9"]].assign(IP=lambda d: d["IP"].map(lambda x: fmt(x,"IP"))), hide_index=True, width="stretch")
        download_button(splits, f"player_{pid}_splits.csv", "Download split table", f"split_export_{kind}")
    else:
        st.info("This dataset does not contain the selected split field.")
    st.caption("For another season, change Season in the sidebar. Benchmarks are recomputed within that season instead of pooling years into a misleading comparison.")

with tabs[3]:
    section("", "Two players. The same frame of reference.", "Comparison players come from this league and date range.")
    choices = population[~population["player_id"].eq(pid)]
    if choices.empty:
        st.info("A second player is not available in this selection.")
    else:
        labels = dict(zip(choices["player_id"], choices["Player"] + " · " + choices["Team"]))
        other = st.selectbox("Compare against", list(labels), format_func=lambda p: f"{labels[p]} · ID {p}", key=f"compare_pick_{kind}")
        other_df = src[src["player_id"].eq(other)]
        cmp_line = enriched_line(other_df, kind, cohort)
        cmp_name = other_df.iloc[-1]["player_full_name"]
        vs_a, vs_b = st.columns(2)
        with vs_a:
            st.markdown(f"<div style='display:flex;align-items:center;gap:.6rem'>{player_photo_html(pid, 44)}<b>{names[pid]}</b></div>", unsafe_allow_html=True)
        with vs_b:
            st.markdown(f"<div style='display:flex;align-items:center;gap:.6rem'>{player_photo_html(other, 44)}<b>{cmp_name}</b></div>", unsafe_allow_html=True)
        chart(charts.compare_dots(line, cmp_line, [names[pid], cmp_name], ["AVG", "OBP", "SLG"] if kind == "batting" else ["K_pct", "BB_pct", "K_BB_pct"]), "player_comparison")
        keys = ["G", "PA", "AVG", "OBP", "SLG", "OPS", "ISO", "HR", "BB_pct", "K_pct"] if kind == "batting" else ["G", "IP", "ERA", "WHIP", "K9", "BB9", "K_BB_pct", "FIP_est"]
        comparison = pd.DataFrame({"Metric": [label(k) for k in keys], f"{names[pid]} · {pid}": [fmt(line.get(k),k) for k in keys], f"{cmp_name} · {other}": [fmt(cmp_line.get(k),k) for k in keys]})
        st.dataframe(comparison, hide_index=True, width="stretch")
        download_button(comparison, f"compare_{pid}_{other}.csv", "Download comparison", f"compare_export_{kind}")

with tabs[4]:
    section("", "Recent coverage", f"News search for \"{names[pid]}\", via Google News — indexes ESPN, SB Nation, MiLB.com and local beat writers, not one site.")
    if st.button("Load recent news", key=f"news_lookup_{pid}"):
        with st.spinner("Searching for recent coverage…"):
            st.session_state[f"news_{pid}"] = news.fetch_news(f"{names[pid]} {latest['team_name']} baseball")
    if f"news_{pid}" in st.session_state:
        news_list(st.session_state[f"news_{pid}"])
    else:
        st.caption("Not loaded yet — click above. Coverage on complex-league and short-season players is often thin.")

with tabs[5]:
    section("", "The complete metric sheet", "Every original metric is listed, including unavailable fields. Extra source columns remain in the game-log export.")
    sheet = stat_sheet(line, cohort, kind)
    query = st.text_input("Find a metric", placeholder="Try walks, WHIP, power…", key=f"metric_search_{kind}")
    visible = sheet[sheet.astype(str).apply(lambda col: col.str.contains(query, case=False, regex=False)).any(axis=1)] if query else sheet
    st.dataframe(visible, hide_index=True, width="stretch", height=430)
    download_button(sheet, f"player_{pid}_{kind}_metrics.csv", "Download complete metric sheet", f"metrics_export_{kind}")
    notes = st.text_area("Your scouting / coaching notes", placeholder="What did you observe? What would you check next?", key=f"notes_{pid}_{kind}")
    report = f"# {names[pid]} · {ctx.season}\n\n{ctx.description}\n\nDates: {ctx.start} to {ctx.end}. Source: {ctx.location}.\n\n"
    report += "\n".join(f"- {r['Metric']}: {r['Value']}" for _, r in sheet.iterrows())
    report += f"\n\n## Notes\n{notes}\n\nObserved games only. Small samples are not stable skill estimates. Estimated metrics are not official park-adjusted values.\n"
    st.download_button("Download player report", report.encode(), f"player_{pid}_report.md", "text/markdown", key=f"report_export_{kind}")
    with st.expander("Full status record"):
        st.caption(f"Same lookup shown in the header badge above, for {names[pid]}.")
        st.dataframe(pd.DataFrame([player_bio]).drop(columns=["fetched_at"], errors="ignore"), hide_index=True, width="stretch")
