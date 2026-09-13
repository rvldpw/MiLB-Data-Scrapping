"""Shared design system: theme CSS, and small HTML component builders
(hero banners, stat cards, section headers, scrollable tables) so all three
pages look like one product instead of default Streamlit boxes.

Colors match .streamlit/config.toml (dark navy + orange accent). Semantic
colors (green=good/red=bad) are separate from the orange brand accent so a
"below average" badge never gets confused with the theme color.
"""
import base64

import pandas as pd
import streamlit as st

INK = "#0b1220"
CARD = "#141d30"
CARD_BORDER = "#253150"
MUTED = "#8b96ad"
ACCENT = "#f97316"
ACCENT_2 = "#fb923c"
GOOD = "#22c55e"
BAD = "#ef4444"
WARN = "#f59e0b"
BLUE = "#38bdf8"

THEME_CSS = f"""
<style>
.block-container {{ padding-top: 1.4rem; max-width: 1300px; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}
hr {{ border-color: {CARD_BORDER} !important; }}

/* ---- hero banner ---- */
.hero {{
  background: linear-gradient(120deg, #1a2540 0%, #0f1830 60%, #0b1220 100%);
  border: 1px solid {CARD_BORDER}; border-radius: 16px;
  padding: 22px 26px; margin-bottom: 18px;
  display: flex; align-items: center; gap: 16px;
}}
.hero .hero-icon {{ font-size: 2.4rem; line-height: 1; }}
.hero h1 {{ margin: 0; font-size: 1.7rem; color: #f8fafc; }}
.hero p {{ margin: 4px 0 0 0; color: {MUTED}; font-size: 0.92rem; }}

/* ---- section header ---- */
.sec {{ display:flex; align-items:baseline; gap:10px; margin: 6px 0 2px 0; }}
.sec .sec-icon {{ font-size: 1.3rem; }}
.sec h3 {{ margin:0; color:#f1f5f9; }}
.sec-sub {{ color:{MUTED}; font-size:0.87rem; margin: 2px 0 14px 0; }}

/* ---- stat cards ---- */
.stat-grid {{ display:grid; grid-template-columns: repeat(var(--n,4), 1fr); gap:10px; margin-bottom: 14px; }}
@media (max-width: 900px) {{ .stat-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
.stat-card {{
  background:{CARD}; border:1px solid {CARD_BORDER}; border-radius:12px;
  padding:12px 14px; min-height: 78px;
}}
.stat-card .lbl {{ color:{MUTED}; font-size:0.74rem; text-transform:uppercase; letter-spacing:.04em; }}
.stat-card .val {{ color:#f8fafc; font-size:1.35rem; font-weight:700; margin-top:2px; }}
.stat-card .sub {{ font-size:0.78rem; margin-top:3px; font-weight:600; }}

/* ---- badges / pills ---- */
.pill {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.8rem; font-weight:600; }}

/* ---- player header card ---- */
.player-card {{
  background:{CARD}; border:1px solid {CARD_BORDER}; border-radius:16px;
  padding:18px; display:flex; gap:18px; align-items:center; margin-bottom:14px;
}}
.player-card img {{ border: 2px solid {CARD_BORDER}; }}
.player-name {{ font-size:1.5rem; font-weight:700; color:#f8fafc; margin:0; }}
.player-meta {{ color:{MUTED}; font-size:0.92rem; margin-top:4px; line-height:1.9; }}

/* ---- scrollable custom tables ---- */
.scroll-table {{ overflow-x:auto; -webkit-overflow-scrolling:touch; border:1px solid {CARD_BORDER};
  border-radius:12px; background:{CARD}; }}
.scroll-table table {{ width:100%; border-collapse:collapse; font-size:0.92rem; }}
.scroll-table th {{ text-align:left; padding:10px 12px; color:{MUTED}; font-size:0.76rem;
  text-transform:uppercase; letter-spacing:.03em; border-bottom:1px solid {CARD_BORDER}; }}
.scroll-table td {{ padding:8px 12px; white-space:nowrap; border-bottom:1px solid {CARD_BORDER}22; }}
.scroll-table tr:hover td {{ background: rgba(249,115,22,0.06); }}

/* ---- misc ---- */
.chip {{ display:inline-block; background:{CARD}; border:1px solid {CARD_BORDER}; border-radius:8px;
  padding:2px 9px; font-size:0.82rem; color:#e2e8f0; margin-right:6px; }}
.vs-divider {{ text-align:center; color:{MUTED}; font-weight:700; font-size:1.1rem; }}

@media (max-width: 640px) {{
  .block-container {{ padding-left: 0.8rem; padding-right: 0.8rem; }}
  .hero {{ padding:16px 18px; }}
  .hero h1 {{ font-size:1.3rem; }}
  h1 {{ font-size: 1.4rem !important; }}
  h3 {{ font-size: 1.05rem !important; }}
}}
</style>
"""


def inject_mobile_css():
    """Kept name for backward compat with earlier pages; now injects the full theme."""
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def hero(icon: str, title: str, subtitle: str = ""):
    st.markdown(
        f"<div class='hero'><div class='hero-icon'>{icon}</div>"
        f"<div><h1>{title}</h1>{f'<p>{subtitle}</p>' if subtitle else ''}</div></div>",
        unsafe_allow_html=True,
    )


def section(icon: str, title: str, subtitle: str = ""):
    st.markdown(f"<div class='sec'><span class='sec-icon'>{icon}</span><h3>{title}</h3></div>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div class='sec-sub'>{subtitle}</div>", unsafe_allow_html=True)


def stat_cards(cards, cols: int = 4):
    """cards: list of dicts {label, value, sub (optional), sub_color (optional)}"""
    items = "".join(
        f"<div class='stat-card'><div class='lbl'>{c['label']}</div><div class='val'>{c['value']}</div>"
        + (f"<div class='sub' style='color:{c.get('sub_color', MUTED)}'>{c['sub']}</div>" if c.get("sub") else "")
        + "</div>"
        for c in cards
    )
    st.markdown(f"<div class='stat-grid' style='--n:{cols}'>{items}</div>", unsafe_allow_html=True)


def scrollable_table(header_html: str, rows_html: str) -> str:
    return f"<div class='scroll-table'><table><tr>{header_html}</tr>{rows_html}</table></div>"


def download_button(df: pd.DataFrame, filename: str, label: str = "⬇️ Export CSV"):
    st.download_button(label, df.to_csv(index=False).encode(), file_name=filename, mime="text/csv")
