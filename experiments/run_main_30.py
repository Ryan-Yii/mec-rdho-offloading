from __future__ import annotations

from experiments.analyze_results import generate_main_figures
from experiments.experiment_core import (
    export_task_parameters,
    load_config,
    run_algorithm_suite,
    write_raw_and_summary,
    write_wilcoxon_results,
)
from src.task_generator import task_generation_parameter_table
from src.utils.io import write_rows


def main() -> None:
    config = load_config("configs/main_40tasks.yaml")
    algorithms = config["experiment"]["algorithms"]
    n_runs = int(config["experiment"]["independent_runs"])
    rows, convergence_rows = run_algorithm_suite(config, algorithms, n_runs=n_runs)
    write_raw_and_summary("results/v2/raw/main_30_raw_results.csv", "results/v2/summary/main_30_summary_mean_std.csv", rows)
    write_rows("results/v2/raw/main_30_convergence.csv", convergence_rows)
    write_wilcoxon_results(rows, "results/v2/statistics/wilcoxon_fitness_results.csv")
    export_task_parameters(config, "results/v2/raw/task_parameters.csv")
    write_rows("results/v2/raw/task_generation_ranges.csv", task_generation_parameter_table())
    generate_main_figures("results/v2/raw/main_30_raw_results.csv", "results/v2/raw/main_30_convergence.csv", "results/v2/figures")


if __name__ == "__main__":
    main()
