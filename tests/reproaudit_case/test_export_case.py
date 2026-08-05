from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.reproaudit_case.source_inventory import CaseContractError
from scripts.reproaudit_case.export_case import export_experiment


ROOT = Path(__file__).resolve().parents[2]


def test_experiment_export_has_exact_schema_and_values(tmp_path: Path) -> None:
    destination = tmp_path / "experiment.yaml"
    export_experiment(ROOT, destination)

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


def test_experiment_export_rejects_parameter_drift(tmp_path: Path) -> None:
    config = yaml.safe_load((ROOT / "configs/main_40tasks.yaml").read_text(encoding="utf-8"))
    config["system"]["tasks"] = 41
    with pytest.raises(CaseContractError, match="system.tasks must equal 40"):
        export_module = __import__("scripts.reproaudit_case.export_case", fromlist=["_export_experiment_from_config"])
        export_module._export_experiment_from_config(config, tmp_path / "out.yaml")
