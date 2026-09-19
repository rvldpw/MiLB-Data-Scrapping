import pandas as pd
import streamlit as st

from dashboard.context import context_note
from dashboard.glossary import METRICS, keys_for, label, code, definition, direction
from dashboard.metric_catalog import RAW_FIELDS
from dashboard.ui import hero, section, note_grid, steps, stat_cards, download_button, without_internals

ctx = st.session_state["_context"]
hero("Analyst guide", "How to read a minor-league player, which numbers matter first, and what every metric here means.")
context_note(ctx)

start, focus, dictionary, coverage_tab, rules = st.tabs(
    ["Start here", "What to focus on", "Metric dictionary", "Data coverage", "How the numbers are built"])

# ---------------------------------------------------------------- Start here
with start:
    section("The job", "A minor-league analyst answers one question: who is getting better, and can they do it a level up?")
    note_grid([
        ("You are running a scouting desk",
         "The minors are a development ladder, not a results table. Nobody wins a trophy in Single-A. The point is to spot "
         "the players who will hold up against better opponents, and to spot them before everyone else does."),
        ("The real scoreboard is promotion",
         "A good season in Single-A means little on its own. What matters is whether the player moved up and kept "
         "producing. The Level now column on every list tells you where they ended up, so you can check your own calls."),
    ])
    section("A routine that works", "Five steps. Repeat them for every player you look at.")
    steps([
        ("Set your window", "In the sidebar, pick a level, a league and a season range. Everything on every page follows those filters, "
                            "so the league average you see is the one this player actually faced."),
        ("Raise the minimum", "On the Overview, set a minimum of about 100 plate appearances or 20 innings. Without it the leaderboard "
                              "fills with players who had one lucky week."),
        ("Sort by the right thing", "For hitters start with OPS. For pitchers start with K−BB%, not ERA. Then open a name."),
        ("Read the player in order", "Sample size first, then the rate stats, then the peer bars, then the trend. Never the other way round."),
        ("Check where they are now", "Look at the Today chip on the player page. Moved up a level? Your read was probably right. "
                                     "Still there two years later? Work out what you missed."),
    ])
    section("The ladder", "Each rung is a real step up in opponent quality. Numbers do not carry across rungs.")
    st.dataframe(pd.DataFrame([
        {"Level": "Rookie / complex", "Typical age": "17–20", "What it tells you": "Raw tools. Results mean very little here."},
        {"Level": "Single-A", "Typical age": "19–21", "What it tells you": "First real test of contact and strike-throwing."},
        {"Level": "High-A", "Typical age": "21–22", "What it tells you": "Pitchers start using a third pitch. Weak hitters get exposed."},
        {"Level": "Double-A", "Typical age": "22–24", "What it tells you": "The biggest jump. Many scouts treat this as the true proving ground."},
        {"Level": "Triple-A", "Typical age": "24–26", "What it tells you": "A mix of prospects and experienced players waiting on a call."},
        {"Level": "MLB", "Typical age": "25+", "What it tells you": "The destination."},
    ]), hide_index=True, width="stretch")
    note_grid([
        ("Age against level is the whole game",
         "A 20-year-old holding his own in Double-A is a far better prospect than a 24-year-old dominating Single-A. "
         "Always read a stat line next to the player's age, which is on every player page."),
        ("Never compare across levels",
         "A .800 OPS in Single-A and a .800 OPS in Triple-A are not the same achievement. Compare a player with the peers "
         "in his own league, which is exactly what the percentile bars do."),
    ])

