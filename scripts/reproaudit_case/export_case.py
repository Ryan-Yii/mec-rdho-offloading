"""Export the canonical MEC experiment configuration to ReproAudit YAML."""

from __future__ import annotations

import hashlib
import csv
import math
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .constants import (
    ALGORITHMS,
    METRIC_DIRECTIONS,
    METRICS,
    RAW_COLUMNS,
    SOURCE_HASHES,
    SOURCE_SIZES,
    resolve_source_path,
)
from .source_inventory import CaseContractError
from .source_inventory import build_source_inventory, serialize_manifest


CONFIG_PATH = "configs/main_40tasks.yaml"
RAW_PATH = "results/v2/raw/main_30_raw_results.csv"
SUMMARY_PATH = "results/v2/summary/main_30_summary_mean_std.csv"


@dataclass(frozen=True)
class ExportResult:
    output_dir: Path
    files: tuple[Path, ...]
_EXPECTED_TOP_LEVEL = ("system", "experiment", "weights")
_EXPECTED_SYSTEM = ("mobile_devices", "edge_servers", "cloud_servers", "tasks")
_EXPECTED_EXPERIMENT = (
    "seed_start",
    "independent_runs",
    "population_size",
    "max_iterations",
    "algorithms",
)
_EXPECTED_WEIGHTS = ("energy", "delay", "aoi", "qoe", "fairness")
_EXPECTED_SYSTEM_VALUES = {
    "mobile_devices": 20,
    "edge_servers": 4,
    "cloud_servers": 2,
    "tasks": 40,
}
_EXPECTED_EXPERIMENT_VALUES = {
    "seed_start": 20260701,
    "independent_runs": 30,
    "population_size": 50,
    "max_iterations": 150,
}


def _read_config(repo_root: Path) -> dict[str, Any]:
    path = resolve_source_path(repo_root, CONFIG_PATH)
    if not path.is_file():
        raise CaseContractError("canonical configuration is missing")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CaseContractError("cannot read canonical configuration") from exc
    expected_hash = SOURCE_HASHES[CONFIG_PATH]
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != expected_hash:
        raise CaseContractError(
            f"canonical configuration source hash drift: expected {expected_hash}, got {actual_hash}"
        )
    expected_size = SOURCE_SIZES[CONFIG_PATH]
    if len(raw) != expected_size:
        raise CaseContractError(
            f"canonical configuration source size mismatch: expected {expected_size}, got {len(raw)}"
        )
    try:
        payload = yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise CaseContractError("cannot parse canonical configuration") from exc
    if not isinstance(payload, dict):
        raise CaseContractError("canonical configuration must be a mapping")
    return payload


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CaseContractError(f"{name} must be a mapping")
    return value


def _require_exact_keys(mapping: dict[str, Any], expected: tuple[str, ...], name: str) -> None:
    actual = tuple(mapping)
    missing = [key for key in expected if key not in mapping]
    unsupported = [key for key in actual if key not in expected]
    if missing:
        raise CaseContractError(f"missing {name}.{missing[0]}")
    if unsupported:
        raise CaseContractError(f"unsupported config field {name}.{unsupported[0]}")


def _strict_int(value: Any, name: str, *, positive: bool = True) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CaseContractError(f"{name} must be an integer")
    if positive and value <= 0:
        raise CaseContractError(f"{name} must be positive")
    return value


def _validate_config(config: dict[str, Any]) -> None:
    _require_exact_keys(config, _EXPECTED_TOP_LEVEL, "config")
    system = _require_mapping(config["system"], "system")
    experiment = _require_mapping(config["experiment"], "experiment")
    weights = _require_mapping(config["weights"], "weights")
    _require_exact_keys(system, _EXPECTED_SYSTEM, "system")
    _require_exact_keys(experiment, _EXPECTED_EXPERIMENT, "experiment")
    _require_exact_keys(weights, _EXPECTED_WEIGHTS, "weights")

    for key in _EXPECTED_SYSTEM:
        value = _strict_int(system[key], f"system.{key}")
        if value != _EXPECTED_SYSTEM_VALUES[key]:
            raise CaseContractError(
                f"system.{key} must equal {_EXPECTED_SYSTEM_VALUES[key]}"
            )
    for key, expected in _EXPECTED_EXPERIMENT_VALUES.items():
        value = _strict_int(experiment[key], f"experiment.{key}")
        if value != expected:
            raise CaseContractError(f"experiment.{key} must equal {expected}")
    algorithms = experiment["algorithms"]
    if not isinstance(algorithms, list) or tuple(algorithms) != ALGORITHMS:
        raise CaseContractError("experiment.algorithms must match the approved order")
    if any(not isinstance(name, str) or not name.strip() for name in algorithms):
        raise CaseContractError("experiment.algorithms must contain nonempty strings")
    if len(set(algorithms)) != len(algorithms):
        raise CaseContractError("experiment.algorithms must not contain duplicates")
    for key, value in weights.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CaseContractError(f"weights.{key} must be numeric")


