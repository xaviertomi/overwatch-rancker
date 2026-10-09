"""Validate the generated ranking JSON contract."""

import argparse
import json
import math
from collections.abc import Mapping
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import heroes

ROOT_KEYS = {"Résumé_Joueurs", "Tank", "Damage", "Support"}
RANKING_KEYS = {
    "pseudo", "score", "Temps_Jeu_Heures", "Winrate_%", "KDA",
    "Elims_Moyenne", "Assists_Moyenne", "Degats_Moyenne", "Soins_Moyenne",
}
ROLE_NAMES = {"Tank", "Damage", "Support"}


class DatasetValidationError(ValueError):
    """Raised when a dataset is unsafe to publish."""


def _finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DatasetValidationError(f"{label} must be a finite number")
    return value


def validate_dataset(path_or_data):
    if isinstance(path_or_data, (str, Path)):
        path = Path(path_or_data)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DatasetValidationError(f"cannot read valid JSON: {path}") from exc
    else:
        data = path_or_data
    if not isinstance(data, Mapping) or set(data) != ROOT_KEYS:
        raise DatasetValidationError("dataset root keys do not match the contract")
    summary = data["Résumé_Joueurs"]
    if not isinstance(summary, Mapping):
        raise DatasetValidationError("Résumé_Joueurs must be an object")
    for pseudo, entry in summary.items():
        if not isinstance(pseudo, str) or not pseudo.strip():
            raise DatasetValidationError("summary pseudo keys must be non-empty strings")
        if not isinstance(entry, Mapping) or set(entry) != {"Temps_Jeu_Total_Heures"}:
            raise DatasetValidationError(f"invalid summary entry for {pseudo}")
        _finite_number(entry["Temps_Jeu_Total_Heures"], f"summary hours for {pseudo}")

    ranked_count = 0
    for role in ROLE_NAMES:
        role_data = data[role]
        if not isinstance(role_data, Mapping):
            raise DatasetValidationError(f"{role} must be an object")
        for hero, records in role_data.items():
            if hero not in heroes.HERO_ROLES or heroes.HERO_ROLES[hero] != role:
                raise DatasetValidationError(f"{hero} is not a valid {role} hero")
            if not isinstance(records, list):
                raise DatasetValidationError(f"{role}/{hero} must be a list")
            seen = set()
            for record in records:
                ranked_count += 1
                if not isinstance(record, Mapping) or set(record) != RANKING_KEYS:
                    raise DatasetValidationError(f"invalid ranking record for {role}/{hero}")
                pseudo = record["pseudo"]
                if not isinstance(pseudo, str) or not pseudo.strip():
                    raise DatasetValidationError(f"non-empty pseudo required for {role}/{hero}")
                if pseudo in seen:
                    raise DatasetValidationError(f"duplicate pseudo {pseudo} in {role}/{hero}")
                seen.add(pseudo)
                score = _finite_number(record["score"], f"score for {pseudo}")
                if not 0 <= score <= 100:
                    raise DatasetValidationError(f"score out of range for {pseudo}")
                for key, value in record.items():
                    if key != "pseudo":
                        _finite_number(value, f"{key} for {pseudo}")
    if not summary and ranked_count == 0:
        raise DatasetValidationError("dataset contains no summary entry and no ranked player")
    return data


def main_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        validate_dataset(args.path)
    except DatasetValidationError as exc:
        print(f"INVALID: {exc}")
        return 1
    print(f"VALID: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
