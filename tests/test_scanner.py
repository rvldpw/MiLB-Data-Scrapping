from copy import deepcopy
from datetime import date, datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq
import pytest
import yaml

from scanner.build import run, IncompleteRun
from scanner.config import Settings
from scanner.dataset import merge_games, dataset_card
from scanner.fetch import MLBClient, FetchError
from scanner.game_log import parse_boxscore
from scanner.schema import schema_for, stats_columns
from scanner.state import initial_state, choose_season, game_signature, needs_fetch, still_played
from scanner.storage import LocalStore, HubStore, json_bytes, read_json, safe_path

FIXTURES = Path(__file__).parent / "fixtures"


def at(day):
    return datetime.fromisoformat(day + "T09:00:00+00:00")


def sample(season=2021, pk=1, day=None, sport=12, kind="R"):
    game = {
        "gamePk": pk, "season": str(season), "sport_id": sport,
        "gameType": kind, "officialDate": day or f"{season}-06-01",
        "gameDate": f"{season}-06-01T23:00:00Z", "gameNumber": 1,
        "status": {"abstractGameState": "Final", "detailedState": "Final"}, "teams": {},
    }
    box = {"teams": {}}
    for side, team_id, score in (("home", 10, 2), ("away", 20, 1)):
        team = {"id": team_id, "name": f"Team {team_id}",
                "league": {"id": 113, "name": "Eastern League"}, "sport": {"id": sport}}
        game["teams"][side] = {"team": team, "score": score}
        batter_id, pitcher_id = team_id * 10, team_id * 10 + 1
        box["teams"][side] = {
            "team": team, "batters": [batter_id], "pitchers": [pitcher_id],
            "players": {
                str(batter_id): {"person": {"id": batter_id, "fullName": "Same Name"},
                    "position": {"abbreviation": "C"},
                    "stats": {"batting": {"atBats": 4, "hits": 2, "runs": score}},
                    "seasonStats": {"batting": {"hits": 99}}},
                str(pitcher_id): {"person": {"id": pitcher_id, "fullName": "Pitcher"},
                    "position": {"abbreviation": "P"},
                    "stats": {"pitching": {"inningsPitched": "5.2", "strikeOuts": 7}}},
                "bench": {"person": {"id": team_id * 100, "fullName": "Unused"},
                    "stats": {"batting": {}, "pitching": {}},
                    "seasonStats": {"batting": {"hits": 40}}},
            },
        }
    return game, box


class FakeClient:
    def __init__(self, samples):
        self.samples = samples
        self.calls = []
        self.failed = set()

    def schedule(self, season):
        return [deepcopy(g) for g, _ in self.samples if int(g["season"]) == season]

    def boxscore(self, pk):
        self.calls.append(pk)
        if pk in self.failed:
            raise FetchError("temporary failure")
        return deepcopy(next(b for g, b in self.samples if g["gamePk"] == pk))


def settings(**kwargs):
    return Settings(sport_ids=(12,), **kwargs)


def read_table(store, path):
    return pq.ParquetFile(BytesIO(store.read(path))).read()


def test_six_daily_seasons_and_same_day_gate(tmp_path):
    client = FakeClient([sample(year, year) for year in range(2021, 2027)])
    store = LocalStore(tmp_path)
    for offset, year in enumerate(range(2021, 2027), 10):
        now = at(f"2026-09-{offset}")
        result = run(settings(), client, store, now)
        assert result["season"] == year
        assert result["games_fetched"] == 1
        repeated = run(settings(), client, store, now)
        assert repeated["games_fetched"] == 0
        assert repeated["status"] == ("waiting" if year < 2026 else "complete")
    assert client.calls == list(range(2021, 2027))
    assert run(settings(), client, store, at("2026-09-16"))["season"] == 2026


def test_partial_run_resumes_same_season_without_duplicates(tmp_path):
    client = FakeClient([sample(pk=1), sample(pk=2)])
    store = LocalStore(tmp_path)
    config = settings(max_games=1)
    first = run(config, client, store, at("2026-09-10"))
    assert first["status"] == "partial"
    state = read_json(store, "state/index.json", {})
    assert not state["seasons"]["2021"].get("final_complete")
    second = run(config, client, store, at("2026-09-10"))
    assert second["status"] == "complete"
    assert client.calls == [1, 2]
    table = read_table(store, "data/season-2021/league-113/team-10/batting.parquet")
    assert table.num_rows == 2
    assert set(table.column("game_pk").to_pylist()) == {1, 2}


