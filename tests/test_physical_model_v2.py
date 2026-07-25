import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.experiment_core import make_optimizer
from src.metrics import UtilityWeights, _user_qoe_fairness, decode_and_repair, evaluate_solution
from src.task_generator import generate_system


def _system(seed: int = 111, tasks: int = 12):
    return generate_system(seed=seed, num_devices=5, num_edge_servers=3, num_cloud_servers=2, num_tasks=tasks)


def test_decoder_keeps_one_legal_node_and_cpu_bounds():
    system = _system()
    encoded = np.full((len(system.tasks), 2), 1.0)
    decoded = decode_and_repair(system, encoded)
    assert decoded.hard_feasible
    assert len(decoded.node_ids) == len(system.tasks)
    for task, node, frequency in zip(system.tasks, decoded.node_ids, decoded.frequencies_hz):
        assert int(node) in system.legal_nodes_for_task(task)
        assert system.node_min_cpu_hz[node] <= frequency <= system.node_capacity_hz[node]


def test_capacity_projection_is_deterministic_and_conservative():
    system = _system(seed=222, tasks=30)
    encoded = np.ones((len(system.tasks), 2), dtype=float)
    first = decode_and_repair(system, encoded)
    second = decode_and_repair(system, encoded)
    assert np.array_equal(first.node_ids, second.node_ids)
    assert np.array_equal(first.frequencies_hz, second.frequencies_hz)
    usage = np.bincount(first.node_ids, weights=first.frequencies_hz, minlength=system.num_nodes)
    assert np.all(usage <= system.node_capacity_hz + 1.0e-6)


def test_repair_preserves_feasible_cpu_requests_without_saturating_nodes():
    system = generate_system(seed=223, num_devices=5, num_edge_servers=3, num_cloud_servers=2, num_tasks=5)
    encoded = np.zeros((len(system.tasks), 2), dtype=float)
    encoded[:, 1] = 0.25
    decoded = decode_and_repair(system, encoded)
    expected = np.asarray([
        system.device_min_cpu_hz[task.source_device]
        + 0.25 * (system.device_cpu_hz[task.source_device] - system.device_min_cpu_hz[task.source_device])
        for task in system.tasks
    ])
    assert np.allclose(decoded.frequencies_hz, expected)
    usage = np.bincount(decoded.node_ids, weights=decoded.frequencies_hz, minlength=system.num_nodes)
    active = usage > 0.0
    assert np.all(usage[active] < system.node_capacity_hz[active])


def test_utility_coefficients_are_validated_and_change_qoe():
    system = _system(seed=224, tasks=10)
    encoded = np.full((len(system.tasks), 2), 0.55)
    delay_oriented = evaluate_solution(
        system,
        encoded,
        utility_weights=UtilityWeights(delay=0.8, energy=0.1, aoi=0.1),
    )
    energy_oriented = evaluate_solution(
        system,
        encoded,
        utility_weights=UtilityWeights(delay=0.1, energy=0.8, aoi=0.1),
    )
    assert 0.0 <= delay_oriented.qoe <= 1.0
    assert 0.0 <= energy_oriented.qoe <= 1.0
    assert delay_oriented.qoe != pytest.approx(energy_oriented.qoe)
    with pytest.raises(ValueError):
        UtilityWeights(delay=0.5, energy=0.5, aoi=0.5)


def test_server_heterogeneity_scale_preserves_topology_and_changes_dispersion():
    homogeneous = generate_system(
        seed=225,
        num_devices=5,
        num_edge_servers=3,
        num_cloud_servers=2,
        num_tasks=8,
        server_heterogeneity_scale=0.0,
    )
    canonical = generate_system(
        seed=225,
        num_devices=5,
        num_edge_servers=3,
        num_cloud_servers=2,
        num_tasks=8,
        server_heterogeneity_scale=1.0,
    )
    assert np.array_equal(homogeneous.device_to_edge_rate_bps > 0.0, canonical.device_to_edge_rate_bps > 0.0)
    assert np.std(homogeneous.edge_cpu_hz) == pytest.approx(0.0, abs=1.0e-6)
    assert np.std(canonical.edge_cpu_hz) > 0.0


def test_default_server_heterogeneity_is_an_exact_identity():
    implicit = generate_system(seed=226, num_devices=5, num_edge_servers=3, num_cloud_servers=2, num_tasks=8)
    explicit = generate_system(
        seed=226,
        num_devices=5,
        num_edge_servers=3,
        num_cloud_servers=2,
        num_tasks=8,
        server_heterogeneity_scale=1.0,
    )
    assert np.array_equal(implicit.edge_cpu_hz, explicit.edge_cpu_hz)
    assert np.array_equal(implicit.cloud_cpu_hz, explicit.cloud_cpu_hz)
    assert np.array_equal(implicit.device_to_edge_rate_bps, explicit.device_to_edge_rate_bps)
    assert np.array_equal(implicit.edge_to_cloud_rate_bps, explicit.edge_to_cloud_rate_bps)


def test_local_node_is_always_the_source_device():
    system = _system(seed=333)
    encoded = np.zeros((len(system.tasks), 2), dtype=float)
    decoded = decode_and_repair(system, encoded)
    assert np.array_equal(decoded.node_ids, np.asarray([task.source_device for task in system.tasks]))


def test_known_local_delay_energy_and_aoi_formula():
    system = generate_system(seed=445, num_devices=1, num_edge_servers=1, num_cloud_servers=1, num_tasks=1)
    metrics = evaluate_solution(system, np.zeros((1, 2)))
    task = system.tasks[0]
    frequency = system.device_min_cpu_hz[task.source_device]
    assert metrics.delay == pytest.approx(task.cpu_cycles / frequency)
    assert metrics.energy == pytest.approx(system.device_energy_coeff[task.source_device] * task.cpu_cycles * frequency**2)
    assert metrics.aoi == pytest.approx(task.update_interval_s / 2.0 + metrics.delay)


def test_qoe_range_and_user_level_fairness_excludes_priority():
    system = _system(seed=555)
    metrics = evaluate_solution(system, np.full((len(system.tasks), 2), 0.7))
    assert 0.0 <= metrics.qoe <= 1.0
    assert 0.0 <= metrics.fairness <= 1.0
    assert _user_qoe_fairness(np.asarray([0.5, 0.5, 0.5]), np.asarray([0, 0, 1])) == pytest.approx(1.0)


def test_reporting_fitness_is_independent_of_dynamic_search_iteration():
    system = _system(seed=666)
    solution = np.full((len(system.tasks), 2), 0.75)
    early = evaluate_solution(system, solution, penalty_scale=0.5)
    late = evaluate_solution(system, solution, penalty_scale=8.0)
    assert early.reporting_fitness == pytest.approx(late.reporting_fitness)
    assert early.fitness != late.fitness or early.csr == pytest.approx(1.0)


def test_all_algorithms_share_encoding_and_capacity_repair():
    system = _system(seed=777, tasks=8)
    for name in ("RDHO", "RIME", "DBO", "TLBO-HHO", "CWTSSA", "Greedy-ED"):
        result = make_optimizer(name, system, seed=777, max_iter=2, population_size=6).optimize()
        assert decode_and_repair(system, result.solution).hard_feasible


def test_seed_reproducibility_for_physical_model():
    system = _system(seed=888, tasks=8)
    first = make_optimizer("RDHO-core", system, seed=999, max_iter=3, population_size=6).optimize()
    second = make_optimizer("RDHO-core", system, seed=999, max_iter=3, population_size=6).optimize()
    assert np.array_equal(first.solution, second.solution)
    assert first.fitness == pytest.approx(second.fitness)
