from __future__ import annotations

from pathlib import Path

import pytest

from scripts.reproaudit_case.source_inventory import CaseContractError


def test_runtime_rejects_missing_wrong_name_and_hash(tmp_path: Path) -> None:
    from scripts.reproaudit_case.release_runtime import prepare_reproaudit_runtime

    with pytest.raises(CaseContractError, match="missing"):
        prepare_reproaudit_runtime(tmp_path / "reproaudit-0.1.0-py3-none-any.whl", tmp_path / "runtime")
    wrong = tmp_path / "wrong.whl"
    wrong.write_bytes(b"wheel")
    with pytest.raises(CaseContractError, match="filename"):
        prepare_reproaudit_runtime(wrong, tmp_path / "runtime")
    named = tmp_path / "reproaudit-0.1.0-py3-none-any.whl"
    named.write_bytes(b"wheel")
    with pytest.raises(CaseContractError, match="hash"):
        prepare_reproaudit_runtime(named, tmp_path / "runtime")


def test_run_reproaudit_rejects_missing_runtime(tmp_path: Path) -> None:
    from scripts.reproaudit_case.release_runtime import run_reproaudit

    with pytest.raises(CaseContractError, match="runtime Python"):
        run_reproaudit(tmp_path / "python", tmp_path / "case", tmp_path / "reports")
