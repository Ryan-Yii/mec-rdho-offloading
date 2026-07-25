from __future__ import annotations

import argparse
import csv
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.controlled_evidence_reporting import paired_statistics, repository_v2_hashes, sha256_file, summarize_raw


EXPECTED = {
    "controlled_population_stage": {
        "methods": {"RDHO-population-controlled", "RIME-population-controlled", "DBO-population-controlled"},
        "nfe": 3801,
        "refinement_nfe": 0,
    },
    "controlled_common_pipeline": {
        "methods": {"RDHO-common-pipeline", "RIME-common-pipeline", "DBO-common-pipeline"},
        "nfe": 10232,
        "refinement_nfe": 1000,
    },
}


def _same_records(actual: list[dict], expected: list[dict]) -> bool:
    if len(actual) != len(expected):
        return False
    for observed, reference in zip(actual, expected):
        if observed.keys() != reference.keys():
            return False
        for key in observed:
            left, right = observed[key], reference[key]
            if isinstance(left, float) or isinstance(right, float):
                if not np.isclose(float(left), float(right), rtol=0.0, atol=1.0e-12):
                    return False
            elif left != right:
                return False
    return True


def verify(results_root: Path = Path("results")) -> None:
    source_commit = subprocess.check_output(["git", "rev-parse", "cf499f2"], text=True).strip()
    current_v2 = repository_v2_hashes()
    integrity = pd.read_csv(results_root / "audit" / "controlled_evidence_v2_integrity.csv")
    if not integrity["unchanged"].all() or len(integrity) != len(current_v2):
        raise AssertionError("V2 integrity audit is incomplete or failed")
    for row in integrity.itertuples(index=False):
        if row.sha256_before != row.sha256_after or row.sha256_after != current_v2[row.path]:
            raise AssertionError(f"V2 hash mismatch: {row.path}")

    audit = pd.read_csv(results_root / "audit" / "controlled_initial_population_audit.csv")
    if len(audit) != 180:
        raise AssertionError("initial-population audit must contain 180 method rows")
    for (_, _), group in audit.groupby(["experiment", "scenario_seed"]):
        if len(group) != 3 or group["population_hash"].nunique() != 1:
            raise AssertionError("paired methods did not receive one common initial population")

    all_statistics: list[dict] = []
    for experiment, expected in EXPECTED.items():
        raw_path = results_root / "raw" / f"{experiment}_30_raw_results.csv"
        summary_path = results_root / "summary" / f"{experiment}_30_summary.csv"
        stats_path = results_root / "statistics" / f"{experiment}_wilcoxon.csv"
        raw = pd.read_csv(raw_path)
        if len(raw) != 90 or set(raw["method"]) != expected["methods"]:
            raise AssertionError(f"wrong rows or methods in {raw_path}")
        if set(raw["scenario_seed"]) != set(range(20260701, 20260731)):
            raise AssertionError(f"wrong paired scenarios in {raw_path}")
        if not (raw["total_nfe"] == expected["nfe"]).all():
            raise AssertionError(f"NFE mismatch in {raw_path}")
        if not (raw["refinement_nfe"] == expected["refinement_nfe"]).all():
            raise AssertionError(f"refinement NFE mismatch in {raw_path}")
        if not (raw["hard_feasible"] == 1).all() or not (raw["assignment_unique"] == 1).all():
            raise AssertionError(f"feasibility audit failed in {raw_path}")
        if raw["initial_population_hash"].isna().any() or set(raw["code_commit"]) != {source_commit}:
            raise AssertionError(f"provenance is incomplete in {raw_path}")
        for _, group in raw.groupby("scenario_seed"):
            if group["initial_population_hash"].nunique() != 1:
                raise AssertionError(f"raw rows have mismatched common populations in {raw_path}")
        expected_summary = summarize_raw(raw.to_dict("records"))
        actual_summary = pd.read_csv(summary_path).to_dict("records")
        if not _same_records(actual_summary, expected_summary):
            raise AssertionError(f"summary is not rebuilt from raw rows: {summary_path}")
        expected_stats = paired_statistics(raw.to_dict("records"), experiment=experiment)
        actual_stats = pd.read_csv(stats_path).to_dict("records")
        if not _same_records(actual_stats, expected_stats):
            raise AssertionError(f"statistics are not rebuilt from raw rows: {stats_path}")
        all_statistics.extend(expected_stats)

    combined = pd.read_csv(results_root / "statistics" / "controlled_evidence_effect_sizes.csv").to_dict("records")
    if not _same_records(combined, all_statistics):
        raise AssertionError("combined effect-size table is not rebuilt from experiment statistics")
    tracked_v2 = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "results/v2"], text=True, capture_output=True, check=True)
    if tracked_v2.stdout:
        raise AssertionError("new output was mixed into the protected V2 result directory")
    print("controlled RDHO evidence verification: PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the additive controlled RDHO evidence artifacts.")
    parser.add_argument("--results-root", default="results")
    args = parser.parse_args()
    verify(Path(args.results_root))


if __name__ == "__main__":
    main()
