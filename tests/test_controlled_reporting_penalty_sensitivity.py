from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.analyze_controlled_reporting_penalty_sensitivity import analyse, write_outputs


def test_fixed_return_reporting_penalty_sensitivity_reproduces_lambda_one_and_writes_outputs(tmp_path):
    summary, paired = analyse(ROOT / "results" / "raw")
    lambda_one = summary.loc[summary["lambda_ref"] == 1.0]
    assert len(summary) == 18
    assert len(paired) == 12
    assert lambda_one["fixed_return_fitness_mean"].notna().all()
    assert set(paired["comparison"]) == {"RDHO vs RIME", "RDHO vs DBO"}
    assert paired["p_value_holm"].between(0.0, 1.0).all()
    assert paired["significant_holm_0_05"].dtype == bool
    write_outputs(summary, paired, tmp_path)
    assert (tmp_path / "results/statistics/controlled_reporting_penalty_sensitivity.csv").is_file()
    assert (tmp_path / "results/statistics/controlled_reporting_penalty_sensitivity_paired.csv").is_file()
    assert (tmp_path / "paper_tables/controlled_reporting_penalty_sensitivity.md").is_file()
    assert (tmp_path / "docs/controlled_reporting_penalty_sensitivity_report.md").is_file()
