"""Read-only provenance and schema inventory for the canonical MEC sources."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import pandas as pd

from .constants import (
    ALGORITHMS,
    MEC_COMMIT,
    METRICS,
    SOURCE_HASHES,
    SOURCE_PATHS,
    SOURCE_SIZES,
    resolve_source_path,
)


class CaseContractError(ValueError):
    """Raised when a canonical source violates the acceptance contract."""


SourceInventoryError = CaseContractError


@dataclass(frozen=True)
class SourceFileRecord:
    path: str
    sha256: str
    size_bytes: int
    shape: tuple[int, int] | None = None
    columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceInventory:
    mec_commit: str
    files: tuple[SourceFileRecord, ...]
    algorithms: tuple[str, ...]
    metrics: tuple[str, ...]

    def to_manifest_payload(self) -> dict[str, Any]:
        return build_manifest_payload(self)


_RAW_SOURCE = "results/v2/raw/main_30_raw_results.csv"
_SUMMARY_SOURCE = "results/v2/summary/main_30_summary_mean_std.csv"
_RAW_SHAPE = (180, 21)
_SUMMARY_SHAPE = (6, 55)
_RAW_COLUMNS = (
    "run_id", "seed", "algorithm", "fitness", "base_objective", "penalty",
    "search_fitness", "energy", "delay", "aoi", "qoe", "fairness", "csr",
    "hard_feasible", "capacity_utilisation_mean", "capacity_utilisation_max",
    "assignment_unique", "runtime", "nfe", "pre_refinement_fitness",
    "local_refinement_gain",
)
_SUMMARY_COLUMNS = (
    "algorithm", "fitness_mean", "fitness_std", "fitness", "base_objective_mean",
    "base_objective_std", "base_objective", "penalty_mean", "penalty_std", "penalty",
    "search_fitness_mean", "search_fitness_std", "search_fitness", "energy_mean",
    "energy_std", "energy", "delay_mean", "delay_std", "delay", "aoi_mean", "aoi_std",
    "aoi", "qoe_mean", "qoe_std", "qoe", "fairness_mean", "fairness_std", "fairness",
    "csr_mean", "csr_std", "csr", "hard_feasible_mean", "hard_feasible_std",
    "hard_feasible", "capacity_utilisation_mean_mean", "capacity_utilisation_mean_std",
    "capacity_utilisation_mean", "capacity_utilisation_max_mean", "capacity_utilisation_max_std",
    "capacity_utilisation_max", "assignment_unique_mean", "assignment_unique_std",
    "assignment_unique", "runtime_mean", "runtime_std", "runtime", "nfe_mean", "nfe_std",
    "nfe", "pre_refinement_fitness_mean", "pre_refinement_fitness_std",
    "pre_refinement_fitness", "local_refinement_gain_mean", "local_refinement_gain_std",
    "local_refinement_gain",
)


def _git_output(repo_root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), *args],
            stderr=subprocess.STDOUT,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "output", "") or str(exc)
        raise CaseContractError(f"unable to verify Git source provenance: {detail}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise CaseContractError(f"cannot read canonical source {path}") from exc
    return digest.hexdigest()


def _schema(path: Path, relative_path: str) -> tuple[tuple[int, int], tuple[str, ...]]:
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        raise CaseContractError(f"cannot parse canonical CSV {relative_path}") from exc
    shape = tuple(int(value) for value in frame.shape)
    columns = tuple(str(value) for value in frame.columns)
    expected = {
        _RAW_SOURCE: (_RAW_SHAPE, _RAW_COLUMNS),
        _SUMMARY_SOURCE: (_SUMMARY_SHAPE, _SUMMARY_COLUMNS),
    }.get(relative_path)
    if expected is None:
        raise CaseContractError(f"unsupported tabular source {relative_path}")
    if shape != expected[0] or columns != expected[1]:
        raise CaseContractError(
            f"canonical source schema drift for {relative_path}: "
            f"shape={shape!r}, columns={columns!r}"
        )
    return shape, columns


def build_source_inventory(repo_root: Path) -> SourceInventory:
    """Validate and inventory all pinned sources without modifying repository data."""

    root = Path(repo_root).resolve()
    current_head = _git_output(root, "rev-parse", "HEAD")
    if not current_head:
        raise CaseContractError("repository HEAD is empty")
    _git_output(root, "cat-file", "-e", f"{MEC_COMMIT}^{{commit}}")

    records: list[SourceFileRecord] = []
    for relative_path in SOURCE_PATHS:
        path = resolve_source_path(root, relative_path)
        if not path.is_file():
            raise CaseContractError(f"canonical source is missing: {relative_path}")
        actual_hash = _sha256(path)
        expected_hash = SOURCE_HASHES[relative_path]
        if actual_hash != expected_hash:
            raise CaseContractError(
                f"canonical source hash drift for {relative_path}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
        shape: tuple[int, int] | None = None
        columns: tuple[str, ...] = ()
        if relative_path in (_RAW_SOURCE, _SUMMARY_SOURCE):
            shape, columns = _schema(path, relative_path)
        try:
            size_bytes = path.stat().st_size
        except OSError as exc:
            raise CaseContractError(f"cannot stat canonical source {relative_path}") from exc
        expected_size = SOURCE_SIZES[relative_path]
        if size_bytes != expected_size:
            raise CaseContractError(
                f"canonical source size mismatch for {relative_path}: "
                f"expected {expected_size}, got {size_bytes}"
            )
        records.append(
            SourceFileRecord(
                path=relative_path,
                sha256=actual_hash,
                size_bytes=size_bytes,
                shape=shape,
                columns=columns,
            )
        )

    return SourceInventory(
        mec_commit=MEC_COMMIT,
        files=tuple(records),
        algorithms=tuple(ALGORITHMS),
        metrics=tuple(METRICS),
    )


def build_manifest_payload(inventory: SourceInventory) -> dict[str, Any]:
    """Return a stable, timestamp-free JSON-compatible manifest payload."""

    return {
        "algorithms": list(inventory.algorithms),
        "files": [
            {
                "columns": list(record.columns),
                "path": record.path,
                "sha256": record.sha256,
                "shape": list(record.shape) if record.shape is not None else None,
                "size_bytes": record.size_bytes,
            }
            for record in inventory.files
        ],
        "mec_commit": inventory.mec_commit,
        "metrics": list(inventory.metrics),
    }


def serialize_manifest(inventory: SourceInventory) -> bytes:
    """Serialize a manifest deterministically as UTF-8 JSON with one LF."""

    return (
        json.dumps(
            build_manifest_payload(inventory),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


__all__ = [
    "CaseContractError",
    "SourceFileRecord",
    "SourceInventory",
    "SourceInventoryError",
    "build_manifest_payload",
    "build_source_inventory",
    "serialize_manifest",
]
