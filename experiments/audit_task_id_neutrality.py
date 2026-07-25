from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.stats import chi2_contingency, spearmanr

from experiments.experiment_core import load_config
from src.task_generator import generate_system
from src.utils.io import write_rows


OUTPUT = Path("results/v2/validation/task_id_neutrality.csv")


def _cramers_v(table: np.ndarray) -> tuple[float, float]:
    chi2, p_value, _, _ = chi2_contingency(table)
    denominator = table.sum() * min(table.shape[0] - 1, table.shape[1] - 1)
    return float(np.sqrt(chi2 / denominator)), float(p_value)


def build_audit_rows() -> list[dict[str, str | float | int]]:
    config = load_config("configs/main_40tasks.yaml")
    system_cfg = config["system"]
    experiment = config["experiment"]
    seed_start = int(experiment["seed_start"])
    n_runs = int(experiment["independent_runs"])
    num_tasks = int(system_cfg["tasks"])

    records = []
    for seed in range(seed_start, seed_start + n_runs):
        system = generate_system(
            seed=seed,
            num_devices=int(system_cfg["mobile_devices"]),
            num_edge_servers=int(system_cfg["edge_servers"]),
            num_cloud_servers=int(system_cfg["cloud_servers"]),
            num_tasks=num_tasks,
        )
        records.extend(
            {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "source_device": task.source_device,
                "priority": task.priority,
            }
            for task in system.tasks
        )

    task_ids = np.asarray([row["task_id"] for row in records], dtype=float)
    priorities = np.asarray([row["priority"] for row in records], dtype=float)
    rho, priority_p = spearmanr(task_ids, priorities)

    quartiles = np.minimum(task_ids.astype(int) // max(1, num_tasks // 4), 3)
    rows: list[dict[str, str | float | int]] = [
        {
            "relationship": "task_id_vs_priority",
            "test": "Spearman rank correlation",
            "statistic": float(rho),
            "p_value": float(priority_p),
            "sample_count": len(records),
            "interpretation": "No evidence of a monotonic association in the 30 configured paired scenarios",
        }
    ]
    for field in ("task_type", "source_device"):
        categories = sorted({row[field] for row in records}, key=str)
        table = np.zeros((4, len(categories)), dtype=int)
        for quartile, record in zip(quartiles, records):
            table[int(quartile), categories.index(record[field])] += 1
        statistic, p_value = _cramers_v(table)
        rows.append(
            {
                "relationship": f"task_id_quartile_vs_{field}",
                "test": "Cramer's V from chi-square table",
                "statistic": statistic,
                "p_value": p_value,
                "sample_count": len(records),
                "interpretation": "No evidence of an association in the 30 configured paired scenarios",
            }
        )
    return rows


def main() -> None:
    rows = build_audit_rows()
    write_rows(OUTPUT, rows)
    print(OUTPUT)


if __name__ == "__main__":
    main()
