from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from experiments.analyze_results import (
    generate_main_figures,
    generate_sensitivity_figures,
    plot_ablation,
    plot_scalability,
)
from experiments.experiment_core import (
    capture_git_state,
    copy_artifact,
    ensure_fresh_run,
    ensure_legacy_snapshot,
    file_sha256,
    parse_force_flag,
    summarize_mean_std,
    write_wilcoxon_results,
)


INPUT_PATHS = [
    "configs/main_40tasks.yaml",
    "configs/ablation.yaml",
    "configs/sensitivity.yaml",
    "configs/scalability.yaml",
    "results/raw/main_30_raw_results.csv",
    "results/raw/main_30_convergence.csv",
    "results/raw/ablation_30_raw_results.csv",
    "results/sensitivity/raw/weight_sensitivity_raw_results.csv",
    "results/sensitivity/raw/dynamic_penalty_sensitivity_raw_results.csv",
    "results/raw/scalability_raw_results.csv",
]

OUTPUT_PATHS = [
    "results/summary/main_30_summary_mean_std.csv",
    "results/summary/wilcoxon_fitness_results.csv",
    "paper_tables/main_30_summary_mean_std.md",
    "paper_tables/wilcoxon_fitness_results.md",
    "results/figures/convergence_curve.png",
    "results/figures/energy_comparison.png",
    "results/figures/delay_comparison.png",
    "results/figures/aoi_comparison.png",
    "results/figures/qoe_fairness_comparison.png",
    "results/figures/csr_comparison.png",
    "results/figures/radar_chart.png",
    "figures/fig01_convergence_curve.png",
    "figures/fig02_energy_comparison.png",
    "figures/fig03_delay_comparison.png",
    "figures/fig04_aoi_comparison.png",
    "figures/fig05_qoe_fairness_comparison.png",
    "figures/fig06_soft_csr_comparison.png",
    "figures/fig11_normalized_multi_metric_radar.png",
    "results/summary/ablation_30_summary_mean_std.csv",
    "results/summary/ablation_wilcoxon_results.csv",
    "paper_tables/ablation_30_summary_mean_std.md",
    "paper_tables/ablation_wilcoxon_results.md",
    "results/figures/ablation_study_multicolor.png",
    "figures/fig07_ablation_study.png",
    "results/sensitivity/summary/weight_sensitivity_summary_mean_std.csv",
    "results/sensitivity/summary/dynamic_penalty_sensitivity_summary_mean_std.csv",
    "paper_tables/weight_sensitivity_summary.md",
    "paper_tables/dynamic_penalty_sensitivity_summary.md",
    "results/sensitivity/figures/weight_sensitivity_fitness.png",
    "results/sensitivity/figures/weight_sensitivity_qoe_fairness_csr.png",
    "results/sensitivity/figures/penalty_sensitivity_heatmaps.png",
    "figures/supp_weight_sensitivity_fitness.png",
    "figures/fig09_weight_sensitivity_qoe_fairness_csr.png",
    "figures/fig10_penalty_sensitivity_heatmaps.png",
    "results/summary/scalability_summary_mean_std.csv",
    "paper_tables/scalability_summary_mean_std.md",
    "results/figures/scalability.png",
    "figures/fig08_scalability.png",
]


