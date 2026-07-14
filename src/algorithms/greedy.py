from __future__ import annotations

from ..metrics import FitnessWeights
from ..system_model import SystemModel
from .base import MetaheuristicOptimizer, OptimizerResult, greedy_seed_solution


class GreedyEnergyDelay(MetaheuristicOptimizer):
    def __init__(
        self,
        system: SystemModel,
        max_iter: int = 0,
        population_size: int = 0,
        seed: int = 0,
        weights: FitnessWeights | None = None,
        penalty_base: float = 1.0,
        max_evaluations: int | None = None,
        **_: object,
    ) -> None:
        super().__init__(
            system=system,
            max_iter=max_iter,
            population_size=max(1, population_size),
            seed=seed,
            weights=weights,
            penalty_base=penalty_base,
            max_evaluations=max_evaluations,
        )

    def optimize(self) -> OptimizerResult:
        solution = greedy_seed_solution(self.system, self.weights, budget=self.evaluation_budget)
        metrics = self.evaluate_metrics(solution, penalty_scale=1.0)
        return OptimizerResult(
            solution=solution,
            fitness=metrics.reported_fitness,
            reported_fitness=metrics.reported_fitness,
            search_fitness=metrics.search_fitness,
            history=[metrics.reported_fitness],
            nfe_used=self.evaluation_budget.used,
            max_evaluations=self.max_evaluations,
            metrics=metrics,
        )
