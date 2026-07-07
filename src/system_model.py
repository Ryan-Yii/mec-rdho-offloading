from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np


@dataclass(frozen=True)
class Task:
    task_id: int
    source_device: int
    task_type: str
    input_data_mb: float
    cpu_cycles_gcycles: float
    max_delay_s: float
    aoi_threshold_s: float
    energy_budget_j: float
    battery_ratio: float
    priority: float
    update_interval_s: float

    @property
    def input_bits(self) -> float:
        return self.input_data_mb * 8.0e6

    @property
    def cpu_cycles(self) -> float:
        return self.cpu_cycles_gcycles * 1.0e9

    def as_row(self) -> Dict[str, float | int | str]:
        return {
            "task_id": self.task_id,
            "source_device": self.source_device,
            "task_type": self.task_type,
            "input_data_mb": round(self.input_data_mb, 6),
            "cpu_cycles_gcycles": round(self.cpu_cycles_gcycles, 6),
            "max_delay_s": round(self.max_delay_s, 6),
            "aoi_threshold_s": round(self.aoi_threshold_s, 6),
            "energy_budget_j": round(self.energy_budget_j, 6),
            "battery_ratio": round(self.battery_ratio, 6),
            "priority": round(self.priority, 6),
            "update_interval_s": round(self.update_interval_s, 6),
        }


@dataclass(frozen=True)
class SystemModel:
    num_devices: int
    num_edge_servers: int
    num_cloud_servers: int
    tasks: List[Task]
    device_cpu_hz: np.ndarray
    edge_cpu_hz: np.ndarray
    cloud_cpu_hz: np.ndarray
    device_energy_coeff: np.ndarray
    device_tx_power_w: np.ndarray
    device_to_edge_rate_bps: np.ndarray
    edge_to_cloud_rate_bps: np.ndarray

    def nearest_edge(self, device_id: int) -> int:
        return device_id % self.num_edge_servers

    def nearest_cloud(self, edge_id: int) -> int:
        return edge_id % self.num_cloud_servers


MODE_LOCAL = 0
MODE_EDGE = 1
MODE_CLOUD = 2


def clone_solution(solution: np.ndarray) -> np.ndarray:
    return np.array(solution, dtype=float, copy=True)
