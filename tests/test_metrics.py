import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.metrics import evaluate_solution
from src.task_generator import generate_system


def test_metrics_are_finite_and_bounded():
    system = generate_system(seed=20260703, num_devices=5, num_edge_servers=2, num_cloud_servers=1, num_tasks=6)
    solution = np.zeros((len(system.tasks), 2), dtype=float)
    solution[:, 0] = 1
    solution[:, 1] = 0.75
    metrics = evaluate_solution(system, solution)
    assert np.isfinite(metrics.fitness)
    assert metrics.energy > 0
    assert metrics.delay > 0
    assert 0 <= metrics.qoe <= 1
    assert 0 <= metrics.fairness <= 1
    assert 0 <= metrics.csr <= 1
