"""Recent news headlines for a player or team.

Pulled from Google News' public RSS search endpoint - a free aggregator that
indexes wire services, MiLB.com, ESPN, SB Nation, and local beat writers, so
this covers those outlets (among others) without scraping any one site or
needing an API key. Coverage on complex-league or short-season players is
often thin or nonexistent; an empty result means "no recent coverage found
for this search," not a broken feature.
"""
from urllib.parse import quote
from xml.etree import ElementTree

import pandas as pd
import requests
import streamlit as st

RSS = "https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en"
COLUMNS = ["title", "link", "published", "source"]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_news(query: str, max_items: int = 6) -> pd.DataFrame:
    try:
        r = requests.get(RSS.format(quote(query)), timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ElementTree.fromstring(r.content)
        rows = []
        for item in root.findall(".//item")[:max_items]:
            source_el = item.find("source")
            rows.append({
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "published": (item.findtext("pubDate") or "").strip(),
                "source": (source_el.text if source_el is not None else "").strip(),
            })
        return pd.DataFrame(rows, columns=COLUMNS)
    except Exception:
        return pd.DataFrame(columns=COLUMNS)
