from __future__ import annotations

from pathlib import Path
import csv

import pytest
import yaml

from scripts.reproaudit_case.source_inventory import CaseContractError
from scripts.reproaudit_case.export_case import export_experiment


ROOT = Path(__file__).resolve().parents[2]


def test_experiment_export_has_exact_schema_and_values(tmp_path: Path) -> None:
    destination = tmp_path / "experiment.yaml"
    assert export_experiment(ROOT, destination) == destination

    payload = yaml.safe_load(destination.read_text(encoding="utf-8"))
    assert list(payload) == [
        "schema_version",
        "experiment",
        "execution",
        "algorithms",
        "parameters",
        "metrics",
    ]
    assert payload == {
        "schema_version": "1.0",
        "experiment": {
            "name": "MEC main 40-task paired benchmark",
            "task": "MEC task offloading and CPU allocation",
        },
        "execution": {"runs": 30, "seed_column": "seed"},
        "algorithms": ["RDHO", "RIME", "DBO", "TLBO-HHO", "CWTSSA", "Greedy-ED"],
        "parameters": {
            "mobile_devices": 20,
            "edge_servers": 4,
            "cloud_servers": 2,
            "task_count": 40,
            "population_size": 50,
            "max_iterations": 150,
            "seed_start": 20260701,
        },
        "metrics": {
            "fitness": {"direction": "minimize", "primary": True},
            "csr": {"direction": "maximize", "primary": False},
        },
    }
    assert destination.read_bytes().endswith(b"\n")
    assert not destination.read_bytes().endswith(b"\n\n")
    assert "!!python" not in destination.read_text(encoding="utf-8")


def test_experiment_export_is_deterministic_and_does_not_overwrite(tmp_path: Path) -> None:
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    export_experiment(ROOT, first)
    export_experiment(ROOT, second)
    assert first.read_bytes() == second.read_bytes()

    existing = tmp_path / "existing.yaml"
    existing.write_bytes(b"sentinel\n")
    with pytest.raises(FileExistsError):
        export_experiment(ROOT, existing)
    assert existing.read_bytes() == b"sentinel\n"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data["experiment"].pop("algorithms"), "missing experiment.algorithms"),
        (lambda data: data.pop("weights"), "missing config.weights"),
        (lambda data: data["system"].__setitem__("unexpected", 1), "unsupported config field"),
    ],
)
def test_experiment_export_rejects_missing_or_unsupported_fields(
    tmp_path: Path, mutation, message: str
) -> None:
    config = yaml.safe_load((ROOT / "configs/main_40tasks.yaml").read_text(encoding="utf-8"))
    mutation(config)
    import scripts.reproaudit_case.export_case as module

    with pytest.raises(CaseContractError, match=message):
        module._export_experiment_from_config(config, tmp_path / "out.yaml")


def test_experiment_export_rejects_config_source_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.reproaudit_case.export_case as module

    original = (ROOT / "configs/main_40tasks.yaml").read_text(encoding="utf-8")
    mutated = original.replace("population_size: 50", "population_size: 51")
    source = tmp_path / "configs"
    source.mkdir()
    (source / "main_40tasks.yaml").write_text(mutated, encoding="utf-8")
    monkeypatch.setattr(module, "CONFIG_PATH", "configs/main_40tasks.yaml")
    with pytest.raises(CaseContractError, match="source hash drift"):
        module.export_experiment(tmp_path, tmp_path / "out.yaml")


def test_raw_export_has_fixed_shape_order_status_and_roundtrip(tmp_path: Path) -> None:
    import scripts.reproaudit_case.export_case as module

    destination = tmp_path / "raw_results.csv"
    result = module.export_raw_results(ROOT, destination)
    assert result == destination
    with destination.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0]) == ["seed", "algorithm", "status", "fitness", "csr"]
    assert len(rows) == 180
    assert {row["status"] for row in rows} == {"success"}
    assert len({(row["seed"], row["algorithm"]) for row in rows}) == 180
    assert {row["algorithm"] for row in rows} == {
        "RDHO", "RIME", "DBO", "TLBO-HHO", "CWTSSA", "Greedy-ED"
    }
    assert "run_id" not in rows[0]
    assert destination.read_bytes().count(b"\r") == 0
    assert destination.read_bytes().endswith(b"\n")


def test_raw_export_does_not_overwrite(tmp_path: Path) -> None:
    import scripts.reproaudit_case.export_case as module

    destination = tmp_path / "raw_results.csv"
    destination.write_bytes(b"sentinel\n")
    with pytest.raises(FileExistsError):
        module.export_raw_results(ROOT, destination)
    assert destination.read_bytes() == b"sentinel\n"


