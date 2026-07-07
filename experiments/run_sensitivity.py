from __future__ import annotations

import pandas as pd

from experiments.experiment_core import load_config, run_algorithm_suite, write_raw_and_summary


def main() -> None:
    config = load_config("configs/sensitivity.yaml")
    base_weights = dict(config["weights"])
    all_rows = []
    for aoi_weight in config["experiment"]["aoi_weights"]:
        remaining = 1.0 - float(aoi_weight)
        config["weights"] = {
            **base_weights,
            "energy": remaining * 0.1875,
            "delay": remaining * 0.1875,
            "aoi": float(aoi_weight),
            "qoe": remaining * 0.3125,
            "fairness": remaining * 0.3125,
        }
        rows, _ = run_algorithm_suite(config, ["RDHO"], n_runs=int(config["experiment"]["independent_runs"]))
        for row in rows:
            row["aoi_weight"] = float(aoi_weight)
        all_rows.extend(rows)
    write_raw_and_summary(
        "results/raw/sensitivity_raw_results.csv",
        "results/summary/sensitivity_summary_mean_std.csv",
        all_rows,
        group_cols=["aoi_weight"],
    )
    pd.read_csv("results/summary/sensitivity_summary_mean_std.csv").to_markdown("paper_tables/sensitivity_summary.md", index=False)


if __name__ == "__main__":
    main()
