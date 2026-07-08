from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd

from experiments.analyze_results import generate_sensitivity_figures
from experiments.experiment_core import load_config, run_algorithm_suite, write_raw_and_summary


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


def _weight_raw_complete(path: str, settings: list[str], n_runs: int) -> bool:
    if not Path(path).exists():
        return False
    df = pd.read_csv(path)
    counts = df.groupby("setting").size().to_dict()
    return all(counts.get(setting) == n_runs for setting in settings)


def _penalty_raw_complete(path: str, lambdas: list[float], alphas: list[float], n_runs: int) -> bool:
    if not Path(path).exists():
        return False
    df = pd.read_csv(path)
    counts = df.groupby(["lambda0", "alpha"]).size().to_dict()
    expected = [(float(lambda0), float(alpha)) for lambda0 in lambdas for alpha in alphas]
    return all(counts.get(pair) == n_runs for pair in expected)


def run_weight_sensitivity(config: dict) -> None:
    n_runs = int(config["experiment"]["independent_runs"])
    settings = [setting["setting"] for setting in config["weight_settings"]]
    group_cols = ["setting", "description", "weights", "w_energy", "w_delay", "w_aoi", "w_qoe", "w_fairness"]
    if _weight_raw_complete(WEIGHT_RAW, settings, n_runs):
        print(f"Reusing completed weight sensitivity raw results from {WEIGHT_RAW}...")
        rows = pd.read_csv(WEIGHT_RAW).to_dict("records")
        write_raw_and_summary(WEIGHT_RAW, WEIGHT_SUMMARY, rows, group_cols=group_cols)
        _write_markdown_table(WEIGHT_SUMMARY, "paper_tables/weight_sensitivity_summary.md")
        return

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
    lambdas = [float(value) for value in config["penalty_grid"]["lambda0"]]
    alphas = [float(value) for value in config["penalty_grid"]["alpha"]]
    if _penalty_raw_complete(PENALTY_RAW, lambdas, alphas, n_runs):
        print(f"Reusing completed penalty sensitivity raw results from {PENALTY_RAW}...")
        rows = pd.read_csv(PENALTY_RAW).to_dict("records")
        write_raw_and_summary(PENALTY_RAW, PENALTY_SUMMARY, rows, group_cols=["lambda0", "alpha"])
        _write_markdown_table(PENALTY_SUMMARY, "paper_tables/dynamic_penalty_sensitivity_summary.md")
        return

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
    config = load_config("configs/sensitivity.yaml")
    run_weight_sensitivity(config)
    run_penalty_sensitivity(config)
    generate_sensitivity_figures(WEIGHT_RAW, PENALTY_RAW, "results/sensitivity/figures")


if __name__ == "__main__":
    main()