def test_failed_game_does_not_complete_and_successes_persist(tmp_path):
    client = FakeClient([sample(pk=1), sample(pk=2)])
    client.failed.add(1)
    store = LocalStore(tmp_path)
    summary = run(settings(), client, store, at("2026-09-10"))
    assert summary["status"] == "partial"
    assert summary["failures"] == 1
    index = read_json(store, "state/2021.json", {})
    assert set(index) == {"2"}
    client.failed.clear()
    assert run(settings(), client, store, at("2026-09-11"))["status"] == "complete"
    assert client.calls == [1, 2, 1]


def test_permanently_broken_game_is_excluded_not_retried_forever(tmp_path):
    # A "Final" game whose own schedule entry never got a score attached (seen in the
    # wild: postponed/suspended games that MLB's feed marks Final but never backfills) -
    # retrying can never fix stale historical data, so this must not block the season
    # from completing, and must not be re-fetched on every future run either.
    broken, ok1, ok2 = sample(pk=1), sample(pk=2), sample(pk=3)
    broken[0]["teams"]["home"]["score"] = None
    client = FakeClient([broken, ok1, ok2])
    store = LocalStore(tmp_path)
    config = settings(max_games=1)
    first = run(config, client, store, at("2026-09-10"))
    assert first["excluded_games"] == 1
    assert first["failures"] == 0
    second = run(config, client, store, at("2026-09-11"))
    assert second["status"] == "partial"
    third = run(config, client, store, at("2026-09-12"))
    assert third["status"] == "complete"
    assert third["excluded_games"] == 1
    # The broken game was attempted exactly once, ever - never retried on later runs.
    assert client.calls == [1, 2, 3]
    state = read_json(store, "state/index.json", {})
    assert state["seasons"]["2021"]["final_complete"] is True
    assert set(read_json(store, "state/2021.json", {})) == {"2", "3"}


def test_failed_upload_does_not_skip_games(tmp_path):
    class BrokenStore(LocalStore):
        def commit(self, files, message):
            raise RuntimeError("upload failed")
    client = FakeClient([sample()])
    with pytest.raises(RuntimeError, match="upload failed"):
        run(settings(), client, BrokenStore(tmp_path), at("2026-09-10"))
    assert not (tmp_path / "state/index.json").exists()
    assert run(settings(), client, LocalStore(tmp_path), at("2026-09-10"))["games_fetched"] == 1
    assert client.calls == [1, 1]


def test_rollover_reconciles_previous_then_starts_new_year(tmp_path):
    config = settings(start_season=2026)
    client = FakeClient([sample(2026)])
    store = LocalStore(tmp_path)
    run(config, client, store, at("2026-12-31"))
    result = run(config, client, store, at("2027-01-01"))
    assert result["season"] == 2026
    assert result["games_fetched"] == 0
    assert run(config, client, store, at("2027-01-01"))["status"] == "waiting"
    result = run(config, client, store, at("2027-01-02"))
    assert result["season"] == 2027 and result["games_fetched"] == 0
    client.samples.append(sample(2027, 2, "2027-04-10"))
    assert run(config, client, store, at("2027-04-11"))["games_fetched"] == 1


def test_current_only_new_recent_and_changed_games(tmp_path):
    config = settings(start_season=2026)
    old = sample(2026, 1, "2026-04-01")
    recent = sample(2026, 2, "2026-09-09")
    client = FakeClient([old, recent])
    store = LocalStore(tmp_path)
    assert run(config, client, store, at("2026-09-10"))["games_fetched"] == 2
    client.calls.clear()
    client.samples.append(sample(2026, 3, "2026-09-10"))
    assert run(config, client, store, at("2026-09-11"))["games_fetched"] == 2
    assert client.calls == [2, 3]
    client.calls.clear()
    old[0]["teams"]["home"]["score"] = 3
    old[1]["teams"]["home"]["players"]["100"]["stats"]["batting"]["runs"] = 3
    assert run(config, client, store, at("2026-09-11"))["games_fetched"] == 1
    assert client.calls == [1]


