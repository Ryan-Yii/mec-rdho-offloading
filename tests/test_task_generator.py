import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.task_generator import generate_system, task_parameter_rows


def test_same_seed_generates_same_tasks():
    first = generate_system(seed=20260701, num_devices=20, num_edge_servers=4, num_cloud_servers=2, num_tasks=8)
    second = generate_system(seed=20260701, num_devices=20, num_edge_servers=4, num_cloud_servers=2, num_tasks=8)
    assert [task.as_row() for task in first.tasks] == [task.as_row() for task in second.tasks]


def test_task_parameter_export_includes_all_task_types():
    system = generate_system(seed=20260702, num_devices=20, num_edge_servers=4, num_cloud_servers=2, num_tasks=40)
    rows = task_parameter_rows(system.tasks)
    task_types = {row["task_type"] for row in rows}
    assert {"compute_intensive", "data_intensive", "realtime_sensitive", "lightweight"} <= task_types
    assert {"input_data_mb", "cpu_cycles_gcycles", "max_delay_s", "aoi_threshold_s", "energy_budget_j", "battery_ratio"} <= set(rows[0])
