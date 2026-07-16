from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from ..evaluation import EvaluationBudget, EvaluationBudgetExceeded
from ..metrics import FitnessWeights, Metrics, evaluate_solution
from ..system_model import MODE_CLOUD, MODE_LOCAL, SystemModel


@dataclass(frozen=True)
class OptimizerResult:
    solution: np.ndarray
    fitness: float
    history: List[float]
    reported_fitness: float | None = None
    search_fitness: float | None = None
    nfe_used: int = 0
    max_evaluations: int | None = None
    metrics: Metrics | None = None


class MetaheuristicOptimizer:
    def __init__(
        self,
        system: SystemModel,
        max_iter: int = 150,
        population_size: int = 50,
        seed: int = 0,
        weights: FitnessWeights | None = None,
        penalty_base: float = 1.0,
        max_evaluations: int | None = None,
    ) -> None:
        self.system = system
        self.max_iter = max_iter
        self.population_size = population_size
        self.rng = np.random.default_rng(seed)
        self.weights = weights or FitnessWeights()
        self.penalty_base = penalty_base
        self.max_evaluations = max_evaluations
        self.evaluation_budget = EvaluationBudget(max_evaluations)
        self.dim = (len(system.tasks), 2)
        self.penalty_audit: list[dict[str, float | int]] = []

    def clip(self, solution: np.ndarray) -> np.ndarray:
        clipped = np.array(solution, dtype=float, copy=True)
        clipped[:, 0] = np.clip(clipped[:, 0], MODE_LOCAL, MODE_CLOUD)
        clipped[:, 1] = np.clip(clipped[:, 1], 0.2, 1.0)
        return clipped

    def random_population(self, style: str = "uniform") -> np.ndarray:
        if style == "normal":
            modes = self.rng.normal(1.0, 0.7, size=(self.population_size, len(self.system.tasks), 1))
            resources = self.rng.normal(0.68, 0.18, size=(self.population_size, len(self.system.tasks), 1))
        else:
            modes = self.rng.uniform(MODE_LOCAL, MODE_CLOUD, size=(self.population_size, len(self.system.tasks), 1))
            resources = self.rng.uniform(0.2, 1.0, size=(self.population_size, len(self.system.tasks), 1))
        return self.clip_population(np.concatenate([modes, resources], axis=2))

    def clip_population(self, population: np.ndarray) -> np.ndarray:
        clipped = np.array(population, dtype=float, copy=True)
        clipped[:, :, 0] = np.clip(clipped[:, :, 0], MODE_LOCAL, MODE_CLOUD)
        clipped[:, :, 1] = np.clip(clipped[:, :, 1], 0.2, 1.0)
        return clipped

    def penalty_scale(self, iteration: int) -> float:
        return self.penalty_base

    def evaluate_metrics(self, solution: np.ndarray, penalty_scale: float | None = None) -> Metrics:
        scale = self.penalty_base if penalty_scale is None else penalty_scale
        return evaluate_solution(
            self.system,
            self.clip(solution),
            weights=self.weights,
            penalty_scale=scale,
            report_penalty_scale=1.0,
            budget=self.evaluation_budget,
        )

    def evaluate_population_metrics(self, population: np.ndarray, penalty_scale: float) -> list[Metrics]:
        if self.evaluation_budget.remaining is not None and self.evaluation_budget.remaining < len(population):
            raise EvaluationBudgetExceeded("not enough NFE remaining for population evaluation")
        return [self.evaluate_metrics(individual, penalty_scale=penalty_scale) for individual in population]

    def fitness(self, solution: np.ndarray, iteration: int = 0) -> float:
        return self.evaluate_metrics(solution, penalty_scale=self.penalty_scale(iteration)).search_fitness

    def evaluate_population(self, population: np.ndarray, iteration: int = 0) -> np.ndarray:
        metrics = self.evaluate_population_metrics(population, penalty_scale=self.penalty_scale(iteration))
        return np.asarray([metric.search_fitness for metric in metrics], dtype=float)

    def initialize_population(self) -> np.ndarray:
        return self.random_population("uniform")

    def minimum_initial_evaluations(self) -> int:
        return self.population_size

    def reserved_evaluations(self) -> int:
        return 0

    def candidate_acceptance_mask(self, old_search: np.ndarray, candidate_search: np.ndarray) -> np.ndarray:
        return candidate_search < old_search

    def step(self, population: np.ndarray, fitness: np.ndarray, best: np.ndarray, worst: np.ndarray, iteration: int) -> np.ndarray:
        noise = self.rng.normal(0.0, 0.05, size=population.shape)
        return self.clip_population(population + noise * (1.0 - iteration / max(self.max_iter, 1)))

    def _result(self, solution: np.ndarray, metrics: Metrics, history: list[float]) -> OptimizerResult:
        return OptimizerResult(
            solution=self.clip(solution),
            fitness=metrics.reported_fitness,
            reported_fitness=metrics.reported_fitness,
            search_fitness=metrics.search_fitness,
            history=history,
            nfe_used=self.evaluation_budget.used,
            max_evaluations=self.max_evaluations,
            metrics=metrics,
        )

    def optimize(self) -> OptimizerResult:
        minimum = self.minimum_initial_evaluations()
        if self.max_evaluations is not None and self.max_evaluations < minimum:
            raise ValueError(
                f"max_evaluations={self.max_evaluations} is insufficient for initialization; "
                f"at least {minimum} evaluations are required"
            )
        population = self.initialize_population()
        initial_penalty = self.penalty_scale(0)
        initial_metrics = self.evaluate_population_metrics(population, initial_penalty)

        reported_values = np.asarray([metric.reported_fitness for metric in initial_metrics], dtype=float)
        best_idx = int(np.argmin(reported_values))
        best = np.array(population[best_idx], copy=True)
        best_metrics = initial_metrics[best_idx]
        history = [best_metrics.reported_fitness]

        for iteration in range(1, self.max_iter + 1):
            required = 2 * self.population_size
            reserve = self.reserved_evaluations()
            if self.evaluation_budget.remaining is not None and self.evaluation_budget.remaining < required + reserve:
                break

            current_penalty = self.penalty_scale(iteration)
            old_metrics = self.evaluate_population_metrics(population, current_penalty)
            old_search = np.asarray([metric.search_fitness for metric in old_metrics], dtype=float)
            order = np.argsort(old_search)
            current_best = population[int(order[0])]
            current_worst = population[int(order[-1])]

            candidate = self.step(population, old_search, current_best, current_worst, iteration)
            candidate_metrics = self.evaluate_population_metrics(candidate, current_penalty)
            candidate_search = np.asarray([metric.search_fitness for metric in candidate_metrics], dtype=float)

            for idx, metrics in enumerate(candidate_metrics):
                if metrics.reported_fitness < best_metrics.reported_fitness:
                    best = np.array(candidate[idx], copy=True)
                    best_metrics = metrics

            accepted = self.candidate_acceptance_mask(old_search, candidate_search)
            merged_population = np.array(population, copy=True)
            merged_metrics = list(old_metrics)
            for idx, accept in enumerate(accepted):
                if accept:
                    merged_population[idx] = candidate[idx]
                    merged_metrics[idx] = candidate_metrics[idx]

            population = self.clip_population(merged_population)
            iteration_reported = np.asarray([metric.reported_fitness for metric in merged_metrics], dtype=float)
            iteration_best_idx = int(np.argmin(iteration_reported))
            if merged_metrics[iteration_best_idx].reported_fitness < best_metrics.reported_fitness:
                best = np.array(population[iteration_best_idx], copy=True)
                best_metrics = merged_metrics[iteration_best_idx]

            history.append(best_metrics.reported_fitness)
            self.penalty_audit.append(
                {
                    "iteration": iteration,
                    "old_population_penalty_scale": float(current_penalty),
                    "candidate_penalty_scale": float(current_penalty),
                    "reported_best": float(best_metrics.reported_fitness),
                    "history_value": float(history[-1]),
                }
            )
        return self._result(best, best_metrics, history)