def test_old_suspended_game_becomes_final(tmp_path):
    config = settings(start_season=2026)
    game, box = sample(2026, 1, "2026-04-01")
    game["status"]["abstractGameState"] = "Live"
    client, store = FakeClient([(game, box)]), LocalStore(tmp_path)
    assert run(config, client, store, at("2026-09-10"))["games_fetched"] == 0
    game["status"]["abstractGameState"] = "Final"
    game["resumeGameDate"] = "2026-09-10"
    assert run(config, client, store, at("2026-09-11"))["games_fetched"] == 1


def test_corrected_rows_replace_removed_player_and_preserve_doubleheader(tmp_path):
    game, box = sample()
    first = parse_boxscore(game, box, "2026-09-10T09:00:00Z")
    game2 = dict(game, gamePk=2, gameNumber=2)
    second = parse_boxscore(game2, box, "2026-09-10T09:00:00Z")
    store = LocalStore(tmp_path)
    store.commit(merge_games(store, [first, second], {}), "initial")
    index = {"1": {"paths": list(first.tables)}}
    home = box["teams"]["home"]
    batter = home["players"].pop("100")
    batter["person"]["id"] = 999
    batter["stats"]["batting"]["hits"] = 1
    home["players"]["999"] = batter
    home["batters"] = [999]
    corrected = parse_boxscore(game, box, "2026-09-11T09:00:00Z")
    store.commit(merge_games(store, [corrected], index), "correct")
    rows = read_table(store, "data/season-2021/league-113/team-10/batting.parquet").to_pylist()
    assert [(r["game_pk"], r["player_id"], r["batting_H"]) for r in rows] == [(1, 999, 1), (2, 100, 2)]


def test_real_boxscore_uses_game_stats_and_skips_bench(tmp_path):
    game = json.loads((FIXTURES / "game_750975.json").read_text())
    box = json.loads((FIXTURES / "boxscore_750975.json").read_text())
    result = parse_boxscore(game, box, "2026-09-13T00:00:00Z")
    store = LocalStore(tmp_path)
    store.commit(merge_games(store, [result], {}), "sample")
    assert len(result.tables) == 4
    for path, rows in result.tables.items():
        table = read_table(store, path)
        kind = Path(path).stem
        assert table.schema == schema_for(kind)
        side = "home" if rows[0]["is_home"] else "away"
        source = box["teams"][side]
        if kind == "batting":
            assert sum(r["batting_H"] for r in rows) == source["teamStats"]["batting"]["hits"]
            assert sum(r["batting_R"] for r in rows) == rows[0]["team_score"]
        assert all(r["game_pk"] == 750975 and r["resume_date"] == "2024-08-02" for r in rows)


def test_null_schema_and_baseball_innings(tmp_path):
    game, box = sample()
    result = parse_boxscore(game, box, "now")
    store = LocalStore(tmp_path)
    store.commit(merge_games(store, [result], {}), "sample")
    pitching = read_table(store, "data/season-2021/league-113/team-10/pitching.parquet").to_pylist()[0]
    assert pitching["pitching_outs"] == 17 and pitching["pitching_IP_str"] == "5.2"
    batting = read_table(store, "data/season-2021/league-113/team-10/batting.parquet").to_pylist()[0]
    assert batting["batting_H"] == 2 and batting["batting_HR"] is None
    with pytest.raises(ValueError):
        stats_columns("pitching", {"inningsPitched": "5.3"})


def test_historical_empty_or_missing_level_is_not_complete(tmp_path):
    with pytest.raises(IncompleteRun, match="No completed games"):
        run(settings(), FakeClient([]), LocalStore(tmp_path), at("2026-09-10"))
    with pytest.raises(IncompleteRun, match="13"):
        run(Settings(sport_ids=(12, 13)), FakeClient([sample()]), LocalStore(tmp_path), at("2026-09-10"))
    assert not (tmp_path / "state/index.json").exists()


