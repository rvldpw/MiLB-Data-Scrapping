"""Configuration shared by local runs and GitHub Actions."""
from dataclasses import dataclass
import os

# Sport IDs of the MLB Stats API. 17 is every off-season league: the Arizona Fall League, the Caribbean and
# Australian winter leagues and the Caribbean Series. Their seasons start in October and end in February.
LEVELS = {11: "AAA", 12: "AA", 13: "A+", 14: "A", 17: "WIN"}
# MLB Stats API game types, stored unchanged in `game_type`. R is the regular season, A an All-Star
# game and E an exhibition; the rest are postseason rounds (the minors use L and W for league playoffs
# and C for the Triple-A title game).
GAME_TYPES = ("R", "F", "D", "L", "W", "C", "P", "A", "E")


def _csv(name, default):
    return tuple(part.strip() for part in os.getenv(name, default).split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    start_season: int = 2021
    sport_ids: tuple[int, ...] = tuple(LEVELS)
    game_types: tuple[str, ...] = GAME_TYPES
    refresh_days: int = 7
    checkpoint_games: int = 100
    max_games: int = 0
    max_run_minutes: int = 150
    request_timeout: int = 30
    request_delay: float = 0.12
    retries: int = 4

    def __post_init__(self):
        if not 2021 <= self.start_season <= 9998:
            raise ValueError("START_SEASON must be 2021 or later")
        if not self.sport_ids or set(self.sport_ids) - LEVELS.keys():
            raise ValueError("SPORT_IDS must contain only " + ", ".join(f"{i} ({name})" for i, name in LEVELS.items()))
        if not self.game_types or set(self.game_types) - set(GAME_TYPES):
            raise ValueError("GAME_TYPES must contain only " + ", ".join(GAME_TYPES))
        if len(set(self.sport_ids)) != len(self.sport_ids) or len(set(self.game_types)) != len(self.game_types):
            raise ValueError("SPORT_IDS and GAME_TYPES must be unique")
        if not 1 <= self.checkpoint_games <= 100:
            raise ValueError("CHECKPOINT_GAMES must be between 1 and 100")
        if self.refresh_days < 1 or self.max_games < 0 or self.max_run_minutes < 1:
            raise ValueError("Invalid refresh window, game limit, or run duration")

    @classmethod
    def from_env(cls):
        return cls(
            start_season=int(os.getenv("START_SEASON", "2021")),
            sport_ids=tuple(int(s) for s in _csv("SPORT_IDS", ",".join(map(str, LEVELS)))),
            game_types=tuple(s.upper() for s in _csv("GAME_TYPES", ",".join(GAME_TYPES))),
            refresh_days=int(os.getenv("REFRESH_DAYS", "7")),
            checkpoint_games=int(os.getenv("CHECKPOINT_GAMES", "100")),
            max_games=int(os.getenv("MAX_GAMES_PER_RUN", "0")),
            max_run_minutes=int(os.getenv("MAX_RUN_MINUTES", "150")),
        )

    def scope(self):
        return {"start_season": self.start_season, "sport_ids": sorted(self.sport_ids),
                "game_types": sorted(self.game_types)}
