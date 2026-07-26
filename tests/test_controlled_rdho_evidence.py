from __future__ import annotations

import copy
import csv
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.controlled_evidence import build_system_from_config, initial_population_for_seed, run_controlled_method
from experiments.controlled_evidence_reporting import repository_v2_hashes
from experiments.experiment_core import load_config, utility_weights_from_config, weights_from_config
from src.experiments.evaluation_budget import EvaluationBudgetManager
from src.metrics import evaluate_solution


@pytest.fixture(scope="module")
def controlled_config():
    config = load_config("configs/controlled_rdho_evidence_v2.yaml")
    config = copy.deepcopy(config)
    config["system"].update({"mobile_devices": 3, "edge_servers": 2, "cloud_servers": 1, "tasks": 3})
    config["experiment"]["population_size"] = 5
    return config


@pytest.fixture(scope="module")
def shared_population(controlled_config):
    return initial_population_for_seed(controlled_config, 20260701)


@pytest.mark.parametrize("method", ["RDHO", "RIME", "DBO"])
def test_population_stage_uses_identical_common_population_and_exact_3801_nfe(controlled_config, shared_population, method):
    result = run_controlled_method(
        controlled_config,
        experiment="controlled_population_stage",
        scenario_seed=20260701,
        run_id=1,
        method=method,
        initial_population=shared_population,
        total_nfe=3801,
        use_common_refinement=False,
        code_commit="test",
    )
    assert result.row["total_nfe"] == 3801
    assert result.row["refinement_nfe"] == 0
    assert result.row["candidate_nfe"] == 3795
    assert result.population_audit["population_hash"] == result.row["initial_population_hash"]
    assert result.row["hard_feasible"] == 1
    assert result.row["assignment_unique"] == 1
    assert result.row["search_fitness_not_reported"] is True


@pytest.mark.parametrize("method", ["RDHO", "RIME", "DBO"])
def test_common_pipeline_uses_shared_refinement_and_exact_10232_nfe(controlled_config, shared_population, method):
    result = run_controlled_method(
        controlled_config,
        experiment="controlled_common_pipeline",
        scenario_seed=20260701,
        run_id=1,
        method=method,
        initial_population=shared_population,
        total_nfe=10232,
        use_common_refinement=True,
        code_commit="test",
    )
    assert result.row["total_nfe"] == 10232
    assert result.row["refinement_nfe"] == 3 * 5 * 5
    assert result.row["population_nfe"] + result.row["refinement_nfe"] == 10232
    assert result.row["hard_feasible"] == 1
    assert result.row["assignment_unique"] == 1


def test_controlled_runs_are_deterministic_and_do_not_mutate_shared_population(controlled_config, shared_population):
    before = np.array(shared_population, copy=True)
    first = run_controlled_method(
        controlled_config,
        experiment="controlled_population_stage",
        scenario_seed=20260701,
        run_id=1,
        method="RDHO",
        initial_population=shared_population,
        total_nfe=3801,
        use_common_refinement=False,
        code_commit="test",
    )
    second = run_controlled_method(
        controlled_config,
        experiment="controlled_population_stage",
        scenario_seed=20260701,
        run_id=1,
        method="RDHO",
        initial_population=shared_population,
        total_nfe=3801,
        use_common_refinement=False,
        code_commit="test",
    )
    assert np.array_equal(shared_population, before)
    assert first.row["initial_population_hash"] == second.row["initial_population_hash"]
    assert first.row["reporting_fitness"] == pytest.approx(second.row["reporting_fitness"])
    assert first.row["reassignment_count"] == second.row["reassignment_count"]


def test_controlled_budget_manager_uses_the_v2_shared_evaluator(controlled_config):
    import src.experiments.evaluation_budget as budget_module

    assert budget_module.evaluate_solution is evaluate_solution
    system = build_system_from_config(controlled_config, 20260701)
    manager = EvaluationBudgetManager(
        system,
        1,
        weights_from_config(controlled_config["weights"]),
        utility_weights_from_config(controlled_config["utility_weights"]),
    )
    metrics = manager.evaluate(np.zeros((len(system.tasks), 2)), stage="initial", penalty_scale=1.0)
    assert manager.nfe == 1
    assert metrics.hard_feasible


def test_all_controlled_methods_receive_the_same_initial_population_hash(controlled_config, shared_population):
    hashes = set()
    for method in ("RDHO", "RIME", "DBO"):
        result = run_controlled_method(
            controlled_config,
            experiment="controlled_population_stage",
            scenario_seed=20260701,
            run_id=1,
            method=method,
            initial_population=shared_population,
            total_nfe=3801,
            use_common_refinement=False,
            code_commit="test",
        )
        hashes.add(result.population_audit["population_hash"])
    assert len(hashes) == 1


def test_v2_integrity_audit_covers_exactly_the_tracked_clean_checkout_files():
    tracked = {
        line
        for line in subprocess.check_output(
            ["git", "ls-files", "--", "results/v2"], text=True
        ).splitlines()
        if line
    }
    current = set(repository_v2_hashes())
    with (ROOT / "results/audit/controlled_evidence_v2_integrity.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        audit = list(csv.DictReader(handle))

    assert current == tracked
    assert {row["path"] for row in audit} == tracked
    assert all(row["unchanged"] == "True" for row in audit)
    assert all(row["sha256_before"] == row["sha256_after"] for row in audit)