def test_narrower_scope_and_malformed_state_fail_closed(tmp_path):
    store = LocalStore(tmp_path)
    store.commit({"state/index.json": json_bytes(initial_state(Settings()))}, "state")
    for narrower in (settings(), Settings(game_types=("R",)), Settings(start_season=2022)):
        with pytest.raises(ValueError, match="scope"):
            run(narrower, FakeClient([]), store, at("2026-09-10"))
    store.commit({"state/index.json": b"not json"}, "broken")
    with pytest.raises(ValueError):
        run(settings(), FakeClient([]), store, at("2026-09-10"))


def test_schedule_failure_does_not_advance(tmp_path):
    client = FakeClient([])
    def fail(season):
        raise FetchError("schedule failed")
    client.schedule = fail
    with pytest.raises(FetchError):
        run(settings(), client, LocalStore(tmp_path), at("2026-09-10"))
    assert not (tmp_path / "state/index.json").exists()


def test_schedule_deduplicates_resumed_games_and_rejects_truncation(monkeypatch):
    game, _ = sample()
    data = {"totalGames": 2, "dates": [{"games": [game]}, {"games": [deepcopy(game)]}]}
    client = MLBClient(settings())
    monkeypatch.setattr(client, "get", lambda *args, **kwargs: data)
    assert len(client.schedule(2021)) == 1
    data["totalGames"] = 3
    with pytest.raises(FetchError, match="Truncated"):
        client.schedule(2021)


def test_malformed_boxscore_rejected():
    game, box = sample()
    box["teams"]["home"]["players"].pop("101")
    with pytest.raises(ValueError, match="pitching"):
        parse_boxscore(game, box, "now")


def test_dataset_viewer_configs_keep_schemas_separate():
    game, box = sample()
    result = parse_boxscore(game, box, "now")
    frontmatter = dataset_card(result.catalog).decode().split("---")[1]
    configs = yaml.safe_load(frontmatter)["configs"]
    assert {c["config_name"] for c in configs} == {"batting", "pitching", "league-113-batting", "league-113-pitching"}
    assert all(c["data_files"][0]["path"].endswith(c["config_name"].split("-")[-1] + ".parquet") for c in configs)


