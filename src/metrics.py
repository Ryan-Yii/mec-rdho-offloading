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
class UtilityWeights:
    """Internal coefficients of the model-based task utility."""

    delay: float = 0.45
    energy: float = 0.30
    aoi: float = 0.25

    def __post_init__(self) -> None:
        values = (self.delay, self.energy, self.aoi)
        if any(value < 0.0 for value in values) or not np.isclose(sum(values), 1.0):
            raise ValueError("utility weights must be non-negative and sum to 1.0")


@dataclass(frozen=True)
class DecodedSolution:
    """Physical assignment and allocation after deterministic repair."""

    node_ids: np.ndarray
    frequencies_hz: np.ndarray
    modes: np.ndarray
    relay_edge_ids: np.ndarray
    capacity_utilisation: np.ndarray
    hard_feasible: bool


@dataclass(frozen=True)
class Metrics:
    """Metrics for one physical offloading and allocation solution.

    `fitness` uses the supplied search penalty. `reporting_fitness` always uses
    the fixed reference multiplier, so it is independent of a final iteration.
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
    hard_feasible: bool
    capacity_utilisation_mean: float
    capacity_utilisation_max: float
    assignment_unique: bool
    node_ids: tuple[int, ...]
    frequencies_hz: tuple[float, ...]


DEFAULT_WEIGHTS = FitnessWeights()
DEFAULT_UTILITY_WEIGHTS = UtilityWeights()
REPORTING_PENALTY_SCALE = 1.0


def _jain_fairness(values: Iterable[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        return 0.0
    denom = arr.size * np.sum(arr * arr)
    if denom <= 0.0:
        return 0.0
    return float((np.sum(arr) ** 2) / denom)


def _user_qoe_fairness(qoes: np.ndarray, source_devices: np.ndarray) -> float:
    """Jain fairness over mean *base* QoE of active source devices."""

    qoe_arr = np.asarray(qoes, dtype=float)
    source_arr = np.asarray(source_devices, dtype=int)
    if qoe_arr.size == 0 or source_arr.size != qoe_arr.size:
        return 0.0
    means = [float(np.mean(qoe_arr[source_arr == device])) for device in np.unique(source_arr)]
    return _jain_fairness(means)


def fitness_from_components(base_objective: float, csr: float, penalty_scale: float) -> float:
    return float(base_objective + float(penalty_scale) * (1.0 - float(csr)))


def _normalise_solution_shape(system: SystemModel, solution: np.ndarray) -> np.ndarray:
    arr = np.asarray(solution, dtype=float)
    expected = (len(system.tasks), 2)
    if arr.shape != expected:
        raise ValueError(f"solution shape must be {expected}, got {arr.shape}")
    return np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=0.0)


def _decoded_mode(system: SystemModel, node_id: int) -> int:
    kind = system.node_kind(int(node_id))
    if kind == "device":
        return MODE_LOCAL
    if kind == "edge":
        return MODE_EDGE
    return MODE_CLOUD


def _select_node(system: SystemModel, task_idx: int, encoded_node: float) -> int:
    legal = system.legal_nodes_for_task(system.tasks[task_idx])
    if not legal:
        raise ValueError(f"task {task_idx} has no legal execution node")
    coordinate = float(np.clip(encoded_node, 0.0, 1.0))
    index = min(int(np.floor(coordinate * len(legal))), len(legal) - 1)
    return int(legal[index])


def _requested_frequency(system: SystemModel, node_id: int, encoded_resource: float) -> float:
    minimum = float(system.node_min_cpu_hz[node_id])
    capacity = float(system.node_capacity_hz[node_id])
    resource = float(np.clip(encoded_resource, 0.0, 1.0))
    return minimum + resource * (capacity - minimum)


def _reassign_minimum_overflow(system: SystemModel, node_ids: np.ndarray) -> np.ndarray:
    """Make every node able to host its assignments at its minimum CPU rate."""

    repaired = np.asarray(node_ids, dtype=int).copy()
    min_cpu = system.node_min_cpu_hz
    capacities = system.node_capacity_hz
    for _ in range(max(1, len(system.tasks) * system.num_nodes)):
        usage = np.bincount(repaired, weights=min_cpu[repaired], minlength=system.num_nodes)
        overloaded = np.flatnonzero(usage > capacities + 1.0e-6)
        if overloaded.size == 0:
            return repaired
        changed = False
        for node_id in overloaded:
            assigned = np.flatnonzero(repaired == node_id)
            # Deterministic task order avoids random repairs and improves testability.
            for task_idx in assigned[::-1]:
                legal = system.legal_nodes_for_task(system.tasks[int(task_idx)])
                alternatives = [candidate for candidate in legal if candidate != int(node_id)]
                if not alternatives:
                    continue
                candidate_usage = usage.copy()
                candidate_usage[node_id] -= min_cpu[node_id]
                feasible = [
                    candidate
                    for candidate in alternatives
                    if candidate_usage[candidate] + min_cpu[candidate] <= capacities[candidate] + 1.0e-6
                ]
                if feasible:
                    # Largest residual slack, then smallest node ID.
                    target = min(feasible, key=lambda x: (-(capacities[x] - candidate_usage[x] - min_cpu[x]), x))
                    repaired[task_idx] = target
                    changed = True
                    break
        if not changed:
            break
    raise ValueError("no feasible minimum-frequency assignment exists for this scenario")


def decode_and_repair(system: SystemModel, solution: np.ndarray) -> DecodedSolution:
    """Decode a normalised vector into a capacity-feasible physical solution."""

    encoded = _normalise_solution_shape(system, solution)
    node_ids = np.asarray([_select_node(system, idx, value) for idx, value in enumerate(encoded[:, 0])], dtype=int)
    node_ids = _reassign_minimum_overflow(system, node_ids)
    requested = np.asarray(
        [_requested_frequency(system, int(node_id), value) for node_id, value in zip(node_ids, encoded[:, 1])], dtype=float
    )
    frequencies = np.asarray(system.node_min_cpu_hz[node_ids], dtype=float)
    capacities = np.asarray(system.node_capacity_hz, dtype=float)
    for node_id in range(system.num_nodes):
        task_indices = np.flatnonzero(node_ids == node_id)
        if task_indices.size == 0:
            continue
        minimum = float(system.node_min_cpu_hz[node_id])
        # Work in excess-over-minimum space.  Its total budget is capacity
        # minus the minimum allocation retained by every assigned task.
        residual = max(0.0, float(capacities[node_id] - task_indices.size * minimum))
        requested_excess = np.maximum(requested[task_indices] - minimum, 0.0)
        total_excess = float(np.sum(requested_excess))
        if total_excess <= residual:
            # The node is not saturated: retain each task's decoded physical
            # CPU request instead of silently allocating unused capacity.
            frequencies[task_indices] = minimum + requested_excess
        elif total_excess > 0.0 and residual > 0.0:
            # Only an overloaded node is projected proportionally in
            # excess-over-minimum space, preserving every task's minimum CPU.
            frequencies[task_indices] = minimum + residual * (requested_excess / total_excess)
    usage = np.bincount(node_ids, weights=frequencies, minlength=system.num_nodes)
    utilisation = usage / capacities
    modes = np.asarray([_decoded_mode(system, int(node)) for node in node_ids], dtype=int)
    relays = np.full(len(system.tasks), -1, dtype=int)
    for task_idx, node_id in enumerate(node_ids):
        if modes[task_idx] == MODE_CLOUD:
            relays[task_idx] = system.relay_edge_for_cloud(system.tasks[task_idx], int(node_id))
    valid_nodes = all(int(node) in system.legal_nodes_for_task(task) for node, task in zip(node_ids, system.tasks))
    allocation_is_legal = np.all(
        frequencies <= system.node_capacity_hz[node_ids] + 1.0e-6
    ) and np.all(
        frequencies >= system.node_min_cpu_hz[node_ids] - 1.0e-6
    )
    hard_feasible = bool(
        valid_nodes
        and np.all(np.isfinite(frequencies))
        and allocation_is_legal
        # Frequencies are in Hz, so a floating-point accumulation tolerance
        # must scale with the node capacity rather than use an absolute hertz.
        and np.all(usage <= capacities + np.maximum(1.0e-6, capacities * 1.0e-12))
    )
    return DecodedSolution(
        node_ids=node_ids,
        frequencies_hz=frequencies,
        modes=modes,
        relay_edge_ids=relays,
        capacity_utilisation=utilisation,
        hard_feasible=hard_feasible,
    )


def evaluate_solution(
    system: SystemModel,
    solution: np.ndarray,
    weights: FitnessWeights | None = None,
    utility_weights: UtilityWeights | None = None,
    penalty_scale: float = REPORTING_PENALTY_SCALE,
) -> Metrics:
    weights = weights or DEFAULT_WEIGHTS
    utility_weights = utility_weights or DEFAULT_UTILITY_WEIGHTS
    decoded = decode_and_repair(system, solution)
    energies: list[float] = []
    delays: list[float] = []
    aois: list[float] = []
    base_utilities: list[float] = []
    priorities: list[float] = []
    sources: list[int] = []
    satisfied = 0
    total = 0

    for index, task in enumerate(system.tasks):
        node_id = int(decoded.node_ids[index])
        mode = int(decoded.modes[index])
        frequency = float(decoded.frequencies_hz[index])
        computation = task.cpu_cycles / frequency
        if mode == MODE_LOCAL:
            delay = computation
            energy = system.device_energy_coeff[task.source_device] * task.cpu_cycles * frequency**2
        elif mode == MODE_EDGE:
            edge_id = system.edge_index(node_id)
            uplink = task.input_bits / system.device_to_edge_rate_bps[task.source_device, edge_id]
            delay = uplink + computation + system.edge_service_overhead_s
            energy = system.device_tx_power_w[task.source_device] * uplink
        else:
            edge_id = int(decoded.relay_edge_ids[index])
            cloud_id = system.cloud_index(node_id)
            uplink = task.input_bits / system.device_to_edge_rate_bps[task.source_device, edge_id]
            backhaul = task.input_bits / system.edge_to_cloud_rate_bps[edge_id, cloud_id]
            delay = uplink + backhaul + computation + system.cloud_service_overhead_s
            energy = system.device_tx_power_w[task.source_device] * uplink

        aoi = 0.5 * task.update_interval_s + delay
        delay_score = float(np.exp(-delay / max(task.max_delay_s, 1.0e-12)))
        energy_score = float(np.exp(-energy / max(task.energy_budget_j, 1.0e-12)))
        aoi_score = float(np.exp(-aoi / max(task.aoi_threshold_s, 1.0e-12)))
        utility = float(np.clip(
            utility_weights.delay * delay_score
            + utility_weights.energy * energy_score
            + utility_weights.aoi * aoi_score,
            0.0,
            1.0,
        ))

        energies.append(float(energy))
        delays.append(float(delay))
        aois.append(float(aoi))
        base_utilities.append(utility)
        priorities.append(task.priority)
        sources.append(task.source_device)
        for ok in (
            delay <= task.max_delay_s,
            energy <= task.energy_budget_j * max(task.battery_ratio, 0.1),
            aoi <= task.aoi_threshold_s,
        ):
            total += 1
            satisfied += int(ok)

    energy_arr = np.asarray(energies)
    delay_arr = np.asarray(delays)
    aoi_arr = np.asarray(aois)
    utility_arr = np.asarray(base_utilities)
    priority_arr = np.asarray(priorities)
    csr = float(satisfied / total) if total else 0.0
    qoe = float(np.average(utility_arr, weights=priority_arr)) if utility_arr.size else 0.0
    fairness = _user_qoe_fairness(utility_arr, np.asarray(sources, dtype=int))
    energy_norm = float(np.mean([value / max(task.energy_budget_j, 1.0e-12) for value, task in zip(energy_arr, system.tasks)]))
    delay_norm = float(np.mean([value / max(task.max_delay_s, 1.0e-12) for value, task in zip(delay_arr, system.tasks)]))
    aoi_norm = float(np.mean([value / max(task.aoi_threshold_s, 1.0e-12) for value, task in zip(aoi_arr, system.tasks)]))
    base_objective = float(
        weights.energy * energy_norm
        + weights.delay * delay_norm
        + weights.aoi * aoi_norm
        + weights.qoe * (1.0 - qoe)
        + weights.fairness * (1.0 - fairness)
    )
    penalty = float(penalty_scale) * (1.0 - csr)
    reporting = fitness_from_components(base_objective, csr, REPORTING_PENALTY_SCALE)
    active = decoded.capacity_utilisation[decoded.capacity_utilisation > 0.0]
    return Metrics(
        fitness=fitness_from_components(base_objective, csr, penalty_scale),
        reporting_fitness=reporting,
        base_objective=base_objective,
        penalty=penalty,
        energy=float(np.sum(energy_arr)),
        delay=float(np.mean(delay_arr)),
        aoi=float(np.mean(aoi_arr)),
        qoe=qoe,
        fairness=float(fairness),
        csr=csr,
        hard_feasible=decoded.hard_feasible,
        capacity_utilisation_mean=float(np.mean(active)) if active.size else 0.0,
        capacity_utilisation_max=float(np.max(decoded.capacity_utilisation)) if decoded.capacity_utilisation.size else 0.0,
        assignment_unique=bool(decoded.node_ids.size == len(system.tasks)),
        node_ids=tuple(int(value) for value in decoded.node_ids),
        frequencies_hz=tuple(float(value) for value in decoded.frequencies_hz),
    )
