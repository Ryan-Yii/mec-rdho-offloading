from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from experiments.analyze_results import plot_penalty_sensitivity, plot_weight_ranks
from experiments.checkpointing import CheckpointStore
from experiments.experiment_core import (
    build_system_from_config,
    copy_artifact,
    capture_git_state,
    ensure_fresh_run,
    ensure_legacy_snapshot,
    file_sha256,
    load_config,
    run_algorithm_suite,
    run_optimizer,
    weights_from_config,
    write_raw_and_summary,
    write_run_manifest,
)
from experiments.statistical_analysis import PRIMARY_ALGORITHMS, average_ranks, friedman_tests, pairwise_tests
from src.utils.seed import derive_algorithm_seed, derive_scenario_seed


WEIGHT_RAW = "results/sensitivity/raw/weight_sensitivity_raw_results.csv"
WEIGHT_SUMMARY = "results/sensitivity/summary/weight_sensitivity_summary_mean_std.csv"
WEIGHT_RANKS = "results/sensitivity/statistics/weight_sensitivity_ranks.csv"
WEIGHT_FRIEDMAN = "results/sensitivity/statistics/weight_sensitivity_friedman.csv"
WEIGHT_PAIRWISE = "results/sensitivity/statistics/weight_sensitivity_pairwise_equal_budget.csv"
WEIGHT_CONTRACT = "results/sensitivity/checkpoints/weight_sensitivity_contract.json"
WEIGHT_FIGURE = "results/sensitivity/figures/weight_sensitivity_algorithm_ranks.png"
PENALTY_RAW = "results/sensitivity/raw/dynamic_penalty_sensitivity_raw_results.csv"
PENALTY_SUMMARY = "results/sensitivity/summary/dynamic_penalty_sensitivity_summary_mean_std.csv"
WEIGHT_ALGORITHMS = PRIMARY_ALGORITHMS


def build_weight_run_plan(config: dict) -> list[dict[str, object]]:
    experiment = config["experiment"]
    n_runs = int(experiment["independent_runs"])
    master_seed = int(experiment.get("master_seed", experiment["seed_start"]))
    plan = []
    for setting in config["weight_settings"]:
        weights = {key: float(value) for key, value in setting["weights"].items()}
        if not _weights_sum_to_one(weights):
            raise ValueError(f"{setting['setting']} weights must sum to 1.0: {weights}")
        for scenario_id in range(1, n_runs + 1):
            replicate_id = 1
            scenario_seed = derive_scenario_seed(master_seed, scenario_id, replicate_id)
            for algorithm in WEIGHT_ALGORITHMS:
                plan.append(
                    {
                        "setting": setting["setting"],
                        "description": setting["description"],
                        "weights": weights,
                        "scenario_id": scenario_id,
                        "replicate_id": replicate_id,
                        "scenario_seed": scenario_seed,
                        "algorithm": algorithm,
                        "algorithm_seed": derive_algorithm_seed(
                            master_seed,
                            algorithm,
                            scenario_id,
                            replicate_id,
                        ),
                    }
                )
    return plan


def _weights_sum_to_one(weights: dict[str, float]) -> bool:
    return abs(sum(float(value) for value in weights.values()) - 1.0) < 1.0e-9


def _format_weights(weights: dict[str, float]) -> str:
    return (
        f"({weights['energy']:.3f}, {weights['delay']:.3f}, {weights['aoi']:.3f}, "
        f"{weights['qoe']:.3f}, {weights['fairness']:.3f})"
    )


def _write_markdown_table(csv_path: str, markdown_path: str) -> None:
    Path(markdown_path).parent.mkdir(parents=True, exist_ok=True)
    pd.read_csv(csv_path).to_markdown(markdown_path, index=False)


def _weight_contract(config: dict, git_state: dict[str, object]) -> dict[str, object]:
    experiment = config["experiment"]
    return {
        "schema_version": 1,
        "experiment": "cross_algorithm_weight_sensitivity",
        "config_path": "configs/sensitivity.yaml",
        "config_hash": file_sha256("configs/sensitivity.yaml"),
        "git_commit": git_state["commit"],
        "algorithms": list(WEIGHT_ALGORITHMS),
        "settings": [setting["setting"] for setting in config["weight_settings"]],
        "independent_runs": int(experiment["independent_runs"]),
        "max_evaluations": int(experiment["max_evaluations"]),
        "reporting_objective": "F_report = F0 + 1.0 * (1 - CSR)",
        "paired_key": ["setting", "scenario_id", "replicate_id", "algorithm"],
        "seed_policy": {
            "scenario_seed": "derive_seed(master_seed, 'scenario', scenario_id, replicate_id)",
            "algorithm_seed": "derive_seed(master_seed, 'algorithm', algorithm_name, scenario_id, replicate_id)",
        },
    }