def test_hub_commits_state_and_data_with_parent_guard():
    store = HubStore.__new__(HubStore)
    store.repo_id, store.revision, store.cache = "owner/data", "old-sha", {}
    captured = {}
    def commit(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(oid="new-sha")
    store.api = SimpleNamespace(create_commit=commit)
    files = {"data/test.parquet": b"data", "state/index.json": b"{}"}
    store.commit(files, "checkpoint")
    assert captured["parent_commit"] == "old-sha"
    assert {op.path_in_repo for op in captured["operations"]} == set(files)
    assert store.revision == "new-sha" and store.cache == files
    def fail(**kwargs):
        raise RuntimeError("conflict")
    store.api.create_commit = fail
    with pytest.raises(RuntimeError):
        store.commit({"state/index.json": b"changed"}, "bad")
    assert store.revision == "new-sha" and store.cache["state/index.json"] == b"{}"


@pytest.mark.parametrize("path", ["../token", "/tmp/token", "data/../../token", "..\\token"])
def test_unsafe_dataset_paths_rejected(path):
    with pytest.raises(ValueError):
        safe_path(path)


def test_schema_stays_identical_when_missing_field_appears(tmp_path):
    game, box = sample()
    first = parse_boxscore(game, box, "now")
    store = LocalStore(tmp_path)
    store.commit(merge_games(store, [first], {}), "first")
    path = "data/season-2021/league-113/team-10/batting.parquet"
    before = read_table(store, path).schema
    game["gamePk"] = 2
    box["teams"]["home"]["players"]["100"]["stats"]["batting"]["homeRuns"] = 1
    store.commit(merge_games(store, [parse_boxscore(game, box, "later")], {}), "second")
    table = read_table(store, path)
    assert table.schema == before
    assert table.column("batting_HR").to_pylist() == [None, 1]


def test_pitcher_in_batters_list_does_not_create_a_fake_batting_row():
    game, box = sample()
    box["teams"]["home"]["batters"].append(101)
    result = parse_boxscore(game, box, "now")
    rows = result.tables["data/season-2021/league-113/team-10/batting.parquet"]
    assert [r["player_id"] for r in rows] == [100]


def test_missing_table_cannot_silently_erase_committed_data(tmp_path):
    game, box = sample()
    result = parse_boxscore(game, box, "now")
    index = {"1": {"paths": list(result.tables)}}
    with pytest.raises(ValueError, match="missing"):
        merge_games(LocalStore(tmp_path), [result], index)


def test_missing_game_manifest_fails_closed(tmp_path):
    config = settings()
    state = initial_state(config)
    state["seasons"]["2021"] = {"stored_games": 50}
    store = LocalStore(tmp_path)
    store.commit({"state/index.json": json_bytes(state)}, "state")
    with pytest.raises(ValueError, match="Missing game progress"):
        run(config, FakeClient([sample()]), store, at("2026-09-10"))


def test_partial_team_totals_are_rejected():
    game, box = sample()
    box["teams"]["home"]["teamStats"] = {"batting": {"hits": 10}}
    with pytest.raises(ValueError, match="team total"):
        parse_boxscore(game, box, "now")


def test_runtime_budget_preserves_unfinished_season(tmp_path, monkeypatch):
    clock = iter([0, 61])
    monkeypatch.setattr("scanner.build.time.monotonic", lambda: next(clock))
    store = LocalStore(tmp_path)
    result = run(settings(max_run_minutes=1), FakeClient([sample()]), store, at("2026-09-10"))
    assert result["status"] == "partial" and result["games_fetched"] == 0
    assert not read_json(store, "state/index.json", {})["seasons"]["2021"].get("initialized")


def test_downloaded_team_file_works_with_default_parquet_reader(tmp_path):
    game, box = sample()
    result = parse_boxscore(game, box, "now")
    LocalStore(tmp_path).commit(merge_games(LocalStore(tmp_path), [result], {}), "sample")
    path = tmp_path / "data/season-2021/league-113/team-10/batting.parquet"
    table = pq.read_table(path)
    assert table.schema == schema_for("batting")
    assert table.column("season").to_pylist() == [2021]


def test_offline_hub_read_cannot_be_mistaken_for_missing_state(monkeypatch):
    from huggingface_hub.errors import LocalEntryNotFoundError
    store = HubStore.__new__(HubStore)
    store.repo_id, store.revision, store.cache, store.token = "owner/data", "pinned-sha", {}, "test-only"
    def unavailable(**kwargs):
        assert kwargs["revision"] == "pinned-sha"
        raise LocalEntryNotFoundError("network unavailable and no cached file")
    monkeypatch.setattr("scanner.storage.hf_hub_download", unavailable)
    with pytest.raises(LocalEntryNotFoundError):
        read_json(store, "state/index.json", {})
    assert store.cache == {}


def test_confirmed_remote_missing_file_is_allowed_for_new_dataset(monkeypatch):
    import httpx
    from huggingface_hub.errors import RemoteEntryNotFoundError
    store = HubStore.__new__(HubStore)
    store.repo_id, store.revision, store.cache, store.token = "owner/data", "pinned-sha", {}, "test-only"
    def missing(**kwargs):
        response = httpx.Response(404, request=httpx.Request("GET", "https://huggingface.co/test"))
        raise RemoteEntryNotFoundError("remote file does not exist", response=response)
    monkeypatch.setattr("scanner.storage.hf_hub_download", missing)
    assert read_json(store, "state/index.json", {"new": True}) == {"new": True}


def test_triple_a_and_postseason_rows_keep_their_level_and_game_type(tmp_path):
    client = FakeClient([sample(pk=1, sport=11), sample(pk=2, day="2021-09-25", sport=11, kind="W"),
                         sample(pk=3, day="2021-07-14", sport=11, kind="A")])
    store = LocalStore(tmp_path)
    assert run(Settings(sport_ids=(11,)), client, store, at("2026-09-10"))["games_fetched"] == 3
    rows = read_table(store, "data/season-2021/league-113/team-10/batting.parquet").to_pylist()
    assert [(r["team_level"], r["sport_id"], r["game_type"]) for r in rows] == [
        ("AAA", 11, "R"), ("AAA", 11, "A"), ("AAA", 11, "W")]
    assert read_json(store, "catalog.json", {})["2021/113/10"]["team_level"] == "AAA"


def test_schedule_asks_for_and_keeps_only_configured_game_types(monkeypatch):
    games = [sample(pk=pk, kind=kind)[0] for pk, kind in ((1, "R"), (2, "W"), (3, "S"))]
    asked = []
    def get(path, params):
        asked.append(params["gameTypes"])
        return {"totalGames": 3, "dates": [{"games": deepcopy(games)}]}
    client = MLBClient(settings())
    monkeypatch.setattr(client, "get", get)
    assert [g["gamePk"] for g in client.schedule(2021)] == [1, 2]
    client = MLBClient(settings(game_types=("R",)))
    monkeypatch.setattr(client, "get", get)
    assert [g["gamePk"] for g in client.schedule(2021)] == [1]
    assert asked == ["R,F,D,L,W,C,P,A,E", "R"]


def test_settings_read_levels_and_game_types_from_environment(monkeypatch):
    monkeypatch.setenv("SPORT_IDS", "12, 11")
    monkeypatch.setenv("GAME_TYPES", "w,R")
    assert Settings.from_env().scope() == {"start_season": 2021, "sport_ids": [11, 12], "game_types": ["R", "W"]}
    monkeypatch.delenv("SPORT_IDS")
    monkeypatch.delenv("GAME_TYPES")
    assert Settings.from_env() == Settings()
    assert Settings().scope()["sport_ids"] == [11, 12, 13, 14, 17]
    for bad in ({"game_types": ("S",)}, {"game_types": ()}, {"sport_ids": (16,)}, {"game_types": ("R", "R")}):
        with pytest.raises(ValueError):
            Settings(**bad)


def test_wider_scope_reopens_finished_seasons_and_fetches_only_new_games(tmp_path):
    old = Settings(sport_ids=(12,), game_types=("R",))
    client = FakeClient([sample(2021, 1), sample(2022, 2)])
    store = LocalStore(tmp_path)
    for day in ("2026-09-10", "2026-09-11"):
        assert run(old, client, store, at(day))["status"] == "complete"
    # The upgraded workflow adds Triple-A and the postseason to a dataset that was already complete.
    client.samples += [sample(2021, 3, sport=11), sample(2021, 4, "2021-09-25", kind="W"), sample(2022, 5, sport=11)]
    new = Settings(sport_ids=(11, 12), start_season=2021)
    first = run(new, client, store, at("2026-09-12"))
    assert (first["season"], first["games_fetched"], first["status"]) == (2021, 2, "complete")
    assert run(new, client, store, at("2026-09-12"))["status"] == "waiting"
    state = read_json(store, "state/index.json", {})
    assert state["scope"] == new.scope()
    assert state["seasons"]["2021"]["final_complete"] and not state["seasons"]["2022"]["initialized"]
    second = run(new, client, store, at("2026-09-13"))
    assert (second["season"], second["games_fetched"], second["stored_games"]) == (2022, 1, 2)
    assert client.calls == [1, 2, 3, 4, 5]
    rows = read_table(store, "data/season-2021/league-113/team-10/batting.parquet").to_pylist()
    assert sorted((r["game_pk"], r["team_level"], r["game_type"]) for r in rows) == [(1, "AA", "R"), (3, "AAA", "R"), (4, "AA", "W")]
    with pytest.raises(ValueError, match="scope"):
        run(old, client, store, at("2026-09-14"))


def test_postponed_game_is_collected_once_it_is_made_up(tmp_path):
    # A postponed game is "Final" with no score, so it is excluded. The make-up keeps the same
    # game ID: the exclusion must end when the schedule entry changes, and only then.
    config = settings(start_season=2026)
    game, box = sample(2026, 1, "2026-06-01")
    game["teams"]["home"]["score"] = None
    client, store = FakeClient([(game, box)]), LocalStore(tmp_path)
    assert run(config, client, store, at("2026-06-02"))["excluded_games"] == 1
    assert run(config, client, store, at("2026-06-03"))["games_fetched"] == 0
    assert client.calls == [1]
    game["teams"]["home"]["score"] = 2
    made_up = run(config, client, store, at("2026-06-21"))
    assert (made_up["games_fetched"], made_up["excluded_games"], made_up["stored_games"]) == (1, 0, 1)
    assert read_json(store, "state/index.json", {})["seasons"]["2026"]["excluded_games"] == {}


def test_exclusion_recorded_before_signatures_is_checked_once_more(tmp_path):
    config = settings()
    broken, good = sample(pk=1), sample(pk=2)
    broken[0]["teams"]["home"]["score"] = None
    client, store = FakeClient([broken, good]), LocalStore(tmp_path)
    def reopen(legacy=False):
        state = read_json(store, "state/index.json", {})
        state["seasons"]["2021"].update(initialized=False, final_complete=False)
        if legacy:
            del state["seasons"]["2021"]["excluded_games"]["1"]["signature"]  # as written by the previous release
        store.commit({"state/index.json": json_bytes(state)}, "reopen")
    run(config, client, store, at("2026-09-10"))
    reopen(legacy=True)
    assert run(config, client, store, at("2026-09-11"))["excluded_games"] == 1
    reopen()
    assert run(config, client, store, at("2026-09-12"))["status"] == "complete"
    assert client.calls == [1, 2, 1]


def test_runs_forgotten_through_the_off_season_are_caught_up_year_by_year(tmp_path):
    config = settings(start_season=2026)
    client = FakeClient([sample(2026, 1, "2026-07-30")])
    store = LocalStore(tmp_path)
    assert run(config, client, store, at("2026-08-01"))["games_fetched"] == 1
    # Nobody runs the job from August until the next May.
    client.samples += [sample(2026, 2, "2026-08-20"), sample(2026, 3, "2026-09-25", kind="W"),
                       sample(2027, 4, "2027-04-10")]
    first = run(config, client, store, at("2027-05-10"))
    assert (first["season"], first["games_fetched"], first["status"]) == (2026, 2, "complete")
    assert run(config, client, store, at("2027-05-10"))["status"] == "waiting"
    second = run(config, client, store, at("2027-05-11"))
    assert (second["season"], second["games_fetched"]) == (2027, 1)
    state = read_json(store, "state/index.json", {})
    assert state["seasons"]["2026"]["final_complete"] and state["seasons"]["2027"]["initialized"]
    assert client.calls == [1, 2, 3, 4]


def test_a_year_that_was_never_run_is_scraped_before_the_current_one(tmp_path):
    config = settings(start_season=2026)
    client = FakeClient([sample(2026, 1), sample(2027, 2), sample(2028, 3, "2028-04-10")])
    store = LocalStore(tmp_path)
    run(config, client, store, at("2026-06-02"))
    days = ("2028-05-01", "2028-05-02", "2028-05-03")
    assert [run(config, client, store, at(day))["season"] for day in days] == [2026, 2027, 2028]
    assert client.calls == [1, 2, 3]


def test_winter_season_stays_open_into_the_new_year_and_closes_after_its_last_game(tmp_path):
    config = Settings(sport_ids=(12, 17), start_season=2026)
    summer = sample(2026, 9, "2026-06-01")
    december, january = sample(2026, 1, "2026-12-20", sport=17), sample(2026, 2, "2027-01-20", sport=17)
    january[0]["status"]["abstractGameState"] = "Preview"
    client, store = FakeClient([summer, december, january]), LocalStore(tmp_path)
    final = lambda: read_json(store, "state/index.json", {})["seasons"]["2026"]["final_complete"]
    assert run(config, client, store, at("2026-12-21"))["games_fetched"] == 2
    # New Year: the 2026 season still has a game to play, so it is not closed and 2027 does not start.
    saved = store.read("state/index.json")
    new_year = run(config, client, store, at("2027-01-02"))
    assert (new_year["season"], new_year["games_fetched"]) == (2026, 0)
    assert store.read("state/index.json") == saved  # a quiet day writes nothing
    january[0]["status"]["abstractGameState"] = "Final"
    played = run(config, client, store, at("2027-01-21"))
    assert (played["season"], played["games_fetched"]) == (2026, 1) and not final()
    # Stat corrections still arrive inside the refresh window, as for a current season.
    assert run(config, client, store, at("2027-01-22"))["games_fetched"] == 1
    # Frozen 30 days after the last game, not before; the next year starts the day after.
    assert run(config, client, store, at("2027-02-18"))["season"] == 2026 and not final()
    assert run(config, client, store, at("2027-02-19"))["season"] == 2026 and final()
    assert run(config, client, store, at("2027-02-19"))["status"] == "waiting"
    assert run(config, client, store, at("2027-02-20"))["season"] == 2027
    assert client.calls == [9, 1, 2, 2]
    row = read_table(store, "data/season-2026/league-113/team-10/batting.parquet").to_pylist()[-1]
    assert (row["season"], row["game_date"], row["team_level"]) == (2026, "2027-01-20", "WIN")


def test_stray_scheduled_game_cannot_hold_a_past_season_open_beyond_march(tmp_path):
    config = settings(start_season=2026)
    stray = sample(2026, 2, "2027-09-01")
    stray[0]["status"]["abstractGameState"] = "Preview"
    client, store = FakeClient([sample(2026, 1), stray]), LocalStore(tmp_path)
    final = lambda: read_json(store, "state/index.json", {})["seasons"]["2026"]["final_complete"]
    run(config, client, store, at("2026-06-02"))
    assert run(config, client, store, at("2027-03-30"))["season"] == 2026 and not final()
    assert run(config, client, store, at("2027-03-31"))["season"] == 2026 and final()
    assert run(config, client, store, at("2027-04-01"))["season"] == 2027


def test_schedule_remembers_the_last_day_a_game_is_listed_under(monkeypatch):
    # Shapes taken from the live feed. A postponed game keeps its entry on the old day, with the new
    # official date; a suspended game is listed again on the day it resumes, with nothing else changed.
    postponed, makeup = sample(pk=1, day="2021-06-20")[0], sample(pk=1, day="2021-06-20")[0]
    makeup["status"]["abstractGameState"] = "Preview"
    suspended = sample(pk=2, day="2021-06-02")[0]
    suspended["status"]["abstractGameState"] = "Live"
    data = {"totalGames": 4, "dates": [{"date": "2021-06-01", "games": [postponed]},
                                       {"date": "2021-06-02", "games": [suspended]},
                                       {"date": "2021-06-20", "games": [makeup]},
                                       {"date": "2021-07-04", "games": [deepcopy(suspended)]}]}
    client = MLBClient(settings())
    monkeypatch.setattr(client, "get", lambda *args, **kwargs: data)
    games = {g["gamePk"]: g for g in client.schedule(2021)}
    assert games[1]["status"]["abstractGameState"] == "Final" and games[1]["listed_until"] == "2021-06-20"
    assert (games[2]["officialDate"], games[2]["listed_until"]) == ("2021-06-02", "2021-07-04")
    schedule = list(games.values())
    assert still_played(schedule, 2021, date(2021, 8, 2)) and not still_played(schedule, 2021, date(2021, 8, 3))


def test_game_waiting_to_be_resumed_next_year_keeps_its_season_open(tmp_path, monkeypatch):
    # The real client and the run together: only the day the suspended game is listed under says that
    # the 2026 season is not over.
    played, box = sample(2026, 1, "2026-11-01", sport=17)
    suspended = sample(2026, 2, "2026-11-02", sport=17)[0]
    suspended["status"]["abstractGameState"] = "Live"
    listing = {"totalGames": 3, "dates": [{"date": "2026-11-01", "games": [played]},
                                          {"date": "2026-11-02", "games": [suspended]},
                                          {"date": "2027-02-10", "games": [deepcopy(suspended)]}]}
    config = Settings(sport_ids=(17,), start_season=2026)
    client = MLBClient(config)
    monkeypatch.setattr(client, "get", lambda path, params=None: deepcopy(box if "boxscore" in path else listing))
    store = LocalStore(tmp_path)
    assert run(config, client, store, at("2026-11-03"))["games_fetched"] == 1
    result = run(config, client, store, at("2027-01-05"))
    assert result["season"] == 2026
    assert not read_json(store, "state/index.json", {})["seasons"]["2026"]["final_complete"]
