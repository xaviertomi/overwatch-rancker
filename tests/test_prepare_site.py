import json
from pathlib import Path

import pytest

from scripts.prepare_site import prepare_site

FIXTURES = Path(__file__).parent / "fixtures"
META = {"generated_at": "2026-10-09T20:00:00Z", "source_generated_at": "2026-10-09T20:00:00Z", "is_stale": False, "run_id": "test-run"}


def test_prepare_site_copies_relative_generated_pair(tmp_path):
    dataset = tmp_path / "input.json"
    dataset.write_bytes((FIXTURES / "classement-valid.json").read_bytes())
    metadata = tmp_path / "meta.json"
    metadata.write_text(json.dumps(META), encoding="utf-8")
    output = tmp_path / "docs"
    prepare_site(dataset, metadata, output, tmp_path)
    assert (output / "classement.json").read_bytes() == dataset.read_bytes()
    assert json.loads((output / "data-meta.json").read_text(encoding="utf-8")) == META
    assert not (output / "assets").exists()


def test_prepare_site_refuses_invalid_source(tmp_path):
    invalid = tmp_path / "bad.json"
    invalid.write_text("{}", encoding="utf-8")
    metadata = tmp_path / "meta.json"
    metadata.write_text(json.dumps(META), encoding="utf-8")
    with pytest.raises(ValueError):
        prepare_site(invalid, metadata, tmp_path / "docs", tmp_path)


def test_prepare_site_asset_switch(tmp_path):
    dataset = tmp_path / "input.json"
    dataset.write_bytes((FIXTURES / "classement-valid.json").read_bytes())
    metadata = tmp_path / "meta.json"
    metadata.write_text(json.dumps(META), encoding="utf-8")
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "dva.png").write_bytes(b"png")
    output = tmp_path / "docs"
    prepare_site(dataset, metadata, output, tmp_path, allow_hero_assets=True)
    assert (output / "assets" / "heroes" / "dva.png").read_bytes() == b"png"
