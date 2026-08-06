from __future__ import annotations

import pytest

from scripts.reproaudit_case.source_inventory import CaseContractError


def _expected() -> dict:
    return {
        "exit_code": 0,
        "findings": [
            {"rule_id": rule, "rule_name": rule, "status": "SKIP" if rule == "R202" else "PASS", "severity": "INFO", "message": "ok", "evidence": {}}
            for rule in ("R001", "R002", "R003", "R004", "R005", "R101", "R102", "R103", "R201", "R202")
        ],
        "oracle": {"raw": {"row_count": 180}},
    }


def test_compare_baseline_uses_structured_findings_and_oracle() -> None:
    from scripts.reproaudit_case.acceptance import compare_baseline

    expected = _expected()
    report = {**expected, "generated_at": "run-specific", "console": "irrelevant text"}
    oracle = type("Oracle", (), {"payload": {"raw": {"row_count": 180}}})()
    assert compare_baseline(report, oracle, expected) is None


def test_compare_baseline_rejects_wrong_finding_or_oracle() -> None:
    from scripts.reproaudit_case.acceptance import compare_baseline, BaselineMismatch

    expected = _expected()
    report = {**expected, "findings": [*expected["findings"][:-1], {**expected["findings"][-1], "status": "PASS"}]}
    oracle = type("Oracle", (), {"payload": {"raw": {"row_count": 180}}})()
    with pytest.raises(BaselineMismatch, match="R202"):
        compare_baseline(report, oracle, expected)
    report = {**expected}
    oracle = type("Oracle", (), {"payload": {"raw": {"row_count": 179}}})()
    with pytest.raises(BaselineMismatch, match="oracle"):
        compare_baseline(report, oracle, expected)


def test_runner_rejects_nonempty_output_before_wheel_use(tmp_path) -> None:
    from scripts.reproaudit_case.acceptance import run_acceptance

    output = tmp_path / "output"
    output.mkdir()
    (output / "sentinel").write_text("x", encoding="utf-8")
    with pytest.raises(CaseContractError, match="empty"):
        run_acceptance(tmp_path, tmp_path / "wheel.whl", output)


def test_fault_comparison_ignores_passing_rules_but_keeps_skip_and_fail() -> None:
    from scripts.reproaudit_case.acceptance import _observed_nonpass_rule_ids

    report = {
        "findings": [
            {"rule_id": "R001", "status": "ERROR"},
            {"rule_id": "R002", "status": "PASS"},
            {"rule_id": "R202", "status": "SKIP"},
        ]
    }
    assert _observed_nonpass_rule_ids(report) == {"R001", "R202"}
