from __future__ import annotations

import numpy as np

from .base import MetaheuristicOptimizer


class TLBOHHO(MetaheuristicOptimizer):
    def initialize_population(self) -> np.ndarray:
        population = self.random_population("uniform")
        population[:, :, 1] = np.clip(population[:, :, 1] * 0.9 + 0.05, 0.0, 1.0)
        return population

    def step(self, population: np.ndarray, fitness: np.ndarray, best: np.ndarray, worst: np.ndarray, iteration: int) -> np.ndarray:
        progress = iteration / max(self.max_iter, 1)
        mean = np.mean(population, axis=0)
        candidate = np.array(population, copy=True)
        order = np.argsort(fitness)

        for idx in range(self.population_size):
            if self.rng.random() < 0.55:
                teaching_factor = 1 + int(self.rng.random() < 0.5)
                candidate[idx] = population[idx] + self.rng.random(size=self.dim) * (best - teaching_factor * mean)
            elif self.rng.random() < 0.80:
                peer = int(self.rng.choice(order[: max(2, self.population_size // 2)]))
                direction = population[peer] - population[idx]
                candidate[idx] = population[idx] + self.rng.random(size=self.dim) * direction
            else:
                energy = 2.0 * (1.0 - progress) * (2.0 * self.rng.random() - 1.0)
                jump = 2.0 * (1.0 - self.rng.random(size=self.dim))
                candidate[idx] = best - energy * np.abs(jump * best - population[idx])
        return self.clip_population(candidate)
