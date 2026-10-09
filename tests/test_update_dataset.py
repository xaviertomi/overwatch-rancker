import json
from pathlib import Path
from unittest.mock import patch

import pytest

import config
import main
from scripts.update_dataset import UpdateError, run_update

FIXTURE = Path(__file__).parent / "fixtures" / "classement-valid.json"


def metadata(stale=False):
    return {
        "generated_at": "2026-10-09T20:00:00Z",
        "source_generated_at": "2026-10-09T20:00:00Z",
        "is_stale": stale,
        "run_id": "cache",
    }


def write_cache(directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "classement.json").write_bytes(FIXTURE.read_bytes())
    (directory / "data-meta.json").write_text(json.dumps(metadata()), encoding="utf-8")


def test_fresh_complete_success(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", "results")
    work = tmp_path / "work"

    def fresh_pipeline():
        candidate = work / "candidate" / "classement.json"
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(FIXTURE.read_bytes())
        return {"complete": True, "successful_responses": 1}

    with patch("scripts.update_dataset.ranking.main", side_effect=fresh_pipeline):
        result = run_update(work, tmp_path / "cache", tmp_path / "docs", tmp_path, run_id="fresh")

    assert result["outcome"] == "fresh"
    assert result["dataset"] == work / "classement.json"
    assert result["metadata"] == work / "data-meta.json"
    assert (work / "classement.json").read_bytes() == FIXTURE.read_bytes()
    fresh_meta = json.loads((work / "data-meta.json").read_text())
    assert fresh_meta["is_stale"] is False
    assert fresh_meta["source_generated_at"] == fresh_meta["generated_at"]
    assert json.loads((tmp_path / "docs" / "data-meta.json").read_text()) == fresh_meta


@pytest.mark.parametrize(
    "failure",
    [
        {"complete": False, "private_or_unavailable": 1},
        {"complete": False, "transient_failures": 1},
        {"complete": False, "invalid_responses": 1},
    ],
)
def test_incomplete_collection_uses_valid_cache_and_preserves_bytes(tmp_path, failure):
    cache = tmp_path / "cache"
    write_cache(cache)
    work = tmp_path / "work"
    before = (cache / "classement.json").read_bytes()

    with patch("scripts.update_dataset.ranking.main", return_value=failure):
        result = run_update(work, cache, tmp_path / "docs", tmp_path, run_id="stale")

    assert result["outcome"] == "stale"
    assert (tmp_path / "docs" / "classement.json").read_bytes() == before
    written_meta = json.loads((tmp_path / "docs" / "data-meta.json").read_text())
    assert written_meta["is_stale"] is True
    assert written_meta["source_generated_at"] == "2026-10-09T20:00:00Z"


def test_empty_mode_response_counts_as_success(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PLAYERS", ["Empty-1"])
    monkeypatch.setattr(config, "MODES", ["quickplay"])
    monkeypatch.setattr(config, "COLLECTION_POLICY_PATH", str(tmp_path / "policy.json"))
    monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path / "raw"))
    monkeypatch.setattr(config, "REQUEST_DELAY_SECONDS", 0)
    (tmp_path / "policy.json").write_text(
        json.dumps({"version": 1, "excluded_requests": []}), encoding="utf-8"
    )
    with patch.object(main.requests, "get") as request:
        request.return_value.status_code = 200
        request.return_value.json.return_value = {}
        report = main.main()
    assert report["successful_responses"] == 1
    assert report["complete"] is True


def test_invalid_cache_and_no_cache_failure(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "classement.json").write_text("{}", encoding="utf-8")
    (cache / "data-meta.json").write_text(json.dumps(metadata()), encoding="utf-8")
    site = tmp_path / "docs"
    (site / "assets" / "heroes").mkdir(parents=True)
    (site / "index.html").write_text("static page", encoding="utf-8")
    (site / "classement.json").write_text("old data", encoding="utf-8")
    (site / "data-meta.json").write_text(json.dumps(metadata()), encoding="utf-8")
    (site / "assets" / "heroes" / "dva.png").write_bytes(b"old asset")
    with patch("scripts.update_dataset.ranking.main", return_value={"complete": False, "invalid_responses": 1}):
        with pytest.raises(UpdateError):
            run_update(tmp_path / "work", cache, site, tmp_path)
    assert (site / "index.html").read_text(encoding="utf-8") == "static page"
    assert not (site / "classement.json").exists()
    assert not (site / "data-meta.json").exists()
    assert not (site / "assets" / "heroes").exists()
