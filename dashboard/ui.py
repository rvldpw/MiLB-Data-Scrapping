"""A restrained field-report visual language for the native Streamlit app."""
from html import escape
import numpy as np
import pandas as pd
import streamlit as st

from dashboard.glossary import METRICS, label, definition, keys_for, direction
from dashboard.metrics import innings_text

INK = "#1d323d"
MUTED = "#596c72"
ACCENT = "#176b56"
GOOD = ACCENT
BAD = "#ac4f2c"
WARN = "#93601d"
BLUE = "#547b95"
PAPER = "#f5f6f2"
LINE = "#dce2dd"

CSS = """
<style>
:root { --ink:#1d323d; --muted:#596c72; --green:#176b56; --line:#dce2dd; }
.stApp { background:#f5f6f2; color:var(--ink); font-family:'Avenir Next','Segoe UI',sans-serif; }
[data-testid="stHeader"] { background:rgba(245,246,242,.97); }
[data-testid="stSidebar"] { background:#edf0ea; border-right:1px solid var(--line); }
.block-container { max-width:1450px; padding:2.2rem 3rem 4rem; }
h1,h2,h3 { font-family:'Avenir Next','Segoe UI',sans-serif!important; color:var(--ink)!important; letter-spacing:-.035em; }
h1 { font-size:2.7rem!important; font-weight:650!important; line-height:1.12!important; }
h2 { font-size:1.5rem!important; } h3 { font-size:1.13rem!important; }
p,li { line-height:1.6; } .stCaption { color:var(--muted); }
[data-testid="stVerticalBlockBorderWrapper"] > div { border-color:var(--line)!important; border-radius:10px!important; }
[data-testid="stTabs"] button { font-size:.91rem; }
[data-testid="stDataFrame"] { border-radius:6px; }
button,a,input,select { transition:background-color .15s ease,box-shadow .15s ease; }
button:focus-visible,a:focus-visible,input:focus-visible { outline:3px solid #176b56!important; outline-offset:3px; }
.masthead { display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:.1rem 0 1.2rem; border-bottom:1px solid var(--line); margin-bottom:1rem; }
.brand { font-weight:750; font-size:1rem; letter-spacing:-.025em; color:var(--ink); }
.brand span { color:var(--green); margin-right:.5rem; font-weight:500; }
.edition { color:var(--muted); font-size:.78rem; }
.eyebrow { color:var(--green); font-size:.74rem; font-weight:700; letter-spacing:.11em; text-transform:uppercase; margin-bottom:.65rem; }
.page-intro { margin-bottom:.7rem; } .page-intro h1 { margin:0 0 .55rem; }
.page-intro p { color:var(--muted); max-width:760px; font-size:1rem; margin:0; }
.section-title { margin:1.15rem 0 .9rem; } .section-title h2 { margin:0 0 .25rem; }
.section-title p { margin:0; color:var(--muted); font-size:.88rem; }
.metric-strip { display:grid; grid-template-columns:repeat(var(--n,4),minmax(0,1fr)); border-top:1px solid var(--line); border-bottom:1px solid var(--line); margin:.4rem 0 .7rem; padding:.8rem 0; gap:0; }
.metric-cell { min-width:0; padding:0 1.35rem; border-left:1px solid var(--line); }
.metric-cell:first-child { padding-left:0; border-left:0; }
.metric-name { color:var(--muted); font-size:.8rem; font-weight:550; }
.metric-value { font-variant-numeric:tabular-nums; font-size:2rem; font-weight:650; letter-spacing:-.055em; line-height:1.3; margin:.2rem 0; color:var(--ink); }
.metric-note { color:var(--muted); font-size:.75rem; line-height:1.5; }
.brief { background:#e7eee8; border-left:3px solid var(--green); border-radius:0 7px 7px 0; padding:1.05rem 1.15rem; margin:.3rem 0 1rem; }
.brief h4 { margin:0 0 .4rem; color:var(--green); font-size:.9rem; font-weight:650; }
.brief p { margin:0; font-size:.9rem; line-height:1.65; }
.coverage { display:flex; gap:10px; align-items:flex-start; padding:.65rem .9rem; background:#eee9db; color:#634817; border-radius:5px; font-size:.79rem; margin:0 0 1.1rem; }
.identity { display:flex; align-items:center; gap:1.2rem; margin:.5rem 0 1rem; }
.identity-photo { flex-shrink:0; line-height:0; }
.identity .number { white-space:nowrap; flex-shrink:0; font-size:2rem; font-variant-numeric:tabular-nums; border-right:1px solid var(--line); padding-right:1rem; color:var(--green); }
.identity h1 { font-size:2.65rem!important; margin:0; } .identity p { margin:.4rem 0 0; color:var(--muted); }
.subtle { color:var(--muted); font-size:.82rem; }
.legend-rule { font-size:.77rem; color:var(--muted); padding:.2rem 0 .6rem; }
.footer { margin-top:2.5rem; padding-top:1rem; border-top:1px solid var(--line); color:var(--muted); font-size:.75rem; }
@media(max-width:900px){ .block-container{padding:1.5rem 1.3rem 3rem;} .metric-strip{grid-template-columns:repeat(2,minmax(0,1fr));row-gap:1.2rem;} .metric-cell:nth-child(odd){padding-left:0;border-left:0;} }
@media(max-width:600px){ h1,.identity h1{font-size:1.9rem!important;} .metric-value{font-size:1.6rem;} .masthead{align-items:flex-start;} .edition{max-width:120px;text-align:right;} .identity{align-items:flex-start;gap:.7rem;} .metric-cell{padding:0 .6rem;} }
@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important;}}
</style>
"""


