"""Structured comparison of an official audit report with baseline expectations."""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass
import json
from pathlib import Path

from .export_case import export_faithful_case
from .faults import FaultResult, FaultScenario, inject_fault
from .oracle import run_independent_oracle
from .release_runtime import ReleaseCLIError, prepare_reproaudit_runtime, run_reproaudit
from .source_inventory import CaseContractError, SourceFileRecord, build_source_inventory


class BaselineMismatch(AssertionError):
    """Raised when a structured baseline contract differs."""


_RULE_ORDER = (
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
)


@dataclass(frozen=True)
class AcceptanceResult:
    output_dir: Path
    source_hashes_before: tuple[SourceFileRecord, ...]
    source_hashes_after: tuple[SourceFileRecord, ...]
    fault_ids: tuple[str, ...]
    wheel_sha256: str
    exit_code: int


def _without_generated_at(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: item for key, item in value.items() if key != "generated_at"}
    return value


def _assert_subset(actual: Any, expected: Any, path: str) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise BaselineMismatch(f"{path} is not an object")
        for key, value in expected.items():
            if key not in actual:
                raise BaselineMismatch(f"missing {path}.{key}")
            _assert_subset(actual[key], value, f"{path}.{key}")
        return
    if actual != expected:
        raise BaselineMismatch(f"{path} mismatch: expected {expected!r}, got {actual!r}")


def compare_baseline(report: dict[str, Any], oracle: Any, expected: dict[str, Any]) -> None:
    """Compare structured findings and selected oracle evidence, ignoring console text."""

    if not isinstance(report, dict) or not isinstance(expected, dict):
        raise BaselineMismatch("report and expected baseline must be objects")
    actual_exit = report.get("exit_code")
    if actual_exit != expected.get("exit_code"):
        raise BaselineMismatch(f"exit_code mismatch: expected {expected.get('exit_code')!r}, got {actual_exit!r}")
    actual_findings = report.get("findings")
    expected_findings = expected.get("findings")
    if not isinstance(actual_findings, list) or not isinstance(expected_findings, list):
        raise BaselineMismatch("findings must be lists")
    if len(actual_findings) != len(expected_findings):
        raise BaselineMismatch(
            f"finding count mismatch: expected {len(expected_findings)}, got {len(actual_findings)}"
        )
    for index, (actual_finding, expected_finding) in enumerate(
        zip(actual_findings, expected_findings)
    ):
        if not isinstance(actual_finding, dict):
            raise BaselineMismatch(f"finding[{index}] must be an object")
        if not isinstance(expected_finding, dict):
            raise BaselineMismatch("expected finding must be an object")
        rule_id = expected_finding.get("rule_id")
        if actual_finding.get("rule_id") != rule_id:
            raise BaselineMismatch(
                f"finding order mismatch at index {index}: expected {rule_id!r}, "
                f"got {actual_finding.get('rule_id')!r}"
            )
        _assert_subset(actual_finding, expected_finding, f"finding[{rule_id}]")
    if "summary" not in expected:
        raise BaselineMismatch("expected baseline summary is missing")
    _assert_subset(report.get("summary"), expected["summary"], "summary")
    oracle_payload = getattr(oracle, "payload", oracle)
    if "oracle" in expected:
        _assert_subset(oracle_payload, _without_generated_at(expected["oracle"]), "oracle")


def _compare_directories(first: Path, second: Path) -> None:
    first_files = sorted(path.name for path in first.iterdir() if path.is_file())
    second_files = sorted(path.name for path in second.iterdir() if path.is_file())
    if first_files != second_files:
        raise CaseContractError("deterministic export file set mismatch")
    for name in first_files:
        if (first / name).read_bytes() != (second / name).read_bytes():
            raise CaseContractError(f"deterministic output mismatch: {name}")


def _failure_severity(fault_id: str, rule_id: str) -> str:
    if rule_id == "R004" or (rule_id == "R005" and fault_id != "F005B"):
        return "WARNING"
    return "ERROR"


