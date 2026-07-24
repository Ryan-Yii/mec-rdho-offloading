from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from ..metrics import FitnessWeights, Metrics, UtilityWeights, evaluate_solution
from ..system_model import SystemModel


@dataclass
class EvaluationBudgetManager:
    """Hard, uncached NFE accounting for the controlled evidence runners."""

    system: SystemModel
    total_budget: int
    weights: FitnessWeights
    utility_weights: UtilityWeights
    nfe: int = 0
    stage_counts: Counter = field(default_factory=Counter)
    reassignment_count: int = 0
    repair_failure_count: int = 0

    def remaining(self) -> int:
        return self.total_budget - self.nfe

    def evaluate(self, solution: np.ndarray, *, stage: str, penalty_scale: float) -> Metrics:
        if self.nfe >= self.total_budget:
            raise RuntimeError(f"NFE budget exhausted before {stage} evaluation")
        encoded = np.clip(np.asarray(solution, dtype=float), 0.0, 1.0)
        requested_nodes = np.asarray(
            [
                self._encoded_node(task_idx, value)
                for task_idx, value in enumerate(encoded[:, 0])
            ],
            dtype=int,
        )
        try:
            metrics = evaluate_solution(
                self.system,
                encoded,
                weights=self.weights,
                utility_weights=self.utility_weights,
                penalty_scale=penalty_scale,
            )
        except ValueError:
            self.repair_failure_count += 1
            raise
        self.nfe += 1
        self.stage_counts[stage] += 1
        self.reassignment_count += int(
            np.count_nonzero(requested_nodes != np.asarray(metrics.node_ids, dtype=int))
        )
        return metrics

    def _encoded_node(self, task_idx: int, coordinate: float) -> int:
        legal = self.system.legal_nodes_for_task(self.system.tasks[task_idx])
        index = min(int(np.floor(float(np.clip(coordinate, 0.0, 1.0)) * len(legal))), len(legal) - 1)
        return int(legal[index])
