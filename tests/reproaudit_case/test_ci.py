from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_manual_workflow_is_dispatch_only_and_official_wheel_bound() -> None:
    text = (ROOT / ".github/workflows/reproaudit-mec-acceptance.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text and "cron:" not in text
    assert "REPROAUDIT_WHEEL_PATH" in text
    assert "run_reproaudit_acceptance.py" in text
    assert "run_main_30" not in text and "experiments.run_main_30" not in text


def test_pr_ci_has_no_network_wheel_or_experiment_invocation() -> None:
    text = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    assert "pytest -q" in text
    assert "reproaudit-mec-acceptance" not in text
    assert "run_main_30" not in text
