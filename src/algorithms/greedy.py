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
    ) -> None:
        self.system = system
        self.weights = weights or FitnessWeights(energy=0.4, delay=0.4, aoi=0.2, qoe=0.0, fairness=0.0)

    def optimize(self) -> OptimizerResult:
        solution = greedy_seed_solution(self.system, self.weights)
        metrics = evaluate_solution(self.system, solution, weights=self.weights)
        return OptimizerResult(solution=solution, fitness=metrics.fitness, history=[metrics.fitness])
