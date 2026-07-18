from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .system_model import MODE_CLOUD, MODE_EDGE, MODE_LOCAL, SystemModel


@dataclass(frozen=True)
class FitnessWeights:
    energy: float = 0.15
    delay: float = 0.15
    aoi: float = 0.20
    qoe: float = 0.25
    fairness: float = 0.25


@dataclass(frozen=True)
class Metrics:
    """Metrics for one decoded offloading/computation-control solution.

    ``fitness`` uses the caller-supplied penalty scale and is therefore suitable
    for iteration-dependent search. ``reporting_fitness`` always uses the fixed
    reference penalty coefficient 1.0 so final solutions from different
    algorithms and sensitivity settings are directly comparable.
    """

    fitness: float
    reporting_fitness: float
    base_objective: float
    penalty: float
    energy: float
    delay: float
    aoi: float
    qoe: float
    fairness: float
    csr: float


DEFAULT_WEIGHTS = FitnessWeights()
REPORTING_PENALTY_SCALE = 1.0


def _clip_solution(solution: np.ndarray) -> np.ndarray:
    clipped = np.array(solution, dtype=float, copy=True)
    clipped[:, 0] = np.clip(np.rint(clipped[:, 0]), MODE_LOCAL, MODE_CLOUD)
    clipped[:, 1] = np.clip(clipped[:, 1], 0.2, 1.0)
    return clipped