def _summary_from_findings(findings: list[dict[str, Any]], exit_code: int) -> dict[str, int]:
    return {
        "error": sum(
            item.get("status") == "FAIL" and item.get("severity") == "ERROR"
            for item in findings
        ),
        "exit_code": exit_code,
        "pass": sum(item.get("status") == "PASS" for item in findings),
        "skip": sum(item.get("status") == "SKIP" for item in findings),
        "warning": sum(
            item.get("status") == "FAIL" and item.get("severity") == "WARNING"
            for item in findings
        ),
    }


def _validate_fault_report(fault: FaultResult, report: dict[str, Any]) -> None:
    fault_id = fault.scenario_id
    if fault_id == "F900":
        raise BaselineMismatch("F900 produced a normal JSON report")
    if not isinstance(report, dict):
        raise BaselineMismatch(f"{fault_id} report must be an object")
    if report.get("exit_code") != fault.expected_exit_code:
        raise BaselineMismatch(f"{fault_id} exit code mismatch")
    findings = report.get("findings")
    if not isinstance(findings, list) or len(findings) != len(_RULE_ORDER):
        raise BaselineMismatch(
            f"{fault_id} must contain exactly {len(_RULE_ORDER)} findings"
        )
    actual_order = tuple(
        finding.get("rule_id") if isinstance(finding, dict) else None
        for finding in findings
    )
    if actual_order != _RULE_ORDER:
        raise BaselineMismatch(
            f"{fault_id} finding order mismatch: expected {_RULE_ORDER!r}, got {actual_order!r}"
        )

    required = set(fault.expected_findings)
    allowed = set(fault.allowed_cascades)
    forbidden = set(fault.forbidden_findings)
    if required | allowed | forbidden != set(_RULE_ORDER):
        raise BaselineMismatch(f"{fault_id} expectation matrix does not cover every rule")
    if required & allowed or required & forbidden or allowed & forbidden:
        raise BaselineMismatch(f"{fault_id} expectation matrix categories overlap")

    for finding in findings:
        rule_id = finding["rule_id"]
        actual = (finding.get("status"), finding.get("severity"))
        if rule_id in required:
            expected = ("FAIL", _failure_severity(fault_id, rule_id))
            if actual != expected:
                raise BaselineMismatch(
                    f"{fault_id} {rule_id} mismatch: expected {expected!r}, got {actual!r}"
                )
        elif rule_id == "R202" and rule_id in allowed:
            if actual != ("SKIP", "INFO"):
                raise BaselineMismatch(
                    f"{fault_id} R202 mismatch: expected ('SKIP', 'INFO'), got {actual!r}"
                )
        elif rule_id in allowed:
            allowed_outcomes = {
                ("PASS", "INFO"),
                ("FAIL", _failure_severity(fault_id, rule_id)),
            }
            if actual not in allowed_outcomes:
                raise BaselineMismatch(
                    f"{fault_id} {rule_id} has invalid allowed-cascade outcome {actual!r}"
                )
        elif actual != ("PASS", "INFO"):
            raise BaselineMismatch(
                f"{fault_id} forbidden {rule_id} mismatch: expected ('PASS', 'INFO'), "
                f"got {actual!r}"
            )

    expected_summary = _summary_from_findings(findings, fault.expected_exit_code)
    _assert_subset(report.get("summary"), expected_summary, f"{fault_id}.summary")


def _validate_expected_input_error(
    fault_id: str, expected_exit_code: int, error: ReleaseCLIError
) -> None:
    if fault_id != "F900" or expected_exit_code != 3:
        raise error
    expected_output = "INPUT_ERROR: claims.yaml: missing required file"
    if error.exit_code != 3 or error.output.strip() != expected_output:
        raise BaselineMismatch("F900 did not produce the required input-validation exit")


