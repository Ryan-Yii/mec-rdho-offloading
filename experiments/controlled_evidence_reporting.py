from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import rankdata, wilcoxon

from src.utils.io import ensure_parent, write_rows


METHOD_ORDER = ("RDHO", "RIME", "DBO")


def repository_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def repository_v2_hashes() -> dict[str, str]:
    """Hash the versioned V2 evidence that a clean checkout can reproduce."""

    output = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "results/v2"],
    )
    paths = [Path(value.decode("utf-8")) for value in output.split(b"\0") if value]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"tracked V2 evidence is missing: {missing}")
    return {str(path): sha256_file(path) for path in paths}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def summarize_raw(rows: list[dict]) -> list[dict]:
    frame = pd.DataFrame(rows)
    numeric = [
        "reporting_fitness", "base_objective", "energy", "delay", "aoi", "qoe",
        "fairness", "soft_csr", "capacity_utilisation", "runtime_s", "total_nfe",
        "population_nfe", "refinement_nfe", "reassignment_count", "repair_failure_count",
    ]
    records: list[dict] = []
    for method, group in frame.groupby("method", sort=False):
        record: dict[str, object] = {"method": method, "n": int(len(group))}
        for column in numeric:
            values = group[column].to_numpy(dtype=float)
            record[f"{column}_mean"] = float(np.mean(values))
            record[f"{column}_std"] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
            record[f"{column}_median"] = float(np.median(values))
        record["hard_feasible_count"] = int(group["hard_feasible"].sum())
        record["assignment_unique_count"] = int(group["assignment_unique"].sum())
        records.append(record)
    return records


def _bootstrap_median_ci(delta: np.ndarray, seed: int, resamples: int = 10000) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    samples = rng.integers(0, len(delta), size=(resamples, len(delta)))
    medians = np.median(delta[samples], axis=1)
    return float(np.quantile(medians, 0.025)), float(np.quantile(medians, 0.975))


def paired_statistics(rows: list[dict], *, experiment: str) -> list[dict]:
    frame = pd.DataFrame(rows)
    pivot = frame.pivot(index="scenario_seed", columns="method", values="reporting_fitness")
    reference = next(name for name in pivot.columns if name.startswith("RDHO-"))
    baselines = [name for name in pivot.columns if name != reference]
    output: list[dict] = []
    for index, baseline in enumerate(baselines):
        rdho = pivot[reference].to_numpy(dtype=float)
        other = pivot[baseline].to_numpy(dtype=float)
        delta = rdho - other
        nonzero = delta[np.abs(delta) > 1.0e-12]
        if nonzero.size:
            statistic = wilcoxon(rdho, other, alternative="two-sided", zero_method="wilcox")
            ranks = rankdata(np.abs(nonzero))
            positive = float(np.sum(ranks[nonzero > 0]))
            negative = float(np.sum(ranks[nonzero < 0]))
            rank_biserial = (positive - negative) / (positive + negative)
            w_statistic = float(statistic.statistic)
            p_value = float(statistic.pvalue)
        else:
            rank_biserial = 0.0
            w_statistic = 0.0
            p_value = 1.0
        ci_low, ci_high = _bootstrap_median_ci(delta, seed=20260724 + index)
        output.append({
            "experiment": experiment,
            "comparison": f"{reference} vs {baseline}",
            "n_pairs": int(len(delta)),
            "delta_definition": "F_RDHO - F_baseline; negative favours RDHO",
            "rdho_mean": float(np.mean(rdho)),
            "rdho_std": float(np.std(rdho, ddof=1)),
            "baseline_mean": float(np.mean(other)),
            "baseline_std": float(np.std(other, ddof=1)),
            "rdho_median": float(np.median(rdho)),
            "baseline_median": float(np.median(other)),
            "median_paired_difference": float(np.median(delta)),
            "median_difference_ci95_low": ci_low,
            "median_difference_ci95_high": ci_high,
            "w_statistic": w_statistic,
            "p_value_two_sided": p_value,
            "rank_biserial": float(rank_biserial),
            "wins_rdho": int(np.sum(delta < -1.0e-12)),
            "ties": int(np.sum(np.abs(delta) <= 1.0e-12)),
            "losses_rdho": int(np.sum(delta > 1.0e-12)),
        })
    order = sorted(range(len(output)), key=lambda idx: output[idx]["p_value_two_sided"])
    running = 0.0
    for rank, index in enumerate(order):
        adjusted = min(1.0, (len(output) - rank) * output[index]["p_value_two_sided"])
        running = max(running, adjusted)
        output[index]["p_value_holm"] = float(running)
        output[index]["significant_holm_0_05"] = bool(running < 0.05)
    return output


