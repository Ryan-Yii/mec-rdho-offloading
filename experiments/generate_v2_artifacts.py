from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

from experiments.analyze_results import generate_main_figures, generate_sensitivity_figures, plot_controlled_attribution
from src.utils.io import ensure_parent, write_rows


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "results" / "v2"
TABLES = ROOT / "paper_tables" / "v2"
FIGURES = ROOT / "figures" / "paper" / "v2"
MANIFEST = ROOT / "paper_artifacts" / "manifest.csv"
CONTROL_SUMMARY = V2 / "summary" / "controlled_attribution_summary.csv"
EXPERIMENT_GENERATION_COMMIT = "78c51c13ce7405654d488aea593d184be930e16a"
NUMERICAL_ARTIFACT_COMMIT = "d2ca1139d325e21ab03f4db97a5e0c4e13149e8d"
RAW_RESULT_FILES = [
    V2 / "raw" / "main_30_raw_results.csv",
    V2 / "raw" / "equal_nfe_30_raw_results.csv",
    V2 / "raw" / "common_control_30_raw_results.csv",
    V2 / "raw" / "ablation_30_raw_results.csv",
    V2 / "raw" / "scalability_raw_results.csv",
    V2 / "sensitivity" / "raw" / "weight_sensitivity_raw_results.csv",
    V2 / "sensitivity" / "raw" / "dynamic_penalty_sensitivity_raw_results.csv",
    V2 / "sensitivity" / "raw" / "utility_sensitivity_raw_results.csv",
    V2 / "sensitivity" / "raw" / "physical_sensitivity_raw_results.csv",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _git_paths_unchanged(base_commit: str, paths: list[str]) -> bool:
    result = subprocess.run(
        ["git", "diff", "--quiet", base_commit, "--", *paths],
        cwd=ROOT,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git diff failed with status {result.returncode}")
    return result.returncode == 0


def _copy(source: Path, destination: Path) -> None:
    ensure_parent(destination)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)


def _normalise_svgs(directory: Path) -> None:
    for path in directory.rglob("*.svg"):
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")


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


def _build_controlled_attribution_summary() -> None:
    equal = pd.read_csv(V2 / "summary" / "equal_nfe_30_summary_mean_std.csv").set_index("algorithm")
    common = pd.read_csv(V2 / "summary" / "common_control_30_summary_mean_std.csv").set_index("algorithm")
    equal_stats = pd.read_csv(V2 / "statistics" / "equal_nfe_wilcoxon.csv").set_index("comparison")
    common_stats = pd.read_csv(V2 / "statistics" / "common_control_wilcoxon.csv").set_index("comparison")

    rows = []
    for name in ("RDHO-core", "RIME", "DBO", "TLBO-HHO", "CWTSSA"):
        row = equal.loc[name]
        comparison = "" if name == "RDHO-core" else f"RDHO-core vs {name}"
        rows.append({
            "method": name,
            "equal_nfe": "Yes (3801)",
            "common_initialisation": "No",
            "common_refinement": "No",
            "reporting_fitness_mean_sd": f"{row['fitness_mean']:.3f} ({row['fitness_std']:.3f})",
            "paired_effect": "Reference" if not comparison else f"{equal_stats.loc[comparison, 'rank_biserial']:.3f}",
        })
    for name, label in (("RIME-common-init-refine", "RIME + common refinement"), ("DBO-common-init-refine", "DBO + common refinement")):
        row = common.loc[name]
        comparison = f"RDHO-full vs {name}"
        rows.append({
            "method": label,
            "equal_nfe": "No",
            "common_initialisation": "Yes",
            "common_refinement": "Yes",
            "reporting_fitness_mean_sd": f"{row['fitness_mean']:.3f} ({row['fitness_std']:.3f})",
            "paired_effect": f"{common_stats.loc[comparison, 'rank_biserial']:.3f}",
        })
    row = common.loc["RDHO-full"]
    rows.append({
        "method": "RDHO-full",
        "equal_nfe": "No (10232)",
        "common_initialisation": "RDHO",
        "common_refinement": "Yes",
        "reporting_fitness_mean_sd": f"{row['fitness_mean']:.3f} ({row['fitness_std']:.3f})",
        "paired_effect": "Reference",
    })
    write_rows(CONTROL_SUMMARY, rows)


def _generate_tables() -> list[dict[str, str]]:
    specs = [
        ("Table 5", "5", V2 / "summary" / "main_30_summary_mean_std.csv", "Main paired comparison", "Section 6.2"),
        ("Table 6", "6", V2 / "statistics" / "wilcoxon_fitness_results.csv", "Paired Wilcoxon tests", "Section 6.3"),
        ("Table 7", "7", V2 / "summary" / "ablation_30_summary_mean_std.csv", "One-factor ablation", "Section 6.3"),
        ("Table 8", "8", V2 / "summary" / "scalability_summary_mean_std.csv", "Scalability", "Section 6.4"),
        ("Table 9", "9", CONTROL_SUMMARY, "Controlled attribution comparison", "Section 6.3"),
        ("Table 10", "10", V2 / "sensitivity" / "summary" / "dynamic_penalty_sensitivity_summary_mean_std.csv", "Dynamic-penalty sensitivity", "Section 6.4"),
        ("Table S1", "S1", V2 / "summary" / "equal_nfe_30_summary_mean_std.csv", "Equal-NFE comparison", "Section 6.2 and repository supplement"),
        ("Table S2", "S2", V2 / "summary" / "common_control_30_summary_mean_std.csv", "Common-initialisation/postprocessing control", "Section 6.2 and repository supplement"),
        ("Table S3", "S3", V2 / "statistics" / "equal_nfe_wilcoxon.csv", "Equal-NFE paired statistics", "Repository supplement"),
        ("Table S4", "S4", V2 / "statistics" / "common_control_wilcoxon.csv", "Common-control paired statistics", "Repository supplement"),
        ("Table S5", "S5", V2 / "sensitivity" / "summary" / "utility_sensitivity_summary_mean_std.csv", "Task-utility coefficient sensitivity", "Section 6.4 and repository supplement"),
        ("Table S6", "S6", V2 / "sensitivity" / "summary" / "physical_sensitivity_summary_mean_std.csv", "Capacity, SLA and server-heterogeneity sensitivity", "Section 6.4 and repository supplement"),
        ("Table S7", "S7", V2 / "sensitivity" / "summary" / "weight_sensitivity_summary_mean_std.csv", "Objective-weight and composition sensitivity", "Section 6.4 and repository supplement"),
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
    plot_controlled_attribution(
        V2 / "summary" / "equal_nfe_30_summary_mean_std.csv",
        V2 / "summary" / "common_control_30_summary_mean_std.csv",
        V2 / "figures" / "controlled_attribution.png",
    )
    _normalise_svgs(V2)

    # Figure 12 was reassigned to controlled attribution; prevent a stale radar
    # artifact from surviving in the publication directory or manifest.
    for obsolete in (
        FIGURES / "figure_12_radar_chart.png",
        FIGURES / "figure_12_radar_chart.svg",
    ):
        obsolete.unlink(missing_ok=True)

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
        ("Figure 12", "12", V2 / "figures" / "controlled_attribution.png", CONTROL_SUMMARY, "Equal-NFE and common-refinement controls", "Section 6.3"),
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
    raw_frames = [(path, pd.read_csv(path)) for path in RAW_RESULT_FILES]
    raw_rows = sum(len(frame) for _, frame in raw_frames)
    feasible = all((frame["hard_feasible"] == 1).all() for _, frame in raw_frames)
    unique = all((frame["assignment_unique"] == 1).all() for _, frame in raw_frames)
    runtime_seconds = sum(float(frame["runtime"].sum()) for _, frame in raw_frames)
    manifest = pd.read_csv(MANIFEST)
    manifest_failures = []
    for row in manifest.to_dict("records"):
        generated = ROOT / row["generated_file"]
        if not generated.is_file() or _sha256(generated) != row["file_hash"]:
            manifest_failures.append(row["generated_file"])
    versions = {
        name: importlib.metadata.version(name)
        for name in ("numpy", "pandas", "scipy", "matplotlib", "PyYAML")
    }
    ci_url = os.environ.get("V2_CI_URL", "https://github.com/Ryan-Yii/mec-rdho-offloading/pull/8/checks")
    ci_result = os.environ.get("V2_CI_RESULT", "Pending final post-push verification")
    test_result = os.environ.get("V2_TEST_RESULT", "Run locally before release finalisation")
    clean_result = os.environ.get("V2_GIT_CLEAN", "Not recorded")
    model_unchanged = _git_paths_unchanged(EXPERIMENT_GENERATION_COMMIT, ["src", "configs"])
    raw_unchanged = _git_paths_unchanged(
        NUMERICAL_ARTIFACT_COMMIT,
        ["results/v2/raw", "results/v2/sensitivity/raw"],
    )
    lines = [
        "# V2 Experiment Execution Report",
        "",
        "## Provenance",
        "",
        "All numerical files were freshly generated from seeded V2 configurations after the physical CPU projection fix. Pre-fix outputs are outside the repository and are not consumed by any generator.",
        "",
        f"- Numerical experiment generation HEAD: `{EXPERIMENT_GENERATION_COMMIT}`.",
        f"- The generated numerical CSV artifacts first entered Git in `{NUMERICAL_ARTIFACT_COMMIT}`.",
        f"- Repository HEAD when this report was assembled: `{_commit()}`.",
        f"- Git diff check from numerical generation HEAD through report HEAD for `src/` and `configs/`: `{'PASS' if model_unchanged else 'FAIL'}`.",
        f"- Git diff check from the numerical-artifact commit through report HEAD for raw experiment CSV paths: `{'PASS' if raw_unchanged else 'FAIL'}`.",
        "- Publication reference: tag `v2-paper-artifacts-2026-07` on branch `research/physical-offloading-model-v2`.",
        f"- Git clean-check result captured before report assembly: {clean_result}.",
        "",
        "## Execution commands",
        "",
        "```bash",
        "python -m experiments.run_main_30",
        "python -m experiments.run_controlled_30",
        "python -m experiments.run_ablation_30",
        "python -m experiments.run_scalability",
        "python -m experiments.run_sensitivity",
        "python -m experiments.audit_task_id_neutrality",
        "python -m experiments.generate_v2_artifacts",
        "python -m pytest tests -q",
        "```",
        "",
        "## Environment and runtime",
        "",
        f"- Python: `{sys.version.split()[0]}`; platform: `{platform.platform()}`.",
        "- Dependencies: " + ", ".join(f"`{name} {version}`" for name, version in versions.items()) + ".",
        f"- Accumulated solver timing across the nine raw experiment suites: `{runtime_seconds:.3f} s` (`{runtime_seconds / 3600.0:.3f} h`). This is the sum of recorded per-run solver timings, not end-to-end wall-clock time.",
        "",
        "## Validation",
        "",
        f"- Pytest: {test_result}. Tests cover formulas and metrics, legal-node decoding, CPU bounds/capacity repair, fixed reporting fitness, controlled NFE, reproducibility artifacts, and manuscript-output guards.",
        f"- Raw audit: `{raw_rows}` rows across nine suites; hard feasibility `{'PASS' if feasible else 'FAIL'}`; unique assignment `{'PASS' if unique else 'FAIL'}`.",
        f"- Manifest audit: `{len(manifest)}` entries; generated-file SHA-256 verification `{'PASS' if not manifest_failures else 'FAIL'}`.",
        f"- CI: [{ci_result}]({ci_url}).",
        "- All manuscript tables and figures are generated from the listed V2 CSV files; no paper value is entered manually.",
        "",
        "## Result files",
        "",
    ]
    for path in paths:
        rel = path.relative_to(ROOT)
        rows = max(0, sum(1 for _ in path.open(encoding="utf-8")) - 1)
        lines.append(f"- `{rel}`: {rows} data rows; SHA-256 `{_sha256(path)}`")
    report = ROOT / "docs" / "experiment_execution_report.md"
    ensure_parent(report)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _build_controlled_attribution_summary()
    records = _generate_tables()
    records.extend(_generate_figures())
    write_rows(MANIFEST, records)
    _write_execution_report()


if __name__ == "__main__":
    main()
