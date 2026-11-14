import pandas as pd
import streamlit as st

from dashboard import bio
from dashboard.assets import player_photo_url, team_logo_url, team_logo_html
from dashboard.context import context_note
from dashboard import charts
from dashboard.glossary import label, code
from dashboard.metrics import (player_table, line_for, team_table, game_results, standings_path, league_by_month,
                               expected_win_pct, season_path)
from dashboard.ui import (hero, section, stat_cards, chart, fmt, download_button, jump_to_player, club_cards, key_facts,
                          metric_columns)

ctx = st.session_state["_context"]
hero("Overview", "League leaders, how the league plays, and the race between clubs.")
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
headline = "OPS" if kind == "batting" else "ERA"
stat_cards([
    {"label": "Games", "value": f"{both['game_pk'].nunique():,}", "sub": "Unique games on file"},
    {"label": "Players", "value": f"{src['player_id'].nunique():,}", "sub": "Batters" if kind == "batting" else "Pitchers"},
    {"label": "Teams", "value": f"{src['team_id'].nunique():,}", "sub": ctx.league},
    {"label": f"League {headline}", "value": fmt(pooled[headline], headline),
     "sub": "On-base plus slugging" if kind == "batting" else "Earned runs per 9"},
])
qualified = players[players[sample_key].ge(minimum)].copy()
unit = "plate appearances" if kind == "batting" else "innings"
if qualified.empty and not players.empty:
    st.warning(f"No player reaches {minimum:,} {unit} in this selection. The most by anyone is "
               f"{fmt(players[sample_key].max(), sample_key)}, so lower the minimum above to see them.")
metric_options = ["OPS", "OBP", "ISO", "HR", "BB_pct", "K_pct"] if kind == "batting" else ["ERA", "WHIP", "K_BB_pct", "K9", "BB9"]
games = game_results(ctx.batting, ctx.pitching)
players_tab, league_tab, teams_tab = st.tabs(["Players", "League picture", "Teams"])

with players_tab:
    left, right = st.columns([1.65, 1], gap="large")
    with left:
        section("Power vs. strikeouts" if kind == "batting" else "Strikeouts vs. walks", "One dot per player. Bigger dots played more.")
        if not qualified.empty:
            chart(charts.scatter_field(qualified, kind), "overview_landscape")
            st.caption("Upper left is best: more power, fewer strikeouts." if kind == "batting" else "Upper left is best: more strikeouts, fewer walks.")
    with right:
        section("League averages", ctx.description)
        keys = ["AVG", "OBP", "SLG", "OPS", "BB_pct", "K_pct"] if kind == "batting" else ["ERA", "WHIP", "K9", "BB9", "K_pct", "BB_pct"]
        st.dataframe(pd.DataFrame({"Metric": [label(k) for k in keys], "League": [fmt(pooled[k], k) for k in keys]}), hide_index=True, width="stretch")

    section("Player leaderboard", "\"Level now\" is where the player is today.")
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
    paths = season_path(src[src["player_id"].isin(shown["player_id"])], kind)
    for key in shown.columns:
        if key not in ("Player", "Team", "player_id", "team_id"):
            shown[key] = shown[key].map(lambda v, k=key: fmt(v, k))
    shown.insert(0, "#", range(1, len(shown) + 1))
    shown.insert(1, "Photo", shown["player_id"].map(player_photo_url))
    shown.insert(4, "Logo", shown["team_id"].map(team_logo_url))
    shown.insert(6, "Level now", shown["player_id"].map(now["current_level"]))
    shown.insert(7, "Org", shown["player_id"].map(now["current_org"]))
    shown.insert(8, "Path", shown["player_id"].map(paths))
    lead = ["#", "Photo", "Player", "Logo", "Team", "Level now", "Org", "Path"]
    st.dataframe(shown, hide_index=True, width="stretch", height=460,
                 column_order=lead + [c for c in shown.columns if c not in (*lead, "player_id", "team_id")],
                 column_config=metric_columns(shown.columns, {
                     "Photo": st.column_config.ImageColumn("", width="small"), "Logo": st.column_config.ImageColumn("", width="small"),
                     "#": st.column_config.NumberColumn(width="small"),
                     "Org": st.column_config.Column("Org", help="Parent club today"),
                     "Path": st.column_config.LineChartColumn(f"{headline} path", width="small",
                                                              help=f"{label(headline)} after each game, season to date.")}))
    jump_to_player({int(r.player_id): f"{i}. {r.Player} · {r.Team}" for i, r in enumerate(shown.itertuples(), 1)},
                   f"overview_jump_{kind}", kind, "Open one of these players")
    download_button(ranked, f"{ctx.tag}_{ctx.league_id}_{kind}_leaderboard.csv", "Download full leaderboard", "overview_export")

