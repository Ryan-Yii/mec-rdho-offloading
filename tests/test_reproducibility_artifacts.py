import csv
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


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
    assert not (figure_dir / "figure_12_radar_chart.png").exists()
    assert not (figure_dir / "figure_12_radar_chart.svg").exists()


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
