"""Structured comparison of an official audit report with baseline expectations."""

from __future__ import annotations

from typing import Any


class BaselineMismatch(AssertionError):
    """Raised when a structured baseline contract differs."""


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


__all__ = ["BaselineMismatch", "compare_baseline"]
