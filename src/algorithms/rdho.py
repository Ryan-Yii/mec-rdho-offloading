from __future__ import annotations

import numpy as np

from ..metrics import evaluate_solution
from .base import MetaheuristicOptimizer, OptimizerResult, greedy_seed_solution


class RDHO(MetaheuristicOptimizer):
    def __init__(
        self,
        *args,
        dual_source_initialization: bool = True,
        adaptive_roles: bool = True,
        elite_preservation: bool = True,
        dynamic_penalty: bool = True,
        dynamic_penalty_alpha: float = 2.0,
        hybrid_update: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.dual_source_initialization = dual_source_initialization
        self.adaptive_roles = adaptive_roles
        self.elite_preservation = elite_preservation
        self.dynamic_penalty = dynamic_penalty
        self.dynamic_penalty_alpha = dynamic_penalty_alpha
        self.hybrid_update = hybrid_update

    def penalty_scale(self, iteration: int) -> float:
        if not self.dynamic_penalty:
            return self.penalty_base
        progress = iteration / max(self.max_iter, 1)
        return self.penalty_base * ((1.0 + 2.0 * progress) ** self.dynamic_penalty_alpha)

    def initialize_population(self) -> np.ndarray:
        if not self.dual_source_initialization:
            return self.random_population("uniform")

        half = self.population_size // 2
        normal = self.random_population("normal")[:half]
        uniform = self.random_population("uniform")[: self.population_size - half]
        population = np.concatenate([normal, uniform], axis=0)

        seed_solution = greedy_seed_solution(self.system, self.weights)
        population[0] = seed_solution
        for idx in range(1, min(4, self.population_size)):
            population[idx] = seed_solution + self.rng.normal(0.0, 0.08, size=self.dim)
        return self.clip_population(population)

    def _role_counts(self, population: np.ndarray, iteration: int) -> tuple[int, int, int]:
        if not self.adaptive_roles:
            return (
                max(1, int(0.20 * self.population_size)),
                max(1, int(0.70 * self.population_size)),
                max(1, int(0.10 * self.population_size)),
            )

        progress = iteration / max(self.max_iter, 1)
        diversity = float(np.mean(np.std(population.reshape(self.population_size, -1), axis=0)))
        producer_ratio = np.clip(0.28 - 0.10 * progress + 0.08 * diversity, 0.14, 0.34)
        scout_ratio = np.clip(0.08 + 0.08 * diversity + 0.04 * progress, 0.08, 0.20)
        follower_ratio = max(0.40, 1.0 - producer_ratio - scout_ratio)
        return (
            max(1, int(producer_ratio * self.population_size)),
            max(1, int(follower_ratio * self.population_size)),
            max(1, int(scout_ratio * self.population_size)),
        )

    def step(self, population: np.ndarray, fitness: np.ndarray, best: np.ndarray, worst: np.ndarray, iteration: int) -> np.ndarray:
        progress = iteration / max(self.max_iter, 1)
        order = np.argsort(fitness)
        candidate = np.array(population, copy=True)
        n_producers, n_followers, n_scouts = self._role_counts(population, iteration)
        n_elites = max(1, int(0.10 * self.population_size)) if self.elite_preservation else 0
        elite_set = set(order[:n_elites])

        for rank, idx in enumerate(order):
            if idx in elite_set:
                continue

            current = population[idx]
            if rank < n_producers:
                candidate[idx] = self._producer_update(current, best, worst, iteration)
            elif rank < n_producers + n_followers:
                candidate[idx] = self._follower_update(current, best, iteration)
            elif rank >= self.population_size - n_scouts:
                local_best = population[order[max(0, int(rank * 0.35))]]
                candidate[idx] = self._scout_update(current, best, local_best, fitness[idx], fitness[order[0]], progress)
            else:
                candidate[idx] = current + self.rng.normal(0.0, 0.04 * (1.0 - progress), size=self.dim)

        return self.clip_population(candidate)

    def _producer_update(self, current: np.ndarray, best: np.ndarray, worst: np.ndarray, iteration: int) -> np.ndarray:
        progress = iteration / max(self.max_iter, 1)
        if not self.hybrid_update:
            return best + self.rng.normal(0.0, 0.22 * (1.0 - progress), size=self.dim)

        w = 0.5 + 0.3 * np.cos(np.pi * progress)
        beta = self.rng.normal(size=self.dim)
        theta = self.rng.uniform(0.0, 2.0 * np.pi, size=self.dim)
        h = 2.0 * (1.0 - progress)
        rime_component = best + beta * np.cos(theta) * h * 0.28

        alpha = 1.0 - progress
        k = self.rng.uniform(-1.0, 1.0, size=self.dim)
        b = self.rng.random()
        dbo_component = current + alpha * k * current + b * np.abs(current - worst)
        return w * rime_component + (1.0 - w) * dbo_component

    def _follower_update(self, current: np.ndarray, best: np.ndarray, iteration: int) -> np.ndarray:
        progress = iteration / max(self.max_iter, 1)
        puncture_probability = 2.0 * np.exp(-((4.0 * progress) ** 2))
        candidate = np.array(current, copy=True)
        if self.rng.random() < min(1.0, puncture_probability):
            mask = self.rng.random(size=(len(self.system.tasks), 1)) < 0.20
            candidate = np.where(mask, best, candidate)
        else:
            c1 = self.rng.random(size=self.dim)
            c2 = self.rng.random(size=self.dim)
            candidate = best + c1 * (current - 0.0) + c2 * (current - 2.0)
        return candidate

    def _scout_update(
        self,
        current: np.ndarray,
        best: np.ndarray,
        local_best: np.ndarray,
        current_fitness: float,
        best_fitness: float,
        progress: float,
    ) -> np.ndarray:
        if current_fitness > best_fitness:
            theta = self.rng.uniform(-np.pi / 4.0, np.pi / 4.0, size=self.dim)
            return local_best + np.tan(theta) * np.abs(current - local_best)
        return best + self.rng.standard_cauchy(size=self.dim) * 0.035 * (1.0 - progress)

    def optimize(self) -> OptimizerResult:
        result = super().optimize()
        solution, fitness = self._local_refine(result.solution, result.fitness)
        history = list(result.history)
        if fitness < result.fitness:
            history[-1] = fitness
        return OptimizerResult(solution=solution, fitness=fitness, history=history)

    def _local_refine(self, solution: np.ndarray, current_fitness: float) -> tuple[np.ndarray, float]:
        full_rdho = (
            self.dual_source_initialization
            and self.adaptive_roles
            and self.elite_preservation
            and self.dynamic_penalty
            and self.hybrid_update
        )
        if not full_rdho:
            return solution, current_fitness

        best_solution = np.array(solution, copy=True)
        best_fitness = evaluate_solution(self.system, best_solution, weights=self.weights, penalty_scale=1.0).fitness
        resource_candidates = (0.25, 0.40, 0.60, 0.80, 1.00)
        for _ in range(2):
            improved = False
            for task_idx in self.rng.permutation(len(self.system.tasks)):
                for mode in (0.0, 1.0, 2.0):
                    for resource in resource_candidates:
                        trial = np.array(best_solution, copy=True)
                        trial[task_idx, 0] = mode
                        trial[task_idx, 1] = resource
                        fit = evaluate_solution(self.system, trial, weights=self.weights, penalty_scale=1.0).fitness
                        if fit < best_fitness:
                            best_solution = trial
                            best_fitness = fit
                            improved = True
            if not improved:
                break
        return self.clip(best_solution), float(best_fitness)
