from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from experiments.audit_results import audit_main_frame
from experiments.experiment_core import RDHO_VARIANTS, file_sha256
from experiments.statistical_analysis import PRIMARY_ALGORITHMS, friedman_tests


def validate_statistical_separation(primary: pd.DataFrame, supplementary: pd.DataFrame) -> None:
    if "Greedy-ED" in set(primary["comparison_algorithm"]):
        raise ValueError("Greedy-ED is present in primary equal-budget inference")
    if not primary["comparison_algorithm"].isin(PRIMARY_ALGORITHMS[1:]).all():
        raise ValueError("primary inference contains an unapproved comparison algorithm")
    if not primary["inference_tier"].eq("primary_equal_budget").all() or not primary["equal_budget"].astype(bool).all():
        raise ValueError("primary inference labels are inconsistent with equal-budget analysis")
    expected_family_size = len(PRIMARY_ALGORITHMS) - 1
    if not primary["holm_family_size"].eq(expected_family_size).all():
        raise ValueError("primary Holm family size is not seven")
    if set(supplementary["comparison_algorithm"]) != {"Greedy-ED"}:
        raise ValueError("supplementary inference must contain only Greedy-ED")
    if not supplementary["inference_tier"].eq("supplementary_effectiveness_vs_cost").all():
        raise ValueError("Greedy-ED comparison is missing its supplementary label")
    if supplementary["equal_budget"].astype(bool).any():
        raise ValueError("Greedy-ED comparison is incorrectly labelled equal-budget")


def verify_manifest_records(
    manifest: dict[str, object],
    root: str | Path,
    *,
    sections: Sequence[str] = ("inputs", "outputs"),
) -> int:
    root_path = Path(root)
    checked = 0
    for section in sections:
        for record in manifest.get(section, []):
            path = root_path / str(record["path"])
            if not path.is_file():
                raise FileNotFoundError(f"manifest artifact is missing: {record['path']}")
            actual = file_sha256(path)
            if actual != record["sha256"]:
                raise ValueError(f"manifest hash mismatch: {record['path']}")
            checked += 1
    return checked


def _require_files(root: Path, paths: Iterable[str]) -> None:
    missing = [path for path in paths if not (root / path).is_file()]
    if missing:
        raise FileNotFoundError(f"required formal artifacts are missing: {missing}")


def _validate_unique(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    if frame.duplicated(columns, keep=False).any():
        raise ValueError(f"{label} contains duplicate rows for key {columns}")


def _validate_run_manifest(root: Path, relative_path: str) -> int:
    path = root / relative_path
    manifest = json.loads(path.read_text(encoding="utf-8"))
    config_path = root / manifest["config_path"]
    if file_sha256(config_path) != manifest["config_hash"]:
        raise ValueError(f"run manifest config hash mismatch: {relative_path}")
    records = [
        record
        for record in manifest.get("output_artifacts", [])
        if "/raw/" in str(record["path"]) or "/checkpoints/" in str(record["path"])
    ]
    checked = 0
    for record in records:
        artifact = root / record["path"]
        if not artifact.is_file():
            raise FileNotFoundError(f"run-manifest artifact is missing: {record['path']}")
        if file_sha256(artifact) != record["sha256"]:
            raise ValueError(f"run-manifest artifact hash mismatch: {record['path']}")
        checked += 1
    return checked


def validate_artifacts(root: str | Path = ".") -> list[str]:
    root_path = Path(root)
    required = [
        "results/raw/main_30_raw_results.csv",
        "results/raw/ablation_30_raw_results.csv",
        "results/sensitivity/raw/weight_sensitivity_raw_results.csv",
        "results/statistics/main_friedman_equal_budget.csv",
        "results/statistics/main_pairwise_equal_budget.csv",
        "results/statistics/main_greedy_supplementary.csv",
        "results/statistics/ablation_friedman.csv",
        "results/statistics/ablation_pairwise.csv",
        "results/sensitivity/statistics/weight_sensitivity_friedman.csv",
        "results/sensitivity/statistics/weight_sensitivity_pairwise_equal_budget.csv",
        "results/sensitivity/statistics/weight_sensitivity_ranks.csv",
        "results/manifests/ablation_30_manifest.json",
        "results/manifests/weight_sensitivity_manifest.json",
        "results/manifests/postrun_analysis_manifest.json",
        "docs/main_result_audit.md",
        "docs/manuscript_revision_package.md",
        "figures/fig07_ablation_study.png",
        "figures/fig09_weight_sensitivity_algorithm_ranks.png",
    ]
    _require_files(root_path, required)
    checks: list[str] = []

    main = pd.read_csv(root_path / "results/raw/main_30_raw_results.csv")
    _validate_unique(main, ["scenario_id", "replicate_id", "algorithm"], "main results")
    audit_main_frame(main)
    checks.append("main raw results: 30 paired scenarios, objective decomposition, seeds, and NFE")

    ablation = pd.read_csv(root_path / "results/raw/ablation_30_raw_results.csv")
    _validate_unique(ablation, ["scenario_id", "replicate_id", "algorithm"], "ablation results")
    if set(ablation["algorithm"]) != set(RDHO_VARIANTS):
        raise ValueError("ablation raw results do not contain the seven approved variants")
    if len(ablation) != 30 * len(RDHO_VARIANTS):
        raise ValueError("ablation raw result row count is not 30 x 7")
    friedman_tests(ablation, tuple(RDHO_VARIANTS))
    checks.append("ablation raw results: seven variants and complete pairing")

    weight = pd.read_csv(root_path / "results/sensitivity/raw/weight_sensitivity_raw_results.csv")
    _validate_unique(weight, ["setting", "scenario_id", "replicate_id", "algorithm"], "weight results")
    if set(weight["setting"]) != {"S1", "S2", "S3", "S4", "S5"}:
        raise ValueError("weight sensitivity setting set is incomplete")
    if set(weight["algorithm"]) != set(PRIMARY_ALGORITHMS):
        raise ValueError("weight sensitivity algorithm set is incomplete")
    if len(weight) != 5 * 30 * len(PRIMARY_ALGORITHMS):
        raise ValueError("weight sensitivity raw result row count is not 5 x 30 x 8")
    friedman_tests(weight, PRIMARY_ALGORITHMS, group_cols=["setting"])
    checks.append("weight raw results: five settings, eight algorithms, and complete pairing")

    primary = pd.read_csv(root_path / "results/statistics/main_pairwise_equal_budget.csv")
    supplementary = pd.read_csv(root_path / "results/statistics/main_greedy_supplementary.csv")
    validate_statistical_separation(primary, supplementary)
    checks.append("primary and supplementary inferential statistics are separated")

    postrun_path = root_path / "results/manifests/postrun_analysis_manifest.json"
    postrun = json.loads(postrun_path.read_text(encoding="utf-8"))
    count = verify_manifest_records(postrun, root_path)
    checks.append(f"post-run analysis manifest hashes: {count} artifacts")
    for manifest_path in (
        "results/manifests/ablation_30_manifest.json",
        "results/manifests/weight_sensitivity_manifest.json",
    ):
        checked = _validate_run_manifest(root_path, manifest_path)
        checks.append(f"{manifest_path}: config plus {checked} artifact hashes")
    return checks


def main() -> None:
    checks = validate_artifacts()
    print(f"Artifact validation passed: {len(checks)} checks")
    for check in checks:
        print(f"- {check}")


if __name__ == "__main__":
    main()
