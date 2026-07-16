from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from experiments.audit_results import audit_main_frame
from experiments.checkpointing import CheckpointStore
from experiments.experiment_core import RDHO_VARIANTS, make_optimizer
from experiments.run_sensitivity import WEIGHT_ALGORITHMS, build_weight_run_plan
from experiments.statistical_analysis import (
    PRIMARY_ALGORITHMS,
    average_ranks,
    friedman_tests,
    pairwise_tests,
)
from experiments.validate_artifacts import validate_statistical_separation, verify_manifest_records
from src.metrics import FitnessWeights
from src.task_generator import generate_system


APPROVED_ABLATION_VARIANTS = (
    "RDHO-core",
    "RDHO-core w/o hybrid RIME-DBO fusion",
    "RDHO-core w/o dual-source initialization",
    "RDHO-core w/o adaptive role allocation",
    "RDHO-core w/o elite preservation",
    "RDHO-core w/o dynamic penalty",
    "RDHO-full",
)


def _system():
    return generate_system(
        seed=20260716,
        num_devices=5,
        num_edge_servers=2,
        num_cloud_servers=1,
        num_tasks=8,
    )


def _paired_frame(algorithms=PRIMARY_ALGORITHMS, settings=("S1",)) -> pd.DataFrame:
    rows = []
    for setting_index, setting in enumerate(settings):
        for scenario_id in range(1, 7):
            for algorithm_index, algorithm in enumerate(algorithms):
                rows.append(
                    {
                        "setting": setting,
                        "scenario_id": scenario_id,
                        "replicate_id": 1,
                        "algorithm": algorithm,
                        "fitness": 0.70 + 0.03 * algorithm_index + 0.001 * scenario_id + 0.01 * setting_index,
                    }
                )
    return pd.DataFrame(rows)


def test_approved_ablation_variants_have_isolated_flags():
    assert tuple(RDHO_VARIANTS) == APPROVED_ABLATION_VARIANTS
    assert RDHO_VARIANTS["RDHO-core w/o hybrid RIME-DBO fusion"] == {
        "hybrid_update": False,
        "local_refinement": False,
    }
    assert RDHO_VARIANTS["RDHO-core w/o dual-source initialization"] == {
        "dual_source_initialization": False,
        "local_refinement": False,
    }
    assert all(
        options["local_refinement"] is False
        for name, options in RDHO_VARIANTS.items()
        if name.startswith("RDHO-core")
    )
    assert RDHO_VARIANTS["RDHO-full"]["local_refinement"] is True


def test_no_hybrid_variant_uses_the_predefined_nonhybrid_update():
    first = make_optimizer(
        "RDHO-core w/o hybrid RIME-DBO fusion",
        _system(),
        seed=41,
        max_iter=10,
        population_size=4,
        max_evaluations=100,
    )
    second = make_optimizer(
        "RDHO-core w/o hybrid RIME-DBO fusion",
        _system(),
        seed=41,
        max_iter=10,
        population_size=4,
        max_evaluations=100,
    )
    shape = (8, 2)
    best = np.full(shape, 0.75)

    update_a = first._producer_update(np.zeros(shape), best, np.ones(shape), iteration=3)
    update_b = second._producer_update(np.full(shape, 9.0), best, np.full(shape, -9.0), iteration=3)

    assert first.hybrid_update is False
    assert np.array_equal(update_a, update_b)


def test_primary_statistics_are_key_aligned_and_exclude_greedy():
    assert tuple(PRIMARY_ALGORITHMS) == tuple(WEIGHT_ALGORITHMS)
    assert "Greedy-ED" not in PRIMARY_ALGORITHMS
    frame = _paired_frame()
    shuffled = frame.sample(frac=1.0, random_state=7).reset_index(drop=True)

    omnibus = friedman_tests(shuffled, PRIMARY_ALGORITHMS)
    comparisons = pairwise_tests(
        shuffled,
        reference_algorithm="RDHO",
        comparison_algorithms=PRIMARY_ALGORITHMS[1:],
        bootstrap_samples=500,
        bootstrap_seed=123,
    )

    assert omnibus.iloc[0]["n_blocks"] == 6
    assert omnibus.iloc[0]["n_algorithms"] == 8
    assert len(comparisons) == 7
    assert comparisons["inference_tier"].eq("primary_equal_budget").all()
    assert comparisons["equal_budget"].all()
    assert set(comparisons["wins"]) == {6}
    assert set(comparisons["ties"]) == {0}
    assert set(comparisons["losses"]) == {0}
    assert comparisons["holm_family_size"].eq(7).all()


