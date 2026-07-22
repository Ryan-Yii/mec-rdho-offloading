from __future__ import annotations

from ..metrics import FitnessWeights, evaluate_solution
from ..system_model import SystemModel
from .base import OptimizerResult, greedy_seed_solution


class GreedyEnergyDelay:
    def __init__(
        self,
        system: SystemModel,
        max_iter: int = 0,
        population_size: int = 0,
        seed: int = 0,
        weights: FitnessWeights | None = None,
        penalty_base: float = 1.0,
        **_: object,
    ) -> None:
        self.system = system
        # Greedy-ED is named after its construction rule; reporting still uses
        # the common physical objective and repair for a fair comparison.
        self.weights = weights or FitnessWeights()
        self.nfe = 0

    def _evaluate(self, solution):
        self.nfe += 1
        return evaluate_solution(self.system, solution, weights=self.weights, penalty_scale=1.0)

    def optimize(self) -> OptimizerResult:
        self.nfe = 0
        solution = greedy_seed_solution(self.system, self.weights, evaluator=self._evaluate)
        metrics = self._evaluate(solution)
        return OptimizerResult(
            solution=solution,
            fitness=metrics.reporting_fitness,
            history=[metrics.reporting_fitness],
            search_fitness=metrics.fitness,
            search_history=[metrics.fitness],
            nfe=self.nfe,
            pre_refinement_fitness=metrics.reporting_fitness,
            local_refinement_gain=0.0,
        )
