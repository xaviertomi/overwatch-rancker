"""Run a complete collection, or publish a validator-approved stale cache."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
import main as ranking
from scripts.prepare_site import prepare_site, validate_metadata
from scripts.validate_json import DatasetValidationError, validate_dataset


class UpdateError(RuntimeError):
    """Raised when no safe deployable dataset exists."""


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_valid_cache(cache_dir):
    dataset = Path(cache_dir) / "classement.json"
    metadata = Path(cache_dir) / "data-meta.json"
    if not dataset.is_file() or not metadata.is_file():
        return None
    try:
        validate_dataset(dataset)
        meta = validate_metadata(metadata)
    except (DatasetValidationError, ValueError, OSError):
        return None
    return dataset, metadata, meta


def _write_metadata(path, generated_at, source_generated_at, is_stale, run_id):
    value = {
        "generated_at": generated_at,
        "source_generated_at": source_generated_at,
        "is_stale": is_stale,
        "run_id": run_id,
    }
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    validate_metadata(path)


def _clear_generated_site_data(site_dir):
    for name in ("classement.json", "data-meta.json"):
        (site_dir / name).unlink(missing_ok=True)
    hero_assets = site_dir / "assets" / "heroes"
    if hero_assets.is_dir():
        shutil.rmtree(hero_assets)


def run_update(work_dir, cache_dir, site_dir, repo_root=".", run_id=None, allow_hero_assets=False):
    work_dir = Path(work_dir)
    cache_dir = Path(cache_dir)
    site_dir = Path(site_dir)
    repo_root = Path(repo_root)
    work_dir.mkdir(parents=True, exist_ok=True)
    cache = _read_valid_cache(cache_dir)
    run_id = run_id or uuid.uuid4().hex
    candidate_dir = work_dir / "candidate"
    if candidate_dir.exists():
        shutil.rmtree(candidate_dir)
    candidate_dir.mkdir(parents=True)
    previous_output = config.OUTPUT_DIR
    report = None
    try:
        config.OUTPUT_DIR = str(candidate_dir)
        report = ranking.main()
    except Exception as exc:
        print(f"Fresh collection failed: {exc}")
    finally:
        config.OUTPUT_DIR = previous_output

    fresh_dataset = candidate_dir / "classement.json"
    fresh_complete = isinstance(report, dict) and report.get("complete") is True
    if fresh_complete:
        try:
            validate_dataset(fresh_dataset)
            generated_at = _now()
            fresh_output = work_dir / "classement.json"
            fresh_meta = work_dir / "data-meta.json"
            shutil.copyfile(fresh_dataset, fresh_output)
            _write_metadata(fresh_meta, generated_at, generated_at, False, run_id)
            prepare_site(fresh_output, fresh_meta, site_dir, repo_root, allow_hero_assets)
            print(f"Update outcome: fresh; report={json.dumps(report, ensure_ascii=False)}")
            return {"outcome": "fresh", "report": report, "dataset": fresh_output, "metadata": fresh_meta}
        except (DatasetValidationError, ValueError, OSError) as exc:
            print(f"Fresh candidate rejected: {exc}")

    if cache is None:
        reason = "no validator-approved cache is available"
        print(f"Update outcome: abort; {reason}; report={json.dumps(report, ensure_ascii=False)}")
        for name in ("classement.json", "data-meta.json"):
            (work_dir / name).unlink(missing_ok=True)
        _clear_generated_site_data(site_dir)
        raise UpdateError(reason)

    cached_dataset, cached_meta_path, cached_meta = cache
    fallback_dataset = work_dir / "classement.json"
    fallback_meta = work_dir / "data-meta.json"
    shutil.copyfile(cached_dataset, fallback_dataset)
    _write_metadata(fallback_meta, _now(), cached_meta["source_generated_at"], True, run_id)
    prepare_site(fallback_dataset, fallback_meta, site_dir, repo_root, allow_hero_assets)
    print(f"Update outcome: stale-safe; cache={cached_dataset}; report={json.dumps(report, ensure_ascii=False)}")
    return {"outcome": "stale", "report": report, "dataset": fallback_dataset, "metadata": fallback_meta}


def main_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--site-dir", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--allow-hero-assets", action="store_true")
    args = parser.parse_args()
    try:
        run_update(args.work_dir, args.cache_dir, args.site_dir, args.repo_root, args.run_id, args.allow_hero_assets)
    except UpdateError as exc:
        print(f"ABORTED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
