from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

import numpy as np

from .system_model import SystemModel, Task


TASK_TYPE_RANGES: Dict[str, Dict[str, Tuple[float, float]]] = {
    "compute_intensive": {
        "input_data_mb": (8.0, 35.0),
        "cpu_cycles_gcycles": (1.8, 4.5),
        "max_delay_s": (1.5, 3.0),
        "aoi_threshold_s": (2.0, 3.0),
        "energy_budget_j": (2.5, 6.0),
        "battery_ratio": (0.45, 1.0),
        "priority": (0.60, 0.90),
        "update_interval_s": (0.50, 1.00),
    },
    "data_intensive": {
        "input_data_mb": (30.0, 90.0),
        "cpu_cycles_gcycles": (0.8, 2.2),
        "max_delay_s": (2.5, 5.0),
        "aoi_threshold_s": (3.0, 5.0),
        "energy_budget_j": (2.0, 5.0),
        "battery_ratio": (0.40, 0.95),
        "priority": (0.50, 0.80),
        "update_interval_s": (0.80, 1.50),
    },
    "realtime_sensitive": {
        "input_data_mb": (2.0, 15.0),
        "cpu_cycles_gcycles": (0.5, 1.8),
        "max_delay_s": (0.35, 1.0),
        "aoi_threshold_s": (0.50, 1.0),
        "energy_budget_j": (1.0, 3.5),
        "battery_ratio": (0.55, 1.0),
        "priority": (0.80, 1.00),
        "update_interval_s": (0.10, 0.30),
    },
    "lightweight": {
        "input_data_mb": (0.5, 5.0),
        "cpu_cycles_gcycles": (0.1, 0.8),
        "max_delay_s": (0.8, 2.0),
        "aoi_threshold_s": (1.0, 2.0),
        "energy_budget_j": (0.5, 2.0),
        "battery_ratio": (0.50, 1.0),
        "priority": (0.40, 0.70),
        "update_interval_s": (0.30, 0.60),
    },
}

TASK_TYPE_ORDER = [
    "compute_intensive",
    "data_intensive",
    "realtime_sensitive",
    "lightweight",
]

TASK_TYPE_PROBABILITIES = np.array([0.28, 0.24, 0.28, 0.20])


def _sample_range(rng: np.random.Generator, values: Tuple[float, float]) -> float:
    return float(rng.uniform(values[0], values[1]))


def generate_system(
    seed: int,
    num_devices: int,
    num_edge_servers: int,
    num_cloud_servers: int,
    num_tasks: int,
) -> SystemModel:
    rng = np.random.default_rng(seed)

    device_cpu_hz = rng.uniform(0.8e9, 2.2e9, size=num_devices)
    edge_cpu_hz = rng.uniform(8.0e9, 18.0e9, size=num_edge_servers)
    cloud_cpu_hz = rng.uniform(25.0e9, 40.0e9, size=num_cloud_servers)
    device_energy_coeff = rng.uniform(0.8e-27, 1.4e-27, size=num_devices)
    device_tx_power_w = rng.uniform(0.2, 0.8, size=num_devices)

    device_to_edge_rate_bps = rng.uniform(8.0e6, 30.0e6, size=(num_devices, num_edge_servers))
    edge_to_cloud_rate_bps = rng.uniform(60.0e6, 150.0e6, size=(num_edge_servers, num_cloud_servers))

    if num_tasks <= len(TASK_TYPE_ORDER):
        task_types = TASK_TYPE_ORDER[:num_tasks]
    else:
        sampled = list(rng.choice(TASK_TYPE_ORDER, size=num_tasks - len(TASK_TYPE_ORDER), p=TASK_TYPE_PROBABILITIES))
        task_types = TASK_TYPE_ORDER + sampled
        rng.shuffle(task_types)

    tasks: List[Task] = []
    for task_id, task_type in enumerate(task_types):
        ranges = TASK_TYPE_RANGES[task_type]
        task = Task(
            task_id=task_id,
            source_device=int(rng.integers(0, num_devices)),
            task_type=task_type,
            input_data_mb=_sample_range(rng, ranges["input_data_mb"]),
            cpu_cycles_gcycles=_sample_range(rng, ranges["cpu_cycles_gcycles"]),
            max_delay_s=_sample_range(rng, ranges["max_delay_s"]),
            aoi_threshold_s=_sample_range(rng, ranges["aoi_threshold_s"]),
            energy_budget_j=_sample_range(rng, ranges["energy_budget_j"]),
            battery_ratio=_sample_range(rng, ranges["battery_ratio"]),
            priority=_sample_range(rng, ranges["priority"]),
            update_interval_s=_sample_range(rng, ranges["update_interval_s"]),
        )
        tasks.append(task)

    return SystemModel(
        num_devices=num_devices,
        num_edge_servers=num_edge_servers,
        num_cloud_servers=num_cloud_servers,
        tasks=tasks,
        device_cpu_hz=device_cpu_hz,
        edge_cpu_hz=edge_cpu_hz,
        cloud_cpu_hz=cloud_cpu_hz,
        device_energy_coeff=device_energy_coeff,
        device_tx_power_w=device_tx_power_w,
        device_to_edge_rate_bps=device_to_edge_rate_bps,
        edge_to_cloud_rate_bps=edge_to_cloud_rate_bps,
    )


def task_parameter_rows(tasks: Iterable[Task]) -> List[Dict[str, float | int | str]]:
    return [task.as_row() for task in tasks]


def task_generation_parameter_table() -> List[Dict[str, str]]:
    rows = []
    for task_type in TASK_TYPE_ORDER:
        values = TASK_TYPE_RANGES[task_type]
        row = {"task_type": task_type}
        for key, bounds in values.items():
            row[key] = f"{bounds[0]}-{bounds[1]}"
        rows.append(row)
    return rows
