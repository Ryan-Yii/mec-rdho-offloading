from pathlib import Path

import pytest

from scripts.reproaudit_case import constants


def test_source_paths_and_hashes_are_pinned():
    assert constants.SOURCE_PATHS == (
        "configs/main_40tasks.yaml",
        "results/v2/raw/main_30_raw_results.csv",
        "results/v2/summary/main_30_summary_mean_std.csv",
        "README.md",
        "docs/experiment_protocol_v2.md",
    )
    assert constants.SOURCE_SHA256 == (
        "d99ba17554e67f6d1ad9aef9bbec9a4470b5b6bde8c77309ed82951e159fe8c4",
        "f885d8dd171e277d351ef268449f0aa5179a26f6e9c66256d4596d37a360c639",
        "751a936d794c642f640d6d9ae0309b153d728932c27e077c5188861feafa28d6",
        "519b055257d1525806d0fbb3edf72f58848ee6ecc96112544158e93eb8f01cb6",
        "c1db229a76a50c6269e1417a521135056cfbdfb29556d1c368d3e96a60a1fa42",
    )


def test_order_directions_tolerances_and_schemas_are_frozen():
    assert constants.ALGORITHMS == (
        "RDHO", "RIME", "DBO", "TLBO-HHO", "CWTSSA", "Greedy-ED"
    )
    assert constants.METRICS == ("fitness", "csr")
    assert constants.METRIC_DIRECTIONS == {"fitness": "minimize", "csr": "maximize"}
    assert constants.PRIMARY_METRIC == "fitness"
    assert constants.ABS_TOLERANCE == 0.00005
    assert constants.REL_TOLERANCE == 0.0
    assert constants.RAW_COLUMNS == ("seed", "algorithm", "status", "fitness", "csr")
    assert constants.SUMMARY_COLUMNS == ("algorithm", "metric", "mean", "std", "median", "n")


def test_resolve_source_path_requires_relative_path_inside_root(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    assert constants.resolve_source_path(repo_root, "README.md") == (repo_root / "README.md").resolve()

    with pytest.raises(ValueError):
        constants.resolve_source_path(repo_root, "/etc/passwd")
    with pytest.raises(ValueError):
        constants.resolve_source_path(repo_root, "../outside.txt")
    with pytest.raises(ValueError):
        constants.resolve_source_path(repo_root, Path(repo_root / "README.md"))


def test_import_does_not_read_source_files(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("constants must not read repository data at import time")

    monkeypatch.setattr(Path, "read_bytes", fail)
    monkeypatch.setattr(Path, "read_text", fail)
    assert constants.ALGORITHMS
