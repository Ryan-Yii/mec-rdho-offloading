import csv
import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from experiments.analyze_results import descriptive_radar_scores


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_baseline_parameters_are_available_and_parseable():
    with (ROOT / "configs" / "baseline_parameters.yaml").open(encoding="utf-8") as handle:
        parameters = yaml.safe_load(handle)

    assert isinstance(parameters, dict)
    assert parameters


def test_main_ablation_scalability_and_sensitivity_outputs_are_present():
    expected = [
        "results/v2/summary/main_30_summary_mean_std.csv",
        "results/v2/summary/equal_nfe_30_summary_mean_std.csv",
        "results/v2/summary/common_control_30_summary_mean_std.csv",
        "results/v2/summary/controlled_attribution_summary.csv",
        "results/v2/summary/ablation_30_summary_mean_std.csv",
        "results/v2/summary/scalability_summary_mean_std.csv",
        "results/v2/sensitivity/summary/weight_sensitivity_summary_mean_std.csv",
        "results/v2/sensitivity/summary/dynamic_penalty_sensitivity_summary_mean_std.csv",
        "results/v2/sensitivity/summary/utility_sensitivity_summary_mean_std.csv",
        "results/v2/sensitivity/summary/physical_sensitivity_summary_mean_std.csv",
    ]

    for relative_path in expected:
        artifact = ROOT / relative_path
        assert artifact.is_file()
        assert artifact.stat().st_size > 0


def test_task_id_neutrality_audit_is_deterministic_and_non_significant():
    from experiments.audit_task_id_neutrality import build_audit_rows

    rows = build_audit_rows()
    assert [row["relationship"] for row in rows] == [
        "task_id_vs_priority",
        "task_id_quartile_vs_task_type",
        "task_id_quartile_vs_source_device",
    ]
    assert all(row["sample_count"] == 1200 for row in rows)
    assert all(float(row["p_value"]) > 0.05 for row in rows)


def test_controlled_attribution_replaces_paper_radar_artifact():
    figure_dir = ROOT / "figures" / "paper" / "v2"
    assert (figure_dir / "figure_12_controlled_attribution.png").is_file()
    assert (figure_dir / "figure_12_controlled_attribution.svg").is_file()
    assert (figure_dir / "figure_s5_descriptive_main_comparison_radar.png").is_file()
    radar_svg = figure_dir / "figure_s5_descriptive_main_comparison_radar.svg"
    assert radar_svg.is_file()
    radar_text = radar_svg.read_text(encoding="utf-8")
    assert "Active-user" in radar_text
    assert "base-utility fairness" in radar_text
    assert "no uncertainty shown" in radar_text
    assert not (figure_dir / "figure_12_radar_chart.png").exists()
    assert not (figure_dir / "figure_12_radar_chart.svg").exists()


def test_supplementary_radar_scores_have_explicit_direction_and_bounds():
    frame = pd.DataFrame(
        {
            "algorithm": ["RDHO", "RIME"],
            "energy": [10.0, 20.0],
            "delay": [2.0, 1.0],
            "aoi": [5.0, 5.0],
            "qoe": [0.4, 0.8],
            "fairness": [0.6, 0.6],
        }
    )

    algorithms, scores = descriptive_radar_scores(frame)

    assert algorithms == ["RDHO", "RIME"]
    np.testing.assert_allclose(scores["energy"], [1.0, 0.0])
    np.testing.assert_allclose(scores["delay"], [0.0, 1.0])
    np.testing.assert_allclose(scores["aoi"], [1.0, 1.0])
    np.testing.assert_allclose(scores["qoe"], [0.0, 1.0])
    np.testing.assert_allclose(scores["fairness"], [1.0, 1.0])
    assert all(np.all((values >= 0.0) & (values <= 1.0)) for values in scores.values())


