from __future__ import annotations

from pathlib import Path

import pytest

from scripts.reproaudit_case.source_inventory import CaseContractError

ROOT = Path(__file__).resolve().parents[2]


def _case(tmp_path: Path) -> Path:
    from scripts.reproaudit_case.export_case import export_faithful_case
    case = tmp_path / "case"
    export_faithful_case(ROOT, case)
    return case


@pytest.mark.parametrize("fault_id", ["F001", "F002", "F003", "F004", "F005A", "F005B", "F101", "F102", "F103", "F201", "F202", "F900"])
def test_all_fixed_faults_create_isolated_variant(tmp_path: Path, fault_id: str) -> None:
    from scripts.reproaudit_case.faults import FaultScenario, inject_fault

    case = _case(tmp_path)
    output = tmp_path / fault_id
    result = inject_fault(case, FaultScenario(fault_id), output)
    assert result.scenario_id == fault_id
    assert result.output_dir == output
    assert output != case
    assert result.expected_exit_code in {0, 1, 2, 3}
    assert result.changed_files
    assert case.exists()


def test_fault_rejects_unknown_and_existing_output(tmp_path: Path) -> None:
    from scripts.reproaudit_case.faults import FaultScenario, inject_fault

    case = _case(tmp_path)
    with pytest.raises(CaseContractError, match="unknown fault"):
        inject_fault(case, FaultScenario("NOPE"), tmp_path / "bad")
    output = tmp_path / "existing"
    output.mkdir()
    (output / "sentinel").write_text("x", encoding="utf-8")
    with pytest.raises(CaseContractError, match="empty"):
        inject_fault(case, FaultScenario("F001"), output)
