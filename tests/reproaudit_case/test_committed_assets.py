from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "case_studies/reproaudit_v0_1"


def test_committed_assets_have_fixed_files_shapes_and_matrices() -> None:
    baseline = ASSET / "faithful_baseline"
    assert {path.name for path in baseline.iterdir()} == {"experiment.yaml", "claims.yaml", "raw_results.csv", "summary_results.csv"}
    manifest = json.loads((ASSET / "source_manifest.json").read_text(encoding="utf-8"))
    assert manifest["case_id"] == "faithful_baseline"
    assert manifest["mec_commit"] == "b8abb436f215a9b2f4d646cf5fc0cf048174b68d"
    expected = json.loads((ASSET / "expected/baseline_expectations.json").read_text(encoding="utf-8"))
    assert expected["exit_code"] == 0
    assert [finding["rule_id"] for finding in expected["findings"]] == ["R001", "R002", "R003", "R004", "R005", "R101", "R102", "R103", "R201", "R202"]
    fault = json.loads((ASSET / "expected/fault_matrix.json").read_text(encoding="utf-8"))
    assert set(fault) == {"F001", "F002", "F003", "F004", "F005A", "F005B", "F101", "F102", "F103", "F201", "F202", "F900"}


def test_reports_are_marker_only_and_assets_have_no_dynamic_metadata() -> None:
    reports = ASSET / "reports"
    assert (reports / ".gitkeep").is_file()
    assert [path.name for path in reports.iterdir()] == [".gitkeep"]
    text = "\n".join(path.read_text(encoding="utf-8") for path in ASSET.rglob("*") if path.is_file() and path.name != ".gitkeep")
    assert "/Users/" not in text and '"generated_at":' not in text and "uuid" not in text.lower()
