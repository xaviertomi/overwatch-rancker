import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def trigger(workflow):
    return workflow.get("on", workflow.get(True))


def actions_in(text):
    return [
        line.rsplit("@", 1)[-1].strip()
        for line in text.splitlines()
        if "uses:" in line and "actions/" in line
    ]


def test_ci_is_read_only_and_runs_both_suites():
    path = ROOT / ".github/workflows/ci.yml"
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    events = trigger(workflow)
    assert "pull_request" in events
    assert events["push"]["branches"] == ["main"]
    assert workflow["permissions"] == {"contents": "read"}
    text = path.read_text(encoding="utf-8")
    assert "npm ci" in text
    assert "python -m pytest -q" in text
    assert "playwright install" in text and "npm test" in text
    assert "deploy-pages" not in text
    assert all(re.fullmatch(r"[0-9a-f]{40}", sha) for sha in actions_in(text))


def test_pages_trigger_ref_guard_permissions_and_deployment_gate():
    path = ROOT / ".github/workflows/pages.yml"
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    events = trigger(workflow)
    assert events["push"]["branches"] == ["main"]
    assert "workflow_dispatch" in events
    assert events["schedule"] == [{"cron": "0 1 * * *", "timezone": "Europe/Paris"}]
    assert "pull_request" not in events
    assert workflow["concurrency"]["cancel-in-progress"] is False

    jobs = workflow["jobs"]
    assert jobs["ref-guard"]["if"] == "github.ref != 'refs/heads/main'"
    assert "exit 1" in jobs["ref-guard"]["steps"][0]["run"]
    assert jobs["collect"]["if"] == "github.ref == 'refs/heads/main'"
    assert jobs["collect"]["permissions"] == {"contents": "write", "actions": "read"}
    assert jobs["pages"]["permissions"] == {
        "contents": "read",
        "pages": "write",
        "id-token": "write",
    }
    assert jobs["pages"]["if"] == "github.ref == 'refs/heads/main' && vars.PAGES_PUBLISH_ENABLED == 'true'"

    text = path.read_text(encoding="utf-8")
    assert all(re.fullmatch(r"[0-9a-f]{40}", sha) for sha in actions_in(text))
    assert "generated-data" in text
    assert "git worktree add" in text
    assert "push origin HEAD:generated-data" in text
    assert "--force" not in text and "--force-with-lease" not in text
    assert "python scripts/update_dataset.py" in text
    assert "python scripts/validate_json.py .work/classement.json" in text
    assert "python scripts/prepare_site.py" in text
    assert "actions/configure-pages@" in text
    assert "actions/upload-pages-artifact@" in text
    assert "actions/deploy-pages@" in text
    assert "pull_request" not in text


def test_pending_run_behavior_is_documented():
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    assert "one pending run" in readme
    assert "replace an obsolete pending refresh" in readme
    assert "cancel-in-progress: false" in readme
