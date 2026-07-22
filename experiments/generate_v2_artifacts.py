from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from experiments.analyze_results import generate_main_figures, generate_sensitivity_figures
from src.utils.io import ensure_parent, write_rows


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "results" / "v2"
TABLES = ROOT / "paper_tables" / "v2"
FIGURES = ROOT / "figures" / "paper" / "v2"
MANIFEST = ROOT / "paper_artifacts" / "manifest.csv"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _copy(source: Path, destination: Path) -> None:
    ensure_parent(destination)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def _artifact_record(
    item: str,
    number: str,
    title: str,
    source_script: str,
    source_data: Path,
    generated: Path,
    location: str,
) -> dict[str, str]:
    return {
        "manuscript_item": item,
        "paper_number": number,
        "title": title,
        "source_script": source_script,
        "source_data": str(source_data.relative_to(ROOT)),
        "generated_file": str(generated.relative_to(ROOT)),
        "file_hash": _sha256(generated),
        "last_generated_commit": _commit(),
        "inserted_manuscript_location": location,
    }


def _generate_tables() -> list[dict[str, str]]:
    specs = [
        ("Table 5", "5", V2 / "summary" / "main_30_summary_mean_std.csv", "Main paired comparison", "Section 6.2"),
        ("Table 6", "6", V2 / "statistics" / "wilcoxon_fitness_results.csv", "Paired Wilcoxon tests", "Section 6.3"),
        ("Table 7", "7", V2 / "summary" / "ablation_30_summary_mean_std.csv", "One-factor ablation", "Section 6.3"),
        ("Table 8", "8", V2 / "summary" / "scalability_summary_mean_std.csv", "Scalability", "Section 6.4"),
        ("Table 9", "9", V2 / "sensitivity" / "summary" / "weight_sensitivity_summary_mean_std.csv", "Objective-weight and composition sensitivity", "Section 6.4"),
        ("Table 10", "10", V2 / "sensitivity" / "summary" / "dynamic_penalty_sensitivity_summary_mean_std.csv", "Dynamic-penalty sensitivity", "Section 6.4"),
        ("Table S1", "S1", V2 / "summary" / "equal_nfe_30_summary_mean_std.csv", "Equal-NFE comparison", "Section 6.2 and repository supplement"),
        ("Table S2", "S2", V2 / "summary" / "common_control_30_summary_mean_std.csv", "Common-initialisation/postprocessing control", "Section 6.2 and repository supplement"),
        ("Table S3", "S3", V2 / "statistics" / "equal_nfe_wilcoxon.csv", "Equal-NFE paired statistics", "Repository supplement"),
        ("Table S4", "S4", V2 / "statistics" / "common_control_wilcoxon.csv", "Common-control paired statistics", "Repository supplement"),
        ("Table S5", "S5", V2 / "sensitivity" / "summary" / "utility_sensitivity_summary_mean_std.csv", "Task-utility coefficient sensitivity", "Section 6.4 and repository supplement"),
        ("Table S6", "S6", V2 / "sensitivity" / "summary" / "physical_sensitivity_summary_mean_std.csv", "Capacity, SLA and server-heterogeneity sensitivity", "Section 6.4 and repository supplement"),
    ]
    records: list[dict[str, str]] = []
    TABLES.mkdir(parents=True, exist_ok=True)
    for item, number, source, title, location in specs:
        if not source.is_file():
            raise FileNotFoundError(source)
        csv_output = TABLES / source.name
        markdown_output = TABLES / f"{source.stem}.md"
        _copy(source, csv_output)
        pd.read_csv(source).to_markdown(markdown_output, index=False)
        for generated in (csv_output, markdown_output):
            records.append(_artifact_record(
                item,
                number,
                title,
                "experiments/generate_v2_artifacts.py",
                source,
                generated,
                location,
            ))
    return records


