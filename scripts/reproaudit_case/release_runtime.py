"""Isolated execution of the pinned ReproAudit release wheel."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from .constants import REPROAUDIT_WHEEL_NAME, REPROAUDIT_WHEEL_SHA256
from .source_inventory import CaseContractError


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    return subprocess.run(command, cwd=cwd, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def prepare_reproaudit_runtime(wheel: Path, temp_dir: Path) -> Path:
    wheel = Path(wheel).resolve()
    runtime = Path(temp_dir).resolve()
    if not wheel.is_file():
        raise CaseContractError("official release wheel is missing")
    if wheel.name != REPROAUDIT_WHEEL_NAME:
        raise CaseContractError(f"official release wheel filename mismatch: {wheel.name}")
    digest = _sha256(wheel)
    if digest != REPROAUDIT_WHEEL_SHA256:
        raise CaseContractError(f"official release wheel hash mismatch: {digest}")
    if sys.version_info[:2] != (3, 11):
        raise CaseContractError("Python 3.11 is required for the release runtime")
    if runtime.exists() and any(runtime.iterdir()):
        raise CaseContractError("runtime directory must be absent or empty")
    runtime.parent.mkdir(parents=True, exist_ok=True)
    create = _run([sys.executable, "-m", "venv", str(runtime)], cwd=runtime.parent)
    if create.returncode:
        raise CaseContractError(f"cannot create release runtime: {create.stdout}")
    runtime_python = runtime / "bin/python"
    install = _run([str(runtime_python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)], cwd=runtime)
    if install.returncode:
        raise CaseContractError(f"cannot install official release wheel: {install.stdout}")
    probe = _run([str(runtime_python), "-c", "import json,reproaudit; print(json.dumps({'version':reproaudit.__version__,'file':reproaudit.__file__}))"], cwd=runtime)
    if probe.returncode:
        raise CaseContractError(f"cannot import installed release: {probe.stdout}")
    try:
        details = json.loads(probe.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise CaseContractError("invalid installed release probe") from exc
    if details.get("version") != "0.1.0" or "site-packages" not in details.get("file", ""):
        raise CaseContractError("installed release provenance mismatch")
    help_result = _run([str(runtime_python), "-m", "reproaudit.cli", "--help"], cwd=runtime)
    if help_result.returncode:
        raise CaseContractError(f"release CLI help failed: {help_result.stdout}")
    return runtime_python


def run_reproaudit(runtime_python: Path, case_dir: Path, report_dir: Path) -> dict[str, Any]:
    runtime_python = Path(runtime_python).resolve()
    if not runtime_python.is_file():
        raise CaseContractError("runtime Python is missing")
    case = Path(case_dir).resolve()
    reports = Path(report_dir).resolve()
    reports.mkdir(parents=True, exist_ok=True)
    result = _run([str(runtime_python), "-m", "reproaudit.cli", "audit", str(case), "--format", "all", "--output-dir", str(reports)], cwd=reports.parent)
    candidates = sorted(reports.glob("*.json"))
    if not candidates:
        if result.returncode:
            raise CaseContractError(f"release CLI failed without JSON report (exit {result.returncode}): {result.stdout}")
        raise CaseContractError("release CLI produced no JSON report")
    try:
        payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CaseContractError("release CLI produced invalid JSON report") from exc
    if not isinstance(payload, dict):
        raise CaseContractError("release CLI JSON report must be an object")
    payload["exit_code"] = result.returncode
    return payload


__all__ = ["prepare_reproaudit_runtime", "run_reproaudit"]
