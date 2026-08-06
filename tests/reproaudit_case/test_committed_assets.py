from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml


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


def test_committed_claims_match_current_exporter_and_official_shape(tmp_path: Path) -> None:
    from scripts.reproaudit_case.export_case import export_faithful_case

    generated = tmp_path / "generated"
    export_faithful_case(ROOT, generated)
    committed = ASSET / "faithful_baseline" / "claims.yaml"
    assert (generated / "claims.yaml").read_bytes() == committed.read_bytes()

    claims = yaml.safe_load(committed.read_text(encoding="utf-8"))
    assert claims["experiment_claims"] == {"runs": 30}
    assert claims["parameter_claims"]["max_iterations"] == 150
    assert claims["reported_results"]["RDHO"]["fitness"] == {"mean": 0.9470}
    assert "parameters" not in claims["experiment_claims"]


def test_official_release_schema_accepts_generated_and_committed_claims(tmp_path: Path) -> None:
    runtime_python = os.environ.get("REPROAUDIT_OFFICIAL_RUNTIME_PYTHON")
    if runtime_python is None:
        pytest.skip("official ReproAudit runtime is supplied only for integration verification")

    from scripts.reproaudit_case.export_case import export_faithful_case

    generated = tmp_path / "generated"
    export_faithful_case(ROOT, generated)
    validation = "from pathlib import Path; import sys, yaml; from reproaudit.models import ClaimsConfig; ClaimsConfig.model_validate(yaml.safe_load(Path(sys.argv[1]).read_text(encoding='utf-8')))"
    for claims_path in (generated / "claims.yaml", ASSET / "faithful_baseline" / "claims.yaml"):
        result = subprocess.run(
            [runtime_python, "-c", validation, str(claims_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        assert result.returncode == 0, result.stdout

    legacy = tmp_path / "legacy-claims.yaml"
    legacy.write_text("schema_version: '1.0'\nexperiment_claims:\n  runs: 30\n  parameters:\n    max_iterations: 150\n", encoding="utf-8")
    rejection = subprocess.run(
        [runtime_python, "-c", validation, str(legacy)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert rejection.returncode != 0
    assert "parameters" in rejection.stdout
