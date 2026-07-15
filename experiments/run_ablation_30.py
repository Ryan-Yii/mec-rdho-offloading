from __future__ import annotations

import sys
from datetime import datetime, timezone

import pandas as pd

from experiments.analyze_results import plot_ablation
from experiments.experiment_core import (
    copy_artifact,
    capture_git_state,
    ensure_fresh_run,
    ensure_legacy_snapshot,
    load_config,
    parse_force_flag,
    run_algorithm_suite,
    write_raw_and_summary,
    write_run_manifest,
    write_wilcoxon_results,
)


def main() -> None:
    force = parse_force_flag()
    git_state = capture_git_state()
    ensure_legacy_snapshot()
    outputs = [
        "results/raw/ablation_30_raw_results.csv",
        "results/summary/ablation_30_summary_mean_std.csv",
        "results/summary/ablation_wilcoxon_results.csv",
        "results/figures/ablation_study_multicolor.png",
        "paper_tables/ablation_30_summary_mean_std.md",
        "paper_tables/ablation_wilcoxon_results.md",
        "figures/fig07_ablation_study.png",
    ]
    ensure_fresh_run(outputs, force=force)
    started_at = datetime.now(timezone.utc).isoformat()
    config = load_config("configs/ablation.yaml")
    variants = config["experiment"]["variants"]
    n_runs = int(config["experiment"]["independent_runs"])
    rows, _ = run_algorithm_suite(config, variants, n_runs=n_runs)
    summary = write_raw_and_summary("results/raw/ablation_30_raw_results.csv", "results/summary/ablation_30_summary_mean_std.csv", rows)
    tests = write_wilcoxon_results(
        rows,
        "results/summary/ablation_wilcoxon_results.csv",
        reference_algorithm="RDHO-core",
    )
    plot_ablation(pd.DataFrame(rows), "results/figures/ablation_study_multicolor.png")
    summary.to_markdown("paper_tables/ablation_30_summary_mean_std.md", index=False)
    tests.to_markdown("paper_tables/ablation_wilcoxon_results.md", index=False)
    copy_artifact("results/figures/ablation_study_multicolor.png", "figures/fig07_ablation_study.png")
    experiment = config["experiment"]
    write_run_manifest(
        "results/manifests/ablation_30_manifest.json",
        config_path="configs/ablation.yaml",
        output_paths=outputs,
        command=[sys.executable, "-m", "experiments.run_ablation_30", *sys.argv[1:]],
        master_seed=int(experiment.get("master_seed", experiment["seed_start"])),
        max_evaluations=int(experiment["max_evaluations"]),
        git_state=git_state,
        started_at=started_at,
        ended_at=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    main()