# ---------------------------------------------------------------- Focus
with focus:
    section("Learn them in this order", "The dictionary lists every metric the scanner collects. These few are the ones that earn their place first.")
    st.dataframe(pd.DataFrame([
        {"Stage": "1. Start", "For hitters": "On-base % (OBP)", "For pitchers": "Strikeout % (K%)",
         "Why it matters": "Reaching base is the single most valuable thing a hitter does. Strikeouts are the out a pitcher controls most."},
        {"Stage": "1. Start", "For hitters": "Strikeout % (K%)", "For pitchers": "Walk % (BB%)",
         "Why it matters": "How often the player wins or loses the at-bat before the ball is in play."},
        {"Stage": "2. Add", "For hitters": "Extra-base power (ISO)", "For pitchers": "K−BB%",
         "Why it matters": "ISO strips out singles and shows real power. K−BB% is the best quick summary of a pitcher."},
        {"Stage": "2. Add", "For hitters": "OPS", "For pitchers": "WHIP",
         "Why it matters": "Fast summaries. Good for sorting a list, too crude for a final judgement."},
        {"Stage": "3. Context", "For hitters": "BABIP", "For pitchers": "FIP (est)",
         "Why it matters": "Both separate luck and defence from the player's own doing."},
        {"Stage": "3. Context", "For hitters": "wOBA, wRC (est)", "For pitchers": "HR/9",
         "Why it matters": "Weighted measures that value each event properly instead of treating all hits alike."},
    ]), hide_index=True, width="stretch")
    section("How much data before you trust a number?",
            "Rates settle at very different speeds. These are rough public research guides, not hard rules.")
    st.dataframe(pd.DataFrame([
        {"Metric": "Strikeout % (K%)", "Roughly settles after": "60 plate appearances", "Read it as": "The fastest honest signal you get."},
        {"Metric": "Walk % (BB%)", "Roughly settles after": "120 plate appearances", "Read it as": "Patience shows up early too."},
        {"Metric": "Extra-base power (ISO)", "Roughly settles after": "160 plate appearances", "Read it as": "Power is real before average is."},
        {"Metric": "On-base % (OBP)", "Roughly settles after": "460 plate appearances", "Read it as": "Most of a full season."},
        {"Metric": "Batting average (AVG)", "Roughly settles after": "900+ plate appearances", "Read it as": "Noisy. Never judge a season on it alone."},
        {"Metric": "Pitcher K%", "Roughly settles after": "70 batters faced", "Read it as": "Trust it first."},
        {"Metric": "Pitcher BB%", "Roughly settles after": "170 batters faced", "Read it as": "Trust it second."},
        {"Metric": "ERA", "Roughly settles after": "A full season, and even then", "Read it as": "Defence and luck live in this number."},
    ]), hide_index=True, width="stretch")
    st.caption("The app warns you when a player is under about 100 plate appearances or 20 innings in your selection.")
    section("Mistakes to avoid", "Every one of these has cost a real analyst a real call.")
    note_grid([
        ("Judging a hot month", "Twenty good games is a mood, not a skill. Check the sample line at the top of the player page before anything else."),
        ("Trusting ERA", "A pitcher with a 2.50 ERA, few strikeouts and plenty of walks is usually about to get worse. Read K−BB% next to it."),
        ("Ignoring age", "The same line from a 19-year-old and a 25-year-old are two completely different reports."),
        ("Reading percentiles as grades", "An 80th percentile here means better than 80 of 100 players in this league and date range. It is not a 20–80 scouting grade."),
        ("Comparing across leagues", "Parks, weather and opponent quality differ. Keep the comparison inside one league."),
        ("Forgetting what is missing", "No exit velocity, no spin, no defence, no injuries. The numbers here start conversations; video and in-person looks finish them."),
    ], cols=3)

