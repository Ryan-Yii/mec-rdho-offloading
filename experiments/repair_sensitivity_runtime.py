from __future__ import annotations

import json
import numbers
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from experiments.experiment_core import (
    build_system_from_config,
    capture_git_state,
    ensure_fresh_run,
    ensure_legacy_snapshot,
    load_config,
    parse_force_flag,
    run_optimizer,
    weights_from_config,
)
from experiments.regenerate_analysis import (
    _artifact_records,
    _environment_record,
    _regenerate_sensitivity,
    file_sha256,
)


SOURCE_PATH = "results/sensitivity/audit/dynamic_penalty_sensitivity_raw_before_runtime_repair.csv"
OUTPUT_PATH = "results/sensitivity/raw/dynamic_penalty_sensitivity_raw_results.csv"
AUDIT_PATH = "results/manifests/sensitivity_runtime_repair.json"
ABSOLUTE_FLOOR_SECONDS = 60.0
MEDIAN_MULTIPLIER = 10.0
NUMERIC_TOLERANCE = 1.0e-12

DOWNSTREAM_OUTPUTS = [
    "results/sensitivity/summary/weight_sensitivity_summary_mean_std.csv",
    "results/sensitivity/summary/dynamic_penalty_sensitivity_summary_mean_std.csv",
    "paper_tables/weight_sensitivity_summary.md",
    "paper_tables/dynamic_penalty_sensitivity_summary.md",
    "results/sensitivity/figures/weight_sensitivity_fitness.png",
    "results/sensitivity/figures/weight_sensitivity_qoe_fairness_csr.png",
    "results/sensitivity/figures/penalty_sensitivity_heatmaps.png",
    "figures/supp_weight_sensitivity_fitness.png",
    "figures/fig09_weight_sensitivity_qoe_fairness_csr.png",
    "figures/fig10_penalty_sensitivity_heatmaps.png",
]


def select_suspended_runtime_rows(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float | int]]:
    if "runtime" not in frame:
        raise ValueError("runtime column is required for suspension audit")
    median = float(frame["runtime"].median())
    threshold = max(ABSOLUTE_FLOOR_SECONDS, MEDIAN_MULTIPLIER * median)
    selected = frame.loc[frame["runtime"] > threshold].copy()
    rule = {
        "suite_median_seconds": median,
        "absolute_floor_seconds": ABSOLUTE_FLOOR_SECONDS,
        "median_multiplier": MEDIAN_MULTIPLIER,
        "effective_threshold_seconds": threshold,
        "affected_rows": int(len(selected)),
    }
    return selected, rule


def _values_match(left: object, right: object, atol: float) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    if isinstance(left, numbers.Number) and isinstance(right, numbers.Number):
        return bool(np.isclose(float(left), float(right), rtol=0.0, atol=atol))
    return str(left) == str(right)


def compare_nonruntime_fields(
    original: Mapping[str, object],
    rerun: Mapping[str, object],
    atol: float = NUMERIC_TOLERANCE,
) -> dict[str, dict[str, object]]:
    differences = {}
    for field, original_value in original.items():
        if field == "runtime":
            continue
        if field not in rerun:
            differences[field] = {"original": original_value, "rerun": "<missing>"}
            continue
        rerun_value = rerun[field]
        if not _values_match(original_value, rerun_value, atol):
            differences[field] = {"original": original_value, "rerun": rerun_value}
    return differences


