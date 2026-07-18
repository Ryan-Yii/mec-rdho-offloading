from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

from experiments.analyze_results import plot_ablation
from experiments.experiment_core import load_config, run_algorithm_suite, write_raw_and_summary


def reuse_main_rdho_rows(rows: List[Dict], main_raw_path: str | Path) -> List[Dict]:
    """Replace the ablation RDHO-full reference with the paired main-run RDHO rows.

    The ablation table uses RDHO-full as its reference configuration. Reusing the
    already reported main-run solutions prevents a second random execution from
    producing a numerically different reference row. Other variants are left
    unchanged.
    """
    path = Path(main_raw_path)
    if not path.exists():
        return rows

    main = pd.read_csv(path)
    main = main[main["algorithm"] == "RDHO"]
    lookup = {(int(row.run_id), int(row.seed)): row._asdict() for row in main.itertuples(index=False)}

    aligned: List[Dict] = []
    for source in rows:
        row = dict(source)
        if row.get("algorithm") == "RDHO-full":
            key = (int(row["run_id"]), int(row["seed"]))
            replacement = lookup.get(key)
            if replacement is not None:
                label = row["algorithm"]
                row.update(replacement)
                row["algorithm"] = label
        aligned.append(row)
    return aligned


def main() -> None:
    config = load_config("configs/ablation.yaml")
    variants = config["experiment"]["variants"]
    n_runs = int(config["experiment"]["independent_runs"])
    rows, _ = run_algorithm_suite(config, variants, n_runs=n_runs)
    rows = reuse_main_rdho_rows(rows, "results/raw/main_30_raw_results.csv")
    write_raw_and_summary("results/raw/ablation_30_raw_results.csv", "results/summary/ablation_30_summary_mean_std.csv", rows)
    pd.read_csv("results/summary/ablation_30_summary_mean_std.csv").to_markdown("paper_tables/ablation_30_summary_mean_std.md", index=False)
    plot_ablation(pd.read_csv("results/raw/ablation_30_raw_results.csv"), "results/figures/ablation_study_multicolor.png")


if __name__ == "__main__":
    main()
