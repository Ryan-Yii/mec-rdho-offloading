from __future__ import annotations

import pandas as pd

from experiments.analyze_results import plot_ablation
from experiments.experiment_core import load_config, run_algorithm_suite, write_raw_and_summary


def main() -> None:
    config = load_config("configs/ablation.yaml")
    variants = config["experiment"]["variants"]
    n_runs = int(config["experiment"]["independent_runs"])
    rows, _ = run_algorithm_suite(config, variants, n_runs=n_runs)
    write_raw_and_summary("results/v2/raw/ablation_30_raw_results.csv", "results/v2/summary/ablation_30_summary_mean_std.csv", rows)
    plot_ablation(pd.read_csv("results/v2/raw/ablation_30_raw_results.csv"), "results/v2/figures/ablation_study.png")


if __name__ == "__main__":
    main()
