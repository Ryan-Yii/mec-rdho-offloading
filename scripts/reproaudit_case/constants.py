"""Immutable contract values for the ReproAudit MEC acceptance case.

This module contains declarations only.  It deliberately does not inspect the
repository or read any source data at import time.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Mapping


MEC_COMMIT = "b8abb436f215a9b2f4d646cf5fc0cf048174b68d"
REPROAUDIT_TAG = "v0.1.0"
REPROAUDIT_COMMIT = "1b6a9eb57529e4d92886fa7aa06dabbba5316105"
REPROAUDIT_WHEEL_NAME = "reproaudit-0.1.0-py3-none-any.whl"
REPROAUDIT_WHEEL_SHA256 = "dfab966ed90b98620d0c6b4fbeb80b31b44879493e092d4ef9314c9812998b5c"

SOURCE_PATHS = (
    "configs/main_40tasks.yaml",
    "results/v2/raw/main_30_raw_results.csv",
    "results/v2/summary/main_30_summary_mean_std.csv",
    "README.md",
    "docs/experiment_protocol_v2.md",
)
SOURCE_SHA256 = (
    "d99ba17554e67f6d1ad9aef9bbec9a4470b5b6bde8c77309ed82951e159fe8c4",
    "f885d8dd171e277d351ef268449f0aa5179a26f6e9c66256d4596d37a360c639",
    "751a936d794c642f640d6d9ae0309b153d728932c27e077c5188861feafa28d6",
    "519b055257d1525806d0fbb3edf72f58848ee6ecc96112544158e93eb8f01cb6",
    "c1db229a76a50c6269e1417a521135056cfbdfb29556d1c368d3e96a60a1fa42",
)
SOURCE_HASHES: Mapping[str, str] = MappingProxyType(dict(zip(SOURCE_PATHS, SOURCE_SHA256)))

ALGORITHMS = ("RDHO", "RIME", "DBO", "TLBO-HHO", "CWTSSA", "Greedy-ED")
METRICS = ("fitness", "csr")
METRIC_DIRECTIONS: Mapping[str, str] = MappingProxyType(
    {"fitness": "minimize", "csr": "maximize"}
)
PRIMARY_METRIC = "fitness"
ABS_TOLERANCE = 0.00005
REL_TOLERANCE = 0.0

RAW_COLUMNS = ("seed", "algorithm", "status", "fitness", "csr")
SUMMARY_COLUMNS = ("algorithm", "metric", "mean", "std", "median", "n")


def resolve_source_path(repo_root: Path, relative_path: str | Path) -> Path:
    """Resolve a repository-relative source path without permitting escapes."""

    root = Path(repo_root).resolve()
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise ValueError("source path must be repository-relative")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("source path escapes repository root") from exc
    return resolved
