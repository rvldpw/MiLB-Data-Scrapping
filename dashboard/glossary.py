"""Human-readable metric definitions shared by charts, tables, and the guide."""
import re
from dashboard.metric_catalog import RAW_FIELDS

# key: label, explanation, calculation, format, better direction
METRICS = {
    "AVG": ("Batting average", "Hits per at-bat. A .300 average means 30 hits per 100 at-bats.", "H / AB", ".3f", "Higher"),
    "OBP": ("On-base percentage", "How often a hitter reaches by a hit, walk, or hit-by-pitch.", "(H + BB + HBP) / (AB + BB + HBP + SF)", ".3f", "Higher"),
    "SLG": ("Slugging", "Total bases per at-bat. Extra-base hits count more.", "TB / AB", ".3f", "Higher"),
    "OPS": ("On-base + slugging", "A quick combined view of reaching base and hitting for power.", "OBP + SLG", ".3f", "Higher"),
    "ISO": ("Extra-base power", "Extra bases per at-bat, beyond the first base on each hit.", "SLG − AVG", ".3f", "Higher"),
    "BABIP": ("Batting average on balls in play", "Hits on balls put in play, excluding home runs. Context matters; higher is not automatically better skill.", "(H − HR) / (AB − SO − HR + SF)", ".3f", "Context"),
    "wOBA": ("Estimated weighted on-base average", "Values each offensive event differently. This estimate uses fixed weights, not season-specific MiLB weights.", "(.690×uBB + .722×HBP + .888×1B + 1.271×2B + 1.616×3B + 2.101×HR) / (AB + uBB + SF + HBP)", ".3f", "Higher"),
    "wRC_est": ("Estimated run-creation index", "100 is the loaded cohort baseline. Not official wRC+: no park adjustment and fixed approximate weights.", "100 × [((wOBA − cohort wOBA) / 1.22) + cohort R/PA] / cohort R/PA", ".0f", "Higher"),
    "OPS_index": ("Unadjusted OPS index", "100 is the loaded cohort baseline. This is not park-adjusted OPS+.", "100 × (OBP/cohort OBP + SLG/cohort SLG − 1)", ".0f", "Higher"),
    "BB_pct": ("Walk rate", "Walks per plate appearance for hitters, or per batter faced for pitchers.", "BB / PA (batting); BB / BF (pitching)", ".1%", "Context"),
    "K_pct": ("Strikeout rate", "Strikeouts per plate appearance for hitters, or per batter faced for pitchers.", "SO / PA (batting); SO / BF (pitching)", ".1%", "Context"),
    "SB_pct": ("Steal success rate", "Successful steals as a share of steal attempts.", "SB / (SB + CS)", ".1%", "Higher"),
    "ERA": ("Earned run average", "Earned runs allowed per nine innings. Lower means fewer earned runs allowed.", "27 × ER / outs", ".2f", "Lower"),
    "RA9": ("Runs allowed per nine", "All runs allowed per nine innings, including unearned runs.", "27 × R / outs", ".2f", "Lower"),
    "WHIP": ("Walks + hits per inning", "How many walks and hits a pitcher allows per inning.", "3 × (BB + H) / outs", ".2f", "Lower"),
    "K9": ("Strikeouts per nine", "Strikeouts scaled to nine innings.", "27 × SO / outs", ".1f", "Higher"),
    "BB9": ("Walks per nine", "Walks allowed scaled to nine innings.", "27 × BB / outs", ".1f", "Lower"),
    "HR9": ("Home runs per nine", "Home runs allowed scaled to nine innings.", "27 × HR / outs", ".2f", "Lower"),
    "H9": ("Hits per nine", "Hits allowed scaled to nine innings.", "27 × H / outs", ".1f", "Lower"),
    "K_BB_pct": ("Strikeout minus walk rate", "The gap between strikeouts and walks, per batter faced. Higher means more strikeouts relative to walks.", "(SO − BB) / BF", ".1%", "Higher"),
    "Strike_pct": ("Strike rate", "Recorded strikes as a share of all pitches. This is not zone percentage or first-pitch strike percentage.", "PI_strikes / PI", ".1%", "Context"),
    "FIP_est": ("Cohort-adjusted FIP", "Uses home runs, walks, hit batters and strikeouts. The constant is estimated from the loaded cohort.", "(13×HR + 3×(BB + HBP) − 2×SO) / IP + cohort constant", ".2f", "Lower"),
    "IP": ("Innings pitched", "Displayed in baseball notation: 5.2 means five innings and two outs, not 5.2 decimal innings.", "outs / 3; display full innings.remainder outs", "innings", "Context"),
    "BA": ("Opponent batting average", "Hits allowed per opponent at-bat.", "H / AB", ".3f", "Lower"),
    "W_pct": ("Decision win rate", "Wins as a share of wins and losses credited to the pitcher.", "W / (W + L)", ".1%", "Context"),
    "SO/BB": ("Strikeout-to-walk ratio", "Strikeouts for each walk allowed. Undefined when there are no walks.", "SO / BB", ".2f", "Higher"),
    "BB/SO": ("Walk-to-strikeout ratio", "Walks for each strikeout recorded.", "BB / SO", ".2f", "Lower"),
    "PI/PA": ("Pitches per batter faced", "Pitching workload per batter faced.", "PI / BF", ".2f", "Context"),
    "PI/IP": ("Pitches per inning", "Pitching workload per inning recorded.", "3 × PI / outs", ".1f", "Context"),
    "HR/PA": ("Home runs per batter faced", "Home runs allowed per batter faced.", "HR / BF", ".1%", "Lower"),
    "GO/AO": ("Ground-out to air-out ratio", "The balance of recorded ground outs and air outs.", "GO / AO", ".2f", "Context"),
}
COUNT_NAMES = {
    "G": "Games", "PA": "Plate appearances", "AB": "At-bats", "H": "Hits", "1B": "Singles", "2B": "Doubles",
    "3B": "Triples", "HR": "Home runs", "RBI": "Runs batted in", "R": "Runs", "BB": "Walks",
    "IBB": "Intentional walks", "SO": "Strikeouts", "TB": "Total bases", "HBP": "Hit by pitch",
    "SB": "Stolen bases", "CS": "Caught stealing", "SH": "Sacrifice bunts", "SF": "Sacrifice flies",
    "W": "Wins", "L": "Losses", "GS": "Games started", "GF": "Games finished", "CG": "Complete games",
    "QS": "Quality starts", "SHO": "Shutouts", "SVO": "Save opportunities", "SV": "Saves", "HLD": "Holds",
    "BS": "Blown saves", "outs": "Outs recorded", "BF": "Batters faced", "ER": "Earned runs", "BK": "Balks",
    "GiDP": "Grounded into double plays", "GiDP_Opp": "Double-play opportunities", "CI": "Catcher interference",
    "IR": "Inherited runners", "IRS": "Inherited runners scored", "BqR": "Bequeathed runners", "BqRS": "Bequeathed runners scored",
    "RS": "Run support", "PK": "Pickoffs", "FH": "Fly-ball hits", "PH": "Pop-up hits", "LH": "Line-drive hits",
    "FO": "Fly outs", "GO": "Ground outs", "AO": "Air outs", "PO": "Pop outs", "LO": "Line outs",
    "PI": "Pitches thrown", "PI_strikes": "Strikes thrown", "WP": "Wild pitches", "XBH": "Extra-base hits",
    "LOB": "Runners left on base", "ground_hits": "Ground-ball hits", "fly_hits": "Fly-ball hits",
    "pop_hits": "Pop-up hits", "line_hits": "Line-drive hits", "pitches_faced": "Pitches faced",
    "swings": "Swings", "whiffs": "Swings and misses", "balls_in_play": "Balls in play",
    "reached_on_error": "Reached on error", "walkoffs": "Walk-offs", "total_swings": "Opponent swings",
    "swing_and_misses": "Opponent swings and misses", "pop_outs": "Pop outs", "line_outs": "Line outs",
    "IP_str": "Innings pitched (source notation)",
}