# ---------------------------------------------------------------- Dictionary
with dictionary:
    mode = st.segmented_control("Metric group", ["Batting", "Pitching"], default="Batting", key="guide_kind")
    kind = "pitching" if mode == "Pitching" else "batting"
    src = ctx.batting if kind == "batting" else ctx.pitching
    query = st.text_input("Search a metric or concept", placeholder="on-base, walks, ERA", key="guide_search")
    rows = [{"Metric": label(key), "Code": code(key), "Meaning": definition(key, kind),
             "How it is worked out": ("Whole innings plus the leftover outs (.1 or .2)." if key == "IP_str"
                                      else "Count of games played." if key == "G"
                                      else METRICS[key][2] if key in METRICS
                                      else "Added up across the selected games. If one game is missing it, the total stays unavailable."),
             "Better when": direction(key, kind)} for key in keys_for(kind)]
    guide = pd.DataFrame(rows)
    visible = guide[guide.astype(str).apply(lambda col: col.str.contains(query, case=False, regex=False)).any(axis=1)] if query else guide
    st.dataframe(visible, hide_index=True, width="stretch", height=440)
    st.caption(f"{len(guide)} metrics for {mode.lower()}. \"Better when\" says which direction is good, or Depends when it needs context.")
    download_button(guide, f"{kind}_metric_dictionary.csv", "Download metric dictionary", "guide_download")

# ---------------------------------------------------------------- Coverage
with coverage_tab:
    kind = "pitching" if st.session_state.get("guide_kind") == "Pitching" else "batting"
    src = ctx.batting if kind == "batting" else ctx.pitching
    section("What is actually available?", "Missing values are shown as missing, never as zero. Group follows the Metric dictionary tab.")
    coverage = [{"Metric": label(col.removeprefix(kind + "_")),
                 "Games with a value": int(src[col].notna().sum()) if col in src else 0,
                 "Games in selection": len(src),
                 "Coverage": (int(src[col].notna().sum()) if col in src else 0) / len(src) if len(src) else 0,
                 "Status": "Complete" if len(src) and (col in src and int(src[col].notna().sum()) == len(src))
                           else "Partial" if (col in src and int(src[col].notna().sum())) else "Not supplied"}
                for col in RAW_FIELDS[kind].values()]
    coverage_df = pd.DataFrame(coverage)
    stat_cards([{"label": "Metrics tracked", "value": len(coverage_df), "sub": "Every column the scanner collects"},
                {"label": "Complete here", "value": int(coverage_df["Status"].eq("Complete").sum()), "sub": "Present in every loaded game"},
                {"label": "Missing or partial", "value": int(coverage_df["Status"].ne("Complete").sum()), "sub": "Totals stay unavailable"}], cols=3)
    st.dataframe(coverage_df, hide_index=True, width="stretch", height=330,
                 column_config={"Coverage": st.column_config.ProgressColumn("Share of games", min_value=0, max_value=1, format="percent")})
    download_button(coverage_df, f"{kind}_coverage.csv", "Download availability report", "coverage_download")
    with st.expander("Browse the game rows behind this selection"):
        st.dataframe(without_internals(src), hide_index=True, width="stretch", height=350)
        download_button(src, f"{ctx.tag}_{ctx.league_id}_{kind}_all_fields.csv", "Download full selected dataset", "all_fields_download")

# ---------------------------------------------------------------- Rules
with rules:
    section("How the numbers are built", "So you can defend any figure in this app.")
    note_grid([
        ("League averages", "Pooled from the games in the selected seasons, league and dates, so they can differ from official league "
                            "numbers. Percentiles compare player rates, and ties share the middle rank."),
        ("Estimates", "wOBA and the run-creation index use fixed weights. The OPS index has no park adjustment. FIP uses a constant "
                      "from the selected league. None of them are official adjusted stats."),
        ("Sums, then rates", "Hits and at-bats are added up first, then divided. Game averages are never averaged. Pitching uses outs, "
                             "so 5.2 innings is 5 innings and 2 outs."),
        ("What box scores miss", "Command, defensive range, exit velocity, spin, pitch shape and injury risk are not in this data."),
    ])
    st.markdown("Further reading: [MLB statistic glossary](https://www.mlb.com/glossary) · "
                "[FanGraphs wOBA methodology](https://library.fangraphs.com/offense/woba/) · "
                "[FanGraphs wRC methodology](https://library.fangraphs.com/offense/wrc/)")
