"""Structured comparison of an official audit report with baseline expectations."""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass
import json
from pathlib import Path

from .export_case import export_faithful_case
from .faults import FaultScenario, inject_fault
from .oracle import run_independent_oracle
from .release_runtime import prepare_reproaudit_runtime, run_reproaudit
from .source_inventory import CaseContractError, SourceFileRecord, build_source_inventory


class BaselineMismatch(AssertionError):
    """Raised when a structured baseline contract differs."""


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
    actual_by_rule = {item.get("rule_id"): item for item in actual_findings if isinstance(item, dict)}
    for expected_finding in expected_findings:
        if not isinstance(expected_finding, dict):
            raise BaselineMismatch("expected finding must be an object")
        rule_id = expected_finding.get("rule_id")
        if rule_id not in actual_by_rule:
            raise BaselineMismatch(f"missing finding {rule_id}")
        _assert_subset(actual_by_rule[rule_id], expected_finding, f"finding[{rule_id}]")
    if len(actual_by_rule) != len(expected_findings):
        raise BaselineMismatch("unexpected finding rule")
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


def run_acceptance(repo_root: Path, wheel: Path, output_dir: Path) -> AcceptanceResult:
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
    case_a, case_b = output / "case-a", output / "case-b"
    export_faithful_case(root, case_a)
    export_faithful_case(root, case_b)
    _compare_directories(case_a, case_b)
    oracle_a = run_independent_oracle(case_a, output / "oracle-a")
    oracle_b = run_independent_oracle(case_b, output / "oracle-b")
    if oracle_a != oracle_b:
        raise CaseContractError("deterministic oracle mismatch")
    runtime_python = prepare_reproaudit_runtime(Path(wheel), output / "runtime")
    baseline_report = run_reproaudit(runtime_python, case_a, output / "baseline-report")
    expected_path = root / "case_studies/reproaudit_v0_1/expected/baseline_expectations.json"
    try:
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CaseContractError("baseline expectations are missing or invalid") from exc
    compare_baseline(baseline_report, oracle_a, expected)
    fault_ids = ("F001", "F002", "F003", "F004", "F005A", "F005B", "F101", "F102", "F103", "F201", "F202", "F900")
    for fault_id in fault_ids:
        fault = inject_fault(case_a, FaultScenario(fault_id), output / "faults" / fault_id)
        try:
            report = run_reproaudit(runtime_python, fault.output_dir, output / "fault-reports" / fault_id)
        except CaseContractError:
            if fault_id == "F900" and fault.expected_exit_code == 3:
                continue
            raise
        if report.get("exit_code") != fault.expected_exit_code:
            raise BaselineMismatch(f"{fault_id} exit code mismatch")
        observed = {finding.get("rule_id") for finding in report.get("findings", []) if isinstance(finding, dict)}
        if not set(fault.expected_findings).issubset(observed):
            raise BaselineMismatch(f"{fault_id} required finding missing")
        if set(fault.forbidden_findings) & observed:
            raise BaselineMismatch(f"{fault_id} forbidden finding observed")
    after = build_source_inventory(root)
    if before.files != after.files:
        raise CaseContractError("canonical source hashes changed during acceptance")
    from .constants import REPROAUDIT_WHEEL_SHA256
    result = AcceptanceResult(output, before.files, after.files, fault_ids, REPROAUDIT_WHEEL_SHA256, 0)
    final_payload = {"exit_code": 0, "fault_ids": list(fault_ids), "wheel_sha256": result.wheel_sha256, "source_hashes": [{"path": item.path, "sha256": item.sha256} for item in after.files]}
    (output / "acceptance-result.json").write_text(json.dumps(final_payload, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


__all__ = ["AcceptanceResult", "BaselineMismatch", "compare_baseline", "run_acceptance"]
