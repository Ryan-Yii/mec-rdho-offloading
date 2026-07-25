"""Post-hoc reporting-penalty sensitivity for fixed controlled returns.

This tool intentionally reads the immutable controlled raw CSVs.  It does not
rerun a solver or select a new incumbent: each row is the solution returned by
the original run, re-scored as B + lambda_ref * (1 - soft_CSR).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, wilcoxon


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_VALUES = (0.5, 1.0, 2.0)
EXPERIMENTS = (
    ("controlled_population_stage", "controlled_population_stage_30_raw_results.csv"),
    ("controlled_common_pipeline", "controlled_common_pipeline_30_raw_results.csv"),
)
METHOD_ORDER = ("RDHO", "RIME", "DBO")


def method_name(label: str) -> str:
    """Convert a raw CSV method label to the manuscript-facing method name."""

    return label.split("-", 1)[0]


def holm_adjust(records: list[dict]) -> None:
    """Apply Holm correction within one experiment and lambda setting."""

    order = sorted(range(len(records)), key=lambda index: records[index]["p_value_two_sided"])
    running = 0.0
    for rank, index in enumerate(order):
        adjusted = min(1.0, (len(records) - rank) * records[index]["p_value_two_sided"])
        running = max(running, adjusted)
        records[index]["p_value_holm"] = float(running)
        records[index]["significant_holm_0_05"] = bool(running < 0.05)


def paired_record(frame: pd.DataFrame, experiment: str, lambda_ref: float, baseline: str) -> dict:
    pivot = frame.pivot(index="scenario_seed", columns="method_short", values="fixed_return_fitness")
    rdho = pivot["RDHO"].to_numpy(dtype=float)
    other = pivot[baseline].to_numpy(dtype=float)
    delta = rdho - other
    nonzero = delta[np.abs(delta) > 1.0e-12]
    if nonzero.size:
        statistic = wilcoxon(rdho, other, alternative="two-sided", zero_method="wilcox")
        ranks = rankdata(np.abs(nonzero))
        positive = float(np.sum(ranks[nonzero > 0.0]))
        negative = float(np.sum(ranks[nonzero < 0.0]))
        rank_biserial = (positive - negative) / (positive + negative)
        p_value = float(statistic.pvalue)
        w_statistic = float(statistic.statistic)
    else:
        rank_biserial = 0.0
        p_value = 1.0
        w_statistic = 0.0
    return {
        "experiment": experiment,
        "lambda_ref": lambda_ref,
        "comparison": f"RDHO vs {baseline}",
        "n_pairs": int(len(delta)),
        "delta_definition": "fixed-return F_lambda(RDHO) - fixed-return F_lambda(baseline); negative favours RDHO",
        "rdho_mean": float(np.mean(rdho)),
        "baseline_mean": float(np.mean(other)),
        "mean_paired_difference": float(np.mean(delta)),
        "median_paired_difference": float(np.median(delta)),
        "w_statistic": w_statistic,
        "p_value_two_sided": p_value,
        "rank_biserial": float(rank_biserial),
        "wins_rdho": int(np.sum(delta < -1.0e-12)),
        "ties": int(np.sum(np.abs(delta) <= 1.0e-12)),
        "losses_rdho": int(np.sum(delta > 1.0e-12)),
    }


def analyse(raw_dir: Path, lambda_values: tuple[float, ...] = LAMBDA_VALUES) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return summary and paired records without modifying source evidence."""

    summaries: list[dict] = []
    paired: list[dict] = []
    for experiment, filename in EXPERIMENTS:
        raw = pd.read_csv(raw_dir / filename)
        required = {"scenario_seed", "method", "reporting_fitness", "base_objective", "soft_csr", "qoe", "fairness", "total_nfe", "runtime_s"}
        missing = required.difference(raw.columns)
        if missing:
            raise ValueError(f"{filename} misses required columns: {sorted(missing)}")
        raw = raw.copy()
        raw["method_short"] = raw["method"].map(method_name)
        if set(raw["method_short"]) != set(METHOD_ORDER):
            raise ValueError(f"{filename} does not contain exactly {METHOD_ORDER}")
        if not np.allclose(raw["reporting_fitness"], raw["base_objective"] + (1.0 - raw["soft_csr"])):
            raise ValueError(f"{filename} is inconsistent with its fixed lambda_ref=1 reporting fitness")
        for lambda_ref in lambda_values:
            rescored = raw.copy()
            rescored["fixed_return_fitness"] = rescored["base_objective"] + lambda_ref * (1.0 - rescored["soft_csr"])
            for method in METHOD_ORDER:
                group = rescored.loc[rescored["method_short"] == method]
                record: dict[str, object] = {
                    "experiment": experiment,
                    "lambda_ref": lambda_ref,
                    "method": method,
                    "n": int(len(group)),
                }
                for column in ("fixed_return_fitness", "base_objective", "soft_csr", "qoe", "fairness", "total_nfe", "runtime_s"):
                    values = group[column].to_numpy(dtype=float)
                    record[f"{column}_mean"] = float(np.mean(values))
                    record[f"{column}_std"] = float(np.std(values, ddof=1))
                    record[f"{column}_median"] = float(np.median(values))
                summaries.append(record)
            records = [paired_record(rescored, experiment, lambda_ref, baseline) for baseline in ("RIME", "DBO")]
            holm_adjust(records)
            paired.extend(records)
    return pd.DataFrame(summaries), pd.DataFrame(paired)


