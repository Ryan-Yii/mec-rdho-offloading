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
    """Immutable physical cloud-edge-device scenario.

    Node IDs use one global namespace: devices first, then edge servers, then
    cloud servers.  CPU capacity and all allocated frequencies use Hz.
    """

    num_devices: int
    num_edge_servers: int
    num_cloud_servers: int
    tasks: List[Task]
    device_cpu_hz: np.ndarray
    edge_cpu_hz: np.ndarray
    cloud_cpu_hz: np.ndarray
    device_min_cpu_hz: np.ndarray
    edge_min_cpu_hz: np.ndarray
    cloud_min_cpu_hz: np.ndarray
    device_energy_coeff: np.ndarray
    device_tx_power_w: np.ndarray
    device_to_edge_rate_bps: np.ndarray
    edge_to_cloud_rate_bps: np.ndarray
    edge_service_overhead_s: float = 0.010
    cloud_service_overhead_s: float = 0.055

    @property
    def num_nodes(self) -> int:
        return self.num_devices + self.num_edge_servers + self.num_cloud_servers

    @property
    def node_capacity_hz(self) -> np.ndarray:
        return np.concatenate((self.device_cpu_hz, self.edge_cpu_hz, self.cloud_cpu_hz))

    @property
    def node_min_cpu_hz(self) -> np.ndarray:
        return np.concatenate((self.device_min_cpu_hz, self.edge_min_cpu_hz, self.cloud_min_cpu_hz))

    def edge_node_id(self, edge_id: int) -> int:
        return self.num_devices + int(edge_id)

    def cloud_node_id(self, cloud_id: int) -> int:
        return self.num_devices + self.num_edge_servers + int(cloud_id)

    def node_kind(self, node_id: int) -> str:
        if 0 <= node_id < self.num_devices:
            return "device"
        if self.num_devices <= node_id < self.num_devices + self.num_edge_servers:
            return "edge"
        if self.num_devices + self.num_edge_servers <= node_id < self.num_nodes:
            return "cloud"
        raise ValueError(f"invalid global node ID: {node_id}")

    def edge_index(self, node_id: int) -> int:
        if self.node_kind(node_id) != "edge":
            raise ValueError(f"node {node_id} is not an edge server")
        return node_id - self.num_devices

    def cloud_index(self, node_id: int) -> int:
        if self.node_kind(node_id) != "cloud":
            raise ValueError(f"node {node_id} is not a cloud server")
        return node_id - self.num_devices - self.num_edge_servers

    def legal_nodes_for_task(self, task: Task) -> List[int]:
        """Return all legal execution nodes in deterministic global-ID order."""

        nodes = [task.source_device]
        reachable_edges = [
            edge_id
            for edge_id in range(self.num_edge_servers)
            if self.device_to_edge_rate_bps[task.source_device, edge_id] > 0.0
        ]
        nodes.extend(self.edge_node_id(edge_id) for edge_id in reachable_edges)
        for cloud_id in range(self.num_cloud_servers):
            if any(self.edge_to_cloud_rate_bps[edge_id, cloud_id] > 0.0 for edge_id in reachable_edges):
                nodes.append(self.cloud_node_id(cloud_id))
        return nodes

    def relay_edge_for_cloud(self, task: Task, cloud_node_id: int) -> int:
        """Choose the fastest legal fixed relay edge for a selected cloud node."""

        cloud_id = self.cloud_index(cloud_node_id)
        candidates = []
        for edge_id in range(self.num_edge_servers):
            uplink = self.device_to_edge_rate_bps[task.source_device, edge_id]
            backhaul = self.edge_to_cloud_rate_bps[edge_id, cloud_id]
            if uplink > 0.0 and backhaul > 0.0:
                transit = task.input_bits / uplink + task.input_bits / backhaul
                candidates.append((transit, edge_id))
        if not candidates:
            raise ValueError(f"task {task.task_id} has no valid path to cloud node {cloud_node_id}")
        return min(candidates)[1]


MODE_LOCAL = 0
MODE_EDGE = 1
MODE_CLOUD = 2


def clone_solution(solution: np.ndarray) -> np.ndarray:
    return np.array(solution, dtype=float, copy=True)