def test_scalability_rows_record_assignment_uniqueness():
    with (ROOT / "results" / "v2" / "raw" / "scalability_raw_results.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert all(row["assignment_unique"] == "1" for row in rows)


def test_all_1580_primary_rows_are_hard_feasible_and_unique():
    paths = [
        ROOT / "results/v2/raw/main_30_raw_results.csv",
        ROOT / "results/v2/raw/equal_nfe_30_raw_results.csv",
        ROOT / "results/v2/raw/common_control_30_raw_results.csv",
        ROOT / "results/v2/raw/ablation_30_raw_results.csv",
        ROOT / "results/v2/raw/scalability_raw_results.csv",
        ROOT / "results/v2/sensitivity/raw/weight_sensitivity_raw_results.csv",
        ROOT / "results/v2/sensitivity/raw/dynamic_penalty_sensitivity_raw_results.csv",
        ROOT / "results/v2/sensitivity/raw/utility_sensitivity_raw_results.csv",
        ROOT / "results/v2/sensitivity/raw/physical_sensitivity_raw_results.csv",
    ]
    rows = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle))

    assert len(rows) == 1580
    assert all(row["hard_feasible"] == "1" for row in rows)
    assert all(row["assignment_unique"] == "1" for row in rows)


def test_readme_rdho_full_values_match_main_summary():
    with (ROOT / "results" / "v2" / "summary" / "main_30_summary_mean_std.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rdho = next(row for row in rows if row["algorithm"] == "RDHO")

    expected_row = (
        "| RDHO-full | "
        f"{float(rdho['fitness_mean']):.4f} | "
        f"{float(rdho['qoe_mean']):.4f} | "
        f"{float(rdho['fairness_mean']):.4f} | "
        f"{float(rdho['csr_mean']):.4f} | "
        f"{float(rdho['runtime_mean']):.4f} | "
        f"{int(float(rdho['nfe_mean']))} |"
    )
    assert expected_row in (ROOT / "README.md").read_text(encoding="utf-8")


def test_paper_table_rdho_values_match_main_summary():
    with (ROOT / "results" / "v2" / "summary" / "main_30_summary_mean_std.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rdho = next(row for row in rows if row["algorithm"] == "RDHO")
    table = (ROOT / "paper_tables" / "v2" / "main_30_summary_mean_std.md").read_text(encoding="utf-8")

    row = next(line for line in table.splitlines() if re.match(r"\| RDHO\s+\|", line))
    assert f"{float(rdho['fitness_mean']):.6f}" in row
    assert f"{float(rdho['qoe_mean']):.6f}" in row
    assert f"{float(rdho['fairness_mean']):.6f}" in row
    assert f"{float(rdho['csr_mean']):.6f}" in row


def test_release_manifests_match_every_versioned_artifact():
    with (ROOT / "paper_artifacts/manifest.csv").open(newline="", encoding="utf-8") as handle:
        paper_rows = list(csv.DictReader(handle))
    assert len(paper_rows) == 61
    for row in paper_rows:
        path = ROOT / row["generated_file"]
        assert path.is_file()
        assert _sha256(path) == row["file_hash"]

    with (ROOT / "results/audit/controlled_evidence_sha256.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        controlled_rows = list(csv.DictReader(handle))
    for row in controlled_rows:
        path = ROOT / row["path"]
        assert path.is_file()
        assert path.stat().st_size == int(row["bytes"])
        assert _sha256(path) == row["sha256"]

    for manifest in sorted((ROOT / "paper_artifacts").glob("*/paper_artifact_manifest.csv")):
        with manifest.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            path = ROOT / row["generated_file"]
            assert path.is_file()
            assert _sha256(path) == row["file_hash"]

        hashes = manifest.with_name("deliverable_hashes.sha256")
        for line in hashes.read_text(encoding="utf-8").splitlines():
            expected, relative_path = line.split("  ", 1)
            path = ROOT / relative_path
            assert path.is_file()
            assert _sha256(path) == expected
