import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.experiment_core import make_optimizer, run_single_algorithm
from src.task_generator import generate_system


def test_single_algorithm_result_has_required_columns():
    system = generate_system(seed=20260704, num_devices=5, num_edge_servers=2, num_cloud_servers=1, num_tasks=8)
    result = run_single_algorithm(
        system=system,
        algorithm_name="RDHO",
        run_id=1,
        seed=20260704,
        max_iter=3,
        population_size=6,
    )
    expected = {"run_id", "seed", "algorithm", "fitness", "energy", "delay", "aoi", "qoe", "fairness", "csr", "runtime"}
    assert expected <= set(result)
    assert result["algorithm"] == "RDHO"


def test_rdho_dynamic_penalty_accepts_lambda0_and_alpha():
    system = generate_system(seed=20260704, num_devices=5, num_edge_servers=2, num_cloud_servers=1, num_tasks=8)
    optimizer = make_optimizer(
        algorithm_name="RDHO",
        system=system,
        seed=20260704,
        max_iter=10,
        population_size=6,
        penalty_base=0.5,
        dynamic_penalty_alpha=3.0,
    )
    assert optimizer.penalty_scale(10) == pytest.approx(0.5 * ((1.0 + 2.0) ** 3.0))


def test_write_rows_uses_lf_line_endings(tmp_path):
    from src.utils.io import write_rows

    output = tmp_path / 'rows.csv'
    write_rows(output, [{'a': 1}, {'a': 2}])

    payload = output.read_bytes()
    assert b'\r\n' not in payload
    assert payload == b'a\n1\n2\n'


def test_ablation_does_not_reuse_legacy_main_results():
    import inspect
    import experiments.run_ablation_30 as module

    assert "reuse_main_rdho_rows" not in inspect.getsource(module)
