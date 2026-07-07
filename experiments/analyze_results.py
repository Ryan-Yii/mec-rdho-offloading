from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ALGO_ORDER = ["RDHO", "RIME", "DBO", "TLBO-HHO", "CWTSSA", "Greedy-ED"]
COLORS = {
    "RDHO": "#1f4e79",
    "RIME": "#ed7d31",
    "DBO": "#5b9bd5",
    "TLBO-HHO": "#c55a11",
    "CWTSSA": "#70ad47",
    "Greedy-ED": "#8064a2",
}


def _ordered_algorithms(df: pd.DataFrame) -> list[str]:
    present = list(df["algorithm"].unique())
    return [algo for algo in ALGO_ORDER if algo in present] + [algo for algo in present if algo not in ALGO_ORDER]


def _mean_std(df: pd.DataFrame, metric: str) -> tuple[list[str], np.ndarray, np.ndarray]:
    algos = _ordered_algorithms(df)
    means = np.asarray([df[df["algorithm"] == algo][metric].mean() for algo in algos])
    stds = np.asarray([df[df["algorithm"] == algo][metric].std(ddof=1) for algo in algos])
    return algos, means, np.nan_to_num(stds)


def plot_bar(df: pd.DataFrame, metric: str, ylabel: str, output_path: str | Path, higher_is_better: bool = False) -> None:
    algos, means, stds = _mean_std(df, metric)
    x = np.arange(len(algos))
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    bars = ax.bar(x, means, yerr=stds, capsize=4, color=[COLORS.get(a, "#666666") for a in algos], edgecolor="black")
    best_idx = int(np.argmax(means) if higher_is_better else np.argmin(means))
    bars[best_idx].set_linewidth(2.5)
    bars[best_idx].set_edgecolor("#f2c811")
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(algos, rotation=20, ha="right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_qoe_fairness(df: pd.DataFrame, output_path: str | Path) -> None:
    algos, qoe_means, qoe_stds = _mean_std(df, "qoe")
    _, fair_means, fair_stds = _mean_std(df, "fairness")
    x = np.arange(len(algos))
    width = 0.36
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.bar(x - width / 2, qoe_means, width, yerr=qoe_stds, capsize=3, label="QoE", color="#4472c4", edgecolor="black")
    ax.bar(x + width / 2, fair_means, width, yerr=fair_stds, capsize=3, label="Fairness", color="#70ad47", edgecolor="black")
    ax.axhline(0.8, color="#c00000", linestyle="--", linewidth=1.2)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_xticks(x)
    ax.set_xticklabels(algos, rotation=20, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_radar(df: pd.DataFrame, output_path: str | Path) -> None:
    algos = _ordered_algorithms(df)
    metrics = ["energy", "delay", "aoi", "qoe", "fairness"]
    means = {metric: np.asarray([df[df["algorithm"] == algo][metric].mean() for algo in algos]) for metric in metrics}
    normalized = {}
    for metric, values in means.items():
        if np.max(values) == np.min(values):
            normalized[metric] = np.ones_like(values)
        elif metric in {"energy", "delay", "aoi"}:
            normalized[metric] = 1.0 - (values - np.min(values)) / (np.max(values) - np.min(values))
        else:
            normalized[metric] = (values - np.min(values)) / (np.max(values) - np.min(values))

    labels = ["Energy", "Delay", "AoI", "QoE", "Fairness"]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"polar": True})
    for idx, algo in enumerate(algos):
        values = [normalized[m][idx] for m in metrics]
        values += values[:1]
        ax.plot(angles, values, label=algo, color=COLORS.get(algo, "#666666"), linewidth=1.8)
        ax.fill(angles, values, alpha=0.08, color=COLORS.get(algo, "#666666"))
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1)
    ax.legend(loc="upper right", bbox_to_anchor=(1.32, 1.12))
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_convergence(convergence_csv: str | Path, output_path: str | Path) -> None:
    df = pd.read_csv(convergence_csv)
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for algo in _ordered_algorithms(df):
        subset = df[df["algorithm"] == algo]
        mean_curve = subset.groupby("iteration")["fitness"].mean()
        ax.plot(mean_curve.index, mean_curve.values, label=algo, color=COLORS.get(algo, "#666666"), linewidth=2)
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Fitness")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def generate_main_figures(raw_csv: str | Path, convergence_csv: str | Path, output_dir: str | Path = "results/figures") -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(raw_csv)
    plot_convergence(convergence_csv, output / "convergence_curve.png")
    plot_bar(df, "energy", "Total energy consumption (J)", output / "energy_comparison.png")
    plot_bar(df, "delay", "Average delay (s)", output / "delay_comparison.png")
    plot_bar(df, "aoi", "Average AoI (s)", output / "aoi_comparison.png")
    plot_qoe_fairness(df, output / "qoe_fairness_comparison.png")
    plot_bar(df, "csr", "Constraint satisfaction rate", output / "csr_comparison.png", higher_is_better=True)
    plot_radar(df, output / "radar_chart.png")


if __name__ == "__main__":
    generate_main_figures("results/raw/main_30_raw_results.csv", "results/raw/main_30_convergence.csv")
