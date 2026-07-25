from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

import numpy as np

from experiments.experiment_core import (
    build_system_from_config,
    common_initial_population,
    utility_weights_from_config,
    weights_from_config,
)
from src.algorithms import DBO, RDHO, RIME
from src.experiments.evaluation_budget import EvaluationBudgetManager
from src.metrics import Metrics, decode_and_repair, fitness_from_components
from src.utils.seed import derive_seed


METHODS = {
    "RDHO": "RDHO-population-controlled",
    "RIME": "RIME-population-controlled",
    "DBO": "DBO-population-controlled",
}


@dataclass(frozen=True)
class ControlledRun:
    row: dict
    population_audit: dict
    nfe_audit: dict


def population_sha256(population: np.ndarray) -> str:
    """Hash the exact canonical float64 layout passed to each method."""

    canonical = np.ascontiguousarray(np.asarray(population, dtype="<f8"))
    return hashlib.sha256(canonical.tobytes()).hexdigest()


def _make_population_algorithm(
    method: str,
    system,
    *,
    population_size: int,
    rng_seed: int,
    max_iter: int,
    weights,
    utility_weights,
    penalty_base: float,
    dynamic_penalty_alpha: float,
):
    common = dict(
        system=system,
        max_iter=max_iter,
        population_size=population_size,
        seed=rng_seed,
        weights=weights,
        utility_weights=utility_weights,
        penalty_base=penalty_base,
    )
    if method == "RDHO":
        return RDHO(
            **common,
            dual_source_initialization=False,
            local_refinement=False,
            dynamic_penalty_alpha=dynamic_penalty_alpha,
        )
    if method == "RIME":
        return RIME(**common)
    if method == "DBO":
        return DBO(**common)
    raise ValueError(f"unsupported controlled method: {method}")


def _search_fitness(metrics: list[Metrics], penalty_scale: float) -> np.ndarray:
    return np.asarray(
        [fitness_from_components(item.base_objective, item.csr, penalty_scale) for item in metrics],
        dtype=float,
    )


def _refine(
    solution: np.ndarray,
    fitness: float,
    budget: EvaluationBudgetManager,
) -> tuple[np.ndarray, float]:
    """The existing deterministic common refinement, with explicit NFE accounting."""

    best_solution = np.array(solution, copy=True)
    best_fitness = float(fitness)
    for task_idx in range(len(budget.system.tasks)):
        for node in (0.08, 0.28, 0.48, 0.68, 0.88):
            for resource in (0.10, 0.30, 0.55, 0.80, 1.00):
                trial = np.array(best_solution, copy=True)
                trial[task_idx] = (node, resource)
                metrics = budget.evaluate(trial, stage="refinement", penalty_scale=1.0)
                if metrics.reporting_fitness < best_fitness:
                    best_solution = trial
                    best_fitness = float(metrics.reporting_fitness)
    return np.clip(best_solution, 0.0, 1.0), best_fitness


def _validate_result(system, solution: np.ndarray) -> None:
    decoded = decode_and_repair(system, solution)
    if not decoded.hard_feasible:
        raise AssertionError("controlled optimizer returned a hard-infeasible solution")
    if len(decoded.node_ids) != len(system.tasks):
        raise AssertionError("controlled optimizer did not assign every task once")
    for task, node, frequency in zip(system.tasks, decoded.node_ids, decoded.frequencies_hz):
        if int(node) not in system.legal_nodes_for_task(task):
            raise AssertionError("controlled optimizer returned an illegal node")
        if not system.node_min_cpu_hz[node] - 1.0e-6 <= frequency <= system.node_capacity_hz[node] + 1.0e-6:
            raise AssertionError("controlled optimizer returned an out-of-bounds CPU allocation")
    usage = np.bincount(decoded.node_ids, weights=decoded.frequencies_hz, minlength=system.num_nodes)
    if not np.all(usage <= system.node_capacity_hz + np.maximum(1.0e-6, system.node_capacity_hz * 1.0e-12)):
        raise AssertionError("controlled optimizer exceeded aggregate node capacity")