with league_tab:
    section("Where the league sits", f"Every player with at least {minimum:,} {unit}.")
    spread_key = st.segmented_control("Metric", [k for k in metric_options if k != "HR"], format_func=code,
                                      default=metric_options[0], key=f"overview_spread_{kind}") or metric_options[0]
    values = qualified[spread_key].dropna() if spread_key in qualified else pd.Series(dtype=float)
    if len(values) < 5:
        st.info("A spread needs at least five players. Lower the minimum above.")
    else:
        better_low = spread_key in ("ERA", "WHIP", "BB9") or (spread_key == "K_pct" and kind == "batting")
        best, worst = (values.quantile(.1), values.quantile(.9)) if better_low else (values.quantile(.9), values.quantile(.1))
        chart(charts.distribution(values, spread_key), "overview_spread")
        key_facts([("Players", f"{len(values):,}"), ("Best tenth from", fmt(best, spread_key)), ("Middle", fmt(values.median(), spread_key)),
                   ("Weakest tenth from", fmt(worst, spread_key)),
                   ("Middle half", f"{fmt(values.quantile(.25), spread_key)} – {fmt(values.quantile(.75), spread_key)}")])

    months = league_by_month(ctx.batting, ctx.pitching)
    if not games.empty:
        decided = games[games["result"].isin(["W", "L"])]
        home = decided[decided["is_home"].eq(True)]
        once = games.drop_duplicates("game_pk")
        section("How games go", "Shares of all games in this selection.")
        key_facts([("Runs per team game", fmt(games["team_score"].mean(), digits=2)),
                   ("Home teams win", "N/A" if home.empty else f"{home['result'].eq('W').mean():.1%}"),
                   ("One-run games", f"{once['Margin'].abs().eq(1).mean():.1%}"),
                   ("Decided by 5+", f"{once['Margin'].abs().ge(5).mean():.1%}"),
                   ("Shutouts", f"{(once['team_score'].eq(0) | once['opponent_score'].eq(0)).mean():.1%}")])
    if len(months) > 1:
        section("Through the season", "Scoring and plate discipline, month by month.")
        a, b = st.columns(2, gap="large")
        with a:
            chart(charts.month_bars(months, "R_G", "Runs per team game"), "overview_month_runs")
        with b:
            chart(charts.month_lines(months, ["K_pct", "BB_pct"]), "overview_month_rates")

with teams_tab:
    teams = team_table(ctx.batting, ctx.pitching)
    if teams.empty:
        st.info("No team results in this selection.")
    else:
        teams = teams.sort_values("W_pct", ascending=False, na_position="last")
        decided = teams["W"] + teams["L"]
        teams["xW"] = (expected_win_pct(teams["RS"].astype(float), teams["RA"].astype(float)) * decided).round()
        teams["Luck"] = teams["W"] - teams["xW"]
        path = standings_path(games)
        tracks = path.groupby("team_id")["Over"].apply(list)
        section("The race", "Wins minus losses through the season. Chip: runs scored minus allowed.")
        club_cards([{"logo": team_logo_html(r.team_id, 26), "name": r.Team, "record": f"{r.W}–{r.L}", "margin": r.Margin,
                     "diff": "N/A" if pd.isna(r.Margin) else f"{r.Margin:+.0f}", "path": tracks.get(r.team_id, [])}
                    for r in teams.itertuples()])
        section("Scoring and prevention", "Dotted lines are the league. Green clubs outscore their opponents.")
        chart(charts.team_quadrant(teams), "overview_quadrant")
        section("Standings", "Expected wins come from runs scored and allowed. Luck is wins above that.")
        team_cols = ["Team", "Games", "W", "L", "W_pct", "RS", "RA", "Margin", "xW", "Luck", "OPS", "ERA", "WHIP"]
        board = teams.reindex(columns=["team_id", *team_cols])
        for key in ("W_pct", "OPS", "ERA", "WHIP"):
            board[key] = board[key].map(lambda v, k=key: fmt(v, k))
        for key in ("xW", "Luck", "Margin"):
            board[key] = board[key].map(lambda v, k=key: "N/A" if pd.isna(v) else f"{v:+.0f}" if k != "xW" else f"{v:.0f}")
        board.insert(1, "Logo", board["team_id"].map(team_logo_url))
        st.dataframe(board, hide_index=True, width="stretch",
                     column_order=[c for c in board.columns if c != "team_id"],
                     column_config=metric_columns(board.columns, {
                         "Logo": st.column_config.ImageColumn("", width="small"),
                         "Games": st.column_config.Column("G", help="Games on file"),
                         "W_pct": st.column_config.Column("Win %", help="Wins as a share of decided games"),
                         "RS": st.column_config.Column("RS", help="Runs scored"), "RA": st.column_config.Column("RA", help="Runs allowed"),
                         "Margin": st.column_config.Column("Diff", help="Runs scored minus runs allowed"),
                         "xW": st.column_config.Column("Exp. W", help="Wins a club with these runs usually has (Pythagorean expectation, exponent 1.83)"),
                         "Luck": st.column_config.Column("Luck", help="Actual wins minus expected wins")}))
        download_button(teams, f"{ctx.tag}_{ctx.league_id}_teams.csv", "Download team table", "overview_teams_export")

with st.expander("What is in this data"):
    st.write("Only games in this dataset are counted. A team or player may have played more.")
    st.write(f"Source: {ctx.location}. Batting rows: {len(ctx.batting):,}. Pitching rows: {len(ctx.pitching):,}.")
    st.write("New to this? The Analyst guide page explains which numbers to trust and how to read a player.")
