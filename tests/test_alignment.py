import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.experiment_core import make_optimizer, run_single_algorithm
from src.algorithms.base import MetaheuristicOptimizer
from src.metrics import _user_qoe_fairness, evaluate_solution
from src.task_generator import generate_system


def test_metrics_expose_base_and_penalty_decomposition():
    system = generate_system(seed=11, num_devices=4, num_edge_servers=2, num_cloud_servers=1, num_tasks=8)
    solution = np.column_stack((np.ones(8), np.full(8, 0.7)))
    metrics = evaluate_solution(system, solution, penalty_scale=3.5)

    assert metrics.penalty == pytest.approx(3.5 * (1.0 - metrics.csr))
    assert metrics.fitness == pytest.approx(metrics.base_objective + metrics.penalty)
    assert metrics.reporting_fitness == pytest.approx(metrics.base_objective + (1.0 - metrics.csr))


def test_user_qoe_fairness_aggregates_tasks_by_source_device():
    qoes = np.asarray([1.0, 0.0, 0.5])
    source_devices = np.asarray([0, 0, 1])
    # Per-user means are [0.5, 0.5], hence perfect fairness.
    assert _user_qoe_fairness(qoes, source_devices) == pytest.approx(1.0)


class _DeterministicOptimizer(MetaheuristicOptimizer):
    """One-dimensional marker encoded in the computation-control slot."""

    def initialize_population(self) -> np.ndarray:
        pop = np.zeros((2, len(self.system.tasks), 2), dtype=float)
        pop[:, :, 0] = 1.0
        pop[0, :, 1] = 0.2
        pop[1, :, 1] = 0.4
        return pop

    def step(self, population, fitness, best, worst, iteration):
        candidate = np.array(population, copy=True)
        candidate[0, :, 1] = 0.8
        candidate[1, :, 1] = 1.0
        return candidate


def test_optimizer_history_uses_fixed_reference_reporting_fitness():
    system = generate_system(seed=12, num_devices=3, num_edge_servers=1, num_cloud_servers=1, num_tasks=4)
    optimizer = _DeterministicOptimizer(system=system, max_iter=2, population_size=2, seed=0, penalty_base=7.0)
    result = optimizer.optimize()

    reported = evaluate_solution(system, result.solution, penalty_scale=1.0).reporting_fitness
    assert result.fitness == pytest.approx(reported)
    assert result.history[-1] == pytest.approx(reported)
    assert result.nfe >= 2


def test_rdho_ablation_switches_do_not_disable_local_refinement():
    system = generate_system(seed=13, num_devices=5, num_edge_servers=2, num_cloud_servers=1, num_tasks=8)
    ablated = make_optimizer(
        "RDHO-w/o adaptive role allocation",
        system=system,
        seed=13,
        max_iter=2,
        population_size=6,
    )
    core = make_optimizer(
        "RDHO-core",
        system=system,
        seed=13,
        max_iter=2,
        population_size=6,
    )
    assert ablated.local_refinement is True
    assert core.local_refinement is False


def test_greedy_ed_accepts_common_optimizer_arguments_and_reports_nfe():
    system = generate_system(seed=14, num_devices=5, num_edge_servers=2, num_cloud_servers=1, num_tasks=8)
    optimizer = make_optimizer(
        "Greedy-ED",
        system=system,
        seed=14,
        max_iter=3,
        population_size=6,
        penalty_base=2.0,
    )
    result = optimizer.optimize()
    assert result.nfe > 0


def test_experiment_row_contains_reporting_components_and_nfe():
    system = generate_system(seed=15, num_devices=5, num_edge_servers=2, num_cloud_servers=1, num_tasks=8)
    row = run_single_algorithm(system, "RDHO-core", run_id=1, seed=15, max_iter=2, population_size=6)
    assert {"fitness", "base_objective", "penalty", "nfe", "pre_refinement_fitness", "local_refinement_gain"} <= set(row)



def test_wilcoxon_output_includes_holm_effect_size_and_wtl(tmp_path):
    from experiments.experiment_core import write_wilcoxon_results

    rows = []
    for run_id in range(1, 7):
        rows.append({"run_id": run_id, "algorithm": "RDHO", "fitness": float(run_id)})
        rows.append({"run_id": run_id, "algorithm": "RIME", "fitness": float(run_id + 1)})
    result = write_wilcoxon_results(rows, tmp_path / "stats.csv")
    assert {"w_statistic", "p_value", "p_holm", "median_difference", "rank_biserial", "wins", "ties", "losses"} <= set(result.columns)
    assert result.iloc[0]["wins"] == 6
    assert result.iloc[0]["median_difference"] == -1.0
    assert result.iloc[0]["rank_biserial"] == -1.0


def test_additional_figure_generators_create_files(tmp_path):
    import pandas as pd
    from experiments.analyze_results import plot_ablation, plot_scalability

    ablation = pd.DataFrame({
        "algorithm": ["RDHO-full", "RDHO-core"],
        "fitness": [0.8, 0.9],
        "csr": [0.7, 0.65],
    })
    scale = pd.DataFrame({
        "task_number": [20, 40],
        "fitness": [0.8, 0.9],
        "csr": [0.7, 0.68],
        "runtime": [2.0, 4.0],
    })
    ablation_path = tmp_path / "ablation.png"
    scale_path = tmp_path / "scale.png"
    plot_ablation(ablation, ablation_path)
    plot_scalability(scale, scale_path)
    assert ablation_path.exists() and ablation_path.stat().st_size > 0
    assert scale_path.exists() and scale_path.stat().st_size > 0


def test_rdho_follower_foraging_uses_coordinate_specific_bounds():
    from src.algorithms.rdho import RDHO

    system = generate_system(seed=16, num_devices=3, num_edge_servers=1, num_cloud_servers=1, num_tasks=4)
    optimizer = RDHO(system=system, max_iter=10, population_size=6, seed=0)
    current = np.column_stack((np.full(4, 1.0), np.full(4, 0.6)))
    best = np.column_stack((np.full(4, 1.0), np.full(4, 0.6)))

    class _NoPunctureRng:
        def random(self, size=None):
            if size is None:
                return 1.0
            return np.ones(size, dtype=float)

    optimizer.rng = _NoPunctureRng()
    updated = optimizer._follower_update(current, best, iteration=10)
    # With c1=c2=1, r should use L_r=0.2 and U_r=1.0:
    # 0.6 + (0.6-0.2) + (0.6-1.0) = 0.6.
    assert updated[:, 1] == pytest.approx(np.full(4, 0.6))


def test_all_rdho_variants_share_same_base_random_stream():
    system = generate_system(seed=17, num_devices=3, num_edge_servers=1, num_cloud_servers=1, num_tasks=4)
    full = make_optimizer("RDHO-full", system=system, seed=17, max_iter=2, population_size=6)
    core = make_optimizer("RDHO-core", system=system, seed=17, max_iter=2, population_size=6)
    assert full.rng.random() == pytest.approx(core.rng.random())
