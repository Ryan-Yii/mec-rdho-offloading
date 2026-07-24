from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.controlled_evidence import initial_population_for_seed, run_controlled_method
from experiments.controlled_evidence_reporting import (
    environment_record,
    plot_combined_paired_differences,
    plot_experiment,
    paired_statistics,
    repository_commit,
    repository_v2_hashes,
    sha256_file,
    write_experiment_outputs,
    write_markdown_table,
)
from experiments.experiment_core import load_config
from src.utils.io import write_json, write_rows


def _assert_v2_unchanged(before: dict[str, str], after: dict[str, str]) -> None:
    if before != after:
        changed = sorted(set(before).symmetric_difference(after))
        changed.extend(path for path in before if path in after and before[path] != after[path])
        raise AssertionError(f"existing V2 results changed during controlled evidence run: {changed}")


def _artifact_manifest(*artifact_roots: Path) -> list[dict]:
    records: list[dict] = []
    excluded = {root / "audit" / "controlled_evidence_sha256.csv" for root in artifact_roots}
    excluded.update(root / "audit" / "controlled_evidence_v2_integrity.csv" for root in artifact_roots)
    for root in artifact_roots:
        for path in sorted(root.rglob("*")):
            if path.is_file() and "v2" not in path.parts and path not in excluded and (
                path.name.startswith("controlled_")
                or path.name == "manuscript_impact_report.md"
            ):
                records.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return records


def _checkpoint_path(checkpoint_root: Path, experiment: str, scenario_seed: int, method: str) -> Path:
    return checkpoint_root / experiment / str(scenario_seed) / f"{method}.json"


def run_atomic_checkpoint(
    *,
    checkpoint_root: Path,
    experiment: str,
    scenario_seed: int,
    method: str,
    run_id: int,
) -> Path:
    """Compute one bounded run and persist an immutable result checkpoint."""

    if experiment not in {"controlled_population_stage", "controlled_common_pipeline"}:
        raise ValueError(f"unknown controlled experiment: {experiment}")
    if method not in {"RDHO", "RIME", "DBO"}:
        raise ValueError(f"unknown controlled method: {method}")
    target = _checkpoint_path(checkpoint_root, experiment, scenario_seed, method)
    if target.exists():
        raise FileExistsError(f"refusing to overwrite existing checkpoint: {target}")
    config = load_config("configs/controlled_rdho_evidence_v2.yaml")
    setting = config[experiment]
    result = run_controlled_method(
        config,
        experiment=experiment,
        scenario_seed=scenario_seed,
        run_id=run_id,
        method=method,
        initial_population=initial_population_for_seed(config, scenario_seed),
        total_nfe=int(setting["total_nfe"]),
        use_common_refinement=bool(setting["common_refinement"]),
        code_commit=repository_commit(),
    )
    write_json(target, {"row": result.row, "population_audit": result.population_audit, "nfe_audit": result.nfe_audit})
    print(f"checkpoint completed: {experiment} seed={scenario_seed} method={method}", flush=True)
    return target


def _load_checkpoint_rows(checkpoint_root: Path, seeds: list[int]):
    grouped = {
        "controlled_population_stage": ([], [], []),
        "controlled_common_pipeline": ([], [], []),
    }
    for experiment, (rows, audits, nfe_audits) in grouped.items():
        for run_id, scenario_seed in enumerate(seeds, start=1):
            per_seed_hashes = []
            for method in ("RDHO", "RIME", "DBO"):
                path = _checkpoint_path(checkpoint_root, experiment, scenario_seed, method)
                if not path.exists():
                    raise FileNotFoundError(f"missing checkpoint required for assembly: {path}")
                payload = json.loads(path.read_text(encoding="utf-8"))
                row = payload["row"]
                if row["experiment"] != experiment or row["scenario_seed"] != scenario_seed or row["run_id"] != run_id:
                    raise AssertionError(f"checkpoint provenance mismatch: {path}")
                rows.append(row)
                audits.append(payload["population_audit"])
                nfe_audits.append(payload["nfe_audit"])
                per_seed_hashes.append(payload["population_audit"]["population_hash"])
            if len(set(per_seed_hashes)) != 1:
                raise AssertionError(f"common population hash mismatch in {experiment} seed {scenario_seed}")
    return (*grouped["controlled_population_stage"], *grouped["controlled_common_pipeline"])


