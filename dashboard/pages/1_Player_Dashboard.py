import pandas as pd
import streamlit as st

from dashboard import charts, bio, news
from dashboard.assets import player_photo_html
from dashboard.context import context_note
from dashboard.data_loader import LEVEL_LABEL
from dashboard.glossary import label
from dashboard.metrics import line_for, enriched_line, player_table, rolling_rate, split_table
from dashboard.ui import plain, pretty, field_name, without_internals, hero, section, identity, stat_cards, facts_row, league_delta, chart, fmt, sample_note, metric_help, stat_sheet, download_button, news_list

ctx = st.session_state["_context"]
arriving = st.session_state.pop("_goto_player", None)
if arriving:
    target, target_kind = arriving
    st.session_state["player_kind"] = "Pitching" if target_kind == "pitching" else "Batting"
    st.session_state[f"player_team_{target_kind}"] = None
    st.session_state[f"player_position_{target_kind}"] = "All"
else:
    target = None
hero("Player lab", "Game log, trend, splits and peer comparison for one player.")
context_note(ctx)
st.session_state.setdefault("player_kind", "Batting")
mode = st.segmented_control("Player group", ["Batting", "Pitching"], key="player_kind")
kind = "pitching" if mode == "Pitching" else "batting"
src = ctx.batting if kind == "batting" else ctx.pitching
if src.empty:
    st.info("No appearances in this group for these dates.")
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
    st.info("No players match. Change the team or position.")
    st.stop()
people = pool.sort_values(["game_date", "game_pk"])[["player_id", "player_full_name"]].drop_duplicates("player_id", keep="last")
names = dict(people.itertuples(index=False, name=None))
if target is not None:
    if target in names:
        st.session_state[f"player_pick_{kind}"] = target
    else:
        st.warning("That player is not in the current filters. Widen the sidebar filters to see them.")
with controls[0]:
    pid = st.selectbox("Search player", sorted(names, key=names.get), format_func=lambda p: f"{names[p]} · ID {p}", key=f"player_pick_{kind}")
pdf = pool[pool["player_id"].eq(pid)].copy()
latest = pdf.iloc[-1]
cohort = line_for(src, kind)
line = enriched_line(pdf, kind, cohort)
population = player_table(src, kind)
player_bio = bio.get_bios([pid]).iloc[0].to_dict()
now = player_bio.get("current_level") or "Unknown"
identity(names[pid], player_photo_html(pid, 84, "10px"), [
    ("Latest team", latest["team_name"]), ("Position", latest["player_position"]),
    ("Played at", f"{LEVEL_LABEL.get(latest['team_level'], latest['team_level'])} · {ctx.league}"),
    ("In this view", f"{int(line['G'])} game{'s' if int(line['G']) != 1 else ''} · {ctx.period}")],
    bio.level_chip_html(now, player_bio.get("roster_status")),
    " · ".join(dict.fromkeys(x for x in (player_bio.get("current_team"), player_bio.get("current_org")) if isinstance(x, str) and x))
    if now not in ("Unknown", "No team") else "")
details = []
if pd.notna(player_bio.get("age")):
    details.append(("Age", f"{int(player_bio['age'])}", ""))
if player_bio.get("height_cm"):
    details.append(("Height", f"{player_bio['height_cm']} cm", player_bio.get("height") or ""))
if player_bio.get("weight_kg"):
    details.append(("Weight", f"{player_bio['weight_kg']} kg", f"{player_bio.get('weight_lb')} lb"))
if player_bio.get("bats") or player_bio.get("throws"):
    details.append(("Bats / throws", f"{player_bio.get('bats') or 'n/a'} / {player_bio.get('throws') or 'n/a'}", ""))
if player_bio.get("birthplace"):
    details.append(("Born in", player_bio["birthplace"], ""))
if player_bio.get("debut_date"):
    details.append(("MLB debut", player_bio["debut_date"], ""))
if details:
    facts_row(details)
else:
    st.caption("No MLB Stats API record for this player ID.")
st.caption("Level and bio come from the MLB Stats API, not from the game logs.")
path = (pdf.groupby(["season", "team_level", "team_name"], sort=True)["game_pk"].nunique().rename("Games").reset_index()
        .rename(columns={"season": "Season", "team_level": "Level", "team_name": "Team"}))