def test_statistics_reject_duplicate_and_incomplete_pairing():
    frame = _paired_frame()
    with pytest.raises(ValueError, match="duplicate paired result"):
        friedman_tests(pd.concat([frame, frame.iloc[[0]]], ignore_index=True), PRIMARY_ALGORITHMS)

    incomplete = frame.drop(frame.index[-1])
    with pytest.raises(ValueError, match="incomplete paired result"):
        pairwise_tests(
            incomplete,
            reference_algorithm="RDHO",
            comparison_algorithms=PRIMARY_ALGORITHMS[1:],
        )


def test_pairwise_bootstrap_ci_is_deterministic_and_greedy_is_supplementary():
    frame = _paired_frame((*PRIMARY_ALGORITHMS, "Greedy-ED"))
    first = pairwise_tests(
        frame,
        reference_algorithm="RDHO",
        comparison_algorithms=["Greedy-ED"],
        inference_tier="supplementary_effectiveness_vs_cost",
        equal_budget=False,
        bootstrap_samples=1000,
        bootstrap_seed=987,
    )
    second = pairwise_tests(
        frame,
        reference_algorithm="RDHO",
        comparison_algorithms=["Greedy-ED"],
        inference_tier="supplementary_effectiveness_vs_cost",
        equal_budget=False,
        bootstrap_samples=1000,
        bootstrap_seed=987,
    )

    pd.testing.assert_frame_equal(first, second)
    record = first.iloc[0]
    assert record["equal_budget"] == False  # noqa: E712
    assert record["holm_family_size"] == 1
    assert record["mean_difference_ci_low"] <= record["mean_difference"] <= record["mean_difference_ci_high"]


def test_weight_ranks_are_computed_within_each_setting():
    frame = _paired_frame(settings=("S1", "S2"))
    ranks = average_ranks(frame, PRIMARY_ALGORITHMS, group_cols=["setting"])

    assert set(ranks["setting"]) == {"S1", "S2"}
    assert ranks.groupby("setting")["algorithm"].nunique().eq(8).all()
    assert ranks.loc[ranks["algorithm"] == "RDHO", "mean_rank"].eq(1.0).all()
    assert ranks.groupby("setting")["rank_order"].min().eq(1).all()


def test_weight_run_plan_contains_all_settings_and_only_primary_algorithms():
    config = {
        "experiment": {"independent_runs": 2, "master_seed": 20260701, "seed_start": 20260701},
        "weight_settings": [
            {"setting": "S1", "description": "one", "weights": {"energy": 0.2, "delay": 0.2, "aoi": 0.2, "qoe": 0.2, "fairness": 0.2}},
            {"setting": "S2", "description": "two", "weights": {"energy": 0.1, "delay": 0.2, "aoi": 0.3, "qoe": 0.2, "fairness": 0.2}},
        ],
    }

    plan = build_weight_run_plan(config)

    assert len(plan) == 2 * 2 * 8
    assert set(item["algorithm"] for item in plan) == set(PRIMARY_ALGORITHMS)
    for (_, scenario_id), group in pd.DataFrame(plan).groupby(["setting", "scenario_id"]):
        assert group["scenario_seed"].nunique() == 1
        assert group["algorithm_seed"].nunique() == 8


def test_checkpoint_resume_requires_an_exact_contract_and_unique_keys(tmp_path):
    raw_path = tmp_path / "checkpoint.csv"
    contract_path = tmp_path / "contract.json"
    contract = {"schema_version": 1, "config_hash": "abc", "algorithms": list(PRIMARY_ALGORITHMS)}
    store = CheckpointStore(
        raw_path,
        contract_path,
        contract=contract,
        key_columns=("setting", "scenario_id", "replicate_id", "algorithm"),
    )
    store.initialize(force=True)
    row = {"setting": "S1", "scenario_id": 1, "replicate_id": 1, "algorithm": "RDHO", "fitness": 0.8}
    store.append(row)

    resumed = CheckpointStore(
        raw_path,
        contract_path,
        contract=contract,
        key_columns=("setting", "scenario_id", "replicate_id", "algorithm"),
    )
    resumed.initialize(resume=True)
    assert resumed.has_key(row)
    with pytest.raises(ValueError, match="duplicate checkpoint key"):
        resumed.append(row)

    mismatched = CheckpointStore(
        raw_path,
        contract_path,
        contract={**contract, "config_hash": "changed"},
        key_columns=("setting", "scenario_id", "replicate_id", "algorithm"),
    )
    with pytest.raises(RuntimeError, match="checkpoint contract mismatch"):
        mismatched.initialize(resume=True)
    assert json.loads(contract_path.read_text(encoding="utf-8")) == contract


