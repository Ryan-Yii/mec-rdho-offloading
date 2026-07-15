from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd
from scipy.stats import friedmanchisquare, rankdata, wilcoxon

from src.utils.seed import derive_seed


PRIMARY_ALGORITHMS = (
    "RDHO",
    "RIME",
    "DBO",
    "TLBO-HHO",
    "CWTSSA",
    "GA",
    "PSO",
    "DE",
)
PAIR_COLUMNS = ("scenario_id", "replicate_id")
ZERO_TOLERANCE = 1.0e-12


def _as_group_columns(group_cols: Sequence[str] | None) -> list[str]:
    return list(group_cols or [])


def _iter_groups(frame: pd.DataFrame, group_cols: Sequence[str] | None):
    columns = _as_group_columns(group_cols)
    if not columns:
        yield {}, frame
        return
    grouper = columns[0] if len(columns) == 1 else columns
    for keys, group in frame.groupby(grouper, sort=False, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        yield dict(zip(columns, keys)), group


def _paired_pivot(
    frame: pd.DataFrame,
    algorithms: Sequence[str],
    *,
    metric: str,
    group_label: dict[str, object],
) -> pd.DataFrame:
    required = {*PAIR_COLUMNS, "algorithm", metric}
    missing_columns = required - set(frame.columns)
    if missing_columns:
        raise ValueError(f"paired analysis columns are missing: {sorted(missing_columns)}")
    selected = frame[frame["algorithm"].isin(algorithms)].copy()
    missing_algorithms = [algorithm for algorithm in algorithms if algorithm not in set(selected["algorithm"])]
    if missing_algorithms:
        raise ValueError(f"incomplete paired result algorithms in {group_label}: {missing_algorithms}")
    duplicate_mask = selected.duplicated([*PAIR_COLUMNS, "algorithm"], keep=False)
    if duplicate_mask.any():
        keys = selected.loc[duplicate_mask, [*PAIR_COLUMNS, "algorithm"]].drop_duplicates()
        raise ValueError(f"duplicate paired result rows in {group_label}: {keys.to_dict('records')}")
    pivot = selected.pivot(index=list(PAIR_COLUMNS), columns="algorithm", values=metric)
    pivot = pivot.reindex(columns=list(algorithms))
    if pivot.empty or pivot.isna().any().any():
        incomplete = pivot[pivot.isna().any(axis=1)].index.tolist()
        raise ValueError(f"incomplete paired result rows in {group_label}: {incomplete}")
    counts = selected.groupby("algorithm", sort=False).size()
    if counts.nunique() != 1:
        raise ValueError(f"incomplete paired result counts in {group_label}: {counts.to_dict()}")
    return pivot.sort_index()


def friedman_tests(
    frame: pd.DataFrame,
    algorithms: Sequence[str] = PRIMARY_ALGORITHMS,
    *,
    group_cols: Sequence[str] | None = None,
    metric: str = "fitness",
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for group_label, group in _iter_groups(frame, group_cols):
        pivot = _paired_pivot(group, algorithms, metric=metric, group_label=group_label)
        result = friedmanchisquare(*(pivot[algorithm].to_numpy(dtype=float) for algorithm in algorithms))
        records.append(
            {
                **group_label,
                "metric": metric,
                "paired_key": "scenario_id + replicate_id",
                "n_blocks": int(len(pivot)),
                "n_algorithms": int(len(algorithms)),
                "algorithms": "; ".join(algorithms),
                "statistic": float(result.statistic),
                "degrees_of_freedom": int(len(algorithms) - 1),
                "p_value": float(result.pvalue),
                "significant": bool(result.pvalue < 0.05),
            }
        )
    return pd.DataFrame(records)


def _signed_rank_statistics(differences: np.ndarray) -> tuple[float, float, float]:
    normalized = np.asarray(differences, dtype=float).copy()
    normalized[np.abs(normalized) <= ZERO_TOLERANCE] = 0.0
    nonzero = normalized[normalized != 0.0]
    if nonzero.size == 0:
        return 0.0, 1.0, 0.0
    result = wilcoxon(nonzero, alternative="two-sided", zero_method="wilcox")
    ranks = rankdata(np.abs(nonzero))
    positive = float(ranks[nonzero > 0].sum())
    negative = float(ranks[nonzero < 0].sum())
    effect = (positive - negative) / float(ranks.sum())
    return float(result.statistic), float(result.pvalue), float(effect)


def _bootstrap_mean_ci(
    differences: np.ndarray,
    *,
    samples: int,
    seed: int,
) -> tuple[float, float]:
    values = np.asarray(differences, dtype=float)
    if samples <= 0:
        raise ValueError("bootstrap_samples must be positive")
    rng = np.random.default_rng(seed)
    sampled_indices = rng.integers(0, len(values), size=(samples, len(values)))
    means = values[sampled_indices].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return float(low), float(high)


def _apply_holm(records: list[dict[str, object]], group_cols: Sequence[str] | None) -> None:
    if not records:
        return
    frame = pd.DataFrame(records)
    columns = _as_group_columns(group_cols)
    grouped_indices: Iterable[tuple[object, pd.Index]]
    if columns:
        grouper = columns[0] if len(columns) == 1 else columns
        grouped_indices = frame.groupby(grouper, sort=False, dropna=False).groups.items()
    else:
        grouped_indices = [("all", frame.index)]
    for _, indices in grouped_indices:
        family = list(indices)
        order = sorted(family, key=lambda idx: float(records[idx]["raw_p_value"]))
        running_max = 0.0
        total = len(order)
        for rank, idx in enumerate(order):
            adjusted = min(1.0, (total - rank) * float(records[idx]["raw_p_value"]))
            running_max = max(running_max, adjusted)
            records[idx]["adjusted_p_value"] = running_max
        for idx in family:
            records[idx]["holm_family_size"] = total
            records[idx]["significant"] = bool(float(records[idx]["adjusted_p_value"]) < 0.05)


def pairwise_tests(
    frame: pd.DataFrame,
    *,
    reference_algorithm: str,
    comparison_algorithms: Sequence[str],
    group_cols: Sequence[str] | None = None,
    metric: str = "fitness",
    inference_tier: str = "primary_equal_budget",
    equal_budget: bool = True,
    bootstrap_samples: int = 10_000,
    bootstrap_seed: int = 20260716,
) -> pd.DataFrame:
    algorithms = (reference_algorithm, *comparison_algorithms)
    records: list[dict[str, object]] = []
    for group_label, group in _iter_groups(frame, group_cols):
        pivot = _paired_pivot(group, algorithms, metric=metric, group_label=group_label)
        reference = pivot[reference_algorithm].to_numpy(dtype=float)
        for comparison in comparison_algorithms:
            differences = reference - pivot[comparison].to_numpy(dtype=float)
            normalized = differences.copy()
            normalized[np.abs(normalized) <= ZERO_TOLERANCE] = 0.0
            statistic, raw_p_value, effect = _signed_rank_statistics(normalized)
            context = tuple(f"{key}={value}" for key, value in group_label.items())
            ci_seed = derive_seed(bootstrap_seed, "paired-bootstrap", *context, reference_algorithm, comparison)
            ci_low, ci_high = _bootstrap_mean_ci(normalized, samples=bootstrap_samples, seed=ci_seed)
            wins = int(np.sum(normalized < 0.0))
            ties = int(np.sum(normalized == 0.0))
            losses = int(np.sum(normalized > 0.0))
            records.append(
                {
                    **group_label,
                    "comparison": f"{reference_algorithm} vs {comparison}",
                    "reference_algorithm": reference_algorithm,
                    "comparison_algorithm": comparison,
                    "metric": metric,
                    "paired_key": "scenario_id + replicate_id",
                    "inference_tier": inference_tier,
                    "equal_budget": bool(equal_budget),
                    "n_pairs": int(len(normalized)),
                    "wins": wins,
                    "ties": ties,
                    "losses": losses,
                    "zero_tolerance": ZERO_TOLERANCE,
                    "statistic": statistic,
                    "raw_p_value": raw_p_value,
                    "median_difference": float(np.median(normalized)),
                    "mean_difference": float(np.mean(normalized)),
                    "mean_difference_ci_low": ci_low,
                    "mean_difference_ci_high": ci_high,
                    "rank_biserial": effect,
                    "better_algorithm": reference_algorithm if wins > losses else comparison if losses > wins else "Tie",
                }
            )
    _apply_holm(records, group_cols)
    return pd.DataFrame(records)


def average_ranks(
    frame: pd.DataFrame,
    algorithms: Sequence[str] = PRIMARY_ALGORITHMS,
    *,
    group_cols: Sequence[str] | None = None,
    metric: str = "fitness",
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for group_label, group in _iter_groups(frame, group_cols):
        pivot = _paired_pivot(group, algorithms, metric=metric, group_label=group_label)
        scenario_ranks = pivot.rank(axis=1, method="average", ascending=True)
        mean_ranks = scenario_ranks.mean(axis=0).reindex(list(algorithms))
        rank_orders = rankdata(mean_ranks.to_numpy(dtype=float), method="min").astype(int)
        for algorithm, mean_rank, rank_order in zip(algorithms, mean_ranks, rank_orders):
            records.append(
                {
                    **group_label,
                    "algorithm": algorithm,
                    "mean_rank": float(mean_rank),
                    "rank_order": int(rank_order),
                    "n_paired_scenarios": int(len(pivot)),
                    "metric": metric,
                    "paired_key": "scenario_id + replicate_id",
                }
            )
    return pd.DataFrame(records)
