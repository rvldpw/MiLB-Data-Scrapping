"""Purpose-specific Plotly charts with consistent axes and plain-English labels."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from dashboard.ui import ACCENT, INK, MUTED, LINE, GRID, BAD, BLUE, WARN, fmt
from dashboard.glossary import METRICS, label, code, direction
from dashboard.metrics import percentile_rank


def style(fig, height=370):
    fig.update_layout(template="plotly_white", height=height, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", color=INK, size=12),
                      margin=dict(l=15, r=20, t=35, b=30),
                      legend=dict(orientation="h", y=-.2, x=0, title=None),
                      hoverlabel=dict(bgcolor=INK, font_color="#ffffff"),
                      colorway=[ACCENT, BAD, BLUE, WARN], hovermode="closest")
    fig.update_xaxes(showgrid=False, zeroline=False, automargin=True, linecolor=LINE, tickfont_color=MUTED)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, automargin=True, tickfont_color=MUTED)
    return fig


def scatter_field(table, kind, selected=None):
    x, y = ("K_pct", "ISO") if kind == "batting" else ("BB_pct", "K_pct")
    data = table.dropna(subset=[x, y]).copy()
    size = "PA" if kind == "batting" else "IP"
    data["Exposure"] = data[size].fillna(0).clip(lower=1)
    fig = px.scatter(data, x=x, y=y, size="Exposure", size_max=23,
                     hover_name="Player", hover_data={"Team": True, size: ":.1f", x: ":.1%", y: ":.3f" if kind == "batting" else ":.1%", "Exposure": False},
                     color_discrete_sequence=[ACCENT])
    fig.update_traces(marker=dict(opacity=.88, line=dict(width=1, color="#ffffff")))
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
    fig.update_yaxes(title="Power (extra bases per at-bat) · higher is better" if kind == "batting" else "Strikeout rate · higher is better",
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
        fig.add_trace(go.Bar(y=[r[0] for r in rows], x=[100]*len(rows), orientation="h", marker_color=GRID, hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Bar(y=[r[0] for r in rows], x=[r[1] for r in rows], orientation="h", marker_color=ACCENT,
                             text=[f"{r[1]:.0f} · {r[2]}" for r in rows], textposition="outside", cliponaxis=False,
                             hovertemplate="%{y}: better than %{x:.0f}% of peers<extra></extra>", showlegend=False))
        fig.add_vline(x=50, line_color=MUTED, line_dash="dot")
    fig.update_layout(barmode="overlay", bargap=.55)
    fig.update_xaxes(range=[0, 125], tickvals=[0, 25, 50, 75, 100], title="Rank among peers · 50 is average")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return style(fig, 330), len(rows)


def trend(rolling, metric, baseline=None, name="Player"):
    fig = go.Figure()
    # One trace per season so the line never bridges the off-season.
    for season, part in rolling.groupby("season", sort=True):
        fig.add_trace(go.Scatter(x=part["game_date"], y=part["value"], mode="lines+markers", name=f"{name} {season}",
                                 line=dict(width=2.5), marker=dict(size=6), connectgaps=False,
                                 customdata=part[["Games in window", "game_pk"]],
                                 hovertemplate="%{x|%d %b %Y}<br>Value: %{y:.3f}<br>Window: %{customdata[0]} games<br>Game ID: %{customdata[1]}<extra></extra>"))
    fig.update_layout(showlegend=rolling["season"].nunique() > 1 if not rolling.empty else False)
    if baseline is not None and pd.notna(baseline):
        fig.add_hline(y=baseline, line_dash="dot", line_color=MUTED, annotation_text="League", annotation_position="top left")
    fig.update_yaxes(title=label(metric), tickformat=".1%" if metric.endswith("pct") else ".3f" if metric in ("OPS","OBP","wOBA","ISO") else ".2f")
    fig.update_xaxes(title="Game date")
    return style(fig, 350)


def date_axis(fig, dates):
    """Evenly spaced games with readable date ticks (no rotated 'date · id' labels)."""
    dates = pd.Series(dates).reset_index(drop=True)
    step = max(1, -(-len(dates) // 10))
    pattern = "%d %b %y" if dates.dt.year.nunique() > 1 else "%d %b"
    ticks = list(range(0, len(dates), step))
    fig.update_xaxes(tickmode="array", tickvals=ticks, ticktext=[dates[i].strftime(pattern) for i in ticks], tickangle=0, title=None)
    return fig


def game_bars(df, column, name):
    data = df.sort_values(["game_date", "game_pk"]).reset_index(drop=True)
    fig = go.Figure(go.Bar(x=list(data.index), y=data[column], marker_color=ACCENT,
                           customdata=data[["game_date", "game_pk"]].assign(game_date=data["game_date"].dt.strftime("%d %b %Y")),
                           hovertemplate="%{customdata[0]} · game %{customdata[1]}<br>" + name + ": %{y}<extra></extra>"))
    fig.update_yaxes(title=name, rangemode="tozero", **({"dtick": 1} if data[column].max() <= 8 else {}))
    return style(date_axis(fig, data["game_date"]), 310)


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
    for values, name, color in ((a, names[0], ACCENT), (b, names[1], BAD)):
        fig.add_trace(go.Scatter(x=[values.get(k, np.nan) for k in keys], y=[label(k) for k in keys], mode="markers",
                                 marker=dict(color=color,size=12,line=dict(width=1.5,color="#ffffff")), name=name,
                                 hovertemplate="%{y}: %{x:.3f}<extra>" + name + "</extra>"))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return style(fig, 300)


def axis_format(key):
    pattern = METRICS[key][3] if key in METRICS else ".2f"
    return ".1f" if pattern == "innings" else pattern


def distribution(values, key, mark=None, mark_name=""):
    """Where a group of players sits on one metric, with the middle marked and one player if given."""
    data = pd.to_numeric(values, errors="coerce").dropna()
    fig = go.Figure(go.Histogram(x=data, nbinsx=24, marker=dict(color=ACCENT, line=dict(color="#ffffff", width=1)),
                                 hovertemplate="%{x}<br>%{y} players<extra></extra>"))
    if not data.empty:
        fig.add_vline(x=data.median(), line_dash="dot", line_color=INK, annotation_text=f"Middle {fmt(data.median(), key)}",
                      annotation_position="top left", annotation_font_color=INK)
    if mark is not None and pd.notna(mark):
        fig.add_vline(x=mark, line_color=BAD, line_width=3, annotation_text=mark_name,
                      annotation_position="top right", annotation_font_color=BAD)
    fig.update_xaxes(title=label(key), tickformat=axis_format(key))
    fig.update_yaxes(title="Players")
    return style(fig, 330)


def month_bars(table, key, title, pattern=".2f"):
    fig = go.Figure(go.Bar(x=table["Month"], y=table[key], marker_color=ACCENT, cliponaxis=False, textposition="outside",
                           text=[format(v, pattern) if pd.notna(v) else "" for v in table[key]],
                           hovertemplate="%{x}<br>" + title + ": %{text}<extra></extra>"))
    fig.update_xaxes(title=None, type="category")
    fig.update_yaxes(title=title, rangemode="tozero")
    return style(fig, 300)


def month_lines(table, keys):
    fig = go.Figure()
    for key, color in zip(keys, (BAD, BLUE, ACCENT)):
        fig.add_trace(go.Scatter(x=table["Month"], y=table[key], mode="lines+markers", name=label(key),
                                 line=dict(color=color, width=2.5), marker=dict(size=7),
                                 hovertemplate="%{x}<br>" + label(key) + ": %{y:.1%}<extra></extra>"))
    fig.update_xaxes(title=None, type="category")
    fig.update_yaxes(title=None, tickformat=".0%")
    return style(fig, 300)


def team_quadrant(teams):
    """Runs scored and allowed per game for every club. Up and to the right is the strong corner."""
    data = teams.dropna(subset=["RS", "RA", "Games"]).copy()
    data["Scored"], data["Allowed"] = data["RS"] / data["Games"], data["RA"] / data["Games"]
    data = data.sort_values("Scored")
    # Neighbours left to right take turns above and below their dot, so close clubs do not print over each other.
    fig = go.Figure(go.Scatter(
        x=data["Scored"], y=data["Allowed"], mode="markers+text", text=[str(t).split()[-1] for t in data["Team"]],
        textposition=["top center" if i % 2 == 0 else "bottom center" for i in range(len(data))], textfont=dict(size=11, color=MUTED),
        marker=dict(size=15, color=[ACCENT if m >= 0 else BAD for m in data["Margin"]], line=dict(color="#ffffff", width=1.5)),
        customdata=np.stack([data["Team"], data["W"], data["L"]], axis=-1),
        hovertemplate="%{customdata[0]} · %{customdata[1]}–%{customdata[2]}<br>Scores %{x:.2f} a game<br>Allows %{y:.2f} a game<extra></extra>"))
    if not data.empty:
        fig.add_vline(x=data["RS"].sum() / data["Games"].sum(), line_dash="dot", line_color=MUTED, opacity=.6)
        fig.add_hline(y=data["RA"].sum() / data["Games"].sum(), line_dash="dot", line_color=MUTED, opacity=.6)
    fig.update_xaxes(title="Runs scored per game · right is better", tickformat=".1f")
    fig.update_yaxes(title="Runs allowed per game · up is better", tickformat=".1f", autorange="reversed")
    return style(fig, 400)


def season_line(path):
    """One club's wins minus losses after every game."""
    ahead = path.empty or path["Over"].iloc[-1] >= 0
    fig = go.Figure(go.Scatter(
        x=path["Game"], y=path["Over"], mode="lines", line=dict(color=ACCENT if ahead else BAD, width=2.5, shape="hv"),
        fill="tozeroy", fillcolor="rgba(20,122,75,.10)" if ahead else "rgba(224,104,45,.10)",
        customdata=np.stack([path["game_date"].dt.strftime("%d %b %Y"), path["result"], path["opponent_name"].fillna("?")], axis=-1),
        hovertemplate="Game %{x} · %{customdata[0]}<br>%{customdata[1]} vs %{customdata[2]}<br>%{y:+d} against .500<extra></extra>"))
    fig.add_hline(y=0, line_color=MUTED)
    fig.update_xaxes(title="Games played")
    fig.update_yaxes(title="Wins minus losses", tickformat="+d")
    return style(fig, 320)


