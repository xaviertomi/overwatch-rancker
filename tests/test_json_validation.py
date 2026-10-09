import json
from pathlib import Path

import pytest

from scripts.validate_json import DatasetValidationError, validate_dataset

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_and_empty_hero_fixtures():
    assert validate_dataset(FIXTURES / "classement-valid.json")["Tank"]["dva"]
    assert validate_dataset(FIXTURES / "classement-empty-hero.json")["Tank"]["dva"] == []


def test_rejects_malformed_foreign_and_nonfinite(tmp_path):
    with pytest.raises(DatasetValidationError):
        validate_dataset(FIXTURES / "classement-malformed.json")
    data = json.loads((FIXTURES / "classement-valid.json").read_text(encoding="utf-8"))
    data["Résumé_Joueurs"]["Alpha"]["Temps_Jeu_Total_Heures"] = float("nan")
    with pytest.raises(DatasetValidationError):
        validate_dataset(data)
    data = json.loads((FIXTURES / "classement-valid.json").read_text(encoding="utf-8"))
    data["Tank"]["ashe"] = []
    with pytest.raises(DatasetValidationError):
        validate_dataset(data)


def test_rejects_duplicate_pseudo_and_all_empty(tmp_path):
    data = json.loads((FIXTURES / "classement-valid.json").read_text(encoding="utf-8"))
    data["Tank"]["dva"].append(dict(data["Tank"]["dva"][0]))
    with pytest.raises(DatasetValidationError):
        validate_dataset(data)
    empty = {"Résumé_Joueurs": {}, "Tank": {}, "Damage": {}, "Support": {}}
    with pytest.raises(DatasetValidationError):
        validate_dataset(empty)


def test_summary_has_exact_shape_and_no_redundant_pseudo():
    data = json.loads((FIXTURES / "classement-valid.json").read_text(encoding="utf-8"))
    data["Résumé_Joueurs"]["Alpha"]["pseudo"] = "Alpha"
    with pytest.raises(DatasetValidationError):
        validate_dataset(data)
