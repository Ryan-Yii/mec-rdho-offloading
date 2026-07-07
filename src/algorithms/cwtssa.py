from __future__ import annotations

import numpy as np

from .base import MetaheuristicOptimizer


class CWTSSA(MetaheuristicOptimizer):
    def initialize_population(self) -> np.ndarray:
        population = self.random_population("uniform")
        population[:, :, 0] = np.where(self.rng.random(population[:, :, 0].shape) < 0.55, 1.0, population[:, :, 0])
        return self.clip_population(population)

    def step(self, population: np.ndarray, fitness: np.ndarray, best: np.ndarray, worst: np.ndarray, iteration: int) -> np.ndarray:
        progress = iteration / max(self.max_iter, 1)
        order = np.argsort(fitness)
        candidate = np.array(population, copy=True)
        n_producers = max(1, int(0.20 * self.population_size))
        n_scouts = max(1, int(0.10 * self.population_size))
        inertia = 0.9 - 0.5 * progress

        for rank, idx in enumerate(order):
            current = population[idx]
            if rank < n_producers:
                if self.rng.random() < 0.8:
                    candidate[idx] = current * np.exp(-rank / (self.rng.random() * self.max_iter + 1.0))
                else:
                    candidate[idx] = current + self.rng.normal(0.0, 0.15, size=self.dim)
            elif rank >= self.population_size - n_scouts:
                candidate[idx] = best + self.rng.standard_t(df=3, size=self.dim) * 0.12 * (1.0 - progress)
            else:
                sign = self.rng.choice([-1.0, 1.0], size=self.dim)
                candidate[idx] = inertia * current + sign * np.abs(current - best) / (rank + 1)

            if self.rng.random() < 0.20:
                candidate[idx] += self.rng.standard_cauchy(size=self.dim) * 0.025 * (1.0 - progress)
        return self.clip_population(candidate)
