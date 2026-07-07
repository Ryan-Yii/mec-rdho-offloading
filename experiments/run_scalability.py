from __future__ import annotations

import pandas as pd

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
                "runtime": row["runtime"],
            }
            for row in rows
        ]
        all_rows.extend(compact_rows)
    write_raw_and_summary(
        "results/raw/scalability_raw_results.csv",
        "results/summary/scalability_summary_mean_std.csv",
        all_rows,
        group_cols=["task_number"],
    )

    df = pd.read_csv("results/summary/scalability_summary_mean_std.csv")
    df.to_markdown("paper_tables/scalability_summary.md", index=False)


if __name__ == "__main__":
    main()
