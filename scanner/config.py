"""Configuration shared by local runs and GitHub Actions."""
from dataclasses import dataclass
import os

LEVELS = {12: "AA", 13: "A+", 14: "A"}


@dataclass(frozen=True)
class Settings:
    start_season: int = 2021
    sport_ids: tuple[int, ...] = (12, 13, 14)
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
            raise ValueError("SPORT_IDS must contain only 12 (AA), 13 (A+), 14 (A)")
        if len(set(self.sport_ids)) != len(self.sport_ids):
            raise ValueError("SPORT_IDS must be unique")
        if not 1 <= self.checkpoint_games <= 100:
            raise ValueError("CHECKPOINT_GAMES must be between 1 and 100")
        if self.refresh_days < 1 or self.max_games < 0 or self.max_run_minutes < 1:
            raise ValueError("Invalid refresh window, game limit, or run duration")

    @classmethod
    def from_env(cls):
        return cls(
            start_season=int(os.getenv("START_SEASON", "2021")),
            sport_ids=tuple(sorted(int(s.strip()) for s in os.getenv("SPORT_IDS", "12,13,14").split(","))),
            refresh_days=int(os.getenv("REFRESH_DAYS", "7")),
            checkpoint_games=int(os.getenv("CHECKPOINT_GAMES", "100")),
            max_games=int(os.getenv("MAX_GAMES_PER_RUN", "0")),
            max_run_minutes=int(os.getenv("MAX_RUN_MINUTES", "150")),
        )

    def scope(self):
        return {"start_season": self.start_season, "sport_ids": list(self.sport_ids), "game_types": ["R"]}
