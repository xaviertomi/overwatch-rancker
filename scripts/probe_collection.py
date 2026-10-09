"""Probe configured OverFast requests without writing ranking or site data."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
import heroes
import main


def _iso_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hero_path(payload, mode):
    if isinstance(payload.get("heroes"), dict):
        return "heroes", payload["heroes"]
    if isinstance(payload.get("heroes_stats"), dict):
        return "heroes_stats", payload["heroes_stats"]
    nested = payload.get(mode)
    if isinstance(nested, dict) and isinstance(nested.get("heroes"), dict):
        return f"{mode}.heroes", nested["heroes"]
    return "root", payload


def run_probe():
    rows = []
    for player_id in config.PLAYERS:
        for mode in config.MODES:
            outcome_report = {"outcomes": {}}
            started_at = _iso_now()
            payload = main.get_player_stats(player_id, mode, outcome_report)
            outcome = outcome_report["outcomes"].get((player_id, mode), {
                "classification": "transient_failures", "status": None,
            })
            row = {
                "player_id": player_id,
                "gamemode": mode,
                "observed_at": started_at,
                "classification": outcome["classification"],
                "status": outcome.get("status"),
                "top_level_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
                "hero_container_path": None,
                "recognized_hero_count": 0,
                "legitimately_empty_mode": False,
            }
            if isinstance(payload, dict) and outcome["classification"] == "successful_responses":
                path, container = _hero_path(payload, mode)
                recognized = [key for key in container if key in heroes.HERO_ROLES]
                row["hero_container_path"] = path
                row["recognized_hero_count"] = len(recognized)
                row["legitimately_empty_mode"] = len(recognized) == 0
            rows.append(row)
    return {
        "generated_at": _iso_now(),
        "base_url": config.BASE_URL,
        "requests": rows,
    }


def main_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = run_probe()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Probe report written to {args.output} ({len(report['requests'])} requests)")


if __name__ == "__main__":
    main_cli()
