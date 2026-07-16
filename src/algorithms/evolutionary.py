from __future__ import annotations

import numpy as np

from .base import MetaheuristicOptimizer


class GeneticAlgorithm(MetaheuristicOptimizer):
    def step(self, population: np.ndarray, fitness: np.ndarray, best: np.ndarray, worst: np.ndarray, iteration: int) -> np.ndarray:
        candidate = np.array(population, copy=True)
        order = np.argsort(fitness)
        elite_count = max(1, int(0.10 * self.population_size))
        elites = set(int(idx) for idx in order[:elite_count])

        for idx in range(self.population_size):
            if idx in elites:
                continue
            parent_ids = self.rng.choice(order[: max(2, self.population_size // 2)], size=2, replace=True)
            p1 = population[int(parent_ids[0])]
            p2 = population[int(parent_ids[1])]
            mask = self.rng.random(size=self.dim) < 0.5
            child = np.where(mask, p1, p2)
            mutation_scale = 0.10 * (1.0 - iteration / max(self.max_iter, 1))
            mutation_mask = self.rng.random(size=self.dim) < 0.12
            child = child + mutation_mask * self.rng.normal(0.0, mutation_scale, size=self.dim)
            candidate[idx] = child
        return self.clip_population(candidate)


class ParticleSwarmOptimizer(MetaheuristicOptimizer):
    def candidate_acceptance_mask(self, old_search: np.ndarray, candidate_search: np.ndarray) -> np.ndarray:
        return np.ones_like(candidate_search, dtype=bool)

    def initialize_population(self) -> np.ndarray:
        population = super().initialize_population()
        self.velocity = self.rng.normal(0.0, 0.08, size=population.shape)
        return population

    def step(self, population: np.ndarray, fitness: np.ndarray, best: np.ndarray, worst: np.ndarray, iteration: int) -> np.ndarray:
        if not hasattr(self, "velocity"):
            self.velocity = self.rng.normal(0.0, 0.08, size=population.shape)
        if not hasattr(self, "personal_best"):
            self.personal_best = np.array(population, copy=True)
            self.personal_best_fitness = np.array(fitness, copy=True)
        else:
            improved = fitness < self.personal_best_fitness
            self.personal_best[improved] = population[improved]
            self.personal_best_fitness[improved] = fitness[improved]
        inertia = 0.72
        cognitive = 1.49 * self.rng.random(size=population.shape) * (self.personal_best - population)
        social = 1.49 * self.rng.random(size=population.shape) * (best - population)
        self.velocity = inertia * self.velocity + cognitive + social
        return self.clip_population(population + self.velocity)


class DifferentialEvolution(MetaheuristicOptimizer):
    def binomial_crossover_mask(self, crossover_rate: float) -> np.ndarray:
        mask = self.rng.random(size=self.dim) < crossover_rate
        forced = int(self.rng.integers(0, mask.size))
        mask.flat[forced] = True
        return mask

    def step(self, population: np.ndarray, fitness: np.ndarray, best: np.ndarray, worst: np.ndarray, iteration: int) -> np.ndarray:
        candidate = np.array(population, copy=True)
        scale = 0.55
        crossover_rate = 0.75
        for idx in range(self.population_size):
            choices = [choice for choice in range(self.population_size) if choice != idx]
            if len(choices) < 3:
                candidate[idx] = population[idx] + self.rng.normal(0.0, 0.05, size=self.dim)
                continue
            r1, r2, r3 = self.rng.choice(choices, size=3, replace=False)
            mutant = population[int(r1)] + scale * (population[int(r2)] - population[int(r3)])
            mask = self.binomial_crossover_mask(crossover_rate)
            candidate[idx] = np.where(mask, mutant, population[idx])
        return self.clip_population(candidate)
