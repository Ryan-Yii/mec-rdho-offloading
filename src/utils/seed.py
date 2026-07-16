from __future__ import annotations

import random

import numpy as np


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def derive_seed(seed: int, *labels: object) -> int:
    value = seed & 0xFFFFFFFF
    for label in labels:
        text = str(label)
        for char in text:
            value = ((value * 131) + ord(char)) & 0xFFFFFFFF
        value = ((value * 131) + 17) & 0xFFFFFFFF
    return value


def derive_scenario_seed(master_seed: int, scenario_id: int, replicate_id: int) -> int:
    return derive_seed(master_seed, "scenario", scenario_id, replicate_id)


def derive_algorithm_seed(master_seed: int, algorithm_name: str, scenario_id: int, replicate_id: int) -> int:
    return derive_seed(master_seed, "algorithm", algorithm_name, scenario_id, replicate_id)
