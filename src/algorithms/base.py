from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from ..metrics import FitnessWeights, evaluate_solution
from ..system_model import MODE_CLOUD, MODE_LOCAL, SystemModel


@dataclass(frozen=True)
class OptimizerResult:
    solution: np.ndarray
    fitness: float
    history: List[float]


class MetaheuristicOptimizer:
    def __init__(
        self,
        system: SystemModel,
        max_iter: int = 150,
        population_size: int = 50,
        seed: int = 0,
        weights: FitnessWeights | None = None,
        penalty_base: float = 1.0,
    ) -> None:
        self.system = system
        self.max_iter = max_iter
        self.population_size = population_size
        self.rng = np.random.default_rng(seed)
        self.weights = weights or FitnessWeights()
        self.penalty_base = penalty_base
        self.dim = (len(system.tasks), 2)

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

    def fitness(self, solution: np.ndarray, iteration: int = 0) -> float:
        return evaluate_solution(
            self.system,
            self.clip(solution),
            weights=self.weights,
            penalty_scale=self.penalty_scale(iteration),
        ).fitness

    def evaluate_population(self, population: np.ndarray, iteration: int = 0) -> np.ndarray:
        return np.asarray([self.fitness(individual, iteration) for individual in population], dtype=float)

    def initialize_population(self) -> np.ndarray:
        return self.random_population("uniform")

    def step(self, population: np.ndarray, fitness: np.ndarray, best: np.ndarray, worst: np.ndarray, iteration: int) -> np.ndarray:
        noise = self.rng.normal(0.0, 0.05, size=population.shape)
        return self.clip_population(population + noise * (1.0 - iteration / max(self.max_iter, 1)))

    def greedy_accept(self, old_pop: np.ndarray, new_pop: np.ndarray, old_fit: np.ndarray, iteration: int) -> tuple[np.ndarray, np.ndarray]:
        new_fit = self.evaluate_population(new_pop, iteration)
        mask = new_fit < old_fit
        merged = np.array(old_pop, copy=True)
        merged[mask] = new_pop[mask]
        fit = np.array(old_fit, copy=True)
        fit[mask] = new_fit[mask]
        return merged, fit

    def optimize(self) -> OptimizerResult:
        population = self.initialize_population()
        fitness = self.evaluate_population(population, 0)
        best_idx = int(np.argmin(fitness))
        worst_idx = int(np.argmax(fitness))
        best = np.array(population[best_idx], copy=True)
        best_fitness = float(fitness[best_idx])
        history = [best_fitness]

        for iteration in range(1, self.max_iter + 1):
            worst = population[worst_idx]
            candidate = self.step(population, fitness, best, worst, iteration)
            population, fitness = self.greedy_accept(population, candidate, fitness, iteration)
            current_best_idx = int(np.argmin(fitness))
            current_worst_idx = int(np.argmax(fitness))
            if fitness[current_best_idx] < best_fitness:
                best = np.array(population[current_best_idx], copy=True)
                best_fitness = float(fitness[current_best_idx])
            worst_idx = current_worst_idx
            history.append(best_fitness)

        return OptimizerResult(solution=self.clip(best), fitness=best_fitness, history=history)


def greedy_seed_solution(system: SystemModel, weights: FitnessWeights | None = None) -> np.ndarray:
    solution = np.zeros((len(system.tasks), 2), dtype=float)
    solution[:, 0] = 1.0
    solution[:, 1] = 0.70
    candidates = [(0, 0.55), (0, 0.85), (1, 0.45), (1, 0.70), (1, 0.95), (2, 0.55), (2, 0.80), (2, 1.00)]
    for idx in range(len(system.tasks)):
        best_pair = solution[idx].copy()
        best_fit = evaluate_solution(system, solution, weights=weights).fitness
        for mode, resource in candidates:
            trial = np.array(solution, copy=True)
            trial[idx, 0] = mode
            trial[idx, 1] = resource
            fit = evaluate_solution(system, trial, weights=weights).fitness
            if fit < best_fit:
                best_fit = fit
                best_pair = trial[idx].copy()
        solution[idx] = best_pair
    return solution