def label(key):
    return METRICS[key][0] if key in METRICS else COUNT_NAMES.get(key, key.replace("_", " ").capitalize())


def definition(key, kind="batting"):
    if key in METRICS:
        return METRICS[key][1]
    text = label(key) + " recorded in the selected games."
    if kind == "pitching" and key in ("H", "R", "HR", "BB", "2B", "3B", "TB", "SB", "CS"):
        text = label(key) + " allowed in the selected pitching appearances."
    return text


def direction(key, kind):
    if key == "K_pct":
        return "Lower" if kind == "batting" else "Higher"
    if key == "BB_pct":
        return "Higher" if kind == "batting" else "Lower"
    if kind == "pitching" and key in ("OBP", "SLG", "OPS", "ISO"):
        return "Lower"
    return METRICS.get(key, (None, None, None, None, "Context"))[4]


def keys_for(kind):
    counts = [c.removeprefix(kind + "_") for c in RAW_FIELDS[kind].values()]
    rates = (["1B", "AVG", "OBP", "SLG", "OPS", "ISO", "BABIP", "BB_pct", "K_pct", "SB_pct", "GO/AO", "wOBA", "wRC_est", "OPS_index"]
             if kind == "batting" else ["IP", "ERA", "RA9", "WHIP", "K9", "BB9", "HR9", "H9", "K_pct", "BB_pct", "K_BB_pct", "Strike_pct", "FIP_est", "W_pct", "SO/BB", "BB/SO", "BABIP", "BA", "OBP", "SLG", "OPS", "ISO", "PI/PA", "HR/PA", "PI/IP"])
    return list(dict.fromkeys(counts + rates))
