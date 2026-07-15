from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from experiments.analyze_results import generate_main_figures
from experiments.audit_results import audit_main_frame
from experiments.experiment_core import (
    copy_artifact,
    capture_git_state,
    ensure_fresh_run,
    ensure_legacy_snapshot,
    export_task_parameters,
    load_config,
    parse_force_flag,
    run_algorithm_suite,
    write_raw_and_summary,
    write_run_manifest,
)
from experiments.statistical_analysis import PRIMARY_ALGORITHMS, average_ranks, friedman_tests, pairwise_tests
from src.task_generator import task_generation_parameter_table
from src.utils.io import write_rows


def main() -> None:
    force = parse_force_flag()
    git_state = capture_git_state()
    ensure_legacy_snapshot()
    outputs = [
        "results/raw/main_30_raw_results.csv",
        "results/raw/main_30_convergence.csv",
        "results/summary/main_30_summary_mean_std.csv",
        "results/summary/wilcoxon_fitness_results.csv",
        "results/statistics/main_friedman_equal_budget.csv",
        "results/statistics/main_pairwise_equal_budget.csv",
        "results/statistics/main_greedy_supplementary.csv",
        "results/statistics/main_ranks_equal_budget.csv",
        "docs/main_result_audit.md",
        "results/raw/task_parameters.csv",
        "results/raw/task_generation_ranges.csv",
        "results/figures",
        "paper_tables/main_30_summary_mean_std.md",
        "paper_tables/wilcoxon_fitness_results.md",
        "paper_tables/main_friedman_equal_budget.md",
        "paper_tables/main_pairwise_equal_budget.md",
        "paper_tables/main_greedy_supplementary.md",
        "paper_tables/main_ranks_equal_budget.md",
        "paper_tables/task_parameters.md",
        "paper_tables/task_generation_ranges.md",
        "figures/fig01_convergence_curve.png",
        "figures/fig02_energy_comparison.png",
        "figures/fig03_delay_comparison.png",
        "figures/fig04_aoi_comparison.png",
        "figures/fig05_qoe_fairness_comparison.png",
        "figures/fig06_soft_csr_comparison.png",
        "figures/fig11_normalized_multi_metric_radar.png",
    ]
    ensure_fresh_run(outputs, force=force)
    started_at = datetime.now(timezone.utc).isoformat()
    config = load_config("configs/main_40tasks.yaml")
    algorithms = config["experiment"]["algorithms"]
    n_runs = int(config["experiment"]["independent_runs"])
    rows, convergence_rows = run_algorithm_suite(config, algorithms, n_runs=n_runs)
    summary = write_raw_and_summary("results/raw/main_30_raw_results.csv", "results/summary/main_30_summary_mean_std.csv", rows)
    write_rows("results/raw/main_30_convergence.csv", convergence_rows)
    frame = pd.DataFrame(rows)
    omnibus = friedman_tests(frame, PRIMARY_ALGORITHMS)
    wilcoxon = pairwise_tests(
        frame,
        reference_algorithm="RDHO",
        comparison_algorithms=PRIMARY_ALGORITHMS[1:],
    )
    greedy = pairwise_tests(
        frame,
        reference_algorithm="RDHO",
        comparison_algorithms=["Greedy-ED"],
        inference_tier="supplementary_effectiveness_vs_cost",
        equal_budget=False,
    )
    ranks = average_ranks(frame, PRIMARY_ALGORITHMS)
    tables = (
        (omnibus, "results/statistics/main_friedman_equal_budget.csv", "paper_tables/main_friedman_equal_budget.md"),
        (wilcoxon, "results/statistics/main_pairwise_equal_budget.csv", "paper_tables/main_pairwise_equal_budget.md"),
        (greedy, "results/statistics/main_greedy_supplementary.csv", "paper_tables/main_greedy_supplementary.md"),
        (ranks, "results/statistics/main_ranks_equal_budget.csv", "paper_tables/main_ranks_equal_budget.md"),
    )
    for table, csv_path, markdown_path in tables:
        Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(csv_path, index=False)
        table.to_markdown(markdown_path, index=False)
    wilcoxon.to_csv("results/summary/wilcoxon_fitness_results.csv", index=False)
    audit_main_frame(frame, output_path="docs/main_result_audit.md")
    export_task_parameters(config, "results/raw/task_parameters.csv")
    write_rows("results/raw/task_generation_ranges.csv", task_generation_parameter_table())
    generate_main_figures("results/raw/main_30_raw_results.csv", "results/raw/main_30_convergence.csv", "results/figures")
    summary.to_markdown("paper_tables/main_30_summary_mean_std.md", index=False)
    wilcoxon.to_markdown("paper_tables/wilcoxon_fitness_results.md", index=False)
    pd.read_csv("results/raw/task_parameters.csv").to_markdown("paper_tables/task_parameters.md", index=False)
    pd.read_csv("results/raw/task_generation_ranges.csv").to_markdown("paper_tables/task_generation_ranges.md", index=False)
    figure_map = {
        "convergence_curve.png": "fig01_convergence_curve.png",
        "energy_comparison.png": "fig02_energy_comparison.png",
        "delay_comparison.png": "fig03_delay_comparison.png",
        "aoi_comparison.png": "fig04_aoi_comparison.png",
        "qoe_fairness_comparison.png": "fig05_qoe_fairness_comparison.png",
        "csr_comparison.png": "fig06_soft_csr_comparison.png",
        "radar_chart.png": "fig11_normalized_multi_metric_radar.png",
    }
    for source_name, destination_name in figure_map.items():
        copy_artifact(f"results/figures/{source_name}", f"figures/{destination_name}")
    experiment = config["experiment"]
    write_run_manifest(
        "results/manifests/main_30_manifest.json",
        config_path="configs/main_40tasks.yaml",
        output_paths=outputs,
        command=[sys.executable, "-m", "experiments.run_main_30", *sys.argv[1:]],
        master_seed=int(experiment.get("master_seed", experiment["seed_start"])),
        max_evaluations=int(experiment["max_evaluations"]),
        git_state=git_state,
        started_at=started_at,
        ended_at=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    main()