def _auditable_main_frame() -> pd.DataFrame:
    rows = []
    weights = FitnessWeights()
    algorithms = (*PRIMARY_ALGORITHMS, "Greedy-ED")
    for scenario_id in (1, 2):
        for algorithm_index, algorithm in enumerate(algorithms):
            energy_norm = 0.40 + 0.01 * algorithm_index
            delay_norm = 0.50
            aoi_norm = 0.60
            qoe = 0.70
            fairness = 0.90
            csr = 0.80
            base = (
                weights.energy * energy_norm
                + weights.delay * delay_norm
                + weights.aoi * aoi_norm
                + weights.qoe * (1.0 - qoe)
                + weights.fairness * (1.0 - fairness)
            )
            reported = base + 1.0 - csr
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "replicate_id": 1,
                    "scenario_seed": 1000 + scenario_id,
                    "algorithm_seed": 100_000 * scenario_id + algorithm_index,
                    "algorithm": algorithm,
                    "fitness": reported,
                    "reported_fitness": reported,
                    "base_fitness": base,
                    "report_penalty_scale": 1.0,
                    "report_penalty": 1.0 - csr,
                    "energy_norm": energy_norm,
                    "delay_norm": delay_norm,
                    "aoi_norm": aoi_norm,
                    "qoe": qoe,
                    "fairness": fairness,
                    "csr": csr,
                    "nfe_used": 100 if algorithm != "Greedy-ED" else 10,
                    "max_evaluations": 100,
                }
            )
    return pd.DataFrame(rows)


def test_main_audit_recomputes_objective_and_reports_pairwise_outcomes(tmp_path):
    frame = _auditable_main_frame()
    report_path = tmp_path / "main_result_audit.md"

    audit = audit_main_frame(
        frame,
        expected_algorithms=(*PRIMARY_ALGORITHMS, "Greedy-ED"),
        expected_pairs=2,
        weights=FitnessWeights(),
        output_path=report_path,
    )

    assert audit["passed"] is True
    assert audit["row_count"] == 18
    assert audit["outcomes"]["RIME"] == {"wins": 2, "ties": 0, "losses": 0}
    assert "Primary equal-budget algorithms" in report_path.read_text(encoding="utf-8")

    duplicate = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate main-result key"):
        audit_main_frame(duplicate, expected_algorithms=(*PRIMARY_ALGORITHMS, "Greedy-ED"), expected_pairs=2)

    corrupted = frame.copy()
    corrupted.loc[0, "reported_fitness"] += 0.1
    corrupted.loc[0, "fitness"] = corrupted.loc[0, "reported_fitness"]
    with pytest.raises(ValueError, match="reported objective recomputation failed"):
        audit_main_frame(corrupted, expected_algorithms=(*PRIMARY_ALGORITHMS, "Greedy-ED"), expected_pairs=2)


def test_artifact_validator_keeps_primary_and_greedy_inference_separate(tmp_path):
    primary = pairwise_tests(
        _paired_frame(),
        reference_algorithm="RDHO",
        comparison_algorithms=PRIMARY_ALGORITHMS[1:],
        bootstrap_samples=100,
    )
    supplementary_frame = _paired_frame((*PRIMARY_ALGORITHMS, "Greedy-ED"))
    supplementary = pairwise_tests(
        supplementary_frame,
        reference_algorithm="RDHO",
        comparison_algorithms=["Greedy-ED"],
        inference_tier="supplementary_effectiveness_vs_cost",
        equal_budget=False,
        bootstrap_samples=100,
    )

    validate_statistical_separation(primary, supplementary)
    mixed = pd.concat([primary, supplementary], ignore_index=True)
    with pytest.raises(ValueError, match="Greedy-ED is present in primary"):
        validate_statistical_separation(mixed, supplementary)

    artifact = tmp_path / "artifact.csv"
    artifact.write_text("value\n1\n", encoding="utf-8")
    from experiments.experiment_core import file_sha256

    manifest = {
        "outputs": [
            {
                "path": "artifact.csv",
                "sha256": file_sha256(artifact),
            }
        ]
    }
    assert verify_manifest_records(manifest, tmp_path, sections=("outputs",)) == 1
    artifact.write_text("value\n2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="manifest hash mismatch"):
        verify_manifest_records(manifest, tmp_path, sections=("outputs",))