def load_bars(table, size, rate, league_rate, kind, top=12):
    """Who gets the playing time and what they do with it: bar length is playing time, colour is the rate against the league."""
    data = table.dropna(subset=[size]).nlargest(top, size).iloc[::-1]
    higher = direction(rate, kind) == "Higher"
    colors = [MUTED if pd.isna(v) or pd.isna(league_rate) else ACCENT if (v >= league_rate) == higher else BAD for v in data[rate]]
    fig = go.Figure(go.Bar(y=data["Player"], x=data[size], orientation="h", marker_color=colors, cliponaxis=False,
                           text=[fmt(v, rate) for v in data[rate]], textposition="outside",
                           hovertemplate="%{y}<br>" + label(size) + ": %{x:,.0f}<br>" + code(rate) + ": %{text}<extra></extra>"))
    fig.update_xaxes(title=label(size))
    fig.update_yaxes(showgrid=False)
    return style(fig, max(250, 27 * len(data) + 95))


OUT_TYPES = {"batting": [("GO", "Ground"), ("FO", "Fly"), ("LO", "Line"), ("PO", "Pop")],
             "pitching": [("GO", "Ground"), ("FO", "Fly"), ("line_outs", "Line"), ("pop_outs", "Pop")]}


def out_shares(line, kind):
    """Share of outs on balls in play made each way, or None when the source did not record them."""
    counts = [line.get(key, np.nan) for key, _ in OUT_TYPES[kind]]
    total = sum(counts)
    return None if pd.isna(total) or total <= 0 else [c / total for c in counts]


def out_mix(rows, kind):
    """Stacked shares of ground, fly, line and pop outs for each (name, shares) row."""
    fig = go.Figure()
    for index, ((_, name), color) in enumerate(zip(OUT_TYPES[kind], (ACCENT, BLUE, WARN, MUTED))):
        shares = [share[index] for _, share in rows]
        fig.add_trace(go.Bar(y=[n for n, _ in rows], x=shares, orientation="h", name=name, marker_color=color,
                             text=[f"{s:.0%}" for s in shares], textposition="inside", insidetextanchor="middle",
                             textfont=dict(color="#ffffff"), hovertemplate="%{y}<br>" + name + " outs: %{x:.0%}<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=.4, legend_traceorder="normal")
    fig.update_xaxes(tickformat=".0%", range=[0, 1], title=None)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return style(fig, 215)
