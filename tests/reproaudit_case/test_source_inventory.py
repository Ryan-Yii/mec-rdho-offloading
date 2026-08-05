from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from scripts.reproaudit_case.constants import (
    MEC_COMMIT,
    SOURCE_PATHS,
    SOURCE_SHA256,
    SOURCE_SIZES,
)
from scripts.reproaudit_case import source_inventory
from scripts.reproaudit_case.source_inventory import (
    CaseContractError,
    SourceFileRecord,
    SourceInventory,
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


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        stderr=subprocess.STDOUT,
        text=True,
    ).strip()


def _init_git_repo(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    _git(path, "config", "user.name", "Task 2 Test")
    _git(path, "config", "user.email", "task2@example.invalid")
    return path


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _use_single_canonical_source(
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
    pinned_commit: str,
) -> None:
    relative_path = "README.md"
    content = (repo / relative_path).read_bytes()
    monkeypatch.setattr(source_inventory, "MEC_COMMIT", pinned_commit)
    monkeypatch.setattr(source_inventory, "SOURCE_PATHS", (relative_path,))
    monkeypatch.setattr(
        source_inventory,
        "SOURCE_HASHES",
        {relative_path: hashlib.sha256(content).hexdigest()},
    )
    monkeypatch.setattr(source_inventory, "SOURCE_SIZES", {relative_path: len(content)})


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


def test_source_sizes_are_immutable():
    assert dict(SOURCE_SIZES) == {
        "configs/main_40tasks.yaml": 351,
        "results/v2/raw/main_30_raw_results.csv": 51525,
        "results/v2/summary/main_30_summary_mean_std.csv": 6734,
        "README.md": 9027,
        "docs/experiment_protocol_v2.md": 2432,
    }
    with pytest.raises(TypeError):
        SOURCE_SIZES["README.md"] = 0


def test_size_mismatch_is_rejected_with_precise_contract_error(monkeypatch):
    expected = dict(SOURCE_SIZES)
    expected["README.md"] += 1
    monkeypatch.setattr(source_inventory, "SOURCE_SIZES", expected)
    with pytest.raises(CaseContractError, match=r"canonical source size mismatch for README\.md"):
        build_source_inventory(ROOT)


def test_missing_pinned_commit_is_translated_to_contract_error(monkeypatch):
    original = source_inventory.subprocess.check_output

    def fail_cat_file(command, **kwargs):
        if "cat-file" in command:
            raise subprocess.CalledProcessError(1, command, output="missing commit")
        return original(command, **kwargs)

    monkeypatch.setattr(source_inventory.subprocess, "check_output", fail_cat_file)
    with pytest.raises(CaseContractError, match="unable to verify Git source provenance"):
        build_source_inventory(ROOT)


def test_non_ancestor_pinned_commit_is_rejected(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path / "repo")
    (repo / "README.md").write_text("canonical\n", encoding="utf-8")
    base_commit = _commit_all(repo, "base")

    _git(repo, "checkout", "-q", "-b", "branch-a")
    (repo / "branch-a.txt").write_text("a\n", encoding="utf-8")
    _commit_all(repo, "branch a")

    _git(repo, "checkout", "-q", "-b", "branch-b", base_commit)
    (repo / "branch-b.txt").write_text("b\n", encoding="utf-8")
    pinned_commit = _commit_all(repo, "branch b")
    _git(repo, "checkout", "-q", "branch-a")
    _use_single_canonical_source(monkeypatch, repo, pinned_commit)

    with pytest.raises(CaseContractError, match="pinned commit.*ancestor.*HEAD"):
        build_source_inventory(repo)


def test_ancestor_pinned_commit_with_unchanged_source_is_accepted(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path / "repo")
    (repo / "README.md").write_text("canonical\n", encoding="utf-8")
    pinned_commit = _commit_all(repo, "pinned source")
    (repo / "implementation.txt").write_text("later code\n", encoding="utf-8")
    _commit_all(repo, "later implementation")
    _use_single_canonical_source(monkeypatch, repo, pinned_commit)

    inventory = build_source_inventory(repo)

    assert inventory.mec_commit == pinned_commit
    assert _git(repo, "rev-parse", "HEAD") != pinned_commit


def test_committed_canonical_mutation_after_pinned_commit_is_rejected(
    tmp_path,
    monkeypatch,
):
    repo = _init_git_repo(tmp_path / "repo")
    (repo / "README.md").write_text("canonical\n", encoding="utf-8")
    pinned_commit = _commit_all(repo, "pinned source")
    (repo / "README.md").write_text("changed later\n", encoding="utf-8")
    _commit_all(repo, "mutate canonical source")
    _use_single_canonical_source(monkeypatch, repo, pinned_commit)

    with pytest.raises(CaseContractError, match="canonical source.*pinned commit.*README.md"):
        build_source_inventory(repo)


def test_working_tree_canonical_mutation_after_pinned_commit_is_rejected(
    tmp_path,
    monkeypatch,
):
    repo = _init_git_repo(tmp_path / "repo")
    (repo / "README.md").write_text("canonical\n", encoding="utf-8")
    pinned_commit = _commit_all(repo, "pinned source")
    (repo / "implementation.txt").write_text("later code\n", encoding="utf-8")
    _commit_all(repo, "later implementation")
    (repo / "README.md").write_text("working tree change\n", encoding="utf-8")
    _use_single_canonical_source(monkeypatch, repo, pinned_commit)

    with pytest.raises(CaseContractError, match="canonical source.*pinned commit.*README.md"):
        build_source_inventory(repo)


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


def test_manifest_serialization_matches_exact_json_contract():
    inventory = SourceInventory(
        mec_commit="commit-é",
        files=(
            SourceFileRecord(
                path="résultats/数据.csv",
                sha256="abc123",
                size_bytes=7,
                shape=(1, 2),
                columns=("seed", "指标"),
            ),
        ),
        algorithms=("RDHO",),
        metrics=("fitness",),
    )
    expected = (
        "{\n"
        '  "algorithms": [\n'
        '    "RDHO"\n'
        "  ],\n"
        '  "files": [\n'
        "    {\n"
        '      "columns": [\n'
        '        "seed",\n'
        '        "指标"\n'
        "      ],\n"
        '      "path": "résultats/数据.csv",\n'
        '      "sha256": "abc123",\n'
        '      "shape": [\n'
        "        1,\n"
        "        2\n"
        "      ],\n"
        '      "size_bytes": 7\n'
        "    }\n"
        "  ],\n"
        '  "mec_commit": "commit-é",\n'
        '  "metrics": [\n'
        '    "fitness"\n'
        "  ]\n"
        "}\n"
    ).encode("utf-8")

    first = serialize_manifest(inventory)
    second = serialize_manifest(inventory)

    assert first == expected
    assert second == expected
    assert first.count(b"\n") > 1
    assert not first.endswith(b"\n\n")
    assert b"\\u" not in first


def test_manifest_serialization_rejects_nonfinite_numbers():
    inventory = SourceInventory(
        mec_commit="commit",
        files=(
            SourceFileRecord(
                path="README.md",
                sha256="abc123",
                size_bytes=float("nan"),
            ),
        ),
        algorithms=("RDHO",),
        metrics=("fitness",),
    )

    with pytest.raises(ValueError, match="Out of range float values"):
        serialize_manifest(inventory)


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
    with pytest.raises(CaseContractError, match="hash|drift|source"):
        build_source_inventory(clone)