def run_controlled_method(
    config: dict,
    *,
    experiment: str,
    scenario_seed: int,
    run_id: int,
    method: str,
    initial_population: np.ndarray,
    total_nfe: int,
    use_common_refinement: bool,
    code_commit: str,
) -> ControlledRun:
    """Run one solver under an explicit shared population and exact NFE cap."""

    population_size = int(config["experiment"]["population_size"])
    system = build_system_from_config(config, scenario_seed)
    weights = weights_from_config(config.get("weights"))
    utility_weights = utility_weights_from_config(config.get("utility_weights"))
    penalty_config = config.get("penalty", {})
    penalty_base = float(penalty_config.get("lambda0", penalty_config.get("base", 1.0)))
    dynamic_penalty_alpha = float(penalty_config.get("alpha", 2.0))

    if initial_population.shape != (population_size, len(system.tasks), 2):
        raise ValueError("common initial population shape does not match controlled scenario")
    source_hash = population_sha256(initial_population)
    received_population = np.array(initial_population, dtype=float, copy=True)
    received_hash = population_sha256(received_population)
    if source_hash != received_hash:
        raise AssertionError("method did not receive the exact common initial population")

    refinement_nfe = len(system.tasks) * 5 * 5 if use_common_refinement else 0
    final_reporting_nfe = 1
    candidate_budget = total_nfe - population_size - refinement_nfe - final_reporting_nfe
    if candidate_budget < 0:
        raise ValueError("NFE budget cannot accommodate initial and refinement evaluations")

    label = METHODS[method]
    if use_common_refinement:
        label = label.replace("population-controlled", "common-pipeline")
    optimizer = _make_population_algorithm(
        method,
        system,
        population_size=population_size,
        rng_seed=derive_seed(scenario_seed, f"{experiment}:{label}"),
        max_iter=max(1, int(np.ceil(candidate_budget / population_size))),
        weights=weights,
        utility_weights=utility_weights,
        penalty_base=penalty_base,
        dynamic_penalty_alpha=dynamic_penalty_alpha,
    )
    budget = EvaluationBudgetManager(system, total_nfe, weights, utility_weights)
    start = time.perf_counter()
    population = received_population
    metrics = [budget.evaluate(value, stage="initial", penalty_scale=optimizer.penalty_scale(0)) for value in population]
    reporting = np.asarray([item.reporting_fitness for item in metrics], dtype=float)
    incumbent_idx = int(np.argmin(reporting))
    incumbent = np.array(population[incumbent_idx], copy=True)
    incumbent_reporting = float(reporting[incumbent_idx])

    generation = 0
    final_generation_candidates = 0
    while budget.stage_counts["candidate"] < candidate_budget:
        generation += 1
        scale = optimizer.penalty_scale(generation)
        search = _search_fitness(metrics, scale)
        best = np.array(population[int(np.argmin(search))], copy=True)
        worst = np.array(population[int(np.argmax(search))], copy=True)
        candidate = optimizer.step(population, search, best, worst, generation)
        remaining_candidates = candidate_budget - budget.stage_counts["candidate"]
        evaluate_count = min(population_size, remaining_candidates)
        final_generation_candidates = evaluate_count
        candidate_metrics = [
            budget.evaluate(candidate[idx], stage="candidate", penalty_scale=scale)
            for idx in range(evaluate_count)
        ]
        old_search = _search_fitness(metrics[:evaluate_count], scale)
        new_search = _search_fitness(candidate_metrics, scale)
        accepted = new_search < old_search
        for idx, use_candidate in enumerate(accepted):
            if use_candidate:
                population[idx] = candidate[idx]
                metrics[idx] = candidate_metrics[idx]
        reporting = np.asarray([item.reporting_fitness for item in metrics], dtype=float)
        current_idx = int(np.argmin(reporting))
        if reporting[current_idx] < incumbent_reporting:
            incumbent = np.array(population[current_idx], copy=True)
            incumbent_reporting = float(reporting[current_idx])

    pre_refinement_fitness = incumbent_reporting
    if use_common_refinement:
        incumbent, incumbent_reporting = _refine(incumbent, incumbent_reporting, budget)
    final_metrics = budget.evaluate(incumbent, stage="final_reporting", penalty_scale=1.0)
    runtime = time.perf_counter() - start
    _validate_result(system, incumbent)
    if budget.nfe != total_nfe:
        raise AssertionError(f"expected {total_nfe} NFE, received {budget.nfe}")
    if budget.stage_counts["refinement"] != refinement_nfe:
        raise AssertionError("common refinement did not consume its fixed budget")
    if final_metrics.reporting_fitness != incumbent_reporting:
        raise AssertionError("final fixed reporting evaluation disagrees with tracked incumbent")

    population_nfe = budget.nfe - budget.stage_counts["refinement"]
    row = {
        "experiment": experiment,
        "run_id": run_id,
        "scenario_seed": scenario_seed,
        "method": label,
        "reporting_fitness": final_metrics.reporting_fitness,
        "base_objective": final_metrics.base_objective,
        "energy": final_metrics.energy,
        "delay": final_metrics.delay,
        "aoi": final_metrics.aoi,
        "qoe": final_metrics.qoe,
        "fairness": final_metrics.fairness,
        "soft_csr": final_metrics.csr,
        "hard_feasible": int(final_metrics.hard_feasible),
        "capacity_utilisation": final_metrics.capacity_utilisation_mean,
        "capacity_utilisation_max": final_metrics.capacity_utilisation_max,
        "assignment_unique": int(final_metrics.assignment_unique),
        "runtime_s": runtime,
        "total_nfe": budget.nfe,
        "population_nfe": population_nfe,
        "refinement_nfe": budget.stage_counts["refinement"],
        "initial_nfe": budget.stage_counts["initial"],
        "candidate_nfe": budget.stage_counts["candidate"],
        "final_reporting_nfe": budget.stage_counts["final_reporting"],
        "generation_count": generation,
        "final_generation_candidate_count": final_generation_candidates,
        "reassignment_count": budget.reassignment_count,
        "repair_failure_count": budget.repair_failure_count,
        "initial_population_hash": source_hash,
        "code_commit": code_commit,
        "search_fitness_not_reported": True,
    }
    population_audit = {
        "experiment": experiment,
        "scenario_seed": scenario_seed,
        "method": label,
        "population_hash": received_hash,
        "population_size": population_size,
        "dimension": f"{len(system.tasks)}x2",
        "population_shape": "x".join(str(value) for value in received_population.shape),
    }
    nfe_audit = {
        "experiment": experiment,
        "scenario_seed": scenario_seed,
        "method": label,
        "total_nfe": budget.nfe,
        "population_nfe": population_nfe,
        "initial_nfe": budget.stage_counts["initial"],
        "candidate_nfe": budget.stage_counts["candidate"],
        "refinement_nfe": budget.stage_counts["refinement"],
        "final_reporting_nfe": budget.stage_counts["final_reporting"],
        "final_generation_candidate_count": final_generation_candidates,
    }
    return ControlledRun(row=row, population_audit=population_audit, nfe_audit=nfe_audit)


def initial_population_for_seed(config: dict, scenario_seed: int) -> np.ndarray:
    system = build_system_from_config(config, scenario_seed)
    return common_initial_population(system, int(config["experiment"]["population_size"]), scenario_seed)
