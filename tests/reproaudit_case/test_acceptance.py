from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.reproaudit_case.source_inventory import CaseContractError


def _expected() -> dict:
    return {
        "exit_code": 0,
        "findings": [
            {"rule_id": rule, "rule_name": rule, "status": "SKIP" if rule == "R202" else "PASS", "severity": "INFO", "message": "ok", "evidence": {}}
            for rule in ("R001", "R002", "R003", "R004", "R005", "R101", "R102", "R103", "R201", "R202")
        ],
        "summary": {"error": 0, "exit_code": 0, "pass": 9, "skip": 1, "warning": 0},
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


@pytest.mark.parametrize("defect", ["duplicate", "order", "summary"])
def test_compare_baseline_rejects_duplicate_order_and_summary_drift(defect: str) -> None:
    from scripts.reproaudit_case.acceptance import compare_baseline, BaselineMismatch

    expected = _expected()
    report = {**expected, "findings": [dict(item) for item in expected["findings"]]}
    if defect == "duplicate":
        report["findings"].append(dict(report["findings"][0]))
    elif defect == "order":
        report["findings"][0], report["findings"][1] = report["findings"][1], report["findings"][0]
    else:
        report["summary"] = {**expected["summary"], "pass": 8}
    oracle = type("Oracle", (), {"payload": {"raw": {"row_count": 180}}})()

    with pytest.raises(BaselineMismatch):
        compare_baseline(report, oracle, expected)


def test_runner_rejects_nonempty_output_before_wheel_use(tmp_path) -> None:
    from scripts.reproaudit_case.acceptance import run_acceptance

    output = tmp_path / "output"
    output.mkdir()
    (output / "sentinel").write_text("x", encoding="utf-8")
    with pytest.raises(CaseContractError, match="empty"):
        run_acceptance(tmp_path, tmp_path / "wheel.whl", output)


def _fault_report(
    fault_id: str,
    finding_status: str = "FAIL",
    finding_severity: str = "ERROR",
) -> tuple[object, dict]:
    # The injector's paths are irrelevant to report validation, so use a
    # contract-shaped object with no filesystem work.
    source = SimpleNamespace(
        scenario_id=fault_id,
        expected_findings=("R103",),
        allowed_cascades=("R202",),
        forbidden_findings=(
            "R001",
            "R002",
            "R003",
            "R004",
            "R005",
            "R101",
            "R102",
            "R201",
        ),
        expected_exit_code=2,
    )
    findings = []
    for rule in (
        "R001",
        "R002",
        "R003",
        "R004",
        "R005",
        "R101",
        "R102",
        "R103",
        "R201",
        "R202",
    ):
        status = "SKIP" if rule == "R202" else "PASS"
        severity = "INFO"
        if rule == "R103":
            status, severity = finding_status, finding_severity
        findings.append({"rule_id": rule, "rule_name": rule, "status": status, "severity": severity})
    report = {
        "exit_code": 2,
        "findings": findings,
        "summary": {"error": 1, "exit_code": 2, "pass": 8, "skip": 1, "warning": 0},
    }
    return source, report


def test_fault_comparison_accepts_exact_rule_and_summary_semantics() -> None:
    from scripts.reproaudit_case.acceptance import _validate_fault_report

    fault, report = _fault_report("F103")
    assert _validate_fault_report(fault, report) is None


@pytest.mark.parametrize(
    ("status", "severity"),
    [("SKIP", "INFO"), ("FAIL", "WARNING")],
)
def test_fault_comparison_rejects_wrong_required_status_or_severity(
    status: str, severity: str
) -> None:
    from scripts.reproaudit_case.acceptance import BaselineMismatch, _validate_fault_report

    fault, report = _fault_report("F103", status, severity)
    with pytest.raises(BaselineMismatch, match="F103.*R103"):
        _validate_fault_report(fault, report)


def test_fault_comparison_rejects_wrong_allowed_r202_semantics() -> None:
    from scripts.reproaudit_case.acceptance import BaselineMismatch, _validate_fault_report

    fault, report = _fault_report("F103")
    report["findings"][-1].update(status="FAIL", severity="ERROR")
    report["summary"].update(error=2, skip=0)
    with pytest.raises(BaselineMismatch, match="F103.*R202"):
        _validate_fault_report(fault, report)


@pytest.mark.parametrize("defect", ["forbidden", "summary"])
def test_fault_comparison_rejects_forbidden_or_summary_drift(defect: str) -> None:
    from scripts.reproaudit_case.acceptance import BaselineMismatch, _validate_fault_report

    fault, report = _fault_report("F103")
    if defect == "forbidden":
        report["findings"][0].update(status="FAIL", severity="ERROR")
        report["summary"].update({"error": 2, "pass": 7})
    else:
        report["summary"].update(error=99)
    with pytest.raises(BaselineMismatch, match="F103"):
        _validate_fault_report(fault, report)


def test_f900_rejects_normal_json_report() -> None:
    from scripts.reproaudit_case.acceptance import BaselineMismatch, _validate_fault_report

    fault, report = _fault_report("F900")
    fault.expected_findings = ()
    fault.allowed_cascades = ()
    fault.forbidden_findings = tuple(item["rule_id"] for item in report["findings"])
    fault.expected_exit_code = 3
    report.update(
        exit_code=3,
        findings=[],
        summary={"error": 0, "exit_code": 3, "pass": 0, "skip": 0, "warning": 0},
    )
    with pytest.raises(BaselineMismatch, match="F900.*normal JSON report"):
        _validate_fault_report(fault, report)


def test_f900_requires_exact_input_error_exit() -> None:
    from scripts.reproaudit_case.acceptance import (
        BaselineMismatch,
        _validate_expected_input_error,
    )
    from scripts.reproaudit_case.release_runtime import ReleaseCLIError

    _validate_expected_input_error(
        "F900",
        3,
        ReleaseCLIError(
            "input", exit_code=3, output="INPUT_ERROR: claims.yaml: missing required file\n"
        ),
    )
    with pytest.raises(BaselineMismatch, match="input-validation exit"):
        _validate_expected_input_error(
            "F900", 3, ReleaseCLIError("crash", exit_code=1, output="traceback")
        )
    with pytest.raises(BaselineMismatch, match="input-validation exit"):
        _validate_expected_input_error(
            "F900", 3, ReleaseCLIError("false marker", exit_code=3, output="NOT_INPUT_ERROR")
        )


def test_runner_rechecks_source_inventory_when_acceptance_fails(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.reproaudit_case import acceptance
    from scripts.reproaudit_case.source_inventory import SourceInventory

    inventory = SourceInventory("commit", (), (), ())
    calls = []

    def record_inventory(_root):
        calls.append("inventory")
        return inventory

    monkeypatch.setattr(acceptance, "build_source_inventory", record_inventory)
    monkeypatch.setattr(
        acceptance,
        "export_faithful_case",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(CaseContractError("export failed")),
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(CaseContractError, match="export failed"):
        acceptance.run_acceptance(
            repo, tmp_path / "wheel.whl", tmp_path / "acceptance-output"
        )
    assert calls == ["inventory", "inventory"]
