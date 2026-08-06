from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_manual_workflow_is_dispatch_only_and_official_wheel_bound() -> None:
    text = (ROOT / ".github/workflows/reproaudit-mec-acceptance.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text and "cron:" not in text
    assert "wheel_path" in text
    assert "--no-index" in text and "--no-deps" in text
    assert "scripts.run_reproaudit_acceptance" in text
    assert "run_main_30" not in text and "experiments.run_main_30" not in text
    workflow = yaml.safe_load(text)
    for step in workflow["jobs"]["acceptance"]["steps"]:
        assert step.get("env", {}) is not None


def test_pr_ci_has_no_network_wheel_or_experiment_invocation() -> None:
    text = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    job = workflow["jobs"]["test"]
    steps = job["steps"]
    run_commands = [step["run"].strip() for step in steps if "run" in step]
    uses = [step["uses"] for step in steps if "uses" in step]

    assert "actions/checkout@v4" in uses
    assert "actions/setup-python@v5" in uses
    assert "python -m pip install --upgrade pip" in run_commands
    assert "python -m pip install -r requirements.txt" in run_commands
    assert "python -m pytest -q" in run_commands, (
        "tests.yml must run tests through the current Python interpreter"
    )
    assert "pytest -q" not in run_commands, (
        "tests.yml must not use the pytest console entrypoint"
    )
    assert all("PYTHONPATH" not in command for command in run_commands)
    for scope in (workflow, job, *steps):
        assert "PYTHONPATH" not in scope.get("env", {})

    triggers = workflow.get("on", workflow.get(True, {}))
    assert "schedule" not in triggers and "cron" not in triggers
    assert all("reproaudit-mec-acceptance" not in command for command in run_commands)
    assert all("run_main_30" not in command for command in run_commands)
