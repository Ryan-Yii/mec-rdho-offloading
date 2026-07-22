from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

import numpy as np

from ..metrics import FitnessWeights, Metrics, UtilityWeights, evaluate_solution, fitness_from_components
from ..system_model import SystemModel


@dataclass(frozen=True)
class OptimizerResult:
    solution: np.ndarray
    fitness: float
    history: List[float]
    search_fitness: float
    search_history: List[float]
    nfe: int
    pre_refinement_fitness: float
    local_refinement_gain: float


class MetaheuristicOptimizer:
    def __init__(
        self,
        system: SystemModel,
        max_iter: int = 150,
        population_size: int = 50,
        seed: int = 0,
        weights: FitnessWeights | None = None,
        utility_weights: UtilityWeights | None = None,
        penalty_base: float = 1.0,
        common_initial_population: np.ndarray | None = None,
        common_coordinate_refinement: bool = False,
    ) -> None:
        self.system = system
        self.max_iter = max_iter
        self.population_size = population_size
        self.rng = np.random.default_rng(seed)
        self.weights = weights or FitnessWeights()
        self.utility_weights = utility_weights or UtilityWeights()
        self.penalty_base = penalty_base
        self.common_initial_population = None if common_initial_population is None else self.clip_population(common_initial_population)
        self.common_coordinate_refinement = common_coordinate_refinement
        # Per-task coordinates: normalised legal-node index and CPU encoding.
        self.dim = (len(system.tasks), 2)
        self.nfe = 0

    def clip(self, solution: np.ndarray) -> np.ndarray:
        clipped = np.array(solution, dtype=float, copy=True)
        clipped[:] = np.clip(clipped, 0.0, 1.0)
        return clipped

    def random_population(self, style: str = "uniform") -> np.ndarray:
        if style == "normal":
            nodes = self.rng.normal(0.55, 0.25, size=(self.population_size, len(self.system.tasks), 1))
            resources = self.rng.normal(0.60, 0.20, size=(self.population_size, len(self.system.tasks), 1))
        else:
            nodes = self.rng.uniform(0.0, 1.0, size=(self.population_size, len(self.system.tasks), 1))
            resources = self.rng.uniform(0.0, 1.0, size=(self.population_size, len(self.system.tasks), 1))
        return self.clip_population(np.concatenate([nodes, resources], axis=2))

    def clip_population(self, population: np.ndarray) -> np.ndarray:
        clipped = np.array(population, dtype=float, copy=True)
        clipped[:] = np.clip(clipped, 0.0, 1.0)
        return clipped

    def penalty_scale(self, iteration: int) -> float:
        return self.penalty_base

    def evaluate_metrics(self, solution: np.ndarray, penalty_scale: float) -> Metrics:
        self.nfe += 1
        return evaluate_solution(
            self.system,
            self.clip(solution),
            weights=self.weights,
            utility_weights=self.utility_weights,
            penalty_scale=penalty_scale,
        )

    def evaluate_population_metrics(self, population: np.ndarray, iteration: int) -> list[Metrics]:
        scale = self.penalty_scale(iteration)
        return [self.evaluate_metrics(individual, scale) for individual in population]

    def search_fitness_array(self, metrics: list[Metrics], iteration: int) -> np.ndarray:
        scale = self.penalty_scale(iteration)
        return np.asarray([fitness_from_components(item.base_objective, item.csr, scale) for item in metrics], dtype=float)

    @staticmethod
    def reporting_fitness_array(metrics: list[Metrics]) -> np.ndarray:
        return np.asarray([item.reporting_fitness for item in metrics], dtype=float)

    def initialize_population(self) -> np.ndarray:
        return self.random_population("uniform")

    def step(self, population: np.ndarray, fitness: np.ndarray, best: np.ndarray, worst: np.ndarray, iteration: int) -> np.ndarray:
        noise = self.rng.normal(0.0, 0.05, size=population.shape)
        return self.clip_population(population + noise * (1.0 - iteration / max(self.max_iter, 1)))

    def greedy_accept(
        self,
        old_pop: np.ndarray,
        new_pop: np.ndarray,
        old_metrics: list[Metrics],
        iteration: int,
    ) -> tuple[np.ndarray, list[Metrics]]:
        """Compare old and new candidates under the same iteration penalty."""

        new_metrics = self.evaluate_population_metrics(new_pop, iteration)
        old_fit = self.search_fitness_array(old_metrics, iteration)
        new_fit = self.search_fitness_array(new_metrics, iteration)
        mask = new_fit < old_fit
        merged = np.array(old_pop, copy=True)
        merged[mask] = new_pop[mask]
        merged_metrics = [new_metrics[idx] if mask[idx] else old_metrics[idx] for idx in range(len(old_metrics))]
        return merged, merged_metrics

    def optimize(self) -> OptimizerResult:
        self.nfe = 0
        population = np.array(self.common_initial_population, copy=True) if self.common_initial_population is not None else self.initialize_population()
        metrics = self.evaluate_population_metrics(population, 0)

        reporting = self.reporting_fitness_array(metrics)
        incumbent_idx = int(np.argmin(reporting))
        incumbent = np.array(population[incumbent_idx], copy=True)
        incumbent_reporting = float(reporting[incumbent_idx])

        search = self.search_fitness_array(metrics, 0)
        history = [incumbent_reporting]
        search_history = [float(np.min(search))]

        for iteration in range(1, self.max_iter + 1):
            # Re-score the existing population with the current dynamic penalty
            # before using ranks or accepting candidates.
            search = self.search_fitness_array(metrics, iteration)
            best_idx = int(np.argmin(search))
            worst_idx = int(np.argmax(search))
            best = np.array(population[best_idx], copy=True)
            worst = np.array(population[worst_idx], copy=True)

            candidate = self.step(population, search, best, worst, iteration)
            population, metrics = self.greedy_accept(population, candidate, metrics, iteration)

            reporting = self.reporting_fitness_array(metrics)
            current_reporting_idx = int(np.argmin(reporting))
            if reporting[current_reporting_idx] < incumbent_reporting:
                incumbent = np.array(population[current_reporting_idx], copy=True)
                incumbent_reporting = float(reporting[current_reporting_idx])

            search = self.search_fitness_array(metrics, iteration)
            history.append(incumbent_reporting)
            search_history.append(float(np.min(search)))

        pre_refinement = incumbent_reporting
        if self.common_coordinate_refinement:
            incumbent, incumbent_reporting = self.coordinate_refine(incumbent, incumbent_reporting)
        final_search = self.evaluate_metrics(incumbent, self.penalty_scale(self.max_iter)).fitness
        return OptimizerResult(
            solution=self.clip(incumbent),
            fitness=incumbent_reporting,
            history=history,
            search_fitness=float(final_search),
            search_history=search_history,
            nfe=self.nfe,
            pre_refinement_fitness=pre_refinement,
            local_refinement_gain=float(max(0.0, pre_refinement - incumbent_reporting)),
        )

    def coordinate_refine(self, solution: np.ndarray, current_fitness: float) -> tuple[np.ndarray, float]:
        """Shared deterministic post-processing used only in controlled tests."""

        best_solution = np.array(solution, copy=True)
        best_fitness = float(current_fitness)
        for task_idx in range(len(self.system.tasks)):
            for node in (0.08, 0.28, 0.48, 0.68, 0.88):
                for resource in (0.10, 0.30, 0.55, 0.80, 1.00):
                    trial = np.array(best_solution, copy=True)
                    trial[task_idx] = (node, resource)
                    fitness = self.evaluate_metrics(trial, penalty_scale=1.0).reporting_fitness
                    if fitness < best_fitness:
                        best_solution = trial
                        best_fitness = fitness
        return self.clip(best_solution), best_fitness


def greedy_seed_solution(
    system: SystemModel,
    weights: FitnessWeights | None = None,
    utility_weights: UtilityWeights | None = None,
    evaluator: Callable[[np.ndarray], Metrics] | None = None,
) -> np.ndarray:
    solution = np.full((len(system.tasks), 2), 0.5, dtype=float)
    candidates = [(node, resource) for node in (0.08, 0.35, 0.62, 0.90) for resource in (0.20, 0.50, 0.80, 1.00)]
    score = evaluator or (
        lambda value: evaluate_solution(system, value, weights=weights, utility_weights=utility_weights)
    )
    for idx in range(len(system.tasks)):
        best_pair = solution[idx].copy()
        best_fit = score(solution).reporting_fitness
        for node, resource in candidates:
            trial = np.array(solution, copy=True)
            trial[idx, 0] = node
            trial[idx, 1] = resource
            fit = score(trial).reporting_fitness
            if fit < best_fit:
                best_fit = fit
                best_pair = trial[idx].copy()
        solution[idx] = best_pair
    return solution
