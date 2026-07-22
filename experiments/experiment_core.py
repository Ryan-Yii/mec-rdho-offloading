from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import rankdata, wilcoxon

from src.algorithms import CWTSSA, DBO, RDHO, RIME, TLBOHHO, GreedyEnergyDelay
from src.metrics import FitnessWeights, evaluate_solution
from src.system_model import SystemModel
from src.task_generator import generate_system, task_parameter_rows
from src.utils.io import ensure_parent, load_yaml, write_rows
from src.utils.seed import derive_seed


RAW_COLUMNS = [
    "run_id",
    "seed",
    "algorithm",
    "fitness",
    "base_objective",
    "penalty",
    "search_fitness",
    "energy",
    "delay",
    "aoi",
    "qoe",
    "fairness",
    "csr",
    "hard_feasible",
    "capacity_utilisation_mean",
    "capacity_utilisation_max",
    "assignment_unique",
    "runtime",
    "nfe",
    "pre_refinement_fitness",
    "local_refinement_gain",
]

ALGORITHM_CLASSES = {
    "RDHO": RDHO,
    "RIME": RIME,
    "DBO": DBO,
    "TLBO-HHO": TLBOHHO,
    "CWTSSA": CWTSSA,
    "Greedy-ED": GreedyEnergyDelay,
}

RDHO_VARIANTS = {
    "RDHO-full": {"local_refinement": True},
    "RDHO-core": {"local_refinement": False},
    "RDHO-w/o dual-source initialization": {"dual_source_initialization": False, "local_refinement": True},
    "RDHO-w/o adaptive role allocation": {"adaptive_roles": False, "local_refinement": True},
    "RDHO-w/o elite preservation": {"elite_preservation": False, "local_refinement": True},
    "RDHO-w/o dynamic penalty": {"dynamic_penalty": False, "local_refinement": True},
}


def weights_from_config(config: dict | None) -> FitnessWeights:
    config = config or {}
    return FitnessWeights(
        energy=float(config.get("energy", 0.15)),
        delay=float(config.get("delay", 0.15)),
        aoi=float(config.get("aoi", 0.20)),
        qoe=float(config.get("qoe", 0.25)),
        fairness=float(config.get("fairness", 0.25)),
    )


def build_system_from_config(config: dict, seed: int, task_number: int | None = None) -> SystemModel:
    system = config["system"]
    return generate_system(
        seed=seed,
        num_devices=int(system["mobile_devices"]),
        num_edge_servers=int(system["edge_servers"]),
        num_cloud_servers=int(system["cloud_servers"]),
        num_tasks=int(task_number or system["tasks"]),
    )


def make_optimizer(
    algorithm_name: str,
    system: SystemModel,
    seed: int,
    max_iter: int,
    population_size: int,
    weights: FitnessWeights | None = None,
    penalty_base: float = 1.0,
    dynamic_penalty_alpha: float = 2.0,
):
    label = algorithm_name
    kwargs = {}
    if algorithm_name in RDHO_VARIANTS:
        label = "RDHO"
        kwargs.update(RDHO_VARIANTS[algorithm_name])
    if label == "RDHO":
        kwargs["dynamic_penalty_alpha"] = dynamic_penalty_alpha

    cls = ALGORITHM_CLASSES[label]
    return cls(
        system=system,
        max_iter=max_iter,
        population_size=population_size,
        seed=derive_seed(seed, "RDHO" if label == "RDHO" else algorithm_name),
        weights=weights,
        penalty_base=penalty_base,
        **kwargs,
    )


