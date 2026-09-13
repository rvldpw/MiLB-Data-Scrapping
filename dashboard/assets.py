"""Player headshots and team logos, keyed off the MLB person/team IDs already
in the dataset (player_id and team_id are real MLB Stats API IDs, so the
public midfield.mlbstatic.com CDN resolves them directly - MiLB players
included). If an ID has no photo on file, an inline SVG silhouette/shield
renders instead via the <img onerror> fallback, so nothing ever looks blank.
"""

_SILHOUETTE = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<rect width='100' height='100' fill='%23334155'/>"
    "<circle cx='50' cy='38' r='18' fill='%2394a3b8'/>"
    "<path d='M15 95 Q50 60 85 95 Z' fill='%2394a3b8'/>"
    "</svg>"
)

_SHIELD = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
    "<path d='M50 5 L90 20 V50 Q90 80 50 95 Q10 80 10 50 V20 Z' fill='%23334155'/>"
    "<text x='50' y='60' font-size='34' text-anchor='middle' fill='%2394a3b8' "
    "font-family='sans-serif'>%E2%9A%BE</text></svg>"
)


def player_photo_url(player_id) -> str:
    return f"https://midfield.mlbstatic.com/v1/people/{int(player_id)}/spots/120"


def team_logo_url(team_id) -> str:
    return f"https://midfield.mlbstatic.com/v1/team/{int(team_id)}/spots/64"


def player_photo_html(player_id, size=90, radius="50%") -> str:
    url = player_photo_url(player_id)
    return (
        f"<img src='{url}' onerror=\"this.onerror=null;this.src='{_SILHOUETTE}'\" "
        f"style='width:{size}px;height:{size}px;object-fit:cover;border-radius:{radius};"
        f"background:#1e293b;border:1px solid #334155;' />"
    )


def team_logo_html(team_id, size=48) -> str:
    url = team_logo_url(team_id)
    return (
        f"<img src='{url}' onerror=\"this.onerror=null;this.src='{_SHIELD}'\" "
        f"style='width:{size}px;height:{size}px;object-fit:contain;' />"
    )