def _jain_fairness(values: Iterable[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        return 0.0
    denom = arr.size * np.sum(arr * arr)
    if denom <= 0:
        return 0.0
    return float((np.sum(arr) ** 2) / denom)


def _user_qoe_fairness(qoes: np.ndarray, source_devices: np.ndarray) -> float:
    """Return Jain fairness over per-user mean QoE, not individual tasks."""

    qoe_arr = np.asarray(qoes, dtype=float)
    source_arr = np.asarray(source_devices, dtype=int)
    if qoe_arr.size == 0 or source_arr.size != qoe_arr.size:
        return 0.0
    user_means = [float(np.mean(qoe_arr[source_arr == device])) for device in np.unique(source_arr)]
    return _jain_fairness(user_means)


def fitness_from_components(base_objective: float, csr: float, penalty_scale: float) -> float:
    return float(base_objective + float(penalty_scale) * (1.0 - float(csr)))


def evaluate_solution(
    system: SystemModel,
    solution: np.ndarray,
    weights: FitnessWeights | None = None,
    penalty_scale: float = REPORTING_PENALTY_SCALE,
) -> Metrics:
    weights = weights or DEFAULT_WEIGHTS
    solution = _clip_solution(solution)
    modes = solution[:, 0].astype(int)
    resource = solution[:, 1]

    local_load = np.zeros(system.num_devices, dtype=int)
    edge_load = np.zeros(system.num_edge_servers, dtype=int)
    cloud_load = np.zeros(system.num_cloud_servers, dtype=int)

    for idx, task in enumerate(system.tasks):
        mode = modes[idx]
        if mode == MODE_LOCAL:
            local_load[task.source_device] += 1
        elif mode == MODE_EDGE:
            edge_load[system.nearest_edge(task.source_device)] += 1
        else:
            edge_id = system.nearest_edge(task.source_device)
            cloud_load[system.nearest_cloud(edge_id)] += 1

    energies: list[float] = []
    delays: list[float] = []
    aois: list[float] = []
    qoes: list[float] = []
    source_devices: list[int] = []
    satisfied_constraints = 0
    total_constraints = 0

    for idx, task in enumerate(system.tasks):
        mode = modes[idx]
        ratio = float(resource[idx])
        source = task.source_device
        edge_id = system.nearest_edge(source)
        cloud_id = system.nearest_cloud(edge_id)
        cycles = task.cpu_cycles
        data_bits = task.input_bits

        # The second decision variable is a bounded normalised computation-control value. The load
        # attenuation terms provide an load-adjusted service abstraction.
        if mode == MODE_LOCAL:
            load = max(1, local_load[source])
            freq = system.device_cpu_hz[source] * (0.35 + 0.65 * ratio) / (1.0 + 0.07 * (load - 1))
            delay = cycles / max(freq, 1.0)
            energy = system.device_energy_coeff[source] * cycles * (freq**2)
        elif mode == MODE_EDGE:
            load = max(1, edge_load[edge_id])
            uplink = data_bits / system.device_to_edge_rate_bps[source, edge_id]
            freq = system.edge_cpu_hz[edge_id] * (0.40 + 0.60 * ratio) / (1.0 + 0.035 * (load - 1))
            execution = cycles / max(freq, 1.0)
            delay = uplink + execution + 0.010
            energy = system.device_tx_power_w[source] * uplink + 0.015 * execution
        else:
            load = max(1, cloud_load[cloud_id])
            uplink = data_bits / system.device_to_edge_rate_bps[source, edge_id]
            backhaul = data_bits / system.edge_to_cloud_rate_bps[edge_id, cloud_id]
            freq = system.cloud_cpu_hz[cloud_id] * (0.45 + 0.55 * ratio) / (1.0 + 0.020 * (load - 1))
            execution = cycles / max(freq, 1.0)
            delay = uplink + backhaul + execution + 0.055
            energy = system.device_tx_power_w[source] * uplink + 0.010 * (backhaul + execution)

        # Average age under a periodic-update abstraction: half an update
        # interval plus service delay.
        aoi = 0.5 * task.update_interval_s + delay
        delay_score = np.exp(-delay / max(task.max_delay_s, 1.0e-9))
        energy_score = np.exp(-energy / max(task.energy_budget_j, 1.0e-9))
        aoi_score = np.exp(-aoi / max(task.aoi_threshold_s, 1.0e-9))
        qoe = task.priority * (0.45 * delay_score + 0.30 * energy_score + 0.25 * aoi_score)
        qoe = float(np.clip(qoe, 0.0, 1.0))

        energies.append(float(energy))
        delays.append(float(delay))
        aois.append(float(aoi))
        qoes.append(qoe)
        source_devices.append(source)

        for ok in (
            delay <= task.max_delay_s,
            energy <= task.energy_budget_j * max(task.battery_ratio, 0.1),
            aoi <= task.aoi_threshold_s,
        ):
            total_constraints += 1
            satisfied_constraints += int(ok)

    energy_arr = np.asarray(energies)
    delay_arr = np.asarray(delays)
    aoi_arr = np.asarray(aois)
    qoe_arr = np.asarray(qoes)
    csr = satisfied_constraints / total_constraints if total_constraints else 0.0
    fairness = _user_qoe_fairness(qoe_arr, np.asarray(source_devices))

    energy_norm = float(np.mean([e / max(t.energy_budget_j, 1.0e-9) for e, t in zip(energy_arr, system.tasks)]))
    delay_norm = float(np.mean([d / max(t.max_delay_s, 1.0e-9) for d, t in zip(delay_arr, system.tasks)]))
    aoi_norm = float(np.mean([a / max(t.aoi_threshold_s, 1.0e-9) for a, t in zip(aoi_arr, system.tasks)]))
    qoe = float(np.mean(qoe_arr)) if qoe_arr.size else 0.0
    base_objective = float(
        weights.energy * energy_norm
        + weights.delay * delay_norm
        + weights.aoi * aoi_norm
        + weights.qoe * (1.0 - qoe)
        + weights.fairness * (1.0 - fairness)
    )
    penalty = float(penalty_scale) * (1.0 - csr)
    fitness = fitness_from_components(base_objective, csr, penalty_scale)
    reporting_fitness = fitness_from_components(base_objective, csr, REPORTING_PENALTY_SCALE)

    return Metrics(
        fitness=fitness,
        reporting_fitness=reporting_fitness,
        base_objective=base_objective,
        penalty=penalty,
        energy=float(np.sum(energy_arr)),
        delay=float(np.mean(delay_arr)),
        aoi=float(np.mean(aoi_arr)),
        qoe=qoe,
        fairness=float(fairness),
        csr=float(csr),
    )