def _rerun_row(original: Mapping[str, object], config: dict) -> dict[str, object]:
    experiment = config["experiment"]
    scenario_id = int(original["scenario_id"])
    replicate_id = int(original["replicate_id"])
    scenario_seed = int(original["scenario_seed"])
    algorithm_seed = int(original["algorithm_seed"])
    lambda0 = float(original["lambda0"])
    alpha = float(original["alpha"])
    system = build_system_from_config(config, scenario_seed)
    row, _ = run_optimizer(
        system=system,
        algorithm_name="RDHO",
        run_id=int(original["run_id"]),
        seed=int(experiment.get("master_seed", experiment["seed_start"])),
        max_iter=int(experiment["max_iterations"]),
        population_size=int(experiment["population_size"]),
        weights=weights_from_config(config["weights"]),
        penalty_base=lambda0,
        dynamic_penalty_alpha=alpha,
        max_evaluations=int(experiment["max_evaluations"]),
        local_refinement=bool(experiment["local_refinement"]),
        scenario_id=scenario_id,
        replicate_id=replicate_id,
        scenario_seed=scenario_seed,
        algorithm_seed=algorithm_seed,
    )
    row.update({"experiment": "dynamic_penalty", "lambda0": lambda0, "alpha": alpha})
    return row


def main() -> None:
    force = parse_force_flag()
    ensure_legacy_snapshot()
    ensure_fresh_run([OUTPUT_PATH, *DOWNSTREAM_OUTPUTS, AUDIT_PATH], force=force)
    started_at = datetime.now(timezone.utc).isoformat()
    git_state = capture_git_state()
    if git_state.get("code_dirty"):
        raise RuntimeError("runtime repair requires committed configs, source, experiments, and tests")

    source = Path(SOURCE_PATH)
    if not source.is_file():
        raise FileNotFoundError(f"preserved pre-repair raw file is missing: {source}")
    original_frame = pd.read_csv(source)
    selected, selection_rule = select_suspended_runtime_rows(original_frame)
    if selected.empty:
        raise RuntimeError("post-run suspension audit selected no rows")

    config_path = Path("configs/sensitivity.yaml")
    config = load_config(config_path)
    repaired = original_frame.copy()
    repairs = []
    for index, original_series in selected.iterrows():
        original = original_series.to_dict()
        rerun = _rerun_row(original, config)
        differences = compare_nonruntime_fields(original, rerun)
        if differences:
            raise RuntimeError(
                f"deterministic fields changed for scenario {original['scenario_id']}: {differences}"
            )
        repaired.at[index, "runtime"] = float(rerun["runtime"])
        repairs.append(
            {
                "scenario_id": int(original["scenario_id"]),
                "replicate_id": int(original["replicate_id"]),
                "scenario_seed": int(original["scenario_seed"]),
                "algorithm_seed": int(original["algorithm_seed"]),
                "lambda0": float(original["lambda0"]),
                "alpha": float(original["alpha"]),
                "original_runtime_seconds": float(original["runtime"]),
                "rerun_runtime_seconds": float(rerun["runtime"]),
                "nonruntime_differences": {},
            }
        )

    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    repaired.to_csv(OUTPUT_PATH, index=False)
    _regenerate_sensitivity()
    ended_at = datetime.now(timezone.utc).isoformat()
    output_paths = [OUTPUT_PATH, *DOWNSTREAM_OUTPUTS]
    audit = {
        "schema_version": 2,
        "started_at": started_at,
        "ended_at": ended_at,
        "command": [sys.executable, "-m", "experiments.repair_sensitivity_runtime", *sys.argv[1:]],
        "repair_git": git_state,
        "config": {
            "path": config_path.as_posix(),
            "sha256": file_sha256(config_path),
        },
        "reason": (
            "A post-run audit identified wall-clock values that crossed confirmed Windows suspend intervals. "
            "Rows above max(60 seconds, 10 times the suite median) were rerun with identical seeds and settings."
        ),
        "selection_rule": selection_rule,
        "verification": {
            "excluded_fields": ["runtime"],
            "numeric_tolerance": NUMERIC_TOLERANCE,
            "nonruntime_differences": 0,
            "result": "All deterministic non-runtime fields reproduced within tolerance.",
        },
        "inputs": _artifact_records([SOURCE_PATH]),
        "outputs": _artifact_records(output_paths),
        "repairs": repairs,
        "environment": _environment_record(),
    }
    Path(AUDIT_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(AUDIT_PATH).write_text(json.dumps(audit, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