def _experiment_payload(config: dict[str, Any]) -> dict[str, Any]:
    _validate_config(config)
    system = config["system"]
    experiment = config["experiment"]
    return {
        "schema_version": "1.0",
        "experiment": {
            "name": "MEC main 40-task paired benchmark",
            "task": "MEC task offloading and CPU allocation",
        },
        "execution": {"runs": 30, "seed_column": "seed"},
        "algorithms": list(ALGORITHMS),
        "parameters": {
            "mobile_devices": system["mobile_devices"],
            "edge_servers": system["edge_servers"],
            "cloud_servers": system["cloud_servers"],
            "task_count": system["tasks"],
            "population_size": experiment["population_size"],
            "max_iterations": experiment["max_iterations"],
            "seed_start": experiment["seed_start"],
        },
        "metrics": {
            "fitness": {
                "direction": METRIC_DIRECTIONS["fitness"],
                "primary": True,
            },
            "csr": {
                "direction": METRIC_DIRECTIONS["csr"],
                "primary": False,
            },
        },
    }


def _write_new(path: Path, payload: dict[str, Any]) -> Path:
    if path.exists():
        raise FileExistsError(f"destination already exists: {path}")
    try:
        serialized = yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ).rstrip("\n") + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
    except FileExistsError:
        raise
    except OSError as exc:
        raise CaseContractError(f"cannot write experiment export {path}") from exc
    return path


def _export_experiment_from_config(config: dict[str, Any], destination: Path) -> Path:
    return _write_new(Path(destination), _experiment_payload(config))


def export_experiment(repo_root: Path, destination: Path) -> Path:
    """Export a validated, deterministic experiment.yaml from the canonical config."""

    return _export_experiment_from_config(_read_config(Path(repo_root)), Path(destination))


def _read_raw_rows(repo_root: Path) -> list[dict[str, str]]:
    path = resolve_source_path(repo_root, RAW_PATH)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CaseContractError("cannot read canonical raw results") from exc
    expected_hash = SOURCE_HASHES[RAW_PATH]
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != expected_hash:
        raise CaseContractError(f"canonical raw results source hash drift: expected {expected_hash}, got {actual_hash}")
    expected_size = SOURCE_SIZES[RAW_PATH]
    if len(raw) != expected_size:
        raise CaseContractError(f"canonical raw results source size mismatch: expected {expected_size}, got {len(raw)}")
    expected_columns = (
        "run_id", "seed", "algorithm", "fitness", "base_objective", "penalty",
        "search_fitness", "energy", "delay", "aoi", "qoe", "fairness", "csr",
        "hard_feasible", "capacity_utilisation_mean", "capacity_utilisation_max",
        "assignment_unique", "runtime", "nfe", "pre_refinement_fitness",
        "local_refinement_gain",
    )
    try:
        text = raw.decode("utf-8")
        reader = csv.DictReader(text.splitlines())
        if tuple(reader.fieldnames or ()) != expected_columns:
            raise CaseContractError("canonical raw results columns mismatch")
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CaseContractError("cannot parse canonical raw results") from exc
    if not rows:
        raise CaseContractError("canonical raw results has no rows")
    for row in rows:
        if set(row) != set(expected_columns) or None in row:
            raise CaseContractError("canonical raw results row width mismatch")
    return rows


