from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.reproaudit_case.source_inventory import CaseContractError

ROOT = Path(__file__).resolve().parents[2]


def test_extract_claims_has_19_entered_traces_and_exact_values(tmp_path: Path) -> None:
    import scripts.reproaudit_case.extract_claims as module

    destination = tmp_path / "claims.yaml"
    traces = module.extract_claims(ROOT, destination)
    assert len(traces) == 20
    payload = yaml.safe_load(destination.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["experiment_claims"] == {
        "runs": 30,
        "parameters": {
            "mobile_devices": 20,
            "edge_servers": 4,
            "cloud_servers": 2,
            "task_count": 40,
            "population_size": 50,
            "max_iterations": 150,
        },
    }
    assert payload["reported_results"][0] == {
        "algorithm": "RDHO", "metric": "fitness", "mean": "0.9470"
    }
    assert len(payload["reported_results"]) == 12
    assert "best_algorithm" not in payload.get("conclusions", {})
    assert payload["audit"] == {"absolute_tolerance": 0.00005, "relative_tolerance": 0.0}
    assert traces[-1]["disposition"] == "R202_SKIP"


def test_extract_claims_accepts_only_exact_rdho_full_normalization(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.reproaudit_case.extract_claims as module

    for label in ("RDHO Full", "rdho-full", "unknown"):
        monkeypatch.setattr(module, "_README_TABLE", lambda _text, label=label: [(label, "0.1", "0.2")])
        with pytest.raises(CaseContractError, match="unknown README algorithm"):
            module.extract_claims(ROOT, tmp_path / f"{label}.yaml")


def test_extract_claims_does_not_overwrite_or_accept_readme_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.reproaudit_case.extract_claims as module

    destination = tmp_path / "claims.yaml"
    destination.write_bytes(b"sentinel\n")
    with pytest.raises(FileExistsError):
        module.extract_claims(ROOT, destination)
    assert destination.read_bytes() == b"sentinel\n"

    (tmp_path / "README.md").write_text((ROOT / "README.md").read_text(encoding="utf-8") + "\n", encoding="utf-8")
    monkeypatch.setattr(module, "README_PATH", "README.md")
    with pytest.raises(CaseContractError, match="source hash drift"):
        module.extract_claims(tmp_path, tmp_path / "out.yaml")
