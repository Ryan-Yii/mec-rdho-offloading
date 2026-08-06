from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

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


def test_run_reproaudit_requires_installed_console_entry_point(tmp_path: Path) -> None:
    from scripts.reproaudit_case.release_runtime import run_reproaudit

    runtime_python = tmp_path / "bin/python"
    runtime_python.parent.mkdir()
    runtime_python.write_text("", encoding="utf-8")
    with pytest.raises(CaseContractError, match="console entry point"):
        run_reproaudit(runtime_python, tmp_path / "case", tmp_path / "reports")


def test_run_reproaudit_keeps_console_entry_point_beside_symlinked_venv_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.reproaudit_case.release_runtime as module

    base_python = tmp_path / "base" / "python3.11"
    base_python.parent.mkdir()
    base_python.write_text("", encoding="utf-8")
    runtime_python = tmp_path / "runtime" / "bin" / "python"
    runtime_python.parent.mkdir(parents=True)
    runtime_python.symlink_to(base_python)
    cli = runtime_python.parent / "reproaudit"
    cli.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "_run",
        lambda command, *, cwd: type(
            "Result", (), {"returncode": 0, "stdout": "", "args": command}
        )(),
    )
    reports = tmp_path / "reports"
    monkeypatch.setattr(
        module.Path,
        "glob",
        lambda self, pattern: [],
    )
    with pytest.raises(CaseContractError, match="produced no JSON report"):
        module.run_reproaudit(runtime_python, tmp_path / "case", reports)


def test_dependency_wheelhouse_rejects_unpinned_hash_mismatch_and_sdist(tmp_path: Path) -> None:
    from scripts.reproaudit_case.release_runtime import (
        validate_dependency_wheelhouse,
        verify_dependency_wheelhouse_manifest,
    )

    requirements = tmp_path / "requirements.txt"
    requirements.write_text("typer>=0.12\n", encoding="utf-8")
    with pytest.raises(CaseContractError, match="unpinned"):
        validate_dependency_wheelhouse(requirements, tmp_path / "wheelhouse")

    requirements.write_text("typer==0.12.0\n", encoding="utf-8")
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    (wheelhouse / "typer-0.12.0.tar.gz").write_bytes(b"sdist")
    with pytest.raises(CaseContractError, match="sdist"):
        validate_dependency_wheelhouse(requirements, wheelhouse)

    (wheelhouse / "typer-0.12.0.tar.gz").unlink()
    with pytest.raises(CaseContractError, match="missing"):
        validate_dependency_wheelhouse(requirements, wheelhouse)


def test_dependency_wheelhouse_rejects_manifest_hash_mismatch(tmp_path: Path) -> None:
    from scripts.reproaudit_case.release_runtime import (
        validate_dependency_wheelhouse,
        verify_dependency_wheelhouse_manifest,
    )

    requirements = tmp_path / "requirements.txt"
    requirements.write_text("demo-package==1.0\n", encoding="utf-8")
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = wheelhouse / "demo_package-1.0-py3-none-any.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr("demo_package-1.0.dist-info/METADATA", "Name: demo-package\nVersion: 1.0\n")
    payload = validate_dependency_wheelhouse(requirements, wheelhouse)
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"dependencies": []}\n', encoding="utf-8")
    with pytest.raises(CaseContractError, match="hash manifest mismatch"):
        verify_dependency_wheelhouse_manifest(requirements, wheelhouse, manifest)
    assert payload["dependencies"][0]["package"] == "demo-package"