def test_raw_export_rejects_source_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.reproaudit_case.export_case as module

    monkeypatch.setattr(module, "RAW_PATH", "results/v2/raw/main_30_raw_results.csv")
    source = tmp_path / "results/v2/raw"
    source.mkdir(parents=True)
    original = (ROOT / "results/v2/raw/main_30_raw_results.csv").read_bytes()
    (source / "main_30_raw_results.csv").write_bytes(original + b"\n")
    with pytest.raises(CaseContractError, match="source hash drift"):
        module.export_raw_results(tmp_path, tmp_path / "out.csv")


def test_summary_export_projects_official_fields_and_structural_stats(tmp_path: Path) -> None:
    import scripts.reproaudit_case.export_case as module

    destination = tmp_path / "summary_results.csv"
    result = module.export_summary_results(ROOT, destination)
    assert result == destination
    with destination.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0]) == ["algorithm", "metric", "mean", "std", "median", "n"]
    assert len(rows) == 12
    assert [(row["algorithm"], row["metric"]) for row in rows[:4]] == [
        ("RDHO", "fitness"), ("RDHO", "csr"), ("RIME", "fitness"), ("RIME", "csr")
    ]
    rdho_fitness = rows[0]
    assert rdho_fitness["mean"] == "0.9470392278303288"
    assert rdho_fitness["std"] == "0.12019325475607968"
    assert rdho_fitness["n"] == "30"
    assert float(rdho_fitness["median"]) == pytest.approx(0.9528122665474945)
    assert destination.read_bytes().count(b"\r") == 0


def test_summary_export_rejects_source_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.reproaudit_case.export_case as module

    monkeypatch.setattr(module, "SUMMARY_PATH", "results/v2/summary/main_30_summary_mean_std.csv")
    source = tmp_path / "results/v2/summary"
    source.mkdir(parents=True)
    original = (ROOT / "results/v2/summary/main_30_summary_mean_std.csv").read_bytes()
    (source / "main_30_summary_mean_std.csv").write_bytes(original + b"\n")
    with pytest.raises(CaseContractError, match="source hash drift"):
        module.export_summary_results(tmp_path, tmp_path / "out.csv")


def test_faithful_export_is_complete_deterministic_and_source_safe(tmp_path: Path) -> None:
    import scripts.reproaudit_case.export_case as module

    first = tmp_path / "case-a"
    second = tmp_path / "case-b"
    result = module.export_faithful_case(ROOT, first)
    module.export_faithful_case(ROOT, second)
    assert result.output_dir == first
    expected = {"experiment.yaml", "claims.yaml", "raw_results.csv", "summary_results.csv", "source_manifest.json"}
    assert {path.name for path in first.iterdir()} == expected
    for name in expected:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    manifest = (first / "source_manifest.json").read_text(encoding="utf-8")
    assert "/Users/" not in manifest and '"generated_at":' not in manifest
    assert "faithful_baseline" in manifest


def test_faithful_export_materializes_official_claim_shape(tmp_path: Path) -> None:
    import scripts.reproaudit_case.export_case as module

    case = tmp_path / "case"
    module.export_faithful_case(ROOT, case)
    claims = yaml.safe_load((case / "claims.yaml").read_text(encoding="utf-8"))
    assert claims["experiment_claims"] == {"runs": 30}
    assert claims["parameter_claims"]["max_iterations"] == 150
    assert claims["reported_results"]["RDHO"]["fitness"] == {"mean": 0.9470}
    assert "parameters" not in claims["experiment_claims"]


def test_faithful_export_rejects_nonempty_and_source_contained_output(tmp_path: Path) -> None:
    import scripts.reproaudit_case.export_case as module

    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "sentinel").write_text("x", encoding="utf-8")
    with pytest.raises(CaseContractError, match="empty"):
        module.export_faithful_case(ROOT, nonempty)
    with pytest.raises(CaseContractError, match="inside repository"):
        module.export_faithful_case(ROOT, ROOT / "case_studies/reproaudit_v0_1/faithful_baseline")


def test_experiment_export_rejects_parameter_drift(tmp_path: Path) -> None:
    config = yaml.safe_load((ROOT / "configs/main_40tasks.yaml").read_text(encoding="utf-8"))
    config["system"]["tasks"] = 41
    with pytest.raises(CaseContractError, match="system.tasks must equal 40"):
        export_module = __import__("scripts.reproaudit_case.export_case", fromlist=["_export_experiment_from_config"])
        export_module._export_experiment_from_config(config, tmp_path / "out.yaml")
