from __future__ import annotations

import sys
from datetime import datetime, timezone

import pandas as pd

from experiments.analyze_results import plot_scalability
from experiments.experiment_core import (
    copy_artifact,
    ensure_fresh_run,
    load_config,
    parse_force_flag,
    run_algorithm_suite,
    write_raw_and_summary,
    write_run_manifest,
)


def main() -> None:
    force = parse_force_flag()
    outputs = [
        "results/raw/scalability_raw_results.csv",
        "results/summary/scalability_summary_mean_std.csv",
        "results/figures/scalability.png",
        "paper_tables/scalability_summary.md",
        "figures/fig08_scalability.png",
    ]
    ensure_fresh_run(outputs, force=force)
    started_at = datetime.now(timezone.utc).isoformat()
    config = load_config("configs/scalability.yaml")
    task_numbers = config["experiment"]["task_numbers"]
    n_runs = int(config["experiment"]["independent_runs"])
    all_rows = []
    for task_number in task_numbers:
        rows, _ = run_algorithm_suite(config, ["RDHO"], n_runs=n_runs, task_number=int(task_number))
        all_rows.extend(rows)
    write_raw_and_summary(
        "results/raw/scalability_raw_results.csv",
        "results/summary/scalability_summary_mean_std.csv",
        all_rows,
        group_cols=["task_number"],
    )

    df = pd.read_csv("results/summary/scalability_summary_mean_std.csv")
    df.to_markdown("paper_tables/scalability_summary.md", index=False)
    plot_scalability(pd.DataFrame(all_rows), "results/figures/scalability.png")
    copy_artifact("results/figures/scalability.png", "figures/fig08_scalability.png")
    experiment = config["experiment"]
    write_run_manifest(
        "results/manifests/scalability_manifest.json",
        config_path="configs/scalability.yaml",
        output_paths=outputs,
        command=[sys.executable, "-m", "experiments.run_scalability", *sys.argv[1:]],
        master_seed=int(experiment.get("master_seed", experiment["seed_start"])),
        max_evaluations=int(experiment["max_evaluations"]),
        started_at=started_at,
        ended_at=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    main()
