"""Isolated execution of the pinned ReproAudit release wheel."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from zipfile import ZipFile

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


def _locked_requirements(requirements: Path) -> dict[str, str]:
    if not requirements.is_file():
        raise CaseContractError("resolved dependency requirements are missing")
    locked: dict[str, str] = {}
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.count("==") != 1 or any(token in line for token in (">", "<", "~", "*", "@", "/", "\\")):
            raise CaseContractError(f"unpinned dependency requirement: {line}")
        name, version = line.split("==")
        normalized = name.lower().replace("_", "-")
        if not name or not version or normalized == "reproaudit":
            raise CaseContractError(f"invalid dependency requirement: {line}")
        if normalized in locked:
            raise CaseContractError(f"duplicate dependency requirement: {name}")
        locked[normalized] = version
    if not locked:
        raise CaseContractError("resolved dependency requirements are empty")
    return locked


def _wheel_identity(path: Path) -> tuple[str, str, tuple[str, ...]]:
    if path.suffix != ".whl":
        raise CaseContractError(f"dependency wheelhouse contains sdist or non-wheel: {path.name}")
    try:
        with ZipFile(path) as archive:
            metadata = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            if len(metadata) != 1:
                raise CaseContractError(f"wheel metadata ambiguity: {path.name}")
            lines = archive.read(metadata[0]).decode("utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise CaseContractError(f"cannot inspect dependency wheel: {path.name}") from exc
    values = {line.split(": ", 1)[0]: line.split(": ", 1)[1] for line in lines if line.startswith(("Name: ", "Version: "))}
    if "Name" not in values or "Version" not in values:
        raise CaseContractError(f"wheel metadata missing identity: {path.name}")
    parts = path.name[:-4].split("-")
    if len(parts) < 5:
        raise CaseContractError(f"invalid wheel filename: {path.name}")
    return values["Name"].lower().replace("_", "-"), values["Version"], tuple(parts[-3:])


def validate_dependency_wheelhouse(requirements: Path, wheelhouse: Path) -> dict[str, Any]:
    """Fail closed unless an exact locked third-party wheel set is present."""

    locked = _locked_requirements(Path(requirements))
    directory = Path(wheelhouse)
    if not directory.is_dir():
        raise CaseContractError("dependency wheelhouse is missing")
    files = sorted(path for path in directory.iterdir() if path.is_file())
    if not files:
        raise CaseContractError("dependency wheelhouse is missing")
    records: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for path in files:
        name, version, tags = _wheel_identity(path)
        if name == "reproaudit":
            raise CaseContractError("dependency wheelhouse must not contain ReproAudit")
        if name in seen:
            raise CaseContractError(f"ambiguous dependency wheel candidate: {name}")
        seen[name] = version
        records.append({"filename": path.name, "package": name, "sha256": _sha256(path), "size_bytes": path.stat().st_size, "version": version, "wheel_tags": list(tags)})
    if seen != locked:
        missing = sorted(set(locked) - set(seen))
        unexpected = sorted(set(seen) - set(locked))
        if missing:
            raise CaseContractError(f"dependency wheelhouse missing locked wheel: {missing[0]}")
        raise CaseContractError(f"dependency wheelhouse contains unexpected wheel: {unexpected[0]}")
    for name, version in locked.items():
        if seen[name] != version:
            raise CaseContractError(f"dependency wheel version mismatch for {name}: {seen[name]}")
    return {"dependencies": records, "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", "platform": sys.platform}


def verify_dependency_wheelhouse_manifest(requirements: Path, wheelhouse: Path, manifest: Path) -> dict[str, Any]:
    actual = validate_dependency_wheelhouse(requirements, wheelhouse)
    try:
        expected = json.loads(Path(manifest).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CaseContractError("dependency wheelhouse manifest is missing or invalid") from exc
    if actual != expected:
        raise CaseContractError("dependency wheelhouse hash manifest mismatch")
    return actual


def write_dependency_wheelhouse_manifest(requirements: Path, wheelhouse: Path, destination: Path) -> Path:
    """Write the deterministic, platform-specific wheelhouse evidence manifest."""

    payload = validate_dependency_wheelhouse(requirements, wheelhouse)
    target = Path(destination)
    if target.exists():
        raise FileExistsError(f"destination already exists: {target}")
    target.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return target


def install_offline_dependencies(runtime_python: Path, requirements: Path, wheelhouse: Path, manifest: Path) -> None:
    verify_dependency_wheelhouse_manifest(requirements, wheelhouse, manifest)
    result = _run([str(runtime_python), "-m", "pip", "install", "--no-index", "--find-links", str(wheelhouse), "-r", str(requirements)], cwd=Path(wheelhouse))
    if result.returncode:
        raise CaseContractError(f"offline dependency install failed: {result.stdout}")
    check = _run([str(runtime_python), "-m", "pip", "check"], cwd=Path(wheelhouse))
    if check.returncode:
        raise CaseContractError(f"offline dependency consistency failed: {check.stdout}")


def prepare_reproaudit_runtime(
    wheel: Path,
    temp_dir: Path,
    requirements: Path | None = None,
    wheelhouse: Path | None = None,
    wheelhouse_manifest: Path | None = None,
) -> Path:
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
    if requirements is None or wheelhouse is None or wheelhouse_manifest is None:
        raise CaseContractError("locked dependency wheelhouse is required for the release runtime")
    install_offline_dependencies(runtime_python, requirements, wheelhouse, wheelhouse_manifest)
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
    cli = runtime / "bin" / "reproaudit"
    if not cli.is_file():
        raise CaseContractError("installed release console entry point is missing")
    help_result = _run([str(cli), "--help"], cwd=runtime)
    if help_result.returncode:
        raise CaseContractError(f"release CLI help failed: {help_result.stdout}")
    return runtime_python


def run_reproaudit(runtime_python: Path, case_dir: Path, report_dir: Path) -> dict[str, Any]:
    runtime_python = Path(runtime_python).absolute()
    if not runtime_python.is_file():
        raise CaseContractError("runtime Python is missing")
    case = Path(case_dir).resolve()
    reports = Path(report_dir).resolve()
    reports.mkdir(parents=True, exist_ok=True)
    cli = runtime_python.parent / "reproaudit"
    if not cli.is_file():
        raise CaseContractError("installed release console entry point is missing")
    result = _run([str(cli), "audit", str(case), "--format", "all", "--output-dir", str(reports)], cwd=reports.parent)
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


__all__ = [
    "install_offline_dependencies",
    "prepare_reproaudit_runtime",
    "run_reproaudit",
    "validate_dependency_wheelhouse",
    "verify_dependency_wheelhouse_manifest",
    "write_dependency_wheelhouse_manifest",
]
