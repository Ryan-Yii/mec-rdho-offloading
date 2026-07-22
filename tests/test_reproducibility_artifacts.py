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
