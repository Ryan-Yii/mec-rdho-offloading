from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.reproaudit_case.source_inventory import CaseContractError

ROOT = Path(__file__).resolve().parents[2]


def _case(tmp_path: Path) -> Path:
    from scripts.reproaudit_case.export_case import export_faithful_case

    case = tmp_path / "case"
    export_faithful_case(ROOT, case)
    return case


def test_oracle_is_independent_and_deterministic(tmp_path: Path) -> None:
    import scripts.reproaudit_case.oracle as module

    case = _case(tmp_path)
    first = tmp_path / "oracle-a"
    second = tmp_path / "oracle-b"
    report_a = module.run_independent_oracle(case, first)
    report_b = module.run_independent_oracle(case, second)
    assert report_a == report_b
    assert (first / "oracle-report.json").read_bytes() == (second / "oracle-report.json").read_bytes()
    payload = json.loads((first / "oracle-report.json").read_text(encoding="utf-8"))
    assert payload["raw"]["row_count"] == 180
    assert payload["raw"]["algorithms"] == ["RDHO", "RIME", "DBO", "TLBO-HHO", "CWTSSA", "Greedy-ED"]
    assert payload["claims"]["entered_count"] == 12
    assert payload["claims"]["max_absolute_difference"] == pytest.approx(0.0000482372898956)
    assert 'reproaudit' not in module.__dict__


def test_oracle_rejects_nonfinite_raw_metric(tmp_path: Path) -> None:
    import scripts.reproaudit_case.oracle as module

    case = _case(tmp_path)
    raw = case / "raw_results.csv"
    raw.write_text(raw.read_text(encoding="utf-8").replace("1.1085684341068993", "nan", 1), encoding="utf-8")
    with pytest.raises(CaseContractError, match="nonfinite"):
        module.run_independent_oracle(case, tmp_path / "oracle")
