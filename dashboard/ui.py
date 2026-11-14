"""Farmboard visual language: a warm, printed-scorebook look on native Streamlit.

Paper-cream ground, infield-green primary, clay (infield dirt) for contrast, one
serif for headlines and a plain sans with tabular figures for data.
"""
from html import escape
import numpy as np
import pandas as pd
import streamlit as st

from dashboard.glossary import METRICS, COUNT_NAMES, label, code, definition, keys_for, direction
from dashboard.metrics import innings_text

INK = "#14231b"
MUTED = "#566659"
ACCENT = "#147a4b"      # grass
BAD = "#e0682d"         # clay
WARN = "#d9962b"        # gold
BLUE = "#1f4e8c"        # navy
GOOD = ACCENT
PAPER = "#f3f6f0"
CARD = "#ffffff"
LINE = "#d9e1d4"
GRID = "#e6ebe1"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap');
:root { --ink:#14231b; --muted:#566659; --grass:#147a4b; --grass-soft:#dcf1e3; --clay:#e0682d; --clay-soft:#fde5d6;
        --gold:#d9962b; --gold-soft:#fff1c9; --paper:#f3f6f0; --card:#ffffff; --line:#d9e1d4;
        --serif:'Newsreader',Georgia,'Times New Roman',serif; --sans:'IBM Plex Sans','Segoe UI',system-ui,sans-serif; }
