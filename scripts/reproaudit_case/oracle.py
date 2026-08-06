"""Independent standard-library observations for a faithful case."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path
import statistics
from typing import Any

import yaml

from .source_inventory import CaseContractError


@dataclass(frozen=True)
class OracleReport:
    payload: dict[str, Any]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, OracleReport) and self.payload == other.payload


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise CaseContractError(f"cannot read oracle YAML: {path.name}") from exc
    if not isinstance(value, dict):
        raise CaseContractError(f"oracle YAML must be a mapping: {path.name}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise CaseContractError(f"cannot read oracle CSV: {path.name}") from exc
    if not rows:
        raise CaseContractError(f"oracle CSV is empty: {path.name}")
    if any(None in row for row in rows):
        raise CaseContractError(f"oracle CSV row width mismatch: {path.name}")
    return rows


def _finite(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise CaseContractError(f"invalid oracle metric: {label}") from exc
    if not math.isfinite(parsed):
        raise CaseContractError(f"nonfinite oracle metric: {label}")
    return parsed


def run_independent_oracle(case_dir: Path, output_dir: Path) -> OracleReport:
    case = Path(case_dir)
    output = Path(output_dir)
    experiment = _load_yaml(case / "experiment.yaml")
    claims = _load_yaml(case / "claims.yaml")
    raw = _read_csv(case / "raw_results.csv")
    summary = _read_csv(case / "summary_results.csv")
    algorithms = list(experiment.get("algorithms", []))
    metrics = list(experiment.get("metrics", {}))
    grouped: dict[tuple[str, str], list[float]] = {(algorithm, metric): [] for algorithm in algorithms for metric in metrics}
    keys: set[tuple[str, str]] = set()
    statuses: dict[str, int] = {}
    for row in raw:
        algorithm = row.get("algorithm", "")
        try:
            seed = int(row["seed"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CaseContractError("invalid oracle seed") from exc
        key = (seed, algorithm)
        if key in keys:
            raise CaseContractError(f"duplicate oracle key: {key}")
        keys.add(key)
        status = row.get("status", "")
        statuses[status] = statuses.get(status, 0) + 1
        if status == "success":
            for metric in metrics:
                grouped.setdefault((algorithm, metric), []).append(_finite(row.get(metric, ""), f"{algorithm}/{metric}"))
    observations: dict[str, dict[str, dict[str, float | int]]] = {}
    for algorithm in algorithms:
        observations[algorithm] = {}
        for metric in metrics:
            values = grouped.get((algorithm, metric), [])
            if len(values) < 2:
                raise CaseContractError(f"insufficient oracle values: {algorithm}/{metric}")
            observations[algorithm][metric] = {
                "n": len(values),
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "std": statistics.stdev(values),
            }
    summary_observations: dict[str, dict[str, float]] = {}
    for row in summary:
        algorithm, metric = row.get("algorithm", ""), row.get("metric", "")
        summary_observations[f"{algorithm}/{metric}"] = {"mean": _finite(row.get("mean", ""), "summary mean"), "std": _finite(row.get("std", ""), "summary std")}
    differences: list[float] = []
    for algorithm in algorithms:
        for metric in metrics:
            key = f"{algorithm}/{metric}"
            differences.append(abs(observations[algorithm][metric]["mean"] - summary_observations[key]["mean"]))
            differences.append(abs(observations[algorithm][metric]["std"] - summary_observations[key]["std"]))
    reported_results = claims.get("reported_results", {})
    if not isinstance(reported_results, dict):
        raise CaseContractError("invalid oracle reported results")
    entered_count = 0
    for algorithm, metric_claims in reported_results.items():
        if not isinstance(metric_claims, dict):
            raise CaseContractError("invalid oracle claim")
        for metric, claim in metric_claims.items():
            try:
                displayed = Decimal(str(claim["mean"]))
                actual = Decimal(str(observations[algorithm][metric]["mean"]))
            except (KeyError, TypeError, InvalidOperation) as exc:
                raise CaseContractError("invalid oracle claim") from exc
            differences.append(float(abs(actual - displayed)))
            entered_count += 1
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "raw": {"row_count": len(raw), "algorithms": algorithms, "statuses": statuses, "unique_keys": len(keys)},
        "observations": observations,
        "summary": {"row_count": len(summary), "official": summary_observations},
        "claims": {"entered_count": entered_count, "max_absolute_difference": max(differences)},
    }
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "oracle-report.json"
    if report_path.exists():
        raise FileExistsError(f"destination already exists: {report_path}")
    report_path.write_bytes((json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8"))
    return OracleReport(payload)


__all__ = ["OracleReport", "run_independent_oracle"]