def write_markdown_table(path: str | Path, rows: list[dict], columns: list[str], title: str) -> None:
    target = Path(path)
    ensure_parent(target)
    lines = [f"# {title}", "", "| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        rendered = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                rendered.append(f"{value:.6g}")
            else:
                rendered.append(str(value))
        lines.append("| " + " | ".join(rendered) + " |")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_experiment_outputs(
    *,
    rows: list[dict],
    statistics: list[dict],
    output_root: Path,
    raw_name: str,
    summary_name: str,
    statistic_name: str,
    table_name: str,
    table_root: Path | None = None,
) -> tuple[Path, Path, Path, Path]:
    raw_path = output_root / "raw" / raw_name
    summary_path = output_root / "summary" / summary_name
    statistic_path = output_root / "statistics" / statistic_name
    table_path = (table_root or output_root / "paper_tables") / table_name
    summary = summarize_raw(rows)
    write_rows(raw_path, rows)
    write_rows(summary_path, summary)
    write_rows(statistic_path, statistics)
    write_rows(table_path, summary)
    write_markdown_table(
        table_path.with_suffix(".md"), summary,
        ["method", "n", "reporting_fitness_mean", "reporting_fitness_std", "reporting_fitness_median", "total_nfe_mean", "runtime_s_mean"],
        table_path.stem.replace("_", " "),
    )
    return raw_path, summary_path, statistic_path, table_path


def plot_experiment(
    rows: list[dict],
    statistics: list[dict],
    *,
    title: str,
    stem: str,
    output_root: Path,
    figure_root: Path | None = None,
) -> list[Path]:
    frame = pd.DataFrame(rows)
    methods = list(frame["method"].drop_duplicates())
    means = [frame.loc[frame.method == method, "reporting_fitness"].mean() for method in methods]
    stds = [frame.loc[frame.method == method, "reporting_fitness"].std(ddof=1) for method in methods]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    positions = np.arange(len(methods))
    ax.bar(positions, means, yerr=stds, capsize=5, color=["#306998", "#6a994e", "#bc6c25"])
    ax.set_xticks(positions, methods, rotation=12, ha="right")
    ax.set_ylabel("Fixed reporting fitness (lower is better)")
    nfe = int(frame["total_nfe"].iloc[0])
    ax.set_title(f"{title}: mean +/- SD across 30 paired scenarios (NFE={nfe})")
    ax.set_ylim(bottom=0.0)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    figure_root = figure_root or output_root / "figures" / "analysis"
    paths = _save_figure(fig, figure_root / stem)
    plt.close(fig)

    rdho = next(method for method in methods if method.startswith("RDHO-"))
    baselines = [method for method in methods if method != rdho]
    fig, axes = plt.subplots(1, len(baselines), figsize=(6.2 * len(baselines), 4.8), squeeze=False)
    for axis, baseline, stat in zip(axes[0], baselines, statistics):
        paired = frame.pivot(index="scenario_seed", columns="method", values="reporting_fitness")
        delta = paired[rdho] - paired[baseline]
        axis.axhline(0.0, color="black", linewidth=1)
        axis.scatter(np.arange(1, len(delta) + 1), delta, color="#306998")
        axis.set_title(f"{rdho} - {baseline}\nmedian={stat['median_paired_difference']:.4g}")
        axis.set_xlabel("Paired scenario")
        axis.set_ylabel("Delta fixed fitness (negative favours RDHO)")
        axis.grid(alpha=0.25)
    fig.suptitle(f"{title}: paired differences, equal NFE", y=1.02)
    fig.tight_layout()
    paths.extend(_save_figure(fig, figure_root / f"{stem}_paired_differences"))
    plt.close(fig)
    return paths


def plot_combined_paired_differences(
    population_rows: list[dict],
    pipeline_rows: list[dict],
    output_root: Path,
    figure_root: Path | None = None,
) -> list[Path]:
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    for row_index, (name, rows) in enumerate((("Population stage", population_rows), ("Common pipeline", pipeline_rows))):
        frame = pd.DataFrame(rows)
        paired = frame.pivot(index="scenario_seed", columns="method", values="reporting_fitness")
        rdho = next(method for method in paired.columns if method.startswith("RDHO-"))
        for column, baseline in enumerate(method for method in paired.columns if method != rdho):
            axis = axes[row_index, column]
            delta = paired[rdho] - paired[baseline]
            axis.axhline(0.0, color="black", linewidth=1)
            axis.scatter(np.arange(1, len(delta) + 1), delta, color="#306998")
            axis.set_title(f"{name}: RDHO - {baseline}")
            axis.set_ylabel("Delta fitness")
            axis.grid(alpha=0.25)
    for axis in axes[-1]:
        axis.set_xlabel("Paired scenario")
    fig.suptitle("Controlled paired reporting-fitness differences (negative favours RDHO)")
    fig.tight_layout()
    paths = _save_figure(fig, (figure_root or output_root / "figures" / "analysis") / "controlled_paired_differences")
    plt.close(fig)
    return paths


def _save_figure(figure, target_stem: Path) -> list[Path]:
    target_stem.parent.mkdir(parents=True, exist_ok=True)
    png = target_stem.with_suffix(".png")
    pdf = target_stem.with_suffix(".pdf")
    figure.savefig(png, dpi=180, bbox_inches="tight")
    figure.savefig(pdf, bbox_inches="tight")
    return [png, pdf]


def environment_record() -> dict[str, str]:
    import matplotlib as matplotlib_module
    import numpy as numpy_module
    import pandas as pandas_module
    import scipy as scipy_module

    return {
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "numpy": numpy_module.__version__,
        "pandas": pandas_module.__version__,
        "scipy": scipy_module.__version__,
        "matplotlib": matplotlib_module.__version__,
        "matplotlib_backend": matplotlib.get_backend(),
    }
