"""Purpose-specific Plotly charts with consistent axes and plain-English labels."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from dashboard.ui import ACCENT, INK, MUTED, LINE, BAD, BLUE, fmt
from dashboard.glossary import label, direction
from dashboard.metrics import percentile_rank


def style(fig, height=370):
    fig.update_layout(template="plotly_white", height=height, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Avenir Next, Segoe UI, sans-serif", color=INK, size=12),
                      margin=dict(l=15, r=20, t=35, b=30),
                      legend=dict(orientation="h", y=-.2, x=0, title=None),
                      hoverlabel=dict(bgcolor=INK, font_color="#ffffff"),
                      colorway=[ACCENT, BLUE, BAD], hovermode="closest")
    fig.update_xaxes(showgrid=False, zeroline=False, automargin=True, linecolor=LINE, tickfont_color=MUTED)
    fig.update_yaxes(gridcolor=LINE, zeroline=False, automargin=True, tickfont_color=MUTED)
    return fig


def scatter_field(table, kind, selected=None):
    x, y = ("K_pct", "ISO") if kind == "batting" else ("BB_pct", "K_pct")
    data = table.dropna(subset=[x, y]).copy()
    size = "PA" if kind == "batting" else "IP"
    data["Exposure"] = data[size].fillna(0).clip(lower=1)
    fig = px.scatter(data, x=x, y=y, size="Exposure", size_max=23,
                     hover_name="Player", hover_data={"Team": True, size: ":.1f", x: ":.1%", y: ":.3f" if kind == "batting" else ":.1%", "Exposure": False},
                     color_discrete_sequence=[ACCENT])
    fig.update_traces(marker=dict(opacity=.68, line=dict(width=1, color="#ffffff")))
    if not data.empty:
        fig.add_vline(x=data[x].median(), line_dash="dot", line_color=MUTED, opacity=.5)
        fig.add_hline(y=data[y].median(), line_dash="dot", line_color=MUTED, opacity=.5)
    if selected is not None and "player_id" in data:
        p = data[data["player_id"].eq(selected)]
        if not p.empty:
            fig.add_trace(go.Scatter(x=p[x], y=p[y], mode="markers", name="Selected player",
                                     marker=dict(size=22, color="rgba(0,0,0,0)", line=dict(color=INK,width=3)),
                                     text=p["Player"], hovertemplate="%{text}<extra></extra>"))
    fig.update_xaxes(title="Strikeout rate · lower is better" if kind == "batting" else "Walk rate · lower is better", tickformat=".0%")
    fig.update_yaxes(title="Extra-base power (ISO) · higher is better" if kind == "batting" else "Strikeout rate · higher is better",
                     tickformat=".3f" if kind == "batting" else ".0%")
    fig.update_layout(showlegend=False)
    return style(fig, 405)


def percentile_bars(line, population, kind):
    keys = ["OBP", "ISO", "AVG", "BB_pct", "K_pct"] if kind == "batting" else ["K_pct", "BB_pct", "K_BB_pct", "WHIP", "HR9"]
    rows = []
    for key in keys:
        if key not in population:
            continue
        p = percentile_rank(population[key], line.get(key, np.nan), direction(key, kind) == "Lower")
        if pd.notna(p):
            rows.append((label(key), p, fmt(line[key], key)))
    fig = go.Figure()
    if rows:
        fig.add_trace(go.Bar(y=[r[0] for r in rows], x=[100]*len(rows), orientation="h", marker_color="#e3e9e3", hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Bar(y=[r[0] for r in rows], x=[r[1] for r in rows], orientation="h", marker_color=ACCENT,
                             text=[f"{r[1]:.0f} · {r[2]}" for r in rows], textposition="outside", cliponaxis=False,
                             hovertemplate="%{y}: %{x:.0f}th percentile<extra></extra>", showlegend=False))
        fig.add_vline(x=50, line_color=MUTED, line_dash="dot")
    fig.update_layout(barmode="overlay", bargap=.55)
    fig.update_xaxes(range=[0, 125], tickvals=[0, 25, 50, 75, 100], title="Percentile · higher means a more favorable result")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return style(fig, 330), len(rows)


def trend(rolling, metric, baseline=None, name="Player"):
    fig = go.Figure()
    if not rolling.empty:
        fig.add_trace(go.Scatter(x=rolling["game_date"], y=rolling["value"], mode="lines+markers", name=name,
                                 line=dict(color=ACCENT, width=2.5), marker=dict(size=6), connectgaps=False,
                                 customdata=rolling[["Games in window", "game_pk"]],
                                 hovertemplate="%{x|%d %b %Y}<br>Value: %{y:.3f}<br>Window: %{customdata[0]} games<br>Game ID: %{customdata[1]}<extra></extra>"))
    if baseline is not None and pd.notna(baseline):
        fig.add_hline(y=baseline, line_dash="dot", line_color=MUTED, annotation_text="Loaded cohort", annotation_position="top left")
    fig.update_yaxes(title=label(metric), tickformat=".1%" if metric.endswith("pct") else ".3f" if metric in ("OPS","OBP","wOBA","ISO") else ".2f")
    fig.update_xaxes(title="Game date")
    return style(fig, 350)


def game_bars(df, column, name):
    data = df.sort_values(["game_date", "game_pk"])
    dates = data["game_date"].dt.strftime("%d %b") + " · " + data["game_pk"].astype(str)
    fig = go.Figure(go.Bar(x=dates, y=data[column], marker_color=ACCENT,
                            hovertemplate="%{x}<br>" + name + ": %{y}<extra></extra>"))
    fig.update_xaxes(title="Game date · unique game ID", nticks=12)
    fig.update_yaxes(title=name, rangemode="tozero")
    return style(fig, 310)


def split_bars(table, metric):
    fig = px.bar(table, x="Split", y=metric, color_discrete_sequence=[ACCENT], text_auto=".3f" if metric in ("OPS","OBP","wOBA") else ".2f")
    fig.update_xaxes(title=None)
    fig.update_yaxes(title=label(metric))
    return style(fig, 320)


def compare_dots(a, b, names, keys):
    fig = go.Figure()
    for key in keys:
        if pd.notna(a.get(key)) and pd.notna(b.get(key)):
            fig.add_trace(go.Scatter(x=[a[key], b[key]], y=[label(key)]*2, mode="lines", line=dict(color=LINE, width=5), showlegend=False, hoverinfo="skip"))
    for values, name, color in ((a, names[0], ACCENT), (b, names[1], BLUE)):
        fig.add_trace(go.Scatter(x=[values.get(k, np.nan) for k in keys], y=[label(k) for k in keys], mode="markers",
                                 marker=dict(color=color,size=12), name=name,
                                 hovertemplate="%{y}: %{x:.3f}<extra>" + name + "</extra>"))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return style(fig, 300)