def _weight_output_paths() -> list[str]:
    return [
        WEIGHT_RAW,
        WEIGHT_SUMMARY,
        WEIGHT_RANKS,
        WEIGHT_FRIEDMAN,
        WEIGHT_PAIRWISE,
        WEIGHT_CONTRACT,
        WEIGHT_FIGURE,
        "paper_tables/weight_sensitivity_summary.md",
        "paper_tables/weight_sensitivity_ranks.md",
        "paper_tables/weight_sensitivity_friedman.md",
        "paper_tables/weight_sensitivity_pairwise_equal_budget.md",
        "figures/fig09_weight_sensitivity_algorithm_ranks.png",
    ]


def run_weight_sensitivity(
    config: dict,
    *,
    force: bool,
    resume: bool,
    git_state: dict[str, object],
) -> pd.DataFrame:
    if git_state.get("code_dirty") and not resume:
        raise RuntimeError("formal weight sensitivity requires committed configs and code")
    experiment = config["experiment"]
    plan = build_weight_run_plan(config)
    store = CheckpointStore(
        WEIGHT_RAW,
        WEIGHT_CONTRACT,
        contract=_weight_contract(config, git_state),
        key_columns=("setting", "scenario_id", "replicate_id", "algorithm"),
    )
    store.initialize(force=force, resume=resume)
    current_context = None
    system = None
    for index, item in enumerate(plan, start=1):
        if store.has_key(item):
            continue
        context = (item["setting"], item["scenario_id"], item["replicate_id"])
        if context != current_context:
            system = build_system_from_config(config, int(item["scenario_seed"]))
            current_context = context
        if system is None:
            raise RuntimeError("weight-sensitivity scenario was not initialized")
        algorithm = str(item["algorithm"])
        weights = dict(item["weights"])
        row, _ = run_optimizer(
            system=system,
            algorithm_name=algorithm,
            run_id=int(item["scenario_id"]),
            seed=int(experiment.get("master_seed", experiment["seed_start"])),
            max_iter=int(experiment["max_iterations"]),
            population_size=int(experiment["population_size"]),
            weights=weights_from_config(weights),
            penalty_base=1.0,
            dynamic_penalty_alpha=2.0,
            max_evaluations=int(experiment["max_evaluations"]),
            local_refinement=bool(experiment.get("local_refinement", True)) if algorithm == "RDHO" else None,
            scenario_id=int(item["scenario_id"]),
            replicate_id=int(item["replicate_id"]),
            scenario_seed=int(item["scenario_seed"]),
            algorithm_seed=int(item["algorithm_seed"]),
        )
        row.update(
            {
                "experiment": "objective_weight",
                "setting": item["setting"],
                "description": item["description"],
                "weights": _format_weights(weights),
                "w_energy": weights["energy"],
                "w_delay": weights["delay"],
                "w_aoi": weights["aoi"],
                "w_qoe": weights["qoe"],
                "w_fairness": weights["fairness"],
            }
        )
        store.append(row)
        print(f"Weight sensitivity {index}/{len(plan)}: {item['setting']} scenario {item['scenario_id']} {algorithm}")

    frame = pd.DataFrame(store.rows)
    numeric_columns = [column for column in frame.columns if column not in {"algorithm", "experiment", "setting", "description", "weights"}]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column])
    setting_order = [setting["setting"] for setting in config["weight_settings"]]
    frame["setting"] = pd.Categorical(frame["setting"], categories=setting_order, ordered=True)
    frame["algorithm"] = pd.Categorical(frame["algorithm"], categories=list(WEIGHT_ALGORITHMS), ordered=True)
    frame = frame.sort_values(["setting", "scenario_id", "replicate_id", "algorithm"]).reset_index(drop=True)
    frame["setting"] = frame["setting"].astype(str)
    frame["algorithm"] = frame["algorithm"].astype(str)
    store.replace_rows(frame.to_dict("records"))

    group_cols = [
        "setting",
        "description",
        "weights",
        "w_energy",
        "w_delay",
        "w_aoi",
        "w_qoe",
        "w_fairness",
        "algorithm",
    ]
    summary = write_raw_and_summary(WEIGHT_RAW, WEIGHT_SUMMARY, frame.to_dict("records"), group_cols=group_cols)
    ranks = average_ranks(frame, WEIGHT_ALGORITHMS, group_cols=["setting"])
    omnibus = friedman_tests(frame, WEIGHT_ALGORITHMS, group_cols=["setting"])
    pairwise = pairwise_tests(
        frame,
        reference_algorithm="RDHO",
        comparison_algorithms=WEIGHT_ALGORITHMS[1:],
        group_cols=["setting"],
    )
    for table, path in (
        (ranks, WEIGHT_RANKS),
        (omnibus, WEIGHT_FRIEDMAN),
        (pairwise, WEIGHT_PAIRWISE),
    ):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(path, index=False)
    summary.to_markdown("paper_tables/weight_sensitivity_summary.md", index=False)
    ranks.to_markdown("paper_tables/weight_sensitivity_ranks.md", index=False)
    omnibus.to_markdown("paper_tables/weight_sensitivity_friedman.md", index=False)
    pairwise.to_markdown("paper_tables/weight_sensitivity_pairwise_equal_budget.md", index=False)
    plot_weight_ranks(ranks, WEIGHT_FIGURE)
    copy_artifact(WEIGHT_FIGURE, "figures/fig09_weight_sensitivity_algorithm_ranks.png")
    return frame