def e(value):
    return escape(str(value), quote=True)


def inject_mobile_css():
    st.markdown(CSS, unsafe_allow_html=True)


def masthead():
    st.markdown("<div class='masthead'><div class='brand'><span>◈</span>MiLB Analyst Hub</div><div class='edition'>Game logs. Better questions.</div></div>", unsafe_allow_html=True)


def hero(icon, title, subtitle=""):
    st.markdown(f"<div class='page-intro'><div class='eyebrow'>{e(icon)}</div><h1>{e(title)}</h1><p>{e(subtitle)}</p></div>", unsafe_allow_html=True)


def section(icon, title, subtitle=""):
    st.markdown(f"<div class='section-title'><h2>{e(title)}</h2><p>{e(subtitle)}</p></div>", unsafe_allow_html=True)


def stat_cards(cards, cols=4):
    items = "".join(f"<div class='metric-cell'><div class='metric-name'>{e(c['label'])}</div><div class='metric-value'>{e(c['value'])}</div><div class='metric-note'>{e(c.get('sub',''))}</div></div>" for c in cards)
    st.markdown(f"<div class='metric-strip' style='--n:{cols}'>{items}</div>", unsafe_allow_html=True)


def brief(title, text):
    st.markdown(f"<div class='brief'><h4>{e(title)}</h4><p>{e(text)}</p></div>", unsafe_allow_html=True)


def coverage(text):
    st.markdown(f"<div class='coverage'><b>Coverage</b><span>{e(text)}</span></div>", unsafe_allow_html=True)


def identity(title, subtitle, number="", image_html="", badge_html=""):
    photo = f"<div class='identity-photo'>{image_html}</div>" if image_html else ""
    badge = f" {badge_html}" if badge_html else ""
    st.markdown(f"<div class='identity'>{photo}<div class='number'>{e(number)}</div><div><h1>{e(title)}</h1><p>{e(subtitle)}{badge}</p></div></div>", unsafe_allow_html=True)


def fmt(value, key=None, digits=2):
    if value is None or pd.isna(value) or (isinstance(value, (float, np.floating)) and not np.isfinite(value)):
        return "N/A"
    if key == "IP":
        return innings_text(round(value * 3))
    pattern = METRICS[key][3] if key in METRICS else (",.0f" if key else f".{digits}f")
    return format(value, pattern)


def chart(fig, key=None):
    st.plotly_chart(fig, width="stretch", theme=None, key=key,
                    config={"displaylogo": False, "responsive": True, "toImageButtonOptions": {"format": "png", "scale": 2}})


def download_button(df, filename, label="Download table", key=None):
    st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"), file_name=filename, mime="text/csv", key=key)


def stat_sheet(line, context, kind):
    rows = []
    for key in keys_for(kind):
        effective = "IP" if key == "IP_str" else key
        value = line.get(effective, np.nan)
        is_rate = key in METRICS and key != "IP"
        rows.append({"Metric": label(key), "Code": key, "Value": fmt(value, effective),
                     "Cohort rate": fmt(context.get(key), key) if is_rate else "Not comparable as a total",
                     "Read it as": definition(key, kind), "Direction": direction(key, kind),
                     "Availability": "Available" if pd.notna(value) else "Missing or undefined"})
    return pd.DataFrame(rows)


def sample_note(line, kind):
    count, unit = (line.get("PA", 0), "plate appearances") if kind == "batting" else (line.get("IP", 0), "innings")
    floor = 100 if kind == "batting" else 20
    if pd.isna(count) or count < floor:
        coverage(f"{fmt(count, 'PA' if kind == 'batting' else 'IP')} {unit} in this selection. Treat this as an early observation, not a stable skill estimate.")


def metric_help(keys, kind):
    with st.expander("How to read these numbers"):
        for key in keys:
            st.markdown(f"**{label(key)}:** {definition(key, kind)}")


def footer():
    st.markdown("<div class='footer'>MiLB Analyst Hub · Results describe games in the selected data. Estimated metrics are identified; missing values stay N/A.</div>", unsafe_allow_html=True)


def news_list(df):
    if df.empty:
        st.caption("No recent coverage found for this search.")
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
