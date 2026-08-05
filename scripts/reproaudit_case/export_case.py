"""Export the canonical MEC experiment configuration to ReproAudit YAML."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from .constants import (
    ALGORITHMS,
    METRIC_DIRECTIONS,
    SOURCE_HASHES,
    SOURCE_SIZES,
    resolve_source_path,
)
from .source_inventory import CaseContractError


CONFIG_PATH = "configs/main_40tasks.yaml"
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


def _write_new(path: Path, payload: dict[str, Any]) -> None:
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


def _export_experiment_from_config(config: dict[str, Any], destination: Path) -> None:
    _write_new(Path(destination), _experiment_payload(config))


def export_experiment(repo_root: Path, destination: Path) -> None:
    """Export a validated, deterministic experiment.yaml from the canonical config."""

    _export_experiment_from_config(_read_config(Path(repo_root)), Path(destination))


__all__ = ["export_experiment"]