def markdown_table(frame: pd.DataFrame, columns: list[str], title: str) -> str:
    lines = [f"# {title}", "", "| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for _, row in frame.loc[:, columns].iterrows():
        rendered = []
        for value in row:
            rendered.append(f"{value:.6g}" if isinstance(value, float) else str(value))
        lines.append("| " + " | ".join(rendered) + " |")
    return "\n".join(lines) + "\n"


def write_outputs(summary: pd.DataFrame, paired: pd.DataFrame, output_root: Path) -> None:
    statistics = output_root / "results" / "statistics"
    tables = output_root / "paper_tables"
    docs = output_root / "docs"
    for directory in (statistics, tables, docs):
        directory.mkdir(parents=True, exist_ok=True)
    summary_path = statistics / "controlled_reporting_penalty_sensitivity.csv"
    paired_path = statistics / "controlled_reporting_penalty_sensitivity_paired.csv"
    summary.to_csv(summary_path, index=False)
    paired.to_csv(paired_path, index=False)
    table_columns = [
        "experiment", "lambda_ref", "method", "fixed_return_fitness_mean", "base_objective_mean",
        "soft_csr_mean", "qoe_mean", "fairness_mean", "total_nfe_mean", "runtime_s_mean",
    ]
    pair_columns = [
        "experiment", "lambda_ref", "comparison", "mean_paired_difference", "median_paired_difference",
        "p_value_holm", "rank_biserial", "wins_rdho", "ties", "losses_rdho",
    ]
    summary.to_csv(tables / "controlled_reporting_penalty_sensitivity.csv", index=False)
    (tables / "controlled_reporting_penalty_sensitivity.md").write_text(
        markdown_table(summary, table_columns, "Post-hoc fixed-return reporting-penalty sensitivity"), encoding="utf-8"
    )
    (tables / "controlled_reporting_penalty_sensitivity_paired.md").write_text(
        markdown_table(paired, pair_columns, "Paired fixed-return reporting-penalty sensitivity"), encoding="utf-8"
    )
    report = [
        "# Controlled Reporting-Penalty Sensitivity",
        "",
        "This additive analysis rescored each already-returned solution from the immutable controlled raw CSVs as `F_lambda = B + lambda_ref * (1 - soft_CSR)` for lambda_ref in {0.5, 1, 2}.",
        "It neither reruns a solver nor selects a new incumbent. The raw files record `search_fitness_not_reported=True`; therefore these are fixed-return post-hoc checks, not alternative-lambda re-optimisations.",
        "",
        "At lambda_ref=1, the tool checks row-by-row equality with the original reporting fitness before writing any outputs.",
        "",
        "## Interpretation boundary",
        "",
        "The paired results retain the original 30 matched scenarios and use two-sided Wilcoxon tests with Holm correction over RDHO-versus-RIME and RDHO-versus-DBO within each experiment/lambda setting. They only assess ranking robustness of the fixed returned solutions; they cannot establish which method would have found a different incumbent under another reporting penalty.",
        "",
        "Generated summary: `results/statistics/controlled_reporting_penalty_sensitivity.csv`.",
        "Generated paired statistics: `results/statistics/controlled_reporting_penalty_sensitivity_paired.csv`.",
    ]
    (docs / "controlled_reporting_penalty_sensitivity_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rescore fixed controlled returns at alternative reporting penalties.")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "results" / "raw")
    parser.add_argument("--output-root", type=Path, default=ROOT)
    args = parser.parse_args()
    summary, paired = analyse(args.raw_dir)
    write_outputs(summary, paired, args.output_root)
    print(args.output_root / "results/statistics/controlled_reporting_penalty_sensitivity.csv")


if __name__ == "__main__":
    main()
