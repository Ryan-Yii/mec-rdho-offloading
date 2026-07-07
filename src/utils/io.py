from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd
import yaml


def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def ensure_parent(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def write_rows(path: str | Path, rows: Iterable[Mapping]) -> None:
    rows = list(rows)
    ensure_parent(path)
    if not rows:
        Path(path).write_text("", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_frame(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def write_json(path: str | Path, payload: object) -> None:
    ensure_parent(path)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
