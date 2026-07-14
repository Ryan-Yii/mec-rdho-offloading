import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.experiment_core import (
    backup_legacy_results,
    ensure_fresh_run,
    make_optimizer,
    parse_force_flag,
    run_algorithm_suite,
    run_single_algorithm,
    write_wilcoxon_results,
    write_run_manifest,
)
from experiments.analyze_results import ALGO_ORDER, COLORS, plot_ablation, plot_scalability
from src.metrics import evaluate_solution
from src.task_generator import generate_system


def _system(seed: int = 20260710):
    return generate_system(seed=seed, num_devices=5, num_edge_servers=2, num_cloud_servers=1, num_tasks=8)


def _solution(system):
    solution = np.zeros((len(system.tasks), 2), dtype=float)
    solution[:, 0] = 1
    solution[:, 1] = 0.65
    return solution


def test_objective_decomposition_and_reported_fitness_alias():
    system = _system()
    solution = _solution(system)

    low_penalty = evaluate_solution(system, solution, penalty_scale=0.5)
    high_penalty = evaluate_solution(system, solution, penalty_scale=9.0)

    assert low_penalty.fitness == pytest.approx(low_penalty.reported_fitness)
    assert high_penalty.fitness == pytest.approx(high_penalty.reported_fitness)
    assert low_penalty.report_penalty_scale == pytest.approx(1.0)
    assert low_penalty.reported_fitness == pytest.approx(low_penalty.base_fitness + 1.0 * (1.0 - low_penalty.csr))
    assert low_penalty.search_fitness == pytest.approx(low_penalty.base_fitness + 0.5 * (1.0 - low_penalty.csr))
    assert high_penalty.search_fitness == pytest.approx(high_penalty.base_fitness + 9.0 * (1.0 - high_penalty.csr))
    assert high_penalty.reported_fitness == pytest.approx(low_penalty.reported_fitness)
    assert high_penalty.search_fitness != pytest.approx(low_penalty.search_fitness)
    assert low_penalty.energy_norm > 0
    assert low_penalty.delay_norm > 0
    assert low_penalty.aoi_norm > 0


def test_dynamic_penalty_revaluates_old_and_candidate_with_same_scale():
    system = _system()
    optimizer = make_optimizer(
        algorithm_name="RDHO",
        system=system,
        seed=11,
        max_iter=3,
        population_size=5,
        max_evaluations=500,
    )

    result = optimizer.optimize()

    assert result.fitness == pytest.approx(result.reported_fitness)
    assert result.history[-1] == pytest.approx(result.reported_fitness)
    assert optimizer.penalty_audit
    for record in optimizer.penalty_audit:
        assert record["old_population_penalty_scale"] == pytest.approx(record["candidate_penalty_scale"])
        assert record["reported_best"] == pytest.approx(record["history_value"])


def test_nfe_budget_is_counted_and_reported():
    system = _system()
    row = run_single_algorithm(
        system=system,
        algorithm_name="RIME",
        run_id=1,
        seed=20260710,
        max_iter=5,
        population_size=6,
        max_evaluations=80,
    )

    assert row["nfe_used"] <= row["max_evaluations"] == 80
    assert row["nfe_used"] > 6
    assert row["fitness"] == pytest.approx(row["reported_fitness"])
    assert "base_fitness" in row
    assert "search_fitness" in row


def test_local_refinement_is_explicit_and_ablation_variants_are_separate():
    system = _system()

    ablated_with_refine = make_optimizer(
        algorithm_name="RDHO-w/o dynamic penalty",
        system=system,
        seed=3,
        max_iter=1,
        population_size=4,
        max_evaluations=100,
        local_refinement=True,
    )
    core = make_optimizer(
        algorithm_name="RDHO-core",
        system=system,
        seed=3,
        max_iter=1,
        population_size=4,
        max_evaluations=100,
    )
    full = make_optimizer(
        algorithm_name="RDHO-full",
        system=system,
        seed=3,
        max_iter=1,
        population_size=4,
        max_evaluations=100,
    )

    assert ablated_with_refine.dynamic_penalty is False
    assert ablated_with_refine.local_refinement is True
    assert core.local_refinement is False
    assert full.local_refinement is True


def test_paired_scenario_and_algorithm_seeds_are_recorded():
    config = {
        "system": {"mobile_devices": 5, "edge_servers": 2, "cloud_servers": 1, "tasks": 8},
        "experiment": {
            "seed_start": 20260710,
            "independent_runs": 2,
            "population_size": 5,
            "max_iterations": 2,
            "max_evaluations": 120,
        },
        "weights": {"energy": 0.15, "delay": 0.15, "aoi": 0.20, "qoe": 0.25, "fairness": 0.25},
    }

    rows, _ = run_algorithm_suite(config, ["RDHO", "RIME"], n_runs=2)
    df = pd.DataFrame(rows)

    assert {"scenario_id", "replicate_id", "scenario_seed", "algorithm_seed"} <= set(df.columns)
    for (_, _), group in df.groupby(["scenario_id", "replicate_id"]):
        assert group["scenario_seed"].nunique() == 1
        assert group["algorithm_seed"].nunique() == len(group)


@pytest.mark.parametrize("algorithm_name", ["GA", "PSO", "DE", "Greedy-ED"])
def test_standard_baselines_and_greedy_factory_share_reporting_contract(algorithm_name):
    system = _system()
    optimizer = make_optimizer(
        algorithm_name=algorithm_name,
        system=system,
        seed=9,
        max_iter=2,
        population_size=6,
        max_evaluations=120,
    )

    result = optimizer.optimize()

    assert result.solution.shape == (len(system.tasks), 2)
    assert result.fitness == pytest.approx(result.reported_fitness)
    assert result.nfe_used <= 120


