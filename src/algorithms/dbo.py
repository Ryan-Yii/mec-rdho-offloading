from __future__ import annotations

import numpy as np

from .base import MetaheuristicOptimizer


class DBO(MetaheuristicOptimizer):
    def initialize_population(self) -> np.ndarray:
        return self.random_population("uniform")

    def step(self, population: np.ndarray, fitness: np.ndarray, best: np.ndarray, worst: np.ndarray, iteration: int) -> np.ndarray:
        progress = iteration / max(self.max_iter, 1)
        order = np.argsort(fitness)
        candidate = np.array(population, copy=True)
        n_roll = max(1, int(0.20 * self.population_size))
        n_breed = max(1, int(0.20 * self.population_size))
        n_forage = max(1, int(0.40 * self.population_size))
        alpha = 1.0 - progress

        for rank, idx in enumerate(order):
            current = population[idx]
            if rank < n_roll:
                k = self.rng.uniform(-1.0, 1.0, size=self.dim)
                b = self.rng.random()
                candidate[idx] = current + alpha * k * current + b * np.abs(current - worst)
            elif rank < n_roll + n_breed:
                local_best = population[order[max(0, rank // 2)]]
                beta = self.rng.uniform(-1.0, 1.0, size=self.dim)
                candidate[idx] = best + beta * np.abs(current - local_best)
            elif rank < n_roll + n_breed + n_forage:
                c1 = self.rng.random(size=self.dim)
                c2 = self.rng.random(size=self.dim)
                candidate[idx] = best + c1 * current - c2 * (2.0 - current)
            else:
                local_best = population[order[max(0, int(rank * 0.5))]]
                theta = self.rng.uniform(-np.pi / 4.0, np.pi / 4.0, size=self.dim)
                candidate[idx] = local_best + np.tan(theta) * np.abs(current - local_best)
        return self.clip_population(candidate)
