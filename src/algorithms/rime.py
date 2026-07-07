from __future__ import annotations

import numpy as np

from .base import MetaheuristicOptimizer


class RIME(MetaheuristicOptimizer):
    def initialize_population(self) -> np.ndarray:
        return self.random_population("normal")

    def step(self, population: np.ndarray, fitness: np.ndarray, best: np.ndarray, worst: np.ndarray, iteration: int) -> np.ndarray:
        progress = iteration / max(self.max_iter, 1)
        h = 2.0 * (1.0 - progress)
        candidate = np.array(population, copy=True)
        for idx in range(self.population_size):
            if self.rng.random() < (1.0 - progress):
                beta = self.rng.normal()
                theta = self.rng.uniform(0.0, 2.0 * np.pi)
                direction = beta * np.cos(theta) * h
                candidate[idx] = best + direction * self.rng.normal(0.0, 0.30, size=self.dim)
            else:
                candidate[idx] = population[idx]
                task_id = int(self.rng.integers(0, len(self.system.tasks)))
                candidate[idx, task_id] = best[task_id]
                candidate[idx] += self.rng.normal(0.0, 0.035 * (1.0 - progress), size=self.dim)
        return self.clip_population(candidate)
