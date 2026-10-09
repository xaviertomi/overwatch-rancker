import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import config
import heroes
import main
from scripts.collection_policy import PolicyError, validate_policy


class FakeResponse:
    def __init__(self, status=200, payload=None, json_error=None):
        self.status_code = status
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("bad json")
        return self._payload


def hero_payload(time=36000, eliminations=600, assists=60, deaths=100, games_won=30, games_played=50):
    return {"heroes": {"dva": {
        "time_played": time, "eliminations": eliminations, "assists": assists,
        "deaths": deaths, "games_won": games_won, "games_played": games_played,
        "hero_damage_done": 100000, "healing_done": 5000,
    }}}


def test_get_player_stats_classifies_retry_and_success(monkeypatch):
    responses = [FakeResponse(503), FakeResponse(429), FakeResponse(200, {})]
    monkeypatch.setattr(main.time, "sleep", lambda _: None)
    with patch.object(main.requests, "get", side_effect=responses) as request:
        report = {"outcomes": {}}
        assert main.get_player_stats("A-1", "quickplay", report) == {}
        assert request.call_count == 3
        assert report["outcomes"][("A-1", "quickplay")]["classification"] == "successful_responses"


def test_get_player_stats_classifies_failures(monkeypatch):
    monkeypatch.setattr(main.time, "sleep", lambda _: None)
    with patch.object(main.requests, "get", return_value=FakeResponse(404)):
        report = {"outcomes": {}}
        assert main.get_player_stats("A-1", "competitive", report) is None
        assert report["outcomes"][("A-1", "competitive")]["classification"] == "private_or_unavailable"
    with patch.object(main.requests, "get", return_value=FakeResponse(200, [], None)):
        report = {"outcomes": {}}
        assert main.get_player_stats("A-1", "competitive", report) is None
        assert report["outcomes"][("A-1", "competitive")]["classification"] == "invalid_responses"


def test_extract_stats_shapes_precedence_and_reconstruction():
    extracted = main.extract_stats({
        "totals": [{"key": "time_played", "value": 600}],
        "average": [{"key": "eliminations", "value": 5}, {"key": "damage", "value": 100}],
        "extra": {"assists": 2, "games_won": 3},
        "scalar": 9,
    })
    assert extracted["time_played"] == 600
    assert extracted["eliminations"] == 5
    assert extracted["damage_done"] == 100
    assert extracted["assists"] == 2
    assert extracted["games_played"] == 6
    assert main.extract_stats({"average": {"healing": 2}, "time_played": -1})["healing_done"] == 0
    assert main.extract_stats({"average": "bad", "time_played": 0})["deaths"] == 0


def test_extract_stats_total_precedes_average_and_aliases():
    value = main.extract_stats({
        "time_played": 600,
        "eliminations": 9,
        "average": {"eliminations": 99, "damage_avg": 3, "healing_avg": 4, "deaths_avg": 2, "assists_avg": 1},
    })
    assert value["eliminations"] == 9
    assert value["damage_done"] == 3
    assert value["healing_done"] == 4
    assert value["deaths"] == 2
    assert value["assists"] == 1


def test_calculate_norm_boundaries():
    assert main.calculate_norm(5, 5, 5) == 1.0
    assert main.calculate_norm(0, 10, 0) == 1.0
    assert main.calculate_norm(-1, 0, 10) == 0.0
    assert main.calculate_norm(11, 0, 10) == 1.0
    assert main.calculate_norm(2, 0, 10, True) == 0.8


def test_policy_requires_confirmed_configured_pairs():
    base = {"version": 1, "excluded_requests": []}
    assert validate_policy(base, ["A-1"], ["quickplay"]) == base
    malformed = {"version": 1, "excluded_requests": [{"player_id": "A-1", "gamemode": "quickplay"}]}
    with pytest.raises(PolicyError):
        validate_policy(malformed, ["A-1"], ["quickplay"])


def test_main_report_and_output_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PLAYERS", ["Alpha-1", "Bravo-2"])
    monkeypatch.setattr(config, "MODES", ["quickplay", "competitive"])
    monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path / "results"))
    monkeypatch.setattr(config, "COLLECTION_POLICY_PATH", str(tmp_path / "policy.json"))
    monkeypatch.setattr(config, "REQUEST_DELAY_SECONDS", 0)
    (tmp_path / "policy.json").write_text(json.dumps({"version": 1, "excluded_requests": []}), encoding="utf-8")
    payloads = {
        ("Alpha-1", "quickplay"): hero_payload(36000, 600),
        ("Alpha-1", "competitive"): hero_payload(18000, 300),
        ("Bravo-2", "quickplay"): {},
        ("Bravo-2", "competitive"): hero_payload(7200, 100),
    }
    def response(url, params, timeout):
        player = url.rsplit("/", 3)[-3]
        return FakeResponse(200, payloads[(player, params["gamemode"])])
    with patch.object(main.requests, "get", side_effect=response):
        report = main.main()
    assert report == {
        "configured_requests": 4, "excluded_requests": 0, "expected_requests": 4,
        "attempted_requests": 4, "successful_responses": 4,
        "private_or_unavailable": 0, "transient_failures": 0,
        "invalid_responses": 0, "complete": True,
    }
    data = json.loads((tmp_path / "results" / "classement.json").read_text(encoding="utf-8"))
    assert set(data) == {"Résumé_Joueurs", "Tank", "Damage", "Support"}
    assert "Morts_Moyenne" not in json.dumps(data)
    assert list(data["Résumé_Joueurs"]) == ["Alpha", "Bravo"]


def test_main_failure_makes_complete_false(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PLAYERS", ["Alpha-1"])
    monkeypatch.setattr(config, "MODES", ["quickplay", "competitive"])
    monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path / "results"))
    monkeypatch.setattr(config, "COLLECTION_POLICY_PATH", str(tmp_path / "policy.json"))
    monkeypatch.setattr(config, "REQUEST_DELAY_SECONDS", 0)
    (tmp_path / "policy.json").write_text(json.dumps({"version": 1, "excluded_requests": []}), encoding="utf-8")
    with patch.object(main.requests, "get", side_effect=[FakeResponse(200, hero_payload()), FakeResponse(404)]), patch.object(main.time, "sleep", lambda _: None):
        report = main.main()
    assert report["private_or_unavailable"] == 1
    assert report["complete"] is False