def _write_csv_new(path: Path, rows: list[dict[str, str]]) -> Path:
    if path.exists():
        raise FileExistsError(f"destination already exists: {path}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(RAW_COLUMNS), lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(rows)
    except FileExistsError:
        raise
    except OSError as exc:
        raise CaseContractError(f"cannot write raw export {path}") from exc
    return path


def export_raw_results(repo_root: Path, destination: Path) -> Path:
    """Project canonical raw results into the fixed ReproAudit input shape."""

    source_rows = _read_raw_rows(Path(repo_root))
    exported: list[dict[str, str]] = []
    seen: set[tuple[int, str]] = set()
    for row in source_rows:
        try:
            seed = int(row["seed"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CaseContractError("raw seed must be an integer") from exc
        algorithm = row.get("algorithm", "")
        if algorithm not in ALGORITHMS:
            raise CaseContractError(f"unknown raw algorithm: {algorithm}")
        key = (seed, algorithm)
        if key in seen:
            raise CaseContractError(f"duplicate raw key: {key}")
        seen.add(key)
        try:
            fitness = float(row["fitness"])
            csr = float(row["csr"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CaseContractError("raw metrics must be numeric") from exc
        if not math.isfinite(fitness) or not math.isfinite(csr):
            raise CaseContractError("raw metrics must be finite")
        exported.append({"seed": str(seed), "algorithm": algorithm, "status": "success", "fitness": format(fitness, ".17g"), "csr": format(csr, ".17g")})
    if len(exported) != 180:
        raise CaseContractError(f"raw results row count mismatch: expected 180, got {len(exported)}")
    return _write_csv_new(Path(destination), exported)


def _read_summary_rows(repo_root: Path) -> list[dict[str, str]]:
    path = resolve_source_path(repo_root, SUMMARY_PATH)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CaseContractError("cannot read canonical summary results") from exc
    expected_hash = SOURCE_HASHES[SUMMARY_PATH]
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != expected_hash:
        raise CaseContractError(f"canonical summary results source hash drift: expected {expected_hash}, got {actual_hash}")
    expected_size = SOURCE_SIZES[SUMMARY_PATH]
    if len(raw) != expected_size:
        raise CaseContractError(f"canonical summary results source size mismatch: expected {expected_size}, got {len(raw)}")
    try:
        reader = csv.DictReader(raw.decode("utf-8").splitlines())
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CaseContractError("cannot parse canonical summary results") from exc
    if not rows or len(rows) != 6 or len(reader.fieldnames or ()) != 55:
        raise CaseContractError("canonical summary results shape mismatch")
    if any(not row.get("algorithm") or None in row for row in rows):
        raise CaseContractError("canonical summary results row width mismatch")
    if tuple(row["algorithm"] for row in rows) != ALGORITHMS:
        raise CaseContractError("canonical summary results algorithm order mismatch")
    return rows


def _write_summary_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    if path.exists():
        raise FileExistsError(f"destination already exists: {path}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["algorithm", "metric", "mean", "std", "median", "n"], lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    except FileExistsError:
        raise
    except OSError as exc:
        raise CaseContractError(f"cannot write summary export {path}") from exc
    return path


def export_summary_results(repo_root: Path, destination: Path) -> Path:
    """Project official summary means/stds and raw-derived median/count fields."""

    root = Path(repo_root)
    summary_rows = _read_summary_rows(root)
    raw_rows = _read_raw_rows(root)
    values: dict[tuple[str, str], list[float]] = {(algorithm, metric): [] for algorithm in ALGORITHMS for metric in METRICS}
    for row in raw_rows:
        algorithm = row.get("algorithm", "")
        try:
            values[(algorithm, "fitness")].append(float(row["fitness"]))
            values[(algorithm, "csr")].append(float(row["csr"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise CaseContractError("raw metric required for summary is invalid") from exc
    output: list[dict[str, str]] = []
    for source in summary_rows:
        algorithm = source["algorithm"]
        for metric in METRICS:
            raw_values = values[(algorithm, metric)]
            if len(raw_values) != 30 or not all(math.isfinite(value) for value in raw_values):
                raise CaseContractError(f"summary raw structure invalid for {algorithm}/{metric}")
            ordered = sorted(raw_values)
            median = (ordered[14] + ordered[15]) / 2
            prefix = f"{metric}_"
            try:
                mean_text = source[prefix + "mean"]
                std_text = source[prefix + "std"]
                mean = float(mean_text)
                std = float(std_text)
            except (KeyError, TypeError, ValueError) as exc:
                raise CaseContractError(f"official summary field missing for {algorithm}/{metric}") from exc
            if not math.isfinite(mean) or not math.isfinite(std):
                raise CaseContractError(f"official summary field nonfinite for {algorithm}/{metric}")
            output.append({"algorithm": algorithm, "metric": metric, "mean": mean_text, "std": std_text, "median": format(median, ".17g"), "n": str(len(raw_values))})
    return _write_summary_csv(Path(destination), output)


def export_faithful_case(repo_root: Path, output_dir: Path) -> ExportResult:
    """Assemble the deterministic faithful baseline input set."""

    root = Path(repo_root).resolve()
    destination = Path(output_dir).resolve()
    try:
        destination.relative_to(root)
    except ValueError:
        pass
    else:
        raise CaseContractError("output directory is inside repository")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise CaseContractError("output directory must be absent or empty")
    destination.mkdir(parents=True, exist_ok=True)
    parent = destination.parent
    temp_dir = Path(tempfile.mkdtemp(prefix="reproaudit-case-", dir=parent))
    try:
        experiment = export_experiment(root, temp_dir / "experiment.yaml")
        claims_traces = __import__("scripts.reproaudit_case.extract_claims", fromlist=["extract_claims"]).extract_claims(root, temp_dir / "claims.yaml")
        raw = export_raw_results(root, temp_dir / "raw_results.csv")
        summary = export_summary_results(root, temp_dir / "summary_results.csv")
        inventory = build_source_inventory(root)
        manifest = json.loads(serialize_manifest(inventory).decode("utf-8"))
        manifest.update({"case_id": "faithful_baseline", "generated_at_policy": "omitted_for_byte_determinism", "claim_traces": list(claims_traces), "status_source": "absent", "status_mapping": "all canonical source rows mapped to success"})
        manifest_path = temp_dir / "source_manifest.json"
        manifest_path.write_bytes((json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8"))
        files = (experiment, temp_dir / "claims.yaml", raw, summary, manifest_path)
        for source in files:
            target = destination / source.name
            if target.exists():
                raise CaseContractError("output directory must not overwrite files")
            os.replace(source, target)
        return ExportResult(destination, tuple(destination / source.name for source in files))
    except Exception:
        raise
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


__all__ = ["ExportResult", "export_experiment", "export_raw_results", "export_summary_results", "export_faithful_case"]
