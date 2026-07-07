from __future__ import annotations

import random

import numpy as np


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def derive_seed(seed: int, label: str) -> int:
    value = seed & 0xFFFFFFFF
    for char in label:
        value = ((value * 131) + ord(char)) & 0xFFFFFFFF
    return value
