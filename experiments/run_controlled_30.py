from __future__ import annotations

from experiments.analyze_results import generate_main_figures
from experiments.experiment_core import load_config, run_algorithm_suite, write_raw_and_summary, write_wilcoxon_results
from src.utils.io import write_rows


def main() -> None:
    config = load_config("configs/controlled.yaml")
    n_runs = int(config["experiment"]["independent_runs"])

    equal_names = config["equal_nfe"]["algorithms"]
    equal_rows, equal_history = run_algorithm_suite(
        config,
        equal_names,
        n_runs=n_runs,
        algorithm_iterations=config["equal_nfe"]["algorithm_iterations"],
    )
    write_raw_and_summary("results/v2/raw/equal_nfe_30_raw_results.csv", "results/v2/summary/equal_nfe_30_summary_mean_std.csv", equal_rows)
    write_rows("results/v2/raw/equal_nfe_30_convergence.csv", equal_history)
    write_wilcoxon_results(equal_rows, "results/v2/statistics/equal_nfe_wilcoxon.csv", reference="RDHO-core")

    controlled_names = config["common_controls"]["algorithms"]
    controlled_rows, controlled_history = run_algorithm_suite(config, controlled_names, n_runs=n_runs)
    write_raw_and_summary("results/v2/raw/common_control_30_raw_results.csv", "results/v2/summary/common_control_30_summary_mean_std.csv", controlled_rows)
    write_rows("results/v2/raw/common_control_30_convergence.csv", controlled_history)
    write_wilcoxon_results(
        controlled_rows,
        "results/v2/statistics/common_control_wilcoxon.csv",
        reference="RDHO-full",
        preferred=["RIME-common-init", "DBO-common-init", "RIME-common-init-refine", "DBO-common-init-refine", "RDHO-core"],
    )
    generate_main_figures(
        "results/v2/raw/common_control_30_raw_results.csv",
        "results/v2/raw/common_control_30_convergence.csv",
        "results/v2/figures/controlled",
    )


if __name__ == "__main__":
    main()