def assemble_checkpoints(*, checkpoint_root: Path, output_root: Path, seeds: list[int]):
    """Assemble only a complete immutable checkpoint set into evidence files."""

    before_v2 = repository_v2_hashes()
    population_rows, population_audit, population_nfe, pipeline_rows, pipeline_audit, pipeline_nfe = _load_checkpoint_rows(checkpoint_root, seeds)
    population_statistics = paired_statistics(population_rows, experiment="controlled_population_stage")
    pipeline_statistics = paired_statistics(pipeline_rows, experiment="controlled_common_pipeline")
    write_rows(output_root / "audit" / "controlled_initial_population_audit.csv", [*population_audit, *pipeline_audit])
    write_rows(output_root / "audit" / "controlled_population_stage_nfe_audit.csv", population_nfe)
    write_rows(output_root / "audit" / "controlled_common_pipeline_nfe_audit.csv", pipeline_nfe)
    tables_root = Path("paper_tables") if output_root == Path("results") else output_root / "paper_tables"
    figures_root = Path("figures") / "analysis" if output_root == Path("results") else output_root / "figures" / "analysis"
    write_experiment_outputs(rows=population_rows, statistics=population_statistics, output_root=output_root, raw_name="controlled_population_stage_30_raw_results.csv", summary_name="controlled_population_stage_30_summary.csv", statistic_name="controlled_population_stage_wilcoxon.csv", table_name="controlled_population_stage_results.csv", table_root=tables_root)
    write_experiment_outputs(rows=pipeline_rows, statistics=pipeline_statistics, output_root=output_root, raw_name="controlled_common_pipeline_30_raw_results.csv", summary_name="controlled_common_pipeline_30_summary.csv", statistic_name="controlled_common_pipeline_wilcoxon.csv", table_name="controlled_common_pipeline_results.csv", table_root=tables_root)
    combined_statistics = [*population_statistics, *pipeline_statistics]
    write_rows(output_root / "statistics" / "controlled_evidence_effect_sizes.csv", combined_statistics)
    write_rows(tables_root / "controlled_evidence_statistics.csv", combined_statistics)
    write_markdown_table(tables_root / "controlled_evidence_statistics.md", combined_statistics, ["experiment", "comparison", "n_pairs", "median_paired_difference", "median_difference_ci95_low", "median_difference_ci95_high", "p_value_two_sided", "p_value_holm", "rank_biserial", "wins_rdho", "ties", "losses_rdho", "significant_holm_0_05"], "Controlled RDHO evidence paired statistics")
    plot_experiment(population_rows, population_statistics, title="Controlled population-stage comparison", stem="controlled_population_stage_reporting_fitness", output_root=output_root, figure_root=figures_root)
    plot_experiment(pipeline_rows, pipeline_statistics, title="Controlled common-pipeline comparison", stem="controlled_common_pipeline_reporting_fitness", output_root=output_root, figure_root=figures_root)
    plot_combined_paired_differences(population_rows, pipeline_rows, output_root, figure_root=figures_root)
    _assert_v2_unchanged(before_v2, repository_v2_hashes())
    v2_audit = [{"path": path, "sha256_before": digest, "sha256_after": repository_v2_hashes()[path], "unchanged": True} for path, digest in before_v2.items()]
    write_rows(output_root / "audit" / "controlled_evidence_v2_integrity.csv", v2_audit)
    write_json(output_root / "audit" / "controlled_evidence_environment.json", environment_record())
    write_rows(
        output_root / "audit" / "controlled_evidence_sha256.csv",
        _artifact_manifest(output_root, tables_root, figures_root, Path("docs")),
    )
    return population_rows, population_statistics, pipeline_rows, pipeline_statistics


def main() -> None:
    parser = argparse.ArgumentParser(description="Run both strictly controlled RDHO evidence experiments.")
    parser.add_argument("--smoke", action="store_true", help="Run only scenario seeds 20260701 and 20260702.")
    parser.add_argument("--output-root", default="results", help="Directory receiving raw, summary, statistics, and audit evidence.")
    parser.add_argument("--checkpoint-root", default="work/controlled_evidence_checkpoints", help="Immutable per-method checkpoint directory.")
    parser.add_argument("--checkpoint", action="store_true", help="Compute one bounded experiment/seed/method checkpoint.")
    parser.add_argument("--assemble", action="store_true", help="Assemble a complete checkpoint set into evidence files.")
    parser.add_argument("--experiment", choices=["controlled_population_stage", "controlled_common_pipeline"])
    parser.add_argument("--scenario-seed", type=int)
    parser.add_argument("--method", choices=["RDHO", "RIME", "DBO"])
    args = parser.parse_args()
    seeds = list(range(20260701, 20260731))
    selected_seeds = seeds[:2] if args.smoke else seeds
    if args.checkpoint:
        if args.experiment is None or args.scenario_seed is None or args.method is None:
            parser.error("--checkpoint requires --experiment, --scenario-seed, and --method")
        if args.scenario_seed not in selected_seeds:
            parser.error("--scenario-seed is not included by the selected seed range")
        run_atomic_checkpoint(
            checkpoint_root=Path(args.checkpoint_root),
            experiment=args.experiment,
            scenario_seed=args.scenario_seed,
            method=args.method,
            run_id=selected_seeds.index(args.scenario_seed) + 1,
        )
    elif args.assemble:
        assemble_checkpoints(checkpoint_root=Path(args.checkpoint_root), output_root=Path(args.output_root), seeds=selected_seeds)
    else:
        parser.error("choose --checkpoint for one run or --assemble after every checkpoint is complete")


if __name__ == "__main__":
    main()