def test_pso_uses_personal_best_state():
    optimizer = make_optimizer(
        algorithm_name="PSO",
        system=_system(),
        seed=19,
        max_iter=2,
        population_size=6,
        max_evaluations=120,
    )

    optimizer.optimize()

    assert optimizer.personal_best.shape == (6, 8, 2)
    assert optimizer.personal_best_fitness.shape == (6,)


def test_local_refinement_uses_final_search_penalty_scale():
    optimizer = make_optimizer(
        algorithm_name="RDHO-full",
        system=_system(),
        seed=21,
        max_iter=1,
        population_size=4,
        max_evaluations=100,
    )

    optimizer.optimize()

    assert optimizer.local_refinement_audit
    expected_scale = optimizer.penalty_scale(optimizer.max_iter)
    assert all(scale == pytest.approx(expected_scale) for scale in optimizer.local_refinement_audit)


def test_local_refinement_budget_is_reserved_under_shared_nfe_cap():
    system = _system()
    optimizers = {
        name: make_optimizer(
            algorithm_name=name,
            system=system,
            seed=23,
            max_iter=100,
            population_size=4,
            max_evaluations=300,
        )
        for name in ("RDHO-core", "RDHO-full", "RIME")
    }

    results = {name: optimizer.optimize() for name, optimizer in optimizers.items()}

    assert optimizers["RDHO-full"].local_refinement_audit
    assert not optimizers["RDHO-core"].local_refinement_audit
    assert max(result.nfe_used for result in results.values()) - min(result.nfe_used for result in results.values()) < 8
    assert all(result.nfe_used <= 300 for result in results.values())


def test_standard_baselines_have_distinct_figure_styles():
    for algorithm in ("GA", "PSO", "DE"):
        assert algorithm in ALGO_ORDER
        assert algorithm in COLORS
    assert len({COLORS[algorithm] for algorithm in ("GA", "PSO", "DE")}) == 3


def test_ablation_and_scalability_figures_are_reproducible(tmp_path):
    ablation_rows = []
    for variant, offset in (("RDHO-core", 0.0), ("RDHO-full", -0.1)):
        for run_id in (1, 2):
            ablation_rows.append({"algorithm": variant, "fitness": 1.0 + offset + 0.01 * run_id})
    scalability_rows = []
    for task_number in (20, 40):
        for run_id in (1, 2):
            scalability_rows.append(
                {
                    "task_number": task_number,
                    "fitness": 0.8 + 0.01 * run_id,
                    "csr": 0.7 - 0.001 * task_number,
                    "runtime": 0.1 * task_number,
                }
            )

    ablation_path = tmp_path / "ablation.png"
    scalability_path = tmp_path / "scalability.png"
    plot_ablation(pd.DataFrame(ablation_rows), ablation_path)
    plot_scalability(pd.DataFrame(scalability_rows), scalability_path)

    assert ablation_path.stat().st_size > 0
    assert scalability_path.stat().st_size > 0


def test_legacy_backup_and_manifest(tmp_path):
    results_root = tmp_path / "results"
    raw_dir = results_root / "raw"
    raw_dir.mkdir(parents=True)
    old_csv = raw_dir / "old.csv"
    old_csv.write_text("algorithm,fitness\nRDHO,1.0\n", encoding="utf-8")

    backup_root = backup_legacy_results(results_root=results_root)
    copied = backup_root / "raw" / "old.csv"
    assert copied.exists()
    assert copied.read_text(encoding="utf-8") == old_csv.read_text(encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"
    manifest = write_run_manifest(
        manifest_path,
        config_path="configs/main_40tasks.yaml",
        output_paths=["results/raw/main_30_raw_results.csv"],
        command=["python", "-m", "experiments.run_main_30", "--force"],
        master_seed=20260710,
        max_evaluations=120,
    )

    assert manifest_path.exists()
    assert manifest["config_hash"]
    assert manifest["git"]["commit"]
    assert manifest["max_evaluations"] == 120
    assert manifest["output_paths"] == ["results/raw/main_30_raw_results.csv"]


def test_force_flag_is_explicit_and_disables_reuse():
    assert parse_force_flag([]) is False
    assert parse_force_flag(["--force"]) is True


def test_existing_formal_outputs_require_force(tmp_path):
    output = tmp_path / "formal.csv"
    output.write_text("old\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        ensure_fresh_run([output], force=False)
    ensure_fresh_run([output], force=True)


def test_wilcoxon_pairs_by_scenario_and_replicate(tmp_path):
    rows = []
    for scenario_id in (1, 2):
        for replicate_id in (1, 2):
            rows.extend(
                [
                    {
                        "run_id": 1,
                        "scenario_id": scenario_id,
                        "replicate_id": replicate_id,
                        "algorithm": "RDHO",
                        "fitness": 0.8 + 0.01 * scenario_id,
                    },
                    {
                        "run_id": 1,
                        "scenario_id": scenario_id,
                        "replicate_id": replicate_id,
                        "algorithm": "RIME",
                        "fitness": 1.0 + 0.01 * replicate_id,
                    },
                ]
            )

    result = write_wilcoxon_results(rows, tmp_path / "wilcoxon.csv")

    comparison = result.loc[result["comparison"] == "RDHO vs RIME"].iloc[0]
    assert comparison["n_pairs"] == 4
