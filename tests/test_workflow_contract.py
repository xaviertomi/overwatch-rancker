from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def trigger(workflow):
    return workflow.get("on", workflow.get(True))


def test_ci_is_read_only_and_runs_both_suites():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    assert "pull_request" in trigger(workflow)
    assert workflow["permissions"] == {"contents": "read"}
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "npm ci" in text and "python -m pytest -q" in text and "playwright install" in text
    assert "deploy-pages" not in text


def test_pages_schedule_concurrency_permissions_and_gate():
    workflow = yaml.safe_load((ROOT / ".github/workflows/pages.yml").read_text())
    actions = trigger(workflow)
    assert actions["schedule"] == [{"cron": "0 */6 * * *"}]
    assert workflow["concurrency"]["cancel-in-progress"] is False
    text = (ROOT / ".github/workflows/pages.yml").read_text()
    assert "github.ref == 'refs/heads/main'" in text
    assert "PAGES_PUBLISH_ENABLED == 'true'" in text
    assert "generated-data" in text and "validate_json.py" in text and "complete" in text
    assert "pull_request" not in actions
    assert "actions/configure-pages@" in text and "actions/upload-pages-artifact@" in text and "actions/deploy-pages@" in text
    for line in text.splitlines():
        if "uses:" in line and "actions/" in line:
            assert len(line.rsplit("@", 1)[-1].strip()) == 40