def run_acceptance(
    repo_root: Path,
    wheel: Path,
    output_dir: Path,
    requirements: Path | None = None,
    wheelhouse: Path | None = None,
    wheelhouse_manifest: Path | None = None,
) -> AcceptanceResult:
    """Run the full staged acceptance workflow outside canonical sources."""

    root = Path(repo_root).resolve()
    output = Path(output_dir).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise CaseContractError("acceptance output directory must be absent or empty")
    try:
        output.relative_to(root)
    except ValueError:
        pass
    else:
        raise CaseContractError("acceptance output must be outside repository")
    output.mkdir(parents=True, exist_ok=True)
    before = build_source_inventory(root)
    after = None
    try:
        case_a, case_b = output / "case-a", output / "case-b"
        export_faithful_case(root, case_a)
        export_faithful_case(root, case_b)
        _compare_directories(case_a, case_b)
        oracle_a = run_independent_oracle(case_a, output / "oracle-a")
        oracle_b = run_independent_oracle(case_b, output / "oracle-b")
        if oracle_a != oracle_b:
            raise CaseContractError("deterministic oracle mismatch")
        runtime_python = prepare_reproaudit_runtime(
            Path(wheel), output / "runtime", requirements, wheelhouse, wheelhouse_manifest
        )
        baseline_report = run_reproaudit(runtime_python, case_a, output / "baseline-report")
        expected_path = root / "case_studies/reproaudit_v0_1/expected/baseline_expectations.json"
        try:
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CaseContractError("baseline expectations are missing or invalid") from exc
        compare_baseline(baseline_report, oracle_a, expected)
        fault_ids = (
            "F001",
            "F002",
            "F003",
            "F004",
            "F005A",
            "F005B",
            "F101",
            "F102",
            "F103",
            "F201",
            "F202",
            "F900",
        )
        fault_exit_codes: dict[str, int] = {}
        fault_evidence: dict[str, Any] = {}
        for fault_id in fault_ids:
            fault = inject_fault(case_a, FaultScenario(fault_id), output / "faults" / fault_id)
            try:
                report = run_reproaudit(
                    runtime_python,
                    fault.output_dir,
                    output / "fault-reports" / fault_id,
                )
            except ReleaseCLIError as exc:
                _validate_expected_input_error(fault_id, fault.expected_exit_code, exc)
                fault_exit_codes[fault_id] = exc.exit_code
                fault_evidence[fault_id] = {
                    "exit_code": exc.exit_code,
                    "input_error": exc.output.strip(),
                    "normal_json_report": False,
                }
                continue
            _validate_fault_report(fault, report)
            fault_exit_codes[fault_id] = int(report["exit_code"])
            fault_evidence[fault_id] = {
                "exit_code": report["exit_code"],
                "findings": [
                    {
                        "rule_id": finding["rule_id"],
                        "severity": finding["severity"],
                        "status": finding["status"],
                    }
                    for finding in report["findings"]
                ],
                "summary": report["summary"],
            }
    finally:
        after = build_source_inventory(root)
        if before.files != after.files:
            raise CaseContractError("canonical source hashes changed during acceptance")

    if after is None:
        raise CaseContractError("canonical source inventory was not revalidated")
    from .constants import REPROAUDIT_WHEEL_SHA256
    result = AcceptanceResult(
        output,
        before.files,
        after.files,
        fault_ids,
        REPROAUDIT_WHEEL_SHA256,
        0,
    )
    final_payload = {
        "exit_code": 0,
        "fault_evidence": fault_evidence,
        "fault_exit_codes": fault_exit_codes,
        "fault_ids": list(fault_ids),
        "wheel_sha256": result.wheel_sha256,
        "source_hashes": [
            {"path": item.path, "sha256": item.sha256} for item in after.files
        ],
    }
    (output / "acceptance-result.json").write_text(
        json.dumps(final_payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


__all__ = ["AcceptanceResult", "BaselineMismatch", "compare_baseline", "run_acceptance"]