html, body, .stApp, .stApp :where(p,li,label,input,textarea,select,button,td,th,a,span,div):not([data-testid="stIconMaterial"]) { font-family:var(--sans); }
[data-testid="stIconMaterial"] { font-family:'Material Symbols Rounded'!important; }
.stApp { background:var(--paper); color:var(--ink); }
[data-testid="stHeader"] { background:rgba(243,246,240,.94); border-bottom:1px solid var(--line); }
[data-testid="stSidebar"] { background:#123f31; border-right:1px solid var(--line); }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color:#b9cdc1; }
[data-testid="stSidebar"] h3 { font-family:var(--serif)!important; color:#ffffff!important; font-size:1.3rem!important; margin-bottom:.1rem; }
[data-testid="stSidebar"] [data-testid="stExpander"] { background:#185a43; border-color:#2a6650!important; }
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color:#eef4ec; }
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span, [data-testid="stSidebar"] [data-testid="stIconMaterial"] { color:#eef4ec; }
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover { background:rgba(255,255,255,.08); }
[data-testid="stSidebar"] [data-testid="stTooltipIcon"] svg { color:#b9cdc1; stroke:#b9cdc1; }
[data-testid="stSidebar"] .stButton button p, [data-testid="stSidebar"] [data-baseweb="select"] [data-testid="stIconMaterial"],
[data-testid="stSidebar"] [data-baseweb="input"] [data-testid="stIconMaterial"] { color:var(--ink); }
.block-container { max-width:1400px; padding:5rem 2.6rem 3.5rem; }
h1,h2,h3,h4 { font-family:var(--serif)!important; color:var(--ink)!important; letter-spacing:-.01em; }
h3 { font-size:1.2rem!important; }
p,li { line-height:1.6; }
[data-testid="stCaptionContainer"], .stCaption { color:var(--muted); }
[data-testid="stVerticalBlockBorderWrapper"] > div { border-color:var(--line)!important; border-radius:8px!important; }
[data-testid="stTabs"] [role="tab"] { font-weight:500; padding:.55rem .1rem; margin-right:1.3rem; }
[data-testid="stTabs"] [role="tablist"] { border-bottom:1px solid var(--line); }
[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:6px; overflow:hidden; }
[data-testid="stExpander"] { border:1px solid var(--line)!important; border-radius:8px!important; background:var(--card); }
[data-testid="stDownloadButton"] button, .stButton button { border-radius:6px; font-weight:500; }
button:focus-visible, a:focus-visible, input:focus-visible, [role="tab"]:focus-visible { outline:3px solid var(--clay)!important; outline-offset:2px; }

[data-testid="stAlert"] > div { background:var(--card)!important; color:var(--ink)!important; border:1px solid var(--line); border-radius:8px; }
.pagehead { padding:.2rem 0 1rem; border-bottom:1px solid var(--line); margin-bottom:.9rem; }
.pagehead h1 { font-size:2.35rem!important; font-weight:600!important; line-height:1.1!important; margin:0 0 .35rem!important; padding:0!important; }
.pagehead h1::after { content:''; display:block; width:44px; height:4px; background:var(--clay); border-radius:2px; margin-top:.55rem; }
.pagehead p { margin:0; color:var(--muted); font-size:1rem; max-width:720px; }
.section-title { margin:1.5rem 0 .8rem; }
.section-title h2 { font-size:1.4rem!important; font-weight:600!important; margin:0 0 .15rem!important; padding:0!important; }
.section-title p { margin:0; color:var(--muted); font-size:.87rem; }

.scope { display:flex; flex-wrap:wrap; margin:.1rem 0 1rem; border:1px solid var(--line); border-radius:8px; background:var(--card); overflow:hidden; }
.scope > div { padding:.5rem .95rem; border-right:1px solid var(--line); min-width:0; }
.scope > div:last-child { border-right:0; }
.scope small { display:block; color:var(--muted); font-size:.68rem; letter-spacing:.06em; text-transform:uppercase; font-weight:500; }
.scope b { font-weight:600; font-size:.88rem; font-variant-numeric:tabular-nums; white-space:nowrap; }

.metric-strip { display:grid; grid-template-columns:repeat(var(--n,4),minmax(0,1fr)); background:var(--card); border:1px solid var(--line);
  border-radius:10px; margin:.25rem 0 1.1rem; box-shadow:0 1px 2px rgba(20,35,27,.05); overflow:hidden; }
.metric-cell { min-width:0; padding:.85rem 1.1rem .9rem; border-left:1px solid var(--line); display:flex; flex-direction:column; gap:.1rem; }
.metric-cell:first-child { border-left:0; }
.metric-name { color:var(--muted); font-size:.7rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.metric-value { font-variant-numeric:tabular-nums; font-size:clamp(1.45rem,1.15rem + .9vw,1.85rem); font-weight:600; letter-spacing:-.025em;
  line-height:1.15; color:var(--ink); overflow-wrap:anywhere; }
.metric-value.txt { font-size:1.05rem; font-weight:550; letter-spacing:0; line-height:1.35; }
.metric-note { color:var(--muted); font-size:.75rem; line-height:1.4; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.delta { display:inline-flex; align-items:center; gap:.25rem; font-size:.73rem; font-weight:600; border-radius:4px; padding:.1rem .4rem;
  background:#eef1ec; color:var(--muted); width:fit-content; font-variant-numeric:tabular-nums; }
.delta.good { background:var(--grass-soft); color:#0b5a37; }
.delta.bad { background:var(--clay-soft); color:#9c4418; }
.note { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:.95rem 1.1rem; margin:.3rem 0 .8rem; }
.note h4 { margin:0 0 .3rem!important; font-size:1.02rem!important; font-weight:600!important; }
.note p { margin:0; font-size:.88rem; line-height:1.6; color:#2b3d33; }
.note-grid { display:grid; grid-template-columns:repeat(var(--n,2),minmax(0,1fr)); gap:.75rem; margin:.3rem 0 1.1rem; align-items:stretch; }
.note-grid .note { margin:0; height:100%; }
.steps { counter-reset:step; display:grid; gap:.55rem; margin:.4rem 0 1.1rem; }
.step { position:relative; background:var(--card); border:1px solid var(--line); border-radius:10px; padding:.8rem 1rem .8rem 3rem; }
.step::before { counter-increment:step; content:counter(step); position:absolute; left:.85rem; top:.8rem; width:1.5rem; height:1.5rem;
  border-radius:50%; background:var(--grass); color:#fff; font-size:.8rem; font-weight:700; display:grid; place-items:center; }
.step b { display:block; font-size:.95rem; margin-bottom:.15rem; }
.step span { color:var(--muted); font-size:.87rem; line-height:1.55; }
@media(max-width:700px){ .note-grid{grid-template-columns:1fr;} }
.coverage { display:flex; gap:.6rem; align-items:baseline; padding:.6rem .9rem; background:var(--gold-soft); color:#6b4a00; border-radius:6px; font-size:.82rem; margin:0 0 1rem; }
.coverage b { font-weight:600; white-space:nowrap; }
.identity { display:flex; align-items:flex-start; gap:1.3rem; margin:.5rem 0 1.1rem; }
.identity > div:last-child { flex:1; min-width:0; }
.identity .facts { display:grid; grid-template-columns:repeat(auto-fit,minmax(215px,1fr)); gap:.7rem 0; }
.identity .facts .fact { padding:0 1rem 0 0; border-left:0; }
.identity .facts .fact span { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.identity-photo { flex-shrink:0; line-height:0; }
.identity h1 { font-size:2.2rem!important; margin:0 0 .55rem!important; line-height:1.1!important; padding:0!important; }
.facts { display:flex; flex-wrap:wrap; gap:.6rem 0; }
.facts.card { display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); background:var(--card); border:1px solid var(--line);
  border-radius:10px; padding:.8rem 0; margin:.25rem 0 1.1rem; box-shadow:0 1px 2px rgba(20,35,27,.05); row-gap:.95rem; }
.facts.card .fact { padding:0 1.1rem; border-left:1px solid var(--line); }
.facts.card .fact:first-child { padding-left:1.1rem; border-left:0; }
.fact { padding:0 1.15rem; border-left:1px solid var(--line); min-width:0; }
.fact:first-child { padding-left:0; border-left:0; }
.fact small { display:block; color:var(--muted); font-size:.68rem; letter-spacing:.06em; text-transform:uppercase; font-weight:500; margin-bottom:.15rem; }
.fact span { font-size:.95rem; font-weight:600; display:block; }
.fact .sub { display:block; color:var(--muted); font-size:.76rem; font-weight:400; margin-top:.1rem; }
.lvl, .fact .lvl { display:inline-block; border-radius:4px; padding:.12rem .55rem; font-size:.78rem; font-weight:600; white-space:nowrap; }
.subtle { color:var(--muted); font-size:.82rem; }
.footer { margin-top:2.5rem; padding-top:.9rem; border-top:1px solid var(--line); color:var(--muted); font-size:.76rem; }
.club-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(205px,1fr)); gap:.7rem; margin:.3rem 0 1.1rem; }
.club { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:.75rem .9rem .55rem; min-width:0; box-shadow:0 1px 2px rgba(20,35,27,.05); }
.club-head { display:flex; align-items:center; gap:.5rem; min-width:0; }
.club-head b { font-size:.82rem; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.club-line { display:flex; align-items:center; justify-content:space-between; gap:.5rem; margin:.35rem 0 .3rem; }
.club-record { font-size:1.25rem; font-weight:600; font-variant-numeric:tabular-nums; letter-spacing:-.02em; }
.spark { display:block; width:100%; height:34px; }
.key-facts { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); background:var(--card); border:1px solid var(--line);
  border-radius:10px; margin:.25rem 0 1.1rem; overflow:hidden; }
.key-facts > div { padding:.6rem .9rem; border-right:1px solid var(--line); border-bottom:1px solid var(--line); margin:0 -1px -1px 0; min-width:0; }
.key-facts small { display:block; color:var(--muted); font-size:.68rem; letter-spacing:.06em; text-transform:uppercase; font-weight:600;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.key-facts b { font-size:1.05rem; font-weight:600; font-variant-numeric:tabular-nums; white-space:nowrap; }
@media(max-width:900px){ .block-container{padding:4.5rem 1rem 3rem;} .metric-strip{grid-template-columns:repeat(2,minmax(0,1fr));} .metric-cell:nth-child(odd){border-left:0;} .metric-cell:nth-child(n+3){border-top:1px solid var(--line);} .metric-cell{padding:.75rem .9rem;} .metric-cell:last-child:nth-child(odd){grid-column:1/-1;} .scope > div{flex:1 1 40%; border-bottom:1px solid var(--line);} .scope > div:nth-child(n+3){flex-basis:100%;} }
@media(max-width:600px){ .pagehead h1,.identity h1{font-size:1.75rem!important;} .metric-value{font-size:1.5rem;} .identity{align-items:flex-start;gap:.75rem;} .fact{padding:0 .8rem 0 0;border-left:0;flex:1 1 45%;} .metric-cell{padding:.75rem .8rem;}
  .key-facts{grid-template-columns:repeat(2,minmax(0,1fr));} .facts.card{grid-template-columns:repeat(2,minmax(0,1fr));} .facts.card .fact{border-left:0;}
  .identity{display:grid; grid-template-columns:auto minmax(0,1fr); align-items:center; gap:.7rem .8rem;} .identity > div:last-child{display:contents;}
  .identity h1{margin:0!important;} .identity-photo img{width:56px!important; height:56px!important;}
  .identity .facts{grid-column:1 / -1; grid-template-columns:1fr; gap:0; border-top:1px solid var(--line);}
  .identity .facts .fact{display:flex; justify-content:space-between; align-items:baseline; gap:.9rem; padding:.4rem 0; border-bottom:1px solid var(--line);}
  .identity .facts .fact small{margin:0; flex-shrink:0;} .identity .facts .fact > span{text-align:right; min-width:0;}
  .club-grid{grid-template-columns:1fr; gap:.45rem;} .club{display:grid; grid-template-columns:minmax(0,1fr) auto; column-gap:.75rem; align-items:center; padding:.55rem .8rem;}
  .club-line{margin:0; grid-column:2; grid-row:1;} .club .spark{grid-column:1 / -1; height:26px; margin-top:.25rem;} }
@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important;}}
</style>
"""


def e(value):
    return escape(str(value), quote=True)


def inject_mobile_css():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title, subtitle=""):
    st.markdown(f"<div class='pagehead'><h1>{e(title)}</h1><p>{e(subtitle)}</p></div>", unsafe_allow_html=True)


def section(title, subtitle=""):
    st.markdown(f"<div class='section-title'><h2>{e(title)}</h2><p>{e(subtitle)}</p></div>", unsafe_allow_html=True)


def stat_cards(cards, cols=4):
    """Headline numbers. Each card: label, value, optional sub and delta (text, tone)."""
    items = ""
    for c in cards:
        value, delta = str(c["value"]), c.get("delta")
        chip = f"<span class='delta {e(delta[1] or '')}'>{e(delta[0])}</span>" if delta else ""
        note = f"<div class='metric-note'>{e(c['sub'])}</div>" if c.get("sub") else ""
        items += (f"<div class='metric-cell'><div class='metric-name'>{e(c['label'])}</div>"
                  f"<div class='metric-value{' txt' if len(value) > 7 else ''}'>{e(value)}</div>{chip}{note}</div>")
    st.markdown(f"<div class='metric-strip' style='--n:{cols}'>{items}</div>", unsafe_allow_html=True)


def facts_row(items):
    """Descriptive details (a bio, a scope). Small labels, readable text, never headline numerals."""
    cells = "".join(f"<div class='fact'><small>{e(k)}</small><span>{e(v)}</span>"
                    + (f"<span class='sub'>{e(sub)}</span>" if sub else "") + "</div>"
                    for k, v, sub in items)
    st.markdown(f"<div class='facts card'>{cells}</div>", unsafe_allow_html=True)


def league_delta(value, league, key, kind):
    """How far this value sits from the league, and whether that is the good side."""
    if value is None or league is None or pd.isna(value) or pd.isna(league) or key == "IP":
        return None
    gap = value - league
    if fmt(abs(gap), key) == fmt(0, key):  # a gap too small to show is no gap
        return ("level with league", None)
    wanted = direction(key, kind)
    tone = None if wanted not in ("Higher", "Lower") else ("good" if (gap > 0) == (wanted == "Higher") else "bad")
    return (f"{fmt(abs(gap), key)} {'above' if gap > 0 else 'below'} league", tone)


def sparkline(values, width=120, height=30):
    """An inline line for a short series around zero: green when it ends at or above zero, clay below."""
    values = [float(v) for v in values]
    if len(values) < 2:
        return "<svg class='spark' viewBox='0 0 120 30'></svg>"
    low, high = min(values + [0]), max(values + [0])
    scale = (height - 4) / ((high - low) or 1)
    y = lambda v: height - 2 - (v - low) * scale
    points = " ".join(f"{i * width / (len(values) - 1):.1f},{y(v):.1f}" for i, v in enumerate(values))
    color = ACCENT if values[-1] >= 0 else BAD
    return (f"<svg class='spark' viewBox='0 0 {width} {height}' preserveAspectRatio='none' role='img' aria-label='Wins minus losses through the season'>"
            f"<line x1='0' x2='{width}' y1='{y(0):.1f}' y2='{y(0):.1f}' stroke='#c9d3c5' stroke-dasharray='3 3' vector-effect='non-scaling-stroke'/>"
            f"<polyline points='{points}' fill='none' stroke='{color}' stroke-width='2' stroke-linejoin='round' vector-effect='non-scaling-stroke'/></svg>")


def club_cards(rows):
    """One card per club: logo, name, record, run difference and the path of its season. `logo` is trusted markup."""
    items = ""
    for r in rows:
        tone = "good" if r["margin"] > 0 else "bad" if r["margin"] < 0 else ""
        items += (f"<div class='club'><div class='club-head'>{r['logo']}<b title='{e(r['name'])}'>{e(r['name'])}</b></div>"
                  f"<div class='club-line'><span class='club-record'>{e(r['record'])}</span>"
                  f"<span class='delta {tone}'>{e(r['diff'])}</span></div>{sparkline(r['path'])}</div>")
    st.markdown(f"<div class='club-grid'>{items}</div>", unsafe_allow_html=True)


def key_facts(items):
    """A tidy grid of small labelled figures: every cell one line, all the same height."""
    cells = "".join(f"<div><small>{e(k)}</small><b>{e(v)}</b></div>" for k, v in items)
    st.markdown(f"<div class='key-facts'>{cells}</div>", unsafe_allow_html=True)


def metric_columns(columns, extra=None):
    """Short conventional headers (OPS, K%) with the full name on hover, so a wide table fits the page."""
    config = {c: st.column_config.Column(code(c), help=label(c)) for c in columns if c in METRICS or c in COUNT_NAMES}
    return {**config, **(extra or {})}


# Card titles short enough to stay on one line on a phone.
CARD_NAMES = {"OPS": "OPS", "OBP": "On-base %", "ISO": "Power (ISO)", "K_pct": "Strikeout rate", "BB_pct": "Walk rate",
              "ERA": "ERA", "WHIP": "WHIP", "K_BB_pct": "K minus BB %", "IP": "Innings", "AVG": "Average", "SLG": "Slugging %"}


def card_name(key):
    return CARD_NAMES.get(key, code(key))


def scope_bar(items):
    cells = "".join(f"<div><small>{e(k)}</small><b>{e(v)}</b></div>" for k, v in items)
    st.markdown(f"<div class='scope'>{cells}</div>", unsafe_allow_html=True)


def brief(title, text):
    st.markdown(f"<div class='note'><h4>{e(title)}</h4><p>{e(text)}</p></div>", unsafe_allow_html=True)


def note_grid(cards, cols=2):
    """Equal-height explanation cards, so a row never ends ragged."""
    items = "".join(f"<div class='note'><h4>{e(t)}</h4><p>{e(body)}</p></div>" for t, body in cards)
    st.markdown(f"<div class='note-grid' style='--n:{cols}'>{items}</div>", unsafe_allow_html=True)


def steps(items):
    """A numbered routine."""
    cells = "".join(f"<div class='step'><b>{e(t)}</b><span>{e(body)}</span></div>" for t, body in items)
    st.markdown(f"<div class='steps'>{cells}</div>", unsafe_allow_html=True)


def coverage(text):
    st.markdown(f"<div class='coverage'><b>Note</b><span>{e(text)}</span></div>", unsafe_allow_html=True)


def identity(title, image_html="", facts=(), now_html="", now_sub=""):
    """Header: photo, name, then labelled facts. `now_html` is trusted markup (a level chip)."""
    photo = f"<div class='identity-photo'>{image_html}</div>" if image_html else ""
    cells = "".join(f"<div class='fact'><small>{e(k)}</small><span>{e(v)}</span></div>" for k, v in facts)
    if now_html:
        sub = f"<span class='sub'>{e(now_sub)}</span>" if now_sub else ""
        cells += f"<div class='fact'><small>Today</small><span>{now_html}{sub}</span></div>"
    st.markdown(f"<div class='identity'>{photo}<div><h1>{e(title)}</h1><div class='facts'>{cells}</div></div></div>", unsafe_allow_html=True)


def fmt(value, key=None, digits=2):
    if value is None or pd.isna(value) or (isinstance(value, (float, np.floating)) and not np.isfinite(value)):
        return "N/A"
    if key == "IP":
        return innings_text(round(value * 3))
    pattern = METRICS[key][3] if key in METRICS else (",.0f" if key else f".{digits}f")
    return format(value, pattern)


PCT_NAMES = {"BB_pct": "Walk %", "K_pct": "Strikeout %", "K_BB_pct": "K minus BB %"}
HEADERS = {**PCT_NAMES, "G": "Games", "PA": "Plate appearances", "AB": "At-bats", "H": "Hits", "HR": "Home runs", "RBI": "Runs batted in", "BB": "Walks",
           "SO": "Strikeouts", "AVG": "Batting avg", "OBP": "On-base %", "SLG": "Slugging %", "IP": "Innings", "GS": "Starts", "K9": "K per 9", "BB9": "BB per 9",
           "Org": "Parent club today", "Org today": "Parent club today", "TB": "Total bases"}


# Dataset columns that are not metrics, named the way the app talks about them.
INTERNAL_FIELDS = ("raw_stats_json", "source_url", "fetched_at", "sport_id", "fip_raw", "fip_const")


def without_internals(df):
    """Drop the plumbing columns readers should never see."""
    return df.drop(columns=[c for c in df.columns if c in INTERNAL_FIELDS], errors="ignore")


FIELD_NAMES = {"game_pk": "Game ID", "game_date": "Game date", "player_id": "Player ID", "team_id": "Team ID",
               "league_id": "League ID", "sport_id": "Level ID", "pos_group": "Position group",
               "raw_stats_json": "Raw source JSON", "source_url": "Source URL", "game_type": "Game type", "is_home": "Home game", "team_level": "Level",
               "player_full_name": "Player", "team_name": "Team", "opponent_name": "Opponent",
               "league_name": "League", "fetched_at": "Fetched at", "IP_str": "Innings (source notation)"}


def field_name(column, kind):
    """A dataset column such as batting_PA shown as a person would say it."""
    column = str(column)
    if column in FIELD_NAMES:
        return FIELD_NAMES[column]
    bare = column.removeprefix(kind + "_")
    if bare in FIELD_NAMES:
        return FIELD_NAMES[bare]
    if bare in METRICS or bare in COUNT_NAMES:
        return label(bare)
    return bare.replace("_", " ").capitalize()


def plain(df):
    """Readable column headers. An internal key never reaches the screen."""
    return df.rename(columns=lambda c: HEADERS.get(c) or (label(c) if "_" in str(c) and not str(c).endswith("_id") else c))


def pretty(df):
    """Display copy of a metrics table: formatted numbers, readable percentage headers."""
    out = df.copy()
    for column in out.columns:
        if pd.api.types.is_numeric_dtype(out[column]):
            out[column] = out[column].map(lambda v, k=column: fmt(v, k))
    return plain(out)


def open_player(player_id, kind):
    """Send the reader to the Player lab with this player already chosen."""
    st.session_state["_goto_player"] = (int(player_id), kind)
    st.switch_page("pages/1_Player_Dashboard.py")


def jump_to_player(options, key, kind, label="Open a player"):
    """A name picker plus button, for opening someone straight from a table."""
    if not options:
        return
    picker, go, _ = st.columns([2, 1, 1], gap="medium", vertical_alignment="bottom")
    with picker:
        chosen = st.selectbox(label, list(options), format_func=options.get, key=key)
    with go:
        if st.button("Open player page", key=key + "_go", width="stretch", type="primary"):
            open_player(chosen, kind)


def chart(fig, key=None):
    # Only the picture button stays: zoom and pan tools cover the labels of small charts.
    st.plotly_chart(fig, width="stretch", theme=None, key=key,
                    config={"displaylogo": False, "responsive": True, "toImageButtonOptions": {"format": "png", "scale": 2},
                            "modeBarButtonsToRemove": ["zoom2d", "pan2d", "select2d", "lasso2d", "zoomIn2d", "zoomOut2d",
                                                       "autoScale2d", "resetScale2d"]})


def download_button(df, filename, label="Download table", key=None):
    st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"), file_name=filename, mime="text/csv", key=key)


def stat_sheet(line, context, kind):
    rows = []
    for key in keys_for(kind):
        effective = "IP" if key == "IP_str" else key
        value = line.get(effective, np.nan)
        is_rate = key in METRICS and key != "IP"
        rows.append({"Metric": label(key), "Code": code(key), "Value": fmt(value, effective),
                     "League rate": fmt(context.get(key), key) if is_rate else "Not comparable as a total",
                     "Read it as": definition(key, kind), "Direction": direction(key, kind),
                     "Availability": "Available" if pd.notna(value) else "Missing or undefined"})
    return pd.DataFrame(rows)


def sample_note(line, kind):
    count, unit = (line.get("PA", 0), "plate appearances") if kind == "batting" else (line.get("IP", 0), "innings")
    floor = 100 if kind == "batting" else 20
    if pd.isna(count) or count < floor:
        coverage(f"{fmt(count, 'PA' if kind == 'batting' else 'IP')} {unit} so far. Small sample.")


def metric_help(keys, kind):
    with st.expander("How to read these numbers"):
        for key in keys:
            st.markdown(f"**{label(key)}:** {definition(key, kind)}")


def footer():
    st.markdown("<div class='footer'>Farmboard. Game logs from the scanner, current levels from the MLB Stats API. Estimated metrics are labeled and missing values show as N/A.</div>", unsafe_allow_html=True)


def news_list(df):
    if df.empty:
        st.caption("No recent coverage found.")
        return
    for _, r in df.iterrows():
        when = r["published"]
        try:
            when = pd.to_datetime(when).strftime("%d %b %Y")
        except Exception:
            pass
        st.markdown(
            f"**[{e(r['title'])}]({r['link']})**  \n<span class='subtle'>{e(r['source'])}"
            + (f" · {e(when)}" if when else "") + "</span>",
            unsafe_allow_html=True,
        )
