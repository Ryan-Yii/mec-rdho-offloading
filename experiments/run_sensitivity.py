from __future__ import annotations

import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from experiments.analyze_results import generate_sensitivity_figures
from experiments.experiment_core import (
    copy_artifact,
    ensure_fresh_run,
    load_config,
    parse_force_flag,
    run_algorithm_suite,
    write_raw_and_summary,
    write_run_manifest,
)


WEIGHT_RAW = "results/sensitivity/raw/weight_sensitivity_raw_results.csv"
WEIGHT_SUMMARY = "results/sensitivity/summary/weight_sensitivity_summary_mean_std.csv"
PENALTY_RAW = "results/sensitivity/raw/dynamic_penalty_sensitivity_raw_results.csv"
PENALTY_SUMMARY = "results/sensitivity/summary/dynamic_penalty_sensitivity_summary_mean_std.csv"


def _weights_sum_to_one(weights: dict[str, float]) -> bool:
    return abs(sum(float(value) for value in weights.values()) - 1.0) < 1.0e-9


def _format_weights(weights: dict[str, float]) -> str:
    return (
        f"({weights['energy']:.3f}, {weights['delay']:.3f}, {weights['aoi']:.3f}, "
        f"{weights['qoe']:.3f}, {weights['fairness']:.3f})"
    )


def _write_markdown_table(csv_path: str, markdown_path: str) -> None:
    Path(markdown_path).parent.mkdir(parents=True, exist_ok=True)
    pd.read_csv(csv_path).to_markdown(markdown_path, index=False)


def run_weight_sensitivity(config: dict) -> None:
    n_runs = int(config["experiment"]["independent_runs"])
    group_cols = ["setting", "description", "weights", "w_energy", "w_delay", "w_aoi", "w_qoe", "w_fairness"]

    all_rows = []
    for setting in config["weight_settings"]:
        weights = {key: float(value) for key, value in setting["weights"].items()}
        if not _weights_sum_to_one(weights):
            raise ValueError(f"{setting['setting']} weights must sum to 1.0: {weights}")

        print(f"Running weight sensitivity {setting['setting']} with {n_runs} runs...")
        run_config = deepcopy(config)
        run_config["weights"] = weights
        run_config.pop("penalty", None)
        rows, _ = run_algorithm_suite(run_config, ["RDHO"], n_runs=n_runs)
        for row in rows:
            row["experiment"] = "objective_weight"
            row["setting"] = setting["setting"]
            row["description"] = setting["description"]
            row["weights"] = _format_weights(weights)
            row["w_energy"] = weights["energy"]
            row["w_delay"] = weights["delay"]
            row["w_aoi"] = weights["aoi"]
            row["w_qoe"] = weights["qoe"]
            row["w_fairness"] = weights["fairness"]
        all_rows.extend(rows)

    write_raw_and_summary(
        WEIGHT_RAW,
        WEIGHT_SUMMARY,
        all_rows,
        group_cols=group_cols,
    )
    _write_markdown_table(WEIGHT_SUMMARY, "paper_tables/weight_sensitivity_summary.md")


def run_penalty_sensitivity(config: dict) -> None:
    n_runs = int(config["experiment"]["independent_runs"])
    all_rows = []
    for lambda0 in config["penalty_grid"]["lambda0"]:
        for alpha in config["penalty_grid"]["alpha"]:
            print(f"Running penalty sensitivity lambda0={float(lambda0):.1f}, alpha={float(alpha):.1f} with {n_runs} runs...")
            run_config = deepcopy(config)
            run_config["weights"] = deepcopy(config["weights"])
            run_config["penalty"] = {"lambda0": float(lambda0), "alpha": float(alpha)}
            rows, _ = run_algorithm_suite(run_config, ["RDHO"], n_runs=n_runs)
            for row in rows:
                row["experiment"] = "dynamic_penalty"
                row["lambda0"] = float(lambda0)
                row["alpha"] = float(alpha)
            all_rows.extend(rows)

    write_raw_and_summary(
        PENALTY_RAW,
        PENALTY_SUMMARY,
        all_rows,
        group_cols=["lambda0", "alpha"],
    )
    _write_markdown_table(PENALTY_SUMMARY, "paper_tables/dynamic_penalty_sensitivity_summary.md")


def main() -> None:
    force = parse_force_flag()
    outputs = [
        WEIGHT_RAW,
        WEIGHT_SUMMARY,
        PENALTY_RAW,
        PENALTY_SUMMARY,
        "paper_tables/weight_sensitivity_summary.md",
        "paper_tables/dynamic_penalty_sensitivity_summary.md",
        "results/sensitivity/figures",
        "figures/fig09_weight_sensitivity_qoe_fairness_csr.png",
        "figures/fig10_penalty_sensitivity_heatmaps.png",
        "figures/supp_weight_sensitivity_fitness.png",
    ]
    ensure_fresh_run(outputs, force=force)
    started_at = datetime.now(timezone.utc).isoformat()
    config = load_config("configs/sensitivity.yaml")
    run_weight_sensitivity(config)
    run_penalty_sensitivity(config)
    generate_sensitivity_figures(WEIGHT_RAW, PENALTY_RAW, "results/sensitivity/figures")
    copy_artifact(
        "results/sensitivity/figures/weight_sensitivity_qoe_fairness_csr.png",
        "figures/fig09_weight_sensitivity_qoe_fairness_csr.png",
    )
    copy_artifact(
        "results/sensitivity/figures/penalty_sensitivity_heatmaps.png",
        "figures/fig10_penalty_sensitivity_heatmaps.png",
    )
    copy_artifact(
        "results/sensitivity/figures/weight_sensitivity_fitness.png",
        "figures/supp_weight_sensitivity_fitness.png",
    )
    experiment = config["experiment"]
    write_run_manifest(
        "results/manifests/sensitivity_manifest.json",
        config_path="configs/sensitivity.yaml",
        output_paths=outputs,
        command=[sys.executable, "-m", "experiments.run_sensitivity", *sys.argv[1:]],
        master_seed=int(experiment.get("master_seed", experiment["seed_start"])),
        max_evaluations=int(experiment["max_evaluations"]),
        started_at=started_at,
        ended_at=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    main()