sample_note(line, kind)
headline = ["OPS", "OBP", "ISO", "K_pct"] if kind == "batting" else ["ERA", "WHIP", "K_BB_pct", "IP"]
stat_cards([{"label": label(k), "value": fmt(line[k], k),
             "delta": league_delta(line.get(k), cohort.get(k), k, kind),
             "sub": f"League {fmt(cohort.get(k), k)}" if k != "IP" else "5.2 means 5 innings and 2 outs"} for k in headline])
metric_help(headline, kind)

tabs = st.tabs(["Performance", "Game log", "Breakdowns", "Compare", "News", "All metrics & report"])
with tabs[0]:
    a, b = st.columns([1.5, 1], gap="large")
    with a:
        section("Trend", "Each point is recalculated from the last N appearances.")
        opts = ["OPS", "OBP", "ISO", "K_pct", "wOBA"] if kind == "batting" else ["ERA", "WHIP", "K_BB_pct", "K9", "BB9"]
        sub = st.columns([1, 1])
        with sub[0]:
            metric = st.selectbox("Trend metric", opts, format_func=label, key=f"trend_metric_{kind}")
        with sub[1]:
            window = st.select_slider("Games in each point", options=[1, 3, 5, 10, 15, 30], value=10, key=f"trend_window_{kind}")
        rolling = rolling_rate(pdf, kind, window, metric)
        chart(charts.trend(rolling, metric, cohort.get(metric)), "player_trend")
        st.caption(f"Latest point covers {int(rolling['Games in window'].iloc[-1]) if not rolling.empty else 0} of {window} appearances. Lines break between seasons.")
    with b:
        section("Compared with other players", "Same seasons, league and dates. Longer bar = better. 50 is average, 90 means better than 90 of 100 players.")
        min_sample = st.number_input("Others need at least this many plate appearances" if kind == "batting" else "Others need at least this many innings", min_value=0, value=0 if ctx.source == "Included sample" else 100 if kind == "batting" else 20, step=5, key=f"peer_min_{kind}")
        eligible = population[population["PA" if kind == "batting" else "IP"].ge(min_sample)]
        fig, count = charts.percentile_bars(line, eligible, kind)
        if count:
            chart(fig, "player_percentiles")
            st.caption(f"Compared with {len(eligible)} players. Ties share the middle rank.")
        else:
            st.info("Percentiles need at least five peers. Lower the minimum or widen the dates.")

with tabs[1]:
    section("Game log", "Doubleheaders are separate games. Pick one below to see every field.")
    counters = {"Hits": "batting_H", "Total bases": "batting_TB", "Strikeouts": "batting_SO", "Home runs": "batting_HR"} if kind == "batting" else {"Strikeouts": "pitching_SO", "Earned runs": "pitching_ER", "Walks": "pitching_BB", "Pitches": "pitching_PI"}
    selected = st.selectbox("Game-by-game metric", list(counters), key=f"game_metric_{kind}")
    chart(charts.game_bars(pdf, counters[selected], selected), "player_games")
    games = pdf.sort_values(["game_date", "game_pk"], ascending=False)
    line_stats = {"AB": "batting_AB", "H": "batting_H", "HR": "batting_HR", "RBI": "batting_RBI", "BB": "batting_BB", "SO": "batting_SO"} if kind == "batting" else {"IP": "pitching_IP_str", "H": "pitching_H", "ER": "pitching_ER", "BB": "pitching_BB", "SO": "pitching_SO", "Pitches": "pitching_PI"}
    table = pd.DataFrame({"Date": games["game_date"].dt.strftime("%d %b %Y"), "Team": games["team_name"],
                          "Opponent": games.get("opponent_name"), "Result": games.get("result"),
                          "Score": games["team_score"].astype("Int64").astype(str) + "–" + games["opponent_score"].astype("Int64").astype(str)
                                   if {"team_score", "opponent_score"} <= set(games) else None})
    for name, column in line_stats.items():
        table[name] = games[column] if column in games else None
    table["Game ID"] = games["game_pk"].astype(str)
    st.dataframe(plain(table), hide_index=True, width="stretch", height=380)
    st.caption("Score is team first, then opponent." + (" Innings: 5.2 means 5 innings and 2 outs." if kind == "pitching" else ""))
    options = pdf["game_pk"].drop_duplicates().tolist()
    game_labels = {row["game_pk"]: f"{row['game_date']:%d %b %Y} · {row.get('opponent_name', 'opponent unknown')} · Game {row['game_pk']}" for _, row in pdf.iterrows()}
    game = st.selectbox("Inspect one game", options, format_func=game_labels.get, key=f"game_detail_{kind}")
    with st.expander("All fields for the selected game"):
        one = without_internals(pdf[pdf["game_pk"].eq(game)]).T.rename(columns=lambda _: "Value").astype(str)
        one.index = [field_name(i, kind) for i in one.index]
        st.dataframe(one, width="stretch", column_config={"_index": st.column_config.TextColumn("Field")})
    download_button(without_internals(pdf), f"player_{pid}_{ctx.tag}_{kind}_games.csv", "Download this game log", f"games_export_{kind}")

