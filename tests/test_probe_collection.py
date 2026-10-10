import config

from scripts import probe_collection


def test_probe_marks_recognized_but_unplayed_hero_as_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PLAYERS", ["Probe-1"])
    monkeypatch.setattr(config, "MODES", ["quickplay"])
    monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path / "results"))

    def get_stats(player_id, mode, collection_report):
        collection_report["outcomes"][(player_id, mode)] = {
            "classification": "successful_responses",
            "status": 200,
        }
        return {"heroes": {"dva": {"time_played": 0}}}

    monkeypatch.setattr(probe_collection.main, "get_player_stats", get_stats)
    report = probe_collection.run_probe()

    request = report["requests"][0]
    assert request["hero_container_path"] == "heroes"
    assert request["recognized_hero_count"] == 1
    assert request["legitimately_empty_mode"] is True
    assert "time_played" not in request
    assert not (tmp_path / "results").exists()