def _artifact_records(paths: Iterable[str | Path]) -> list[dict[str, object]]:
    records = []
    for value in paths:
        path = Path(value)
        if not path.is_file():
            raise FileNotFoundError(f"analysis artifact is missing: {path}")
        records.append(
            {
                "path": path.as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    return records


def _environment_record() -> dict[str, object]:
    versions = {}
    for package in ("numpy", "pandas", "scipy", "matplotlib", "PyYAML"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "dependencies": versions,
    }


def write_analysis_manifest(
    manifest_path: str | Path,
    *,
    input_paths: Iterable[str | Path],
    output_paths: Iterable[str | Path],
    command: Iterable[str],
    git_state: dict[str, object] | None = None,
) -> dict[str, object]:
    manifest = {
        "schema_version": 1,
        "hash_mode": "sha256-canonical-lf-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": list(command),
        "analysis_git": dict(git_state or capture_git_state()),
        "inputs": _artifact_records(input_paths),
        "outputs": _artifact_records(output_paths),
        "environment": _environment_record(),
    }
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return manifest


def _write_summary(
    frame: pd.DataFrame,
    csv_path: str,
    markdown_path: str,
    group_cols: list[str],
) -> pd.DataFrame:
    summary = summarize_mean_std(frame.to_dict("records"), group_cols=group_cols)
    Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(csv_path, index=False)
    summary.to_markdown(markdown_path, index=False)
    return summary


def _regenerate_main() -> None:
    raw_path = "results/raw/main_30_raw_results.csv"
    frame = pd.read_csv(raw_path)
    _write_summary(
        frame,
        "results/summary/main_30_summary_mean_std.csv",
        "paper_tables/main_30_summary_mean_std.md",
        ["algorithm"],
    )
    tests = write_wilcoxon_results(frame.to_dict("records"), "results/summary/wilcoxon_fitness_results.csv")
    tests.to_markdown("paper_tables/wilcoxon_fitness_results.md", index=False)
    generate_main_figures(raw_path, "results/raw/main_30_convergence.csv", "results/figures")
    mapping = {
        "convergence_curve.png": "fig01_convergence_curve.png",
        "energy_comparison.png": "fig02_energy_comparison.png",
        "delay_comparison.png": "fig03_delay_comparison.png",
        "aoi_comparison.png": "fig04_aoi_comparison.png",
        "qoe_fairness_comparison.png": "fig05_qoe_fairness_comparison.png",
        "csr_comparison.png": "fig06_soft_csr_comparison.png",
        "radar_chart.png": "fig11_normalized_multi_metric_radar.png",
    }
    for source, destination in mapping.items():
        copy_artifact(f"results/figures/{source}", f"figures/{destination}")


def _regenerate_ablation() -> None:
    frame = pd.read_csv("results/raw/ablation_30_raw_results.csv")
    _write_summary(
        frame,
        "results/summary/ablation_30_summary_mean_std.csv",
        "paper_tables/ablation_30_summary_mean_std.md",
        ["algorithm"],
    )
    tests = write_wilcoxon_results(
        frame.to_dict("records"),
        "results/summary/ablation_wilcoxon_results.csv",
        reference_algorithm="RDHO-core",
    )
    tests.to_markdown("paper_tables/ablation_wilcoxon_results.md", index=False)
    plot_ablation(frame, "results/figures/ablation_study_multicolor.png")
    copy_artifact("results/figures/ablation_study_multicolor.png", "figures/fig07_ablation_study.png")


def _regenerate_sensitivity() -> None:
    weight_raw = "results/sensitivity/raw/weight_sensitivity_raw_results.csv"
    penalty_raw = "results/sensitivity/raw/dynamic_penalty_sensitivity_raw_results.csv"
    weight = pd.read_csv(weight_raw)
    penalty = pd.read_csv(penalty_raw)
    weight_groups = [
        "setting",
        "description",
        "weights",
        "w_energy",
        "w_delay",
        "w_aoi",
        "w_qoe",
        "w_fairness",
    ]
    _write_summary(
        weight,
        "results/sensitivity/summary/weight_sensitivity_summary_mean_std.csv",
        "paper_tables/weight_sensitivity_summary.md",
        weight_groups,
    )
    _write_summary(
        penalty,
        "results/sensitivity/summary/dynamic_penalty_sensitivity_summary_mean_std.csv",
        "paper_tables/dynamic_penalty_sensitivity_summary.md",
        ["lambda0", "alpha"],
    )
    generate_sensitivity_figures(weight_raw, penalty_raw, "results/sensitivity/figures")
    copy_artifact(
        "results/sensitivity/figures/weight_sensitivity_fitness.png",
        "figures/supp_weight_sensitivity_fitness.png",
    )
    copy_artifact(
        "results/sensitivity/figures/weight_sensitivity_qoe_fairness_csr.png",
        "figures/fig09_weight_sensitivity_qoe_fairness_csr.png",
    )
    copy_artifact(
        "results/sensitivity/figures/penalty_sensitivity_heatmaps.png",
        "figures/fig10_penalty_sensitivity_heatmaps.png",
    )


def _regenerate_scalability() -> None:
    frame = pd.read_csv("results/raw/scalability_raw_results.csv")
    _write_summary(
        frame,
        "results/summary/scalability_summary_mean_std.csv",
        "paper_tables/scalability_summary_mean_std.md",
        ["task_number"],
    )
    plot_scalability(frame, "results/figures/scalability.png")
    copy_artifact("results/figures/scalability.png", "figures/fig08_scalability.png")


def main() -> None:
    force = parse_force_flag()
    manifest_path = "results/manifests/postrun_analysis_manifest.json"
    ensure_legacy_snapshot()
    ensure_fresh_run([*OUTPUT_PATHS, manifest_path], force=force)
    git_state = capture_git_state()
    if git_state.get("code_dirty"):
        raise RuntimeError("post-run analysis requires committed configs, source, experiments, and tests")

    _regenerate_main()
    _regenerate_ablation()
    _regenerate_sensitivity()
    _regenerate_scalability()
    write_analysis_manifest(
        manifest_path,
        input_paths=INPUT_PATHS,
        output_paths=OUTPUT_PATHS,
        command=[sys.executable, "-m", "experiments.regenerate_analysis", *sys.argv[1:]],
        git_state=git_state,
    )


if __name__ == "__main__":
    main()