def run_optimizer(
    system: SystemModel,
    algorithm_name: str,
    run_id: int,
    seed: int,
    max_iter: int,
    population_size: int,
    weights: FitnessWeights | None = None,
    penalty_base: float = 1.0,
    dynamic_penalty_alpha: float = 2.0,
) -> Tuple[Dict[str, float | int | str], List[float]]:
    optimizer = make_optimizer(
        algorithm_name=algorithm_name,
        system=system,
        seed=seed,
        max_iter=max_iter,
        population_size=population_size,
        weights=weights,
        penalty_base=penalty_base,
        dynamic_penalty_alpha=dynamic_penalty_alpha,
    )
    start = time.perf_counter()
    result = optimizer.optimize()
    runtime = time.perf_counter() - start
    metrics = evaluate_solution(system, result.solution, weights=weights, penalty_scale=1.0)
    row = {
        "run_id": run_id,
        "seed": seed,
        "algorithm": algorithm_name,
        "fitness": metrics.reporting_fitness,
        "base_objective": metrics.base_objective,
        "penalty": 1.0 - metrics.csr,
        "search_fitness": result.search_fitness,
        "energy": metrics.energy,
        "delay": metrics.delay,
        "aoi": metrics.aoi,
        "qoe": metrics.qoe,
        "fairness": metrics.fairness,
        "csr": metrics.csr,
        "hard_feasible": int(metrics.hard_feasible),
        "capacity_utilisation_mean": metrics.capacity_utilisation_mean,
        "capacity_utilisation_max": metrics.capacity_utilisation_max,
        "assignment_unique": int(metrics.assignment_unique),
        "runtime": runtime,
        "nfe": result.nfe,
        "pre_refinement_fitness": result.pre_refinement_fitness,
        "local_refinement_gain": result.local_refinement_gain,
    }
    return row, result.history


def run_single_algorithm(
    system: SystemModel,
    algorithm_name: str,
    run_id: int,
    seed: int,
    max_iter: int,
    population_size: int,
) -> Dict[str, float | int | str]:
    row, _ = run_optimizer(system, algorithm_name, run_id, seed, max_iter, population_size)
    return row


def run_algorithm_suite(
    config: dict,
    algorithms: Iterable[str],
    n_runs: int,
    seeds: Iterable[int] | None = None,
    task_number: int | None = None,
) -> Tuple[List[Dict], List[Dict]]:
    experiment = config["experiment"]
    weights = weights_from_config(config.get("weights"))
    penalty = config.get("penalty", {})
    penalty_base = float(penalty.get("lambda0", penalty.get("base", 1.0)))
    dynamic_penalty_alpha = float(penalty.get("alpha", 2.0))
    max_iter = int(experiment["max_iterations"])
    population_size = int(experiment["population_size"])
    seeds = list(seeds or [int(experiment["seed_start"]) + idx for idx in range(n_runs)])

    rows: List[Dict] = []
    convergence_rows: List[Dict] = []

    for run_id, seed in enumerate(seeds, start=1):
        system = build_system_from_config(config, seed, task_number=task_number)
        for algorithm_name in algorithms:
            row, history = run_optimizer(
                system=system,
                algorithm_name=algorithm_name,
                run_id=run_id,
                seed=seed,
                max_iter=max_iter,
                population_size=population_size,
                weights=weights,
                penalty_base=penalty_base,
                dynamic_penalty_alpha=dynamic_penalty_alpha,
            )
            if task_number is not None:
                row["task_number"] = task_number
            rows.append(row)
            for iteration, fitness in enumerate(history):
                convergence_row = {
                    "run_id": run_id,
                    "seed": seed,
                    "algorithm": algorithm_name,
                    "iteration": iteration,
                    "fitness": fitness,
                }
                if task_number is not None:
                    convergence_row["task_number"] = task_number
                convergence_rows.append(convergence_row)

    return rows, convergence_rows