def run_penalty_sensitivity(config: dict) -> None:
    n_runs = int(config["experiment"]["independent_runs"])
    all_rows = []
    for lambda0 in config["penalty_grid"]["lambda0"]:
        for alpha in config["penalty_grid"]["alpha"]:
            print(f"Running penalty sensitivity lambda0={float(lambda0):.1f}, alpha={float(alpha):.1f} with {n_runs} runs...")
            run_config = deepcopy(config)
            run_config["weights"] = deepcopy(config["weights"])
            run_config["penalty"] = {"lambda0": float(lambda0), "alpha": float(alpha)}
            rows, _ = run_algorithm_suite(run_config, ["RDHO"], n_runs=n_runs)
            for row in rows:
                row["experiment"] = "dynamic_penalty"
                row["lambda0"] = float(lambda0)
                row["alpha"] = float(alpha)
            all_rows.extend(rows)

    write_raw_and_summary(
        PENALTY_RAW,
        PENALTY_SUMMARY,
        all_rows,
        group_cols=["lambda0", "alpha"],
    )
    _write_markdown_table(PENALTY_SUMMARY, "paper_tables/dynamic_penalty_sensitivity_summary.md")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run formal sensitivity experiments")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--force", action="store_true")
    mode.add_argument("--resume", action="store_true")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--weight-only", action="store_true")
    selection.add_argument("--penalty-only", action="store_true")
    args = parser.parse_args()
    if args.resume and not args.weight_only:
        parser.error("--resume is supported only with --weight-only")
    return args


def main() -> None:
    args = _parse_args()
    git_state = capture_git_state()
    ensure_legacy_snapshot()
    started_at = datetime.now(timezone.utc).isoformat()
    config = load_config("configs/sensitivity.yaml")
    experiment = config["experiment"]
    run_weight = not args.penalty_only
    run_penalty = not args.weight_only
    if run_weight:
        if not args.force and not args.resume:
            ensure_fresh_run(_weight_output_paths(), force=False)
        run_weight_sensitivity(config, force=args.force, resume=args.resume, git_state=git_state)
        write_run_manifest(
            "results/manifests/weight_sensitivity_manifest.json",
            config_path="configs/sensitivity.yaml",
            output_paths=_weight_output_paths(),
            command=[sys.executable, "-m", "experiments.run_sensitivity", *sys.argv[1:]],
            master_seed=int(experiment.get("master_seed", experiment["seed_start"])),
            max_evaluations=int(experiment["max_evaluations"]),
            git_state=git_state,
            started_at=started_at,
            ended_at=datetime.now(timezone.utc).isoformat(),
        )
    if run_penalty:
        penalty_outputs = [
            PENALTY_RAW,
            PENALTY_SUMMARY,
            "paper_tables/dynamic_penalty_sensitivity_summary.md",
            "results/sensitivity/figures/penalty_sensitivity_heatmaps.png",
            "figures/fig10_penalty_sensitivity_heatmaps.png",
        ]
        ensure_fresh_run(penalty_outputs, force=args.force)
        run_penalty_sensitivity(config)
        plot_penalty_sensitivity(PENALTY_RAW, "results/sensitivity/figures")
        copy_artifact(
            "results/sensitivity/figures/penalty_sensitivity_heatmaps.png",
            "figures/fig10_penalty_sensitivity_heatmaps.png",
        )


if __name__ == "__main__":
    main()