def _generate_figures() -> list[dict[str, str]]:
    generate_main_figures(
        V2 / "raw" / "main_30_raw_results.csv",
        V2 / "raw" / "main_30_convergence.csv",
        V2 / "figures",
    )
    generate_main_figures(
        V2 / "raw" / "equal_nfe_30_raw_results.csv",
        V2 / "raw" / "equal_nfe_30_convergence.csv",
        V2 / "figures" / "equal_nfe",
    )
    generate_main_figures(
        V2 / "raw" / "common_control_30_raw_results.csv",
        V2 / "raw" / "common_control_30_convergence.csv",
        V2 / "figures" / "controlled",
    )
    generate_sensitivity_figures(
        V2 / "sensitivity" / "raw" / "weight_sensitivity_raw_results.csv",
        V2 / "sensitivity" / "raw" / "dynamic_penalty_sensitivity_raw_results.csv",
        V2 / "sensitivity" / "figures",
        utility_raw_csv=V2 / "sensitivity" / "raw" / "utility_sensitivity_raw_results.csv",
        physical_raw_csv=V2 / "sensitivity" / "raw" / "physical_sensitivity_raw_results.csv",
    )

    specs = [
        ("Figure 1", "1", FIGURES / "system_architecture.png", V2 / "raw" / "task_parameters.csv", "Cloud-edge-device architecture", "Section 3"),
        ("Figure 2", "2", V2 / "figures" / "convergence_curve.png", V2 / "raw" / "main_30_convergence.csv", "End-to-end convergence", "Section 6.2"),
        ("Figure 3", "3", V2 / "figures" / "energy_comparison.png", V2 / "raw" / "main_30_raw_results.csv", "Device-side energy comparison", "Section 6.2"),
        ("Figure 4", "4", V2 / "figures" / "delay_comparison.png", V2 / "raw" / "main_30_raw_results.csv", "Mean delay comparison", "Section 6.2"),
        ("Figure 5", "5", V2 / "figures" / "aoi_comparison.png", V2 / "raw" / "main_30_raw_results.csv", "Average AoI approximation comparison", "Section 6.2"),
        ("Figure 6", "6", V2 / "figures" / "qoe_fairness_comparison.png", V2 / "raw" / "main_30_raw_results.csv", "QoE and active-user fairness comparison", "Section 6.2"),
        ("Figure 7", "7", V2 / "figures" / "csr_comparison.png", V2 / "raw" / "main_30_raw_results.csv", "Soft QoS CSR comparison", "Section 6.2"),
        ("Figure 8", "8", V2 / "figures" / "ablation_study.png", V2 / "raw" / "ablation_30_raw_results.csv", "One-factor RDHO ablation", "Section 6.3"),
        ("Figure 9", "9", V2 / "figures" / "scalability.png", V2 / "raw" / "scalability_raw_results.csv", "Scalability", "Section 6.4"),
        ("Figure 10", "10", V2 / "sensitivity" / "figures" / "weight_sensitivity_qoe_fairness_csr.png", V2 / "sensitivity" / "raw" / "weight_sensitivity_raw_results.csv", "Objective-weight sensitivity", "Section 6.4"),
        ("Figure 11", "11", V2 / "sensitivity" / "figures" / "penalty_sensitivity_heatmaps.png", V2 / "sensitivity" / "raw" / "dynamic_penalty_sensitivity_raw_results.csv", "Dynamic-penalty sensitivity", "Section 6.4"),
        ("Figure 12", "12", V2 / "figures" / "radar_chart.png", V2 / "raw" / "main_30_raw_results.csv", "Normalised multi-metric illustration", "Section 6.2"),
        ("Figure S1", "S1", V2 / "figures" / "equal_nfe" / "convergence_curve.png", V2 / "raw" / "equal_nfe_30_convergence.csv", "Equal-NFE convergence", "Repository supplement"),
        ("Figure S2", "S2", V2 / "figures" / "controlled" / "convergence_curve.png", V2 / "raw" / "common_control_30_convergence.csv", "Common-control convergence", "Repository supplement"),
        ("Figure S3", "S3", V2 / "sensitivity" / "figures" / "utility_sensitivity.png", V2 / "sensitivity" / "raw" / "utility_sensitivity_raw_results.csv", "Task-utility coefficient sensitivity", "Repository supplement"),
        ("Figure S4", "S4", V2 / "sensitivity" / "figures" / "physical_sensitivity.png", V2 / "sensitivity" / "raw" / "physical_sensitivity_raw_results.csv", "Capacity, SLA and server-heterogeneity sensitivity", "Repository supplement"),
    ]

    records: list[dict[str, str]] = []
    FIGURES.mkdir(parents=True, exist_ok=True)
    for item, number, png_source, data_source, title, location in specs:
        if not png_source.is_file():
            raise FileNotFoundError(png_source)
        sources = [png_source]
        vector = png_source.with_suffix(".svg")
        if vector.is_file():
            sources.append(vector)
        for source in sources:
            destination = FIGURES / f"{item.lower().replace(' ', '_')}_{source.name}"
            if item == "Figure 1":
                destination = FIGURES / source.name
            _copy(source, destination)
            records.append(_artifact_record(
                item,
                number,
                title,
                "figures/paper/v2/system_architecture.svg" if item == "Figure 1" else "experiments/generate_v2_artifacts.py",
                data_source,
                destination,
                location,
            ))
    return records


def _write_execution_report() -> None:
    paths = sorted(V2.rglob("*.csv"))
    lines = [
        "# V2 Experiment Execution Report",
        "",
        "All listed files were generated from seeded V2 configurations after the physical CPU projection fix.",
        "The pre-fix outputs are outside the repository and are not consumed by any generator.",
        "",
        f"Generation code commit before result commit: `{_commit()}`",
        "",
    ]
    for path in paths:
        rel = path.relative_to(ROOT)
        rows = max(0, sum(1 for _ in path.open(encoding="utf-8")) - 1)
        lines.append(f"- `{rel}`: {rows} data rows; SHA-256 `{_sha256(path)}`")
    log_dir = V2 / "logs"
    if log_dir.is_dir():
        lines.extend(["", "## Execution logs", ""])
        for path in sorted(log_dir.glob("*.log")):
            lines.append(f"- `{path.relative_to(ROOT)}`: SHA-256 `{_sha256(path)}`")
    report = ROOT / "docs" / "experiment_execution_report.md"
    ensure_parent(report)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    records = _generate_tables()
    records.extend(_generate_figures())
    write_rows(MANIFEST, records)
    _write_execution_report()


if __name__ == "__main__":
    main()