def greedy_seed_solution(
    system: SystemModel,
    weights: FitnessWeights | None = None,
    budget: EvaluationBudget | None = None,
) -> np.ndarray:
    solution, _ = greedy_seed_solution_with_metrics(system, weights=weights, budget=budget)
    return solution


def greedy_seed_solution_with_metrics(
    system: SystemModel,
    weights: FitnessWeights | None = None,
    budget: EvaluationBudget | None = None,
) -> tuple[np.ndarray, Metrics]:
    if budget is not None and not budget.can_consume():
        raise ValueError("max_evaluations is insufficient for initialization; at least one evaluation is required")
    solution = np.zeros((len(system.tasks), 2), dtype=float)
    solution[:, 0] = 1.0
    solution[:, 1] = 0.70
    candidates = [(0, 0.55), (0, 0.85), (1, 0.45), (1, 0.70), (1, 0.95), (2, 0.55), (2, 0.80), (2, 1.00)]
    latest_metrics = evaluate_solution(system, solution, weights=weights, budget=budget)
    for idx in range(len(system.tasks)):
        best_pair = solution[idx].copy()
        if idx > 0:
            if budget is not None and not budget.can_consume():
                return solution, latest_metrics
            latest_metrics = evaluate_solution(system, solution, weights=weights, budget=budget)
        best_metrics = latest_metrics
        for mode, resource in candidates:
            if budget is not None and not budget.can_consume():
                solution[idx] = best_pair
                return solution, best_metrics
            trial = np.array(solution, copy=True)
            trial[idx, 0] = mode
            trial[idx, 1] = resource
            metrics = evaluate_solution(system, trial, weights=weights, budget=budget)
            if metrics.reported_fitness < best_metrics.reported_fitness:
                best_pair = trial[idx].copy()
                best_metrics = metrics
        solution[idx] = best_pair
        latest_metrics = best_metrics
    return solution, latest_metrics
