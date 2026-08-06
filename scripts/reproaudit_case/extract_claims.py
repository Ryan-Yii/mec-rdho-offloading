"""Extract README-backed claims for the faithful MEC case."""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from .constants import ALGORITHMS, SOURCE_HASHES, SOURCE_SIZES, resolve_source_path
from .source_inventory import CaseContractError


README_PATH = "README.md"
_ALGORITHM_MAP = {"RDHO-full": "RDHO"}
_TABLE_HEADER = "| Algorithm | Reporting fitness | QoE | Per-user fairness | Soft CSR | Runtime (s) | NFE |"


def _read_readme(repo_root: Path) -> str:
    path = resolve_source_path(repo_root, README_PATH)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CaseContractError("cannot read canonical README") from exc
    expected_hash = SOURCE_HASHES[README_PATH]
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != expected_hash:
        raise CaseContractError(f"canonical README source hash drift: expected {expected_hash}, got {actual_hash}")
    if len(raw) != SOURCE_SIZES[README_PATH]:
        raise CaseContractError("canonical README source size mismatch")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CaseContractError("canonical README is not UTF-8") from exc


def _README_TABLE(text: str) -> list[tuple[str, str, str]]:
    lines = text.splitlines()
    try:
        start = lines.index(_TABLE_HEADER)
    except ValueError as exc:
        raise CaseContractError("README V2 result table is missing") from exc
    rows: list[tuple[str, str, str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 7:
            raise CaseContractError("README V2 result table shape mismatch")
        rows.append((cells[0], cells[1], cells[4]))
    if len(rows) != len(ALGORITHMS):
        raise CaseContractError("README V2 result table row count mismatch")
    return rows


def _normalize_algorithm(name: str) -> str:
    if name in _ALGORITHM_MAP:
        return _ALGORITHM_MAP[name]
    if name not in ALGORITHMS:
        raise CaseContractError(f"unknown README algorithm: {name}")
    return name


def _decimal_value(value: str, label: str) -> float:
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise CaseContractError(f"invalid README decimal for {label}") from exc
    if not number.is_finite():
        raise CaseContractError(f"nonfinite README decimal for {label}")
    return float(number)


def _write_claims(path: Path, payload: dict[str, Any]) -> Path:
    if path.exists():
        raise FileExistsError(f"destination already exists: {path}")
    serialized = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, default_flow_style=False).rstrip("\n") + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
    except FileExistsError:
        raise
    except OSError as exc:
        raise CaseContractError(f"cannot write claims export {path}") from exc
    return path


def extract_claims(repo_root: Path, destination: Path) -> tuple[dict[str, Any], ...]:
    """Extract README claims and write the strict faithful claims YAML."""

    text = _read_readme(Path(repo_root))
    table = _README_TABLE(text)
    lines = text.splitlines()
    table_start = lines.index(_TABLE_HEADER)
    reported: dict[str, dict[str, dict[str, float]]] = {}
    traces: list[dict[str, Any]] = []
    for index, (source_name, fitness, csr) in enumerate(table, start=1):
        algorithm = _normalize_algorithm(source_name)
        fitness = _decimal_value(fitness, f"{algorithm}.fitness")
        csr = _decimal_value(csr, f"{algorithm}.csr")
        reported[algorithm] = {
            "fitness": {"mean": fitness},
            "csr": {"mean": csr},
        }
        exact = lines[table_start + index + 1]
        traces.extend((
            {"claim_id": f"CRES-{2 * index - 1:03d}", "claim_type": "reported_fitness", "source_path": README_PATH, "source_line": table_start + index + 2, "source_text": exact, "algorithm": algorithm, "metric": "fitness", "display": fitness, "disposition": "entered"},
            {"claim_id": f"CRES-{2 * index:03d}", "claim_type": "reported_csr", "source_path": README_PATH, "source_line": table_start + index + 2, "source_text": exact, "algorithm": algorithm, "metric": "csr", "display": csr, "disposition": "entered"},
        ))
    config_match = re.search(r"canonical configuration uses (\d+) devices, (\d+) edge servers, (\d+) cloud servers, (\d+) tasks, population (\d+), (\d+) iterations, and (\d+) paired scenarios", text)
    if not config_match:
        raise CaseContractError("README configuration claims are missing")
    devices, edge, cloud, tasks, population, iterations, runs = (int(value) for value in config_match.groups())
    parameter_claims = {
        "mobile_devices": devices,
        "edge_servers": edge,
        "cloud_servers": cloud,
        "task_count": tasks,
        "population_size": population,
        "max_iterations": iterations,
    }
    for number, (name, value) in enumerate((("runs", runs), ("mobile_devices", devices), ("edge_servers", edge), ("cloud_servers", cloud), ("task_count", tasks), ("population_size", population), ("max_iterations", iterations)), start=1):
        traces.append({"claim_id": f"CCFG-{number:03d}", "claim_type": "config", "source_path": README_PATH, "source_line": config_match.string[:config_match.start()].count("\n") + 1, "source_text": config_match.group(0), "normalized": {name: value}, "disposition": "entered"})
    conclusion = "RDHO-full beats each configured main baseline in all 30 paired scenarios"
    if conclusion not in text:
        raise CaseContractError("README candidate conclusion is missing")
    traces.append({"claim_id": "CWIN-001", "claim_type": "candidate_conclusion", "source_path": README_PATH, "source_line": text[: text.index(conclusion)].count("\n") + 1, "source_text": conclusion, "disposition": "R202_SKIP"})
    payload = {
        "schema_version": "1.0",
        "experiment_claims": {"runs": runs},
        "parameter_claims": parameter_claims,
        "reported_results": reported,
        "audit": {"absolute_tolerance": 0.00005, "relative_tolerance": 0.0},
    }
    _write_claims(Path(destination), payload)
    return tuple(traces)


__all__ = ["extract_claims"]
