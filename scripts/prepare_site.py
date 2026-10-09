"""Prepare only validator-approved generated files for the static site."""

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.validate_json import DatasetValidationError, validate_dataset

META_KEYS = {"generated_at", "source_generated_at", "is_stale", "run_id"}


def validate_metadata(path_or_data):
    if isinstance(path_or_data, (str, Path)):
        try:
            value = json.loads(Path(path_or_data).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("metadata is not valid JSON") from exc
    else:
        value = path_or_data
    if not isinstance(value, dict) or set(value) != META_KEYS:
        raise ValueError("metadata keys do not match the contract")
    for key in ("generated_at", "source_generated_at"):
        if not isinstance(value[key], str) or not value[key]:
            raise ValueError(f"metadata {key} must be non-empty")
        try:
            datetime.fromisoformat(value[key].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"metadata {key} must be ISO-8601") from exc
    if not isinstance(value["is_stale"], bool):
        raise ValueError("metadata is_stale must be boolean")
    if not isinstance(value["run_id"], str) or not value["run_id"].strip():
        raise ValueError("metadata run_id must be non-empty")
    return value


def prepare_site(dataset_path, metadata_path, output_dir, repo_root, allow_hero_assets=False):
    dataset_path = Path(dataset_path)
    metadata_path = Path(metadata_path)
    output_dir = Path(output_dir)
    repo_root = Path(repo_root)
    validate_dataset(dataset_path)
    metadata = validate_metadata(metadata_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "classement.json").write_bytes(dataset_path.read_bytes())
    (output_dir / "data-meta.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    generated_assets = output_dir / "assets" / "heroes"
    if generated_assets.exists():
        shutil.rmtree(generated_assets)
    if allow_hero_assets:
        source_assets = repo_root / "images"
        heroes = set()
        data = json.loads(dataset_path.read_text(encoding="utf-8"))
        for role in ("Tank", "Damage", "Support"):
            heroes.update(data[role])
        generated_assets.mkdir(parents=True, exist_ok=True)
        for hero in sorted(heroes):
            source = source_assets / f"{hero}.png"
            if source.is_file():
                shutil.copy2(source, generated_assets / source.name)
    return output_dir


def main_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--allow-hero-assets", action="store_true")
    args = parser.parse_args()
    try:
        prepare_site(args.dataset, args.metadata, args.output, args.repo_root, args.allow_hero_assets)
    except (DatasetValidationError, ValueError, OSError) as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(f"Prepared site data in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