with tabs[2]:
    section("Breakdowns", "The same stats split by month, home or away, team or role.")
    with st.expander(f"Where this player appeared in the selected data · {len(path)} stop(s)"):
        st.dataframe(path, hide_index=True, width="stretch")
    split_options = {"Month": "month", "Home / away": "is_home", "Team": "team_name"}
    if ctx.multi_season:
        split_options = {"Season": "season", **split_options}
    if kind == "pitching":
        split_options["Starter / reliever"] = "role"
    split_name = st.selectbox("Break down by", list(split_options), key=f"split_by_{kind}")
    key = split_options[split_name]
    if key in pdf:
        splits = split_table(pdf, kind, key)
        metric = "OPS" if kind == "batting" else "ERA"
        chart(charts.split_bars(splits, metric), "player_splits")
        st.dataframe(pretty(splits[["Split", "G", "PA", "AVG", "OBP", "SLG", "OPS", "BB_pct", "K_pct"] if kind == "batting" else ["Split", "G", "IP", "ERA", "WHIP", "K9", "BB9"]]), hide_index=True, width="stretch")
        download_button(splits, f"player_{pid}_splits.csv", "Download this table", f"split_export_{kind}")
    else:
        st.info("This data has no such split.")
    st.caption("Widen the season range in the sidebar to split by season." if not ctx.multi_season else "Splits cover every selected season.")

with tabs[3]:
    section("Compare two players", "Any other player in this league and date range.")
    choices = population[~population["player_id"].eq(pid)]
    if choices.empty:
        st.info("No second player in this selection.")
    else:
        labels = dict(zip(choices["player_id"], choices["Player"] + " · " + choices["Team"]))
        other = st.selectbox("Compare with", list(labels), format_func=lambda p: f"{labels[p]} · ID {p}", key=f"compare_pick_{kind}")
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
    section("Recent coverage", f"News search for \"{names[pid]}\", from Google News (ESPN, SB Nation, MiLB.com, local writers).")
    if st.button("Load recent news", key=f"news_lookup_{pid}"):
        with st.spinner("Searching for recent coverage…"):
            st.session_state[f"news_{pid}"] = news.fetch_news(f"{names[pid]} {latest['team_name']} baseball")
    if f"news_{pid}" in st.session_state:
        news_list(st.session_state[f"news_{pid}"])
    else:
        st.caption("Click the button to search. Rookie-level players often have little coverage.")

with tabs[5]:
    section("Full metric sheet", "Every metric, including ones with no data. Extra source columns are in the game-log download.")
    sheet = stat_sheet(line, cohort, kind)
    query = st.text_input("Find a metric", placeholder="Try walks, WHIP, power…", key=f"metric_search_{kind}")
    visible = sheet[sheet.astype(str).apply(lambda col: col.str.contains(query, case=False, regex=False)).any(axis=1)] if query else sheet
    st.dataframe(visible, hide_index=True, width="stretch", height=430)
    download_button(sheet, f"player_{pid}_{kind}_metrics.csv", "Download complete metric sheet", f"metrics_export_{kind}")
    notes = st.text_area("Your notes", placeholder="What you saw, what to check next", key=f"notes_{pid}_{kind}")
    report = f"# {names[pid]} · {ctx.period}\n\n{ctx.description}\n\nDates: {ctx.start} to {ctx.end}. Source: {ctx.location}.\n\n"
    report += "\n".join(f"- {r['Metric']}: {r['Value']}" for _, r in sheet.iterrows())
    report += f"\n\n## Notes\n{notes}\n\nObserved games only. Small samples are not stable skill estimates. Estimated metrics are not official park-adjusted values.\n"
    st.download_button("Download player report", report.encode(), f"player_{pid}_report.md", "text/markdown", key=f"report_export_{kind}")
    with st.expander("Full status record"):
        st.caption(f"Raw MLB Stats API record for {names[pid]}.")
        st.dataframe(pd.DataFrame([player_bio]).drop(columns=["fetched_at"], errors="ignore"), hide_index=True, width="stretch")
