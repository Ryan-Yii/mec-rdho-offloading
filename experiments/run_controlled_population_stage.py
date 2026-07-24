from __future__ import annotations

import argparse
from pathlib import Path

from experiments.controlled_evidence import METHODS, initial_population_for_seed, run_controlled_method
from experiments.controlled_evidence_reporting import (
    paired_statistics,
    plot_experiment,
    repository_commit,
    write_experiment_outputs,
)
from experiments.experiment_core import load_config
from src.utils.io import write_rows


def run(*, seeds: list[int], output_root: Path, config_path: str = "configs/controlled_rdho_evidence_v2.yaml") -> tuple[list[dict], list[dict]]:
    config = load_config(config_path)
    code_commit = repository_commit()
    rows: list[dict] = []
    population_audit: list[dict] = []
    nfe_audit: list[dict] = []
    for run_id, scenario_seed in enumerate(seeds, start=1):
        initial_population = initial_population_for_seed(config, scenario_seed)
        expected_hash = None
        for method in METHODS:
            result = run_controlled_method(
                config,
                experiment="controlled_population_stage",
                scenario_seed=scenario_seed,
                run_id=run_id,
                method=method,
                initial_population=initial_population,
                total_nfe=int(config["controlled_population_stage"]["total_nfe"]),
                use_common_refinement=False,
                code_commit=code_commit,
            )
            if expected_hash is None:
                expected_hash = result.population_audit["population_hash"]
            if result.population_audit["population_hash"] != expected_hash:
                raise AssertionError("population hash differs across a paired scenario")
            rows.append(result.row)
            population_audit.append(result.population_audit)
            nfe_audit.append(result.nfe_audit)
        print(f"controlled_population_stage completed scenario {scenario_seed}", flush=True)
    output_root.mkdir(parents=True, exist_ok=True)
    write_rows(output_root / "audit" / "controlled_initial_population_audit.csv", population_audit)
    write_rows(output_root / "audit" / "controlled_population_stage_nfe_audit.csv", nfe_audit)
    statistics = paired_statistics(rows, experiment="controlled_population_stage")
    write_experiment_outputs(
        rows=rows,
        statistics=statistics,
        output_root=output_root,
        raw_name="controlled_population_stage_30_raw_results.csv",
        summary_name="controlled_population_stage_30_summary.csv",
        statistic_name="controlled_population_stage_wilcoxon.csv",
        table_name="controlled_population_stage_results.csv",
    )
    plot_experiment(
        rows,
        statistics,
        title="Controlled population-stage comparison",
        stem="controlled_population_stage_reporting_fitness",
        output_root=output_root,
    )
    return rows, statistics


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RDHO/RIME/DBO controlled population-stage evidence.")
    parser.add_argument("--smoke", action="store_true", help="Run only the first two paired V2 scenario seeds.")
    parser.add_argument("--output-root", default=".", help="Directory receiving additive evidence files.")
    args = parser.parse_args()
    all_seeds = list(range(20260701, 20260731))
    run(seeds=all_seeds[:2] if args.smoke else all_seeds, output_root=Path(args.output_root))


if __name__ == "__main__":
    main()
