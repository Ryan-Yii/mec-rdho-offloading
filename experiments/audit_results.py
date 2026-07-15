from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from src.metrics import FitnessWeights

from .statistical_analysis import PAIR_COLUMNS, PRIMARY_ALGORITHMS, ZERO_TOLERANCE


def _require_allclose(frame: pd.DataFrame, left: str, expected: np.ndarray, message: str) -> None:
    if not np.allclose(frame[left].to_numpy(dtype=float), expected, rtol=1.0e-10, atol=1.0e-10):
        deviations = np.abs(frame[left].to_numpy(dtype=float) - expected)
        raise ValueError(f"{message}; max absolute deviation={float(deviations.max()):.3e}")


def audit_main_frame(
    frame: pd.DataFrame,
    *,
    expected_algorithms: Sequence[str] = (*PRIMARY_ALGORITHMS, "Greedy-ED"),
    expected_pairs: int = 30,
    weights: FitnessWeights | None = None,
    output_path: str | Path | None = None,
) -> dict[str, object]:
    weights = weights or FitnessWeights()
    key_columns = [*PAIR_COLUMNS, "algorithm"]
    required = {
        *key_columns,
        "scenario_seed",
        "algorithm_seed",
        "fitness",
        "reported_fitness",
        "base_fitness",
        "report_penalty_scale",
        "report_penalty",
        "energy_norm",
        "delay_norm",
        "aoi_norm",
        "qoe",
        "fairness",
        "csr",
        "nfe_used",
        "max_evaluations",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"main-result audit columns are missing: {sorted(missing)}")
    duplicates = frame.duplicated(key_columns, keep=False)
    if duplicates.any():
        keys = frame.loc[duplicates, key_columns].drop_duplicates().to_dict("records")
        raise ValueError(f"duplicate main-result key: {keys}")

    expected_set = set(expected_algorithms)
    observed_set = set(frame["algorithm"])
    if observed_set != expected_set:
        raise ValueError(
            f"main-result algorithm set mismatch; missing={sorted(expected_set - observed_set)}, "
            f"unexpected={sorted(observed_set - expected_set)}"
        )
    pair_sets = {
        algorithm: set(map(tuple, group[list(PAIR_COLUMNS)].to_numpy()))
        for algorithm, group in frame.groupby("algorithm", sort=False)
    }
    reference_pairs = pair_sets[expected_algorithms[0]]
    if len(reference_pairs) != expected_pairs:
        raise ValueError(f"expected {expected_pairs} paired scenarios, found {len(reference_pairs)}")
    mismatched_pairs = [algorithm for algorithm, pairs in pair_sets.items() if pairs != reference_pairs]
    if mismatched_pairs:
        raise ValueError(f"incomplete paired scenario sets: {mismatched_pairs}")

    for pair, group in frame.groupby(list(PAIR_COLUMNS), sort=False):
        if group["scenario_seed"].nunique() != 1:
            raise ValueError(f"scenario seed mismatch for paired key {pair}")
        stochastic = group[group["algorithm"].isin(PRIMARY_ALGORITHMS)]
        if stochastic["algorithm_seed"].nunique() != len(PRIMARY_ALGORITHMS):
            raise ValueError(f"stochastic algorithm seed collision for paired key {pair}")
        if stochastic["max_evaluations"].nunique() != 1:
            raise ValueError(f"equal-budget maximum NFE mismatch for paired key {pair}")
    if (frame["nfe_used"].to_numpy(dtype=float) > frame["max_evaluations"].to_numpy(dtype=float)).any():
        raise ValueError("one or more algorithms exceeded max_evaluations")

    _require_allclose(frame, "fitness", frame["reported_fitness"].to_numpy(dtype=float), "fitness alias check failed")
    _require_allclose(
        frame,
        "report_penalty",
        frame["report_penalty_scale"].to_numpy(dtype=float) * (1.0 - frame["csr"].to_numpy(dtype=float)),
        "report penalty recomputation failed",
    )
    base = (
        weights.energy * frame["energy_norm"].to_numpy(dtype=float)
        + weights.delay * frame["delay_norm"].to_numpy(dtype=float)
        + weights.aoi * frame["aoi_norm"].to_numpy(dtype=float)
        + weights.qoe * (1.0 - frame["qoe"].to_numpy(dtype=float))
        + weights.fairness * (1.0 - frame["fairness"].to_numpy(dtype=float))
    )
    _require_allclose(frame, "base_fitness", base, "base objective recomputation failed")
    reported = base + frame["report_penalty"].to_numpy(dtype=float)
    _require_allclose(frame, "reported_fitness", reported, "reported objective recomputation failed")

    pivot = frame.pivot(index=list(PAIR_COLUMNS), columns="algorithm", values="reported_fitness").sort_index()
    outcomes: dict[str, dict[str, int]] = {}
    for baseline in expected_algorithms[1:]:
        differences = pivot[expected_algorithms[0]].to_numpy(dtype=float) - pivot[baseline].to_numpy(dtype=float)
        outcomes[baseline] = {
            "wins": int(np.sum(differences < -ZERO_TOLERANCE)),
            "ties": int(np.sum(np.abs(differences) <= ZERO_TOLERANCE)),
            "losses": int(np.sum(differences > ZERO_TOLERANCE)),
        }

    audit: dict[str, object] = {
        "passed": True,
        "paired_key": "scenario_id + replicate_id",
        "row_count": int(len(frame)),
        "paired_scenarios": int(len(reference_pairs)),
        "algorithms": list(expected_algorithms),
        "primary_equal_budget_algorithms": list(PRIMARY_ALGORITHMS),
        "supplementary_algorithm": "Greedy-ED",
        "outcomes": outcomes,
    }
    if output_path is not None:
        _write_audit_markdown(audit, output_path)
    return audit


def _write_audit_markdown(audit: dict[str, object], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Main Result Audit",
        "",
        "Status: **PASS**",
        "",
        f"Pairing key: `{audit['paired_key']}`.",
        f"Audited rows: {audit['row_count']}; paired scenarios: {audit['paired_scenarios']}.",
        "",
        "## Scope",
        "",
        "Primary equal-budget algorithms: " + ", ".join(audit["primary_equal_budget_algorithms"]) + ".",
        "Greedy-ED is retained only as a supplementary deterministic, lower-NFE heuristic comparison.",
        "",
        "## Checks",
        "",
        "- No duplicate `scenario_id + replicate_id + algorithm` rows.",
        "- Every algorithm uses the same paired scenario keys and scenario seed within a pair.",
        "- Stochastic algorithm seeds are distinct within each paired scenario.",
        "- All eight stochastic algorithms share the same maximum NFE.",
        "- `fitness == reported_fitness` for every row.",
        "- `base_fitness`, `report_penalty`, and `reported_fitness` were recomputed from raw columns.",
        "",
        "## RDHO Outcomes",
        "",
        "| Baseline | Wins | Ties | Losses |",
        "|---|---:|---:|---:|",
    ]
    for baseline, result in audit["outcomes"].items():
        lines.append(f"| {baseline} | {result['wins']} | {result['ties']} | {result['losses']} |")
    lines.extend(
        [
            "",
            "Wins and losses use reported fitness (lower is better) with a tie tolerance of `1e-12`.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
