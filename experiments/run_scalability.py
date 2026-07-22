from __future__ import annotations

import pandas as pd

from experiments.analyze_results import plot_scalability
from experiments.experiment_core import load_config, run_algorithm_suite, write_raw_and_summary


def main() -> None:
    config = load_config("configs/scalability.yaml")
    task_numbers = config["experiment"]["task_numbers"]
    n_runs = int(config["experiment"]["independent_runs"])
    all_rows = []
    for task_number in task_numbers:
        rows, _ = run_algorithm_suite(config, ["RDHO"], n_runs=n_runs, task_number=int(task_number))
        compact_rows = [
            {
                "task_number": row["task_number"],
                "run_id": row["run_id"],
                "seed": row["seed"],
                "fitness": row["fitness"],
                "csr": row["csr"],
                "hard_feasible": row["hard_feasible"],
                "capacity_utilisation_mean": row["capacity_utilisation_mean"],
                "capacity_utilisation_max": row["capacity_utilisation_max"],
                "qoe": row["qoe"],
                "fairness": row["fairness"],
                "runtime": row["runtime"],
                "nfe": row["nfe"],
            }
            for row in rows
        ]
        all_rows.extend(compact_rows)
    write_raw_and_summary(
        "results/v2/raw/scalability_raw_results.csv",
        "results/v2/summary/scalability_summary_mean_std.csv",
        all_rows,
        group_cols=["task_number"],
    )

    plot_scalability(pd.read_csv("results/v2/raw/scalability_raw_results.csv"), "results/v2/figures/scalability.png")


if __name__ == "__main__":
    main()
