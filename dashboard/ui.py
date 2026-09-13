"""Small shared UI bits so the three pages don't repeat themselves.

Streamlit's own layout already reflows `st.columns` to a stacked view on a
narrow viewport and the sidebar already has a built-in collapse/expand
chevron - the CSS below just tightens things up further for a phone: it
keeps our custom HTML tables (the ones with inline player photos) from
squashing by making them scroll sideways instead, and trims some default
padding that eats screen space on a small screen.
"""
import streamlit as st

MOBILE_CSS = """
<style>
/* let wide custom tables scroll horizontally instead of squeezing on phones */
.scroll-table { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.scroll-table table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
.scroll-table th, .scroll-table td { padding: 6px 8px; text-align: left; white-space: nowrap; }
.scroll-table tr:nth-child(even) { background: rgba(148,163,184,0.08); }

@media (max-width: 640px) {
  .block-container { padding-left: 0.8rem; padding-right: 0.8rem; padding-top: 1rem; }
  [data-testid="stMetricValue"] { font-size: 1.15rem; }
  [data-testid="stMetricLabel"] { font-size: 0.78rem; }
  h1 { font-size: 1.5rem !important; }
  h3 { font-size: 1.15rem !important; }
}
</style>
"""


def inject_mobile_css():
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)


def scrollable_table(header_html: str, rows_html: str) -> str:
    return f"<div class='scroll-table'><table><tr>{header_html}</tr>{rows_html}</table></div>"
