from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ALGO_ORDER = ["RDHO", "RIME", "DBO", "TLBO-HHO", "CWTSSA", "Greedy-ED"]
DISPLAY_LABELS = {"RDHO": "RDHO-full"}
CONVERGENCE_LABELS = {"RDHO": "RDHO pre-refinement", "Greedy-ED": "Greedy-ED reference"}

COLORS = {
    "RDHO": "#1f4e79",
    "RIME": "#ed7d31",
    "DBO": "#5b9bd5",
    "TLBO-HHO": "#c55a11",
    "CWTSSA": "#70ad47",
    "Greedy-ED": "#8064a2",
}


def save_figure(fig, output_path: str | Path) -> None:
    """Save a raster manuscript preview and an editable vector counterpart."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=300)
    fig.savefig(output.with_suffix(".svg"), format="svg")


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
    ax.set_xticklabels([DISPLAY_LABELS.get(a, a) for a in algos], rotation=20, ha="right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    save_figure(fig, output_path)
    plt.close(fig)


def plot_qoe_fairness(df: pd.DataFrame, output_path: str | Path) -> None:
    algos, qoe_means, qoe_stds = _mean_std(df, "qoe")
    _, fair_means, fair_stds = _mean_std(df, "fairness")
    x = np.arange(len(algos))
    width = 0.36
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.bar(x - width / 2, qoe_means, width, yerr=qoe_stds, capsize=3, label="QoE", color="#4472c4", edgecolor="black")
    ax.bar(x + width / 2, fair_means, width, yerr=fair_stds, capsize=3, label="Per-user QoE fairness", color="#70ad47", edgecolor="black")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_xticks(x)
    ax.set_xticklabels([DISPLAY_LABELS.get(a, a) for a in algos], rotation=20, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    save_figure(fig, output_path)
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

    labels = ["Device-side energy", "Delay", "AoI", "QoE", "Per-user QoE fairness"]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"polar": True})
    for idx, algo in enumerate(algos):
        values = [normalized[m][idx] for m in metrics]
        values += values[:1]
        ax.plot(angles, values, label=DISPLAY_LABELS.get(algo, algo), color=COLORS.get(algo, "#666666"), linewidth=1.8)
        ax.fill(angles, values, alpha=0.08, color=COLORS.get(algo, "#666666"))
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1)
    ax.legend(loc="upper right", bbox_to_anchor=(1.32, 1.12))
    fig.tight_layout()
    save_figure(fig, output_path)
    plt.close(fig)


def plot_controlled_attribution(
    equal_nfe_summary: str | Path,
    common_control_summary: str | Path,
    output_path: str | Path,
) -> None:
    equal = pd.read_csv(equal_nfe_summary).set_index("algorithm")
    common = pd.read_csv(common_control_summary).set_index("algorithm")
    panels = [
        (
            equal,
            ["RDHO-core", "RIME", "DBO", "TLBO-HHO", "CWTSSA"],
            ["RDHO-core", "RIME", "DBO", "TLBO-HHO", "CWTSSA"],
            "Equal NFE (3,801 evaluations)",
        ),
        (
            common,
            [
                "RIME-common-init",
                "RIME-common-init-refine",
                "DBO-common-init",
                "DBO-common-init-refine",
                "RDHO-core",
                "RDHO-full",
            ],
            ["RIME\ninit.", "RIME\n+ refine", "DBO\ninit.", "DBO\n+ refine", "RDHO\ncore", "RDHO\nfull"],
            "Common initialisation and refinement controls",
        ),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.8))
    for ax, (frame, order, labels, title) in zip(axes, panels):
        means = np.asarray([float(frame.loc[name, "fitness_mean"]) for name in order])
        stds = np.asarray([float(frame.loc[name, "fitness_std"]) for name in order])
        x = np.arange(len(order))
        colors = ["#1f4e79" if name.startswith("RDHO") else "#70ad47" if "refine" in name else "#8faadc" for name in order]
        ax.bar(x, means, yerr=stds, capsize=3, color=colors, edgecolor="black")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=18 if len(order) == 5 else 0, ha="right" if len(order) == 5 else "center")
        ax.set_ylabel("Reporting fitness (lower is better)")
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    save_figure(fig, output_path)
    plt.close(fig)


def plot_convergence(convergence_csv: str | Path, output_path: str | Path) -> None:
    df = pd.read_csv(convergence_csv)
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for algo in _ordered_algorithms(df):
        subset = df[df["algorithm"] == algo]
        mean_curve = subset.groupby("iteration")["fitness"].mean()
        ax.plot(mean_curve.index, mean_curve.values, label=CONVERGENCE_LABELS.get(algo, DISPLAY_LABELS.get(algo, algo)), color=COLORS.get(algo, "#666666"), linewidth=2)
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Fixed-reference reporting fitness")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    save_figure(fig, output_path)
    plt.close(fig)


def generate_main_figures(raw_csv: str | Path, convergence_csv: str | Path, output_dir: str | Path = "results/figures") -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(raw_csv)
    plot_convergence(convergence_csv, output / "convergence_curve.png")
    plot_bar(df, "energy", "Mean device-side energy proxy (J)", output / "energy_comparison.png")
    plot_bar(df, "delay", "Average delay (s)", output / "delay_comparison.png")
    plot_bar(df, "aoi", "Periodic average AoI approximation (s)", output / "aoi_comparison.png")
    plot_qoe_fairness(df, output / "qoe_fairness_comparison.png")
    plot_bar(df, "csr", "Soft CSR", output / "csr_comparison.png", higher_is_better=True)
    plot_radar(df, output / "radar_chart.png")


def plot_weight_sensitivity(raw_csv: str | Path, output_dir: str | Path) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(raw_csv)
    settings = list(dict.fromkeys(df["setting"].tolist()))
    x = np.arange(len(settings))

    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    means = np.asarray([df[df["setting"] == setting]["fitness"].mean() for setting in settings])
    stds = np.asarray([df[df["setting"] == setting]["fitness"].std(ddof=1) for setting in settings])
    ax.bar(x, means, yerr=np.nan_to_num(stds), capsize=4, color="#4472c4", edgecolor="black")
    ax.set_xticks(x)
    ax.set_xticklabels(settings)
    ax.set_ylabel("Fixed-reference reporting fitness")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    save_figure(fig, output / "weight_sensitivity_fitness.png")
    plt.close(fig)

    metrics = [("qoe", "QoE", "#4472c4"), ("fairness", "Per-user QoE fairness", "#70ad47"), ("csr", "Soft CSR", "#ed7d31")]
    width = 0.24
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    for offset, (metric, label, color) in zip((-width, 0.0, width), metrics):
        values = np.asarray([df[df["setting"] == setting][metric].mean() for setting in settings])
        errors = np.asarray([df[df["setting"] == setting][metric].std(ddof=1) for setting in settings])
        ax.bar(x + offset, values, width, yerr=np.nan_to_num(errors), capsize=3, label=label, color=color, edgecolor="black")
    ax.set_xticks(x)
    ax.set_xticklabels(settings)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    save_figure(fig, output / "weight_sensitivity_qoe_fairness_csr.png")
    plt.close(fig)


def _heatmap_table(df: pd.DataFrame, metric: str) -> tuple[list[float], list[float], np.ndarray]:
    lambdas = sorted(float(value) for value in df["lambda0"].unique())
    alphas = sorted(float(value) for value in df["alpha"].unique())
    table = np.zeros((len(lambdas), len(alphas)), dtype=float)
    for i, lambda0 in enumerate(lambdas):
        for j, alpha in enumerate(alphas):
            subset = df[(df["lambda0"] == lambda0) & (df["alpha"] == alpha)]
            table[i, j] = float(subset[metric].mean())
    return lambdas, alphas, table


def plot_penalty_sensitivity(raw_csv: str | Path, output_dir: str | Path) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(raw_csv)
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.8))
    for ax, metric, title, cmap in zip(axes, ("csr", "fitness"), ("Soft CSR", "Reporting fitness"), ("YlGnBu", "YlOrRd")):
        lambdas, alphas, values = _heatmap_table(df, metric)
        im = ax.imshow(values, cmap=cmap, aspect="auto")
        ax.set_xticks(np.arange(len(alphas)))
        ax.set_xticklabels([f"{value:.1f}" for value in alphas])
        ax.set_yticks(np.arange(len(lambdas)))
        ax.set_yticklabels([f"{value:.1f}" for value in lambdas])
        ax.set_xlabel("alpha")
        ax.set_ylabel("lambda0")
        ax.set_title(title)
        for i in range(values.shape[0]):
            for j in range(values.shape[1]):
                ax.text(j, i, f"{values[i, j]:.3f}", ha="center", va="center", color="black", fontsize=9)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    save_figure(fig, output / "penalty_sensitivity_heatmaps.png")
    plt.close(fig)


def generate_sensitivity_figures(
    weight_raw_csv: str | Path,
    penalty_raw_csv: str | Path,
    output_dir: str | Path = "results/sensitivity/figures",
    utility_raw_csv: str | Path | None = None,
    physical_raw_csv: str | Path | None = None,
) -> None:
    plot_weight_sensitivity(weight_raw_csv, output_dir)
    plot_penalty_sensitivity(penalty_raw_csv, output_dir)
    if utility_raw_csv is not None:
        plot_factor_sensitivity(utility_raw_csv, "setting", "Task-utility setting", Path(output_dir) / "utility_sensitivity.png")
    if physical_raw_csv is not None:
        plot_factor_sensitivity(physical_raw_csv, "setting", "Physical-model setting", Path(output_dir) / "physical_sensitivity.png")


def plot_factor_sensitivity(raw_csv: str | Path, category: str, xlabel: str, output_path: str | Path) -> None:
    frame = pd.read_csv(raw_csv)
    grouped = frame.groupby(category, sort=False).agg(
        fitness=("fitness", "mean"),
        csr=("csr", "mean"),
        utilisation=("capacity_utilisation_mean", "mean"),
    ).reset_index()
    x = np.arange(len(grouped))
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.8))
    axes[0].bar(x, grouped["fitness"], color="#4472c4", edgecolor="black")
    axes[0].set_ylabel("Reporting fitness")
    axes[0].grid(axis="y", alpha=0.25)
    width = 0.36
    axes[1].bar(x - width / 2, grouped["csr"], width, label="Soft CSR", color="#70ad47", edgecolor="black")
    axes[1].bar(x + width / 2, grouped["utilisation"], width, label="Active-node utilisation", color="#ed7d31", edgecolor="black")
    axes[1].set_ylim(0, 1.05)
    axes[1].set_ylabel("Mean value")
    axes[1].legend()
    axes[1].grid(axis="y", alpha=0.25)
    for axis in axes:
        axis.set_xticks(x)
        axis.set_xticklabels(grouped[category], rotation=25, ha="right")
        axis.set_xlabel(xlabel)
    fig.tight_layout()
    save_figure(fig, output_path)
    plt.close(fig)


if __name__ == "__main__":
    generate_main_figures("results/raw/main_30_raw_results.csv", "results/raw/main_30_convergence.csv")


def plot_ablation(df: pd.DataFrame, output_path: str | Path) -> None:
    order = [
        "RDHO-full",
        "RDHO-core",
        "RDHO-w/o dual-source initialization",
        "RDHO-w/o adaptive role allocation",
        "RDHO-w/o elite preservation",
        "RDHO-w/o dynamic penalty",
    ]
    present = [name for name in order if name in set(df["algorithm"])]
    if not present:
        present = list(df["algorithm"].unique())
    means_f = np.asarray([df[df["algorithm"] == name]["fitness"].mean() for name in present])
    means_c = np.asarray([df[df["algorithm"] == name]["csr"].mean() for name in present])
    std_f = np.nan_to_num(np.asarray([df[df["algorithm"] == name]["fitness"].std(ddof=1) for name in present]))
    x = np.arange(len(present))
    label_map = {
        "RDHO-full": "RDHO-full",
        "RDHO-core": "RDHO-core",
        "RDHO-w/o dual-source initialization": "w/o dual-source init.",
        "RDHO-w/o adaptive role allocation": "w/o adaptive roles",
        "RDHO-w/o elite preservation": "w/o elite",
        "RDHO-w/o dynamic penalty": "w/o penalty",
    }
    labels = [label_map.get(name, name) for name in present]
    fig, ax1 = plt.subplots(figsize=(9.2, 5.0))
    bars = ax1.bar(x, means_f, yerr=std_f, capsize=3, edgecolor="black", alpha=0.85, color=["#1f4e79", "#70ad47", "#ed7d31", "#5b9bd5", "#8064a2", "#c55a11"][:len(present)])
    ax1.set_ylabel("Reporting fitness (lower is better)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=20, ha="right")
    ax1.grid(axis="y", alpha=0.25)
    ax2 = ax1.twinx()
    ax2.plot(x, means_c, marker="o", linewidth=2, label="Soft CSR")
    ax2.set_ylabel("Soft CSR (higher is better)")
    ax2.set_ylim(0, 1)
    fig.tight_layout()
    save_figure(fig, output_path)
    plt.close(fig)


def plot_scalability(df: pd.DataFrame, output_path: str | Path) -> None:
    grouped = df.groupby("task_number", as_index=False).agg({"fitness": "mean", "csr": "mean", "runtime": "mean"}).sort_values("task_number")
    x = grouped["task_number"].to_numpy()
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.5))
    axes[0].plot(x, grouped["fitness"], marker="o", linewidth=2, label="Reporting fitness")
    axes[0].plot(x, grouped["csr"], marker="s", linewidth=2, label="Soft CSR")
    axes[0].set_xlabel("Number of tasks")
    axes[0].set_ylabel("Value")
    axes[0].grid(alpha=0.25)
    axes[0].legend()
    axes[1].plot(x, grouped["runtime"], marker="o", linewidth=2)
    axes[1].set_xlabel("Number of tasks")
    axes[1].set_ylabel("Runtime (s)")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    save_figure(fig, output_path)
    plt.close(fig)
