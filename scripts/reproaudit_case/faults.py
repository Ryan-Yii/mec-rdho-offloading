"""Fixed, report-independent fault fixtures for acceptance testing."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import shutil
from pathlib import Path
from typing import Any

import yaml

from .source_inventory import CaseContractError


@dataclass(frozen=True)
class FaultScenario:
    scenario_id: str


@dataclass(frozen=True)
class FaultResult:
    scenario_id: str
    output_dir: Path
    changed_files: tuple[str, ...]
    expected_findings: tuple[str, ...]
    allowed_cascades: tuple[str, ...]
    forbidden_findings: tuple[str, ...]
    expected_exit_code: int


_SPECS: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], int]] = {
    "F001": (("R001",), ("R003", "R005", "R101", "R102", "R103", "R202"), ("R002", "R004", "R201"), 2),
    "F002": (("R002",), ("R003", "R202"), ("R001", "R004", "R005", "R101", "R102", "R103", "R201"), 2),
    "F003": (("R003",), ("R202",), ("R001", "R002", "R004", "R005", "R101", "R102", "R103", "R201"), 2),
    "F004": (("R004",), ("R202",), ("R001", "R002", "R003", "R005", "R101", "R102", "R103", "R201"), 1),
    "F005A": (("R005",), ("R001", "R003", "R101", "R102", "R103", "R202"), ("R002", "R004", "R201"), 2),
    "F005B": (("R005",), ("R101", "R102", "R103", "R202"), ("R001", "R002", "R003", "R004", "R201"), 2),
    "F101": (("R101",), ("R202",), ("R001", "R002", "R003", "R004", "R005", "R102", "R103", "R201"), 2),
    "F102": (("R102",), ("R202",), ("R001", "R002", "R003", "R004", "R005", "R101", "R103", "R201"), 2),
    "F103": (("R103",), ("R202",), ("R001", "R002", "R003", "R004", "R005", "R101", "R102", "R201"), 2),
    "F201": (("R201",), ("R202",), ("R001", "R002", "R003", "R004", "R005", "R101", "R102", "R103"), 2),
    "F202": (("R202",), (), ("R001", "R002", "R003", "R004", "R005", "R101", "R102", "R103", "R201"), 2),
    "F900": ((), (), ("R001", "R002", "R003", "R004", "R005", "R101", "R102", "R103", "R201", "R202"), 3),
}


def _mutate_csv(path: Path, scenario_id: str) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames
    if scenario_id in {"F001", "F005A", "F005B"}:
        target = next(row for row in rows if row["algorithm"] == "RDHO" and row["seed"] == "20260701")
        if scenario_id == "F005B":
            target["fitness"] = "NaN"
        else:
            target["status"] = "failed" if scenario_id == "F001" else "timeout"
    elif scenario_id == "F002":
        next(row for row in rows if row["algorithm"] == "RDHO" and row["seed"] == "20260702")["seed"] = "20260701"
    elif scenario_id == "F003":
        next(row for row in rows if row["algorithm"] == "RDHO" and row["seed"] == "20260730")["seed"] = "20260731"
    elif scenario_id == "F004":
        source = [row for row in rows if row["algorithm"] == "Greedy-ED"]
        rows.extend([{**row, "algorithm": "UNDECLARED-CONTROL"} for row in source])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def inject_fault(case_dir: Path, scenario: FaultScenario, output_dir: Path) -> FaultResult:
    scenario_id = scenario.scenario_id
    if scenario_id not in _SPECS:
        raise CaseContractError(f"unknown fault scenario: {scenario_id}")
    source = Path(case_dir).resolve()
    destination = Path(output_dir).resolve()
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise CaseContractError("fault output directory must be absent or empty")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.rmdir()
    shutil.copytree(source, destination)
    changed: list[str] = []
    if scenario_id == "F900":
        (destination / "claims.yaml").unlink()
        changed.append("claims.yaml")
    elif scenario_id == "F202":
        path = destination / "claims.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["conclusions"] = {"best_algorithm": {"metric": "fitness", "algorithm": "DBO"}}
        path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True) , encoding="utf-8")
        changed.append("claims.yaml")
    elif scenario_id in {"F101", "F102"}:
        path = destination / "summary_results.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fields = reader.fieldnames
        target = next(row for row in rows if row["algorithm"] == "RDHO" and row["metric"] == "fitness")
        key = "mean" if scenario_id == "F101" else "std"
        target[key] = str(float(target[key]) + 0.01)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
        changed.append("summary_results.csv")
    elif scenario_id in {"F103", "F201"}:
        path = destination / "claims.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if scenario_id == "F103":
            payload["reported_results"]["RDHO"]["fitness"]["mean"] = 0.9480
        else:
            payload["parameter_claims"]["max_iterations"] = 151
        path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
        changed.append("claims.yaml")
    else:
        path = destination / "raw_results.csv"
        _mutate_csv(path, scenario_id)
        changed.append("raw_results.csv")
    required, allowed, forbidden, exit_code = _SPECS[scenario_id]
    return FaultResult(scenario_id, destination, changed and tuple(changed), required, allowed, forbidden, exit_code)


__all__ = ["FaultResult", "FaultScenario", "inject_fault"]
