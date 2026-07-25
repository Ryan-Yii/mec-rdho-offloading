from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


STYLE = {
    "RDHO": "#306998",
    "RIME": "#6a994e",
    "DBO": "#bc6c25",
}


def short_label(method: str) -> str:
    if method.startswith("RDHO"):
        return "RDHO"
    if method.startswith("RIME"):
        return "RIME"
    if method.startswith("DBO"):
        return "DBO"
    raise ValueError(f"unexpected controlled method: {method}")


def plot_mean_panel(axis, frame: pd.DataFrame, title: str) -> None:
    methods = list(frame["method"].drop_duplicates())
    labels = [short_label(method) for method in methods]
    means = [frame.loc[frame["method"] == method, "reporting_fitness"].mean() for method in methods]
    stds = [frame.loc[frame["method"] == method, "reporting_fitness"].std(ddof=1) for method in methods]
    axis.bar(
        np.arange(len(methods)),
        means,
        yerr=stds,
        capsize=3,
        color=[STYLE[label] for label in labels],
    )
    axis.set_xticks(np.arange(len(methods)), labels)
    axis.set_ylim(bottom=0)
    axis.set_ylabel("Fixed reporting fitness")
    axis.set_title(title)
    axis.grid(axis="y", alpha=0.25)


def controlled_annotation(frame: pd.DataFrame, nfe: int) -> str:
    pivot = frame.pivot(index="scenario_seed", columns="method", values="reporting_fitness")
    rdho = next(name for name in pivot.columns if name.startswith("RDHO-"))
    rime = next(name for name in pivot.columns if name.startswith("RIME-"))
    dbo = next(name for name in pivot.columns if name.startswith("DBO-"))
    rime_wins = int((pivot[rdho] < pivot[rime]).sum())
    dbo_wins = int((pivot[rdho] < pivot[dbo]).sum())
    return (
        f"NFE={nfe}; RDHO lower than RIME: {rime_wins}/30\n"
        f"RDHO lower than DBO: {dbo_wins}/30\n"
        "All paired comparisons: Holm p < 0.05"
    )


def normalize_svg(path: Path) -> None:
    """Remove Matplotlib's whitespace-only SVG line endings for clean diffs."""
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")


def render(population_path: Path, pipeline_path: Path, output_stem: Path) -> list[Path]:
    population = pd.read_csv(population_path)
    pipeline = pd.read_csv(pipeline_path)
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 6.3))
    plot_mean_panel(
        axes[0],
        population,
        "A. Equal-NFE population stage: mean +/- SD",
    )
    axes[0].text(
        0.98, 0.96, controlled_annotation(population, 3801), transform=axes[0].transAxes,
        ha="right", va="top", fontsize=8.6,
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "0.65", "alpha": 0.92},
    )
    plot_mean_panel(
        axes[1],
        pipeline,
        "B. Common-pipeline control: mean +/- SD",
    )
    axes[1].text(
        0.98, 0.96, controlled_annotation(pipeline, 10232), transform=axes[1].transAxes,
        ha="right", va="top", fontsize=8.6,
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "0.65", "alpha": 0.92},
    )
    fig.suptitle(
        "Strictly controlled RDHO evidence (lower reporting fitness is better)",
        fontsize=12,
        y=0.99,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    paths = []
    for suffix in (".png", ".pdf", ".svg"):
        path = output_stem.with_suffix(suffix)
        fig.savefig(path, dpi=220 if suffix == ".png" else None, bbox_inches="tight")
        if suffix == ".svg":
            normalize_svg(path)
        paths.append(path)
    plt.close(fig)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the manuscript Figure 12 directly from controlled raw CSVs."
    )
    parser.add_argument(
        "--population-raw",
        type=Path,
        default=Path("results/raw/controlled_population_stage_30_raw_results.csv"),
    )
    parser.add_argument(
        "--pipeline-raw",
        type=Path,
        default=Path("results/raw/controlled_common_pipeline_30_raw_results.csv"),
    )
    parser.add_argument(
        "--output-stem",
        type=Path,
        default=Path("figures/paper/figure_12_controlled_rdho_evidence"),
    )
    args = parser.parse_args()
    for path in render(args.population_raw, args.pipeline_raw, args.output_stem):
        print(path)


if __name__ == "__main__":
    main()