def summarize_mean_std(raw_rows: List[Dict], group_cols: List[str] | None = None) -> pd.DataFrame:
    group_cols = group_cols or ["algorithm"]
    df = pd.DataFrame(raw_rows)
    numeric_cols = [
        col
        for col in ["fitness", "base_objective", "penalty", "search_fitness", "energy", "delay", "aoi", "qoe", "fairness", "csr", "hard_feasible", "capacity_utilisation_mean", "capacity_utilisation_max", "assignment_unique", "runtime", "nfe", "pre_refinement_fitness", "local_refinement_gain"]
        if col in df.columns
    ]
    records = []
    for keys, group in df.groupby(group_cols, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        record = dict(zip(group_cols, keys))
        for col in numeric_cols:
            record[f"{col}_mean"] = float(group[col].mean())
            record[f"{col}_std"] = float(group[col].std(ddof=1)) if len(group) > 1 else 0.0
            record[col] = f"{record[f'{col}_mean']:.6f} +/- {record[f'{col}_std']:.6f}"
        records.append(record)
    return pd.DataFrame(records)


def write_raw_and_summary(raw_path: str | Path, summary_path: str | Path, rows: List[Dict], group_cols: List[str] | None = None) -> pd.DataFrame:
    ordered_rows = []
    for row in rows:
        first_cols = [col for col in ["task_number", *RAW_COLUMNS] if col in row]
        remaining = [col for col in row.keys() if col not in first_cols]
        ordered_rows.append({col: row[col] for col in [*first_cols, *remaining]})
    write_rows(raw_path, ordered_rows)
    summary = summarize_mean_std(rows, group_cols=group_cols)
    ensure_parent(summary_path)
    summary.to_csv(summary_path, index=False)
    return summary


def write_wilcoxon_results(raw_rows: List[Dict], output_path: str | Path) -> pd.DataFrame:
    """Write paired two-sided Wilcoxon tests with Holm correction and effects."""

    df = pd.DataFrame(raw_rows)
    pivot = df.pivot_table(index="run_id", columns="algorithm", values="fitness", aggfunc="first")
    if "RDHO" not in pivot:
        result = pd.DataFrame()
        result.to_csv(output_path, index=False)
        return result

    preferred = ["RIME", "DBO", "TLBO-HHO", "CWTSSA", "Greedy-ED"]
    baselines = [name for name in preferred if name in pivot]
    records = []
    for baseline in baselines:
        rdho = pivot["RDHO"].to_numpy(dtype=float)
        other = pivot[baseline].to_numpy(dtype=float)
        statistic = wilcoxon(rdho, other, alternative="two-sided", zero_method="wilcox")
        delta = rdho - other
        nonzero = delta[np.abs(delta) > 1.0e-12]
        if nonzero.size:
            ranks = rankdata(np.abs(nonzero))
            positive = float(np.sum(ranks[nonzero > 0]))
            negative = float(np.sum(ranks[nonzero < 0]))
            rank_biserial = (positive - negative) / (positive + negative)
        else:
            rank_biserial = 0.0
        records.append(
            {
                "comparison": f"RDHO vs {baseline}",
                "w_statistic": float(statistic.statistic),
                "p_value": float(statistic.pvalue),
                "median_difference": float(np.median(rdho - other)),
                "rank_biserial": float(rank_biserial),
                "wins": int(np.sum(rdho < other - 1.0e-12)),
                "ties": int(np.sum(np.abs(rdho - other) <= 1.0e-12)),
                "losses": int(np.sum(rdho > other + 1.0e-12)),
            }
        )

    # Holm step-down adjustment.
    order = sorted(range(len(records)), key=lambda idx: records[idx]["p_value"])
    adjusted = [0.0] * len(records)
    running = 0.0
    m = len(records)
    for rank, idx in enumerate(order):
        value = min(1.0, (m - rank) * records[idx]["p_value"])
        running = max(running, value)
        adjusted[idx] = running
    for idx, record in enumerate(records):
        record["p_holm"] = float(adjusted[idx])
        record["significant"] = "Yes" if adjusted[idx] < 0.05 else "No"

    result = pd.DataFrame(records)
    ensure_parent(output_path)
    result.to_csv(output_path, index=False)
    return result


def export_task_parameters(config: dict, output_path: str | Path) -> None:
    seed = int(config["experiment"]["seed_start"])
    system = build_system_from_config(config, seed)
    write_rows(output_path, task_parameter_rows(system.tasks))


def load_config(path: str | Path) -> dict:
    return load_yaml(path)
