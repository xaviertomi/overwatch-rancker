import json
from pathlib import Path
from unittest.mock import patch

import pytest

import config
from scripts.update_dataset import UpdateError, run_update

FIXTURE = Path(__file__).parent / "fixtures" / "classement-valid.json"


def metadata(stale=False):
    return {"generated_at": "2026-10-09T20:00:00Z", "source_generated_at": "2026-10-09T20:00:00Z", "is_stale": stale, "run_id": "cache"}


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
    assert json.loads((tmp_path / "docs" / "data-meta.json").read_text())["is_stale"] is False


def test_partial_failure_uses_valid_cache_and_preserves_bytes(tmp_path):
    cache = tmp_path / "cache"
    write_cache(cache)
    work = tmp_path / "work"
    before = (cache / "classement.json").read_bytes()
    with patch("scripts.update_dataset.ranking.main", return_value={"complete": False, "private_or_unavailable": 1}):
        result = run_update(work, cache, tmp_path / "docs", tmp_path, run_id="stale")
    assert result["outcome"] == "stale"
    assert (tmp_path / "docs" / "classement.json").read_bytes() == before
    written_meta = json.loads((tmp_path / "docs" / "data-meta.json").read_text())
    assert written_meta["is_stale"] is True
    assert written_meta["source_generated_at"] == "2026-10-09T20:00:00Z"


def test_invalid_cache_and_no_cache_failure(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "classement.json").write_text("{}", encoding="utf-8")
    (cache / "data-meta.json").write_text(json.dumps(metadata()), encoding="utf-8")
    with patch("scripts.update_dataset.ranking.main", return_value={"complete": False, "invalid_responses": 1}):
        with pytest.raises(UpdateError):
            run_update(tmp_path / "work", cache, tmp_path / "docs", tmp_path)
    assert not (tmp_path / "docs").exists()
