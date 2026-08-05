from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from scripts.reproaudit_case.constants import MEC_COMMIT, SOURCE_PATHS, SOURCE_SHA256
from scripts.reproaudit_case.source_inventory import (
    build_manifest_payload,
    build_source_inventory,
    serialize_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
RAW_COLUMNS = (
    "run_id", "seed", "algorithm", "fitness", "base_objective", "penalty",
    "search_fitness", "energy", "delay", "aoi", "qoe", "fairness", "csr",
    "hard_feasible", "capacity_utilisation_mean", "capacity_utilisation_max",
    "assignment_unique", "runtime", "nfe", "pre_refinement_fitness",
    "local_refinement_gain",
)
SUMMARY_COLUMNS = (
    "algorithm", "fitness_mean", "fitness_std", "fitness", "base_objective_mean",
    "base_objective_std", "base_objective", "penalty_mean", "penalty_std", "penalty",
    "search_fitness_mean", "search_fitness_std", "search_fitness", "energy_mean",
    "energy_std", "energy", "delay_mean", "delay_std", "delay", "aoi_mean", "aoi_std",
    "aoi", "qoe_mean", "qoe_std", "qoe", "fairness_mean", "fairness_std", "fairness",
    "csr_mean", "csr_std", "csr", "hard_feasible_mean", "hard_feasible_std",
    "hard_feasible", "capacity_utilisation_mean_mean", "capacity_utilisation_mean_std",
    "capacity_utilisation_mean", "capacity_utilisation_max_mean", "capacity_utilisation_max_std",
    "capacity_utilisation_max", "assignment_unique_mean", "assignment_unique_std",
    "assignment_unique", "runtime_mean", "runtime_std", "runtime", "nfe_mean", "nfe_std",
    "nfe", "pre_refinement_fitness_mean", "pre_refinement_fitness_std",
    "pre_refinement_fitness", "local_refinement_gain_mean", "local_refinement_gain_std",
    "local_refinement_gain",
)


def test_inventory_records_exact_hashes_sizes_shapes_and_headers():
    inventory = build_source_inventory(ROOT)
    assert inventory.mec_commit == MEC_COMMIT
    assert tuple(record.path for record in inventory.files) == SOURCE_PATHS
    assert tuple(record.sha256 for record in inventory.files) == SOURCE_SHA256
    assert inventory.algorithms == ("RDHO", "RIME", "DBO", "TLBO-HHO", "CWTSSA", "Greedy-ED")
    assert inventory.metrics == ("fitness", "csr")

    by_path = {record.path: record for record in inventory.files}
    assert {path: by_path[path].size_bytes for path in SOURCE_PATHS} == {
        "configs/main_40tasks.yaml": 351,
        "results/v2/raw/main_30_raw_results.csv": 51525,
        "results/v2/summary/main_30_summary_mean_std.csv": 6734,
        "README.md": 9027,
        "docs/experiment_protocol_v2.md": 2432,
    }
    assert by_path["results/v2/raw/main_30_raw_results.csv"].shape == (180, 21)
    assert by_path["results/v2/raw/main_30_raw_results.csv"].columns == RAW_COLUMNS
    assert by_path["results/v2/summary/main_30_summary_mean_std.csv"].shape == (6, 55)
    assert by_path["results/v2/summary/main_30_summary_mean_std.csv"].columns == SUMMARY_COLUMNS
    assert all(record.size_bytes > 0 for record in inventory.files)


def test_pinned_commit_is_verified_but_current_head_need_not_equal():
    current_head = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
    ).strip()
    assert current_head != MEC_COMMIT
    inventory = build_source_inventory(ROOT)
    assert inventory.mec_commit == MEC_COMMIT


def test_manifest_payload_and_bytes_are_timestamp_free_and_deterministic():
    inventory = build_source_inventory(ROOT)
    first = serialize_manifest(inventory)
    second = serialize_manifest(build_source_inventory(ROOT))
    assert first == second
    assert first.endswith(b"\n")
    payload = build_manifest_payload(inventory)
    assert payload["mec_commit"] == MEC_COMMIT
    assert payload["files"][0]["path"] == SOURCE_PATHS[0]
    assert "generated_at" not in payload
    assert str(ROOT) not in first.decode("utf-8")
    assert hashlib.sha256(first).hexdigest()


def test_one_byte_temporary_source_mutation_is_rejected(tmp_path):
    clone = tmp_path / "repo"
    subprocess.run(
        ["git", "clone", "--local", "--no-hardlinks", str(ROOT), str(clone)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    build_source_inventory(clone)
    source = clone / "README.md"
    original = source.read_bytes()
    source.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    with pytest.raises(Exception, match="hash|drift|source"):
        build_source_inventory(clone)
