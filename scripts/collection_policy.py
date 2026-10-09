"""Validation for the explicit permanently unavailable request policy."""

from datetime import datetime
import json
from pathlib import Path


class PolicyError(ValueError):
    """Raised when the collection policy is not auditable."""


def _timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0


def validate_policy(policy, players, modes):
    if not isinstance(policy, dict) or set(policy) != {"version", "excluded_requests"}:
        raise PolicyError("policy must contain exactly version and excluded_requests")
    if policy["version"] != 1 or not isinstance(policy["excluded_requests"], list):
        raise PolicyError("policy version or excluded_requests is invalid")
    configured = {(player, mode) for player in players for mode in modes}
    seen = set()
    for entry in policy["excluded_requests"]:
        if not isinstance(entry, dict) or set(entry) != {"player_id", "gamemode", "reason", "observed_at", "confirmation_status"}:
            raise PolicyError("policy entry has an invalid shape")
        pair = (entry["player_id"], entry["gamemode"])
        if pair not in configured:
            raise PolicyError(f"policy entry is not configured: {pair}")
        if pair in seen:
            raise PolicyError(f"duplicate policy entry: {pair}")
        seen.add(pair)
        if not isinstance(entry["reason"], str) or not entry["reason"].strip():
            raise PolicyError("policy reason must be non-empty")
        observations = entry["observed_at"]
        if not isinstance(observations, list) or len(observations) != 2 or not all(_timestamp(item) for item in observations):
            raise PolicyError("policy requires two ISO-8601 observation timestamps")
        if observations[0] == observations[1]:
            raise PolicyError("policy observations must be distinct")
        if entry["confirmation_status"] != "confirmed_twice":
            raise PolicyError("policy confirmation_status must be confirmed_twice")
    return policy


def load_policy(path, players=None, modes=None):
    players = players if players is not None else __import__("config").PLAYERS
    modes = modes if modes is not None else __import__("config").MODES
    path = Path(path)
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyError(f"missing collection policy: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PolicyError(f"malformed collection policy: {path}") from exc
    return validate_policy(policy, players, modes)
