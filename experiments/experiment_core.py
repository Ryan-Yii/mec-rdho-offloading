from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import rankdata, wilcoxon

from src.algorithms import (
    CWTSSA,
    DBO,
    RDHO,
    RIME,
    TLBOHHO,
    DifferentialEvolution,
    GeneticAlgorithm,
    GreedyEnergyDelay,
    ParticleSwarmOptimizer,
)
from src.metrics import FitnessWeights
from src.system_model import SystemModel
from src.task_generator import generate_system, task_parameter_rows
from src.utils.io import ensure_parent, load_yaml, write_rows
from src.utils.seed import derive_algorithm_seed, derive_scenario_seed


RAW_COLUMNS = [
    "run_id",
    "seed",
    "scenario_id",
    "replicate_id",
    "scenario_seed",
    "algorithm_seed",
    "algorithm",
    "fitness",
    "reported_fitness",
    "base_fitness",
    "search_fitness",
    "penalty_scale",
    "report_penalty_scale",
    "search_penalty",
    "report_penalty",
    "energy_norm",
    "delay_norm",
    "aoi_norm",
    "energy",
    "delay",
    "aoi",
    "qoe",
    "fairness",
    "csr",
    "nfe_used",
    "max_evaluations",
    "runtime",
]

ALGORITHM_CLASSES = {
    "RDHO": RDHO,
    "RIME": RIME,
    "DBO": DBO,
    "TLBO-HHO": TLBOHHO,
    "CWTSSA": CWTSSA,
    "Greedy-ED": GreedyEnergyDelay,
    "GA": GeneticAlgorithm,
    "PSO": ParticleSwarmOptimizer,
    "DE": DifferentialEvolution,
}

RDHO_VARIANTS = {
    "RDHO-core": {"local_refinement": False},
    "RDHO-full": {"local_refinement": True},
    "RDHO-w/o dual-source initialization": {"dual_source_initialization": False, "local_refinement": False},
    "RDHO-w/o adaptive role allocation": {"adaptive_roles": False, "local_refinement": False},
    "RDHO-w/o elite preservation": {"elite_preservation": False, "local_refinement": False},
    "RDHO-w/o dynamic penalty": {"dynamic_penalty": False, "local_refinement": False},
}


def weights_from_config(config: dict | None) -> FitnessWeights:
    config = config or {}
    return FitnessWeights(
        energy=float(config.get("energy", 0.15)),
        delay=float(config.get("delay", 0.15)),
        aoi=float(config.get("aoi", 0.20)),
        qoe=float(config.get("qoe", 0.25)),
        fairness=float(config.get("fairness", 0.25)),
    )


def build_system_from_config(config: dict, seed: int, task_number: int | None = None) -> SystemModel:
    system = config["system"]
    return generate_system(
        seed=seed,
        num_devices=int(system["mobile_devices"]),
        num_edge_servers=int(system["edge_servers"]),
        num_cloud_servers=int(system["cloud_servers"]),
        num_tasks=int(task_number or system["tasks"]),
    )


def make_optimizer(
    algorithm_name: str,
    system: SystemModel,
    seed: int,
    max_iter: int,
    population_size: int,
    weights: FitnessWeights | None = None,
    penalty_base: float = 1.0,
    dynamic_penalty_alpha: float = 2.0,
    max_evaluations: int | None = None,
    local_refinement: bool | None = None,
):
    label = algorithm_name
    kwargs = {}
    if algorithm_name in RDHO_VARIANTS:
        label = "RDHO"
        kwargs.update(RDHO_VARIANTS[algorithm_name])
    if label == "RDHO":
        kwargs["dynamic_penalty_alpha"] = dynamic_penalty_alpha
    if local_refinement is not None and label == "RDHO":
        kwargs["local_refinement"] = local_refinement

    cls = ALGORITHM_CLASSES[label]
    return cls(
        system=system,
        max_iter=max_iter,
        population_size=population_size,
        seed=seed,
        weights=weights,
        penalty_base=penalty_base,
        max_evaluations=max_evaluations,
        **kwargs,
    )


def run_optimizer(
    system: SystemModel,
    algorithm_name: str,
    run_id: int,
    seed: int,
    max_iter: int,
    population_size: int,
    weights: FitnessWeights | None = None,
    penalty_base: float = 1.0,
    dynamic_penalty_alpha: float = 2.0,
    max_evaluations: int | None = None,
    local_refinement: bool | None = None,
    scenario_id: int | str | None = None,
    replicate_id: int = 1,
    scenario_seed: int | None = None,
    algorithm_seed: int | None = None,
) -> Tuple[Dict[str, float | int | str], List[float]]:
    scenario_id = run_id if scenario_id is None else scenario_id
    scenario_seed = seed if scenario_seed is None else scenario_seed
    algorithm_seed = (
        derive_algorithm_seed(seed, algorithm_name, scenario_id, replicate_id)
        if algorithm_seed is None
        else algorithm_seed
    )
    optimizer = make_optimizer(
        algorithm_name=algorithm_name,
        system=system,
        seed=algorithm_seed,
        max_iter=max_iter,
        population_size=population_size,
        weights=weights,
        penalty_base=penalty_base,
        dynamic_penalty_alpha=dynamic_penalty_alpha,
        max_evaluations=max_evaluations,
        local_refinement=local_refinement,
    )
    start = time.perf_counter()
    result = optimizer.optimize()
    runtime = time.perf_counter() - start
    metrics = result.metrics
    if metrics is None:
        raise RuntimeError(f"{algorithm_name} returned no auditable metrics")
    row = {
        "run_id": run_id,
        "seed": scenario_seed,
        "scenario_id": scenario_id,
        "replicate_id": replicate_id,
        "scenario_seed": scenario_seed,
        "algorithm_seed": algorithm_seed,
        "algorithm": algorithm_name,
        "fitness": metrics.reported_fitness,
        "reported_fitness": metrics.reported_fitness,
        "base_fitness": metrics.base_fitness,
        "search_fitness": metrics.search_fitness,
        "penalty_scale": metrics.penalty_scale,
        "report_penalty_scale": metrics.report_penalty_scale,
        "search_penalty": metrics.search_penalty,
        "report_penalty": metrics.report_penalty,
        "energy_norm": metrics.energy_norm,
        "delay_norm": metrics.delay_norm,
        "aoi_norm": metrics.aoi_norm,
        "energy": metrics.energy,
        "delay": metrics.delay,
        "aoi": metrics.aoi,
        "qoe": metrics.qoe,
        "fairness": metrics.fairness,
        "csr": metrics.csr,
        "nfe_used": result.nfe_used,
        "max_evaluations": result.max_evaluations,
        "runtime": runtime,
    }
    return row, result.history


def run_single_algorithm(
    system: SystemModel,
    algorithm_name: str,
    run_id: int,
    seed: int,
    max_iter: int,
    population_size: int,
    max_evaluations: int | None = None,
) -> Dict[str, float | int | str]:
    row, _ = run_optimizer(
        system,
        algorithm_name,
        run_id,
        seed,
        max_iter,
        population_size,
        max_evaluations=max_evaluations,
    )
    return row


def run_algorithm_suite(
    config: dict,
    algorithms: Iterable[str],
    n_runs: int,
    seeds: Iterable[int] | None = None,
    task_number: int | None = None,
) -> Tuple[List[Dict], List[Dict]]:
    experiment = config["experiment"]
    weights = weights_from_config(config.get("weights"))
    penalty = config.get("penalty", {})
    penalty_base = float(penalty.get("lambda0", penalty.get("base", 1.0)))
    dynamic_penalty_alpha = float(penalty.get("alpha", 2.0))
    max_iter = int(experiment["max_iterations"])
    population_size = int(experiment["population_size"])
    max_evaluations = experiment.get("max_evaluations")
    max_evaluations = int(max_evaluations) if max_evaluations is not None else None
    default_local_refinement = experiment.get("local_refinement")
    if default_local_refinement is not None:
        default_local_refinement = bool(default_local_refinement)
    master_seed = int(experiment.get("master_seed", experiment["seed_start"]))
    provided_seeds = list(seeds) if seeds is not None else None
    if provided_seeds is not None and len(provided_seeds) < n_runs:
        raise ValueError(f"expected at least {n_runs} scenario seeds, got {len(provided_seeds)}")

    rows: List[Dict] = []
    convergence_rows: List[Dict] = []

    for run_id in range(1, n_runs + 1):
        scenario_id = run_id
        replicate_id = 1
        scenario_seed = (
            int(provided_seeds[run_id - 1])
            if provided_seeds is not None
            else derive_scenario_seed(master_seed, scenario_id, replicate_id)
        )
        system = build_system_from_config(config, scenario_seed, task_number=task_number)
        for algorithm_name in algorithms:
            algorithm_seed = derive_algorithm_seed(master_seed, algorithm_name, scenario_id, replicate_id)
            row, history = run_optimizer(
                system=system,
                algorithm_name=algorithm_name,
                run_id=run_id,
                seed=master_seed,
                max_iter=max_iter,
                population_size=population_size,
                weights=weights,
                penalty_base=penalty_base,
                dynamic_penalty_alpha=dynamic_penalty_alpha,
                max_evaluations=max_evaluations,
                local_refinement=default_local_refinement if algorithm_name == "RDHO" else None,
                scenario_id=scenario_id,
                replicate_id=replicate_id,
                scenario_seed=scenario_seed,
                algorithm_seed=algorithm_seed,
            )
            if task_number is not None:
                row["task_number"] = task_number
            rows.append(row)
            for iteration, fitness in enumerate(history):
                convergence_row = {
                    "run_id": run_id,
                    "seed": scenario_seed,
                    "scenario_id": scenario_id,
                    "replicate_id": replicate_id,
                    "scenario_seed": scenario_seed,
                    "algorithm_seed": algorithm_seed,
                    "algorithm": algorithm_name,
                    "iteration": iteration,
                    "fitness": fitness,
                }
                if task_number is not None:
                    convergence_row["task_number"] = task_number
                convergence_rows.append(convergence_row)

    return rows, convergence_rows


def summarize_mean_std(raw_rows: List[Dict], group_cols: List[str] | None = None) -> pd.DataFrame:
    group_cols = group_cols or ["algorithm"]
    df = pd.DataFrame(raw_rows)
    numeric_cols = [
        col
        for col in ["fitness", "energy", "delay", "aoi", "qoe", "fairness", "csr", "runtime"]
        if col in df.columns
    ]
    records = []
    for keys, group in df.groupby(group_cols, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        record = dict(zip(group_cols, keys))
        for col in numeric_cols:
            record[f"{col}_mean"] = float(group[col].mean())
            record[f"{col}_std"] = float(group[col].std(ddof=1)) if len(group) > 1 else 0.0
            record[col] = f"{record[f'{col}_mean']:.6f} +/- {record[f'{col}_std']:.6f}"
        records.append(record)
    return pd.DataFrame(records)


def write_raw_and_summary(raw_path: str | Path, summary_path: str | Path, rows: List[Dict], group_cols: List[str] | None = None) -> pd.DataFrame:
    ordered_rows = []
    for row in rows:
        first_cols = [col for col in ["task_number", *RAW_COLUMNS] if col in row]
        remaining = [col for col in row.keys() if col not in first_cols]
        ordered_rows.append({col: row[col] for col in [*first_cols, *remaining]})
    write_rows(raw_path, ordered_rows)
    summary = summarize_mean_std(rows, group_cols=group_cols)
    ensure_parent(summary_path)
    summary.to_csv(summary_path, index=False)
    return summary


def write_wilcoxon_results(raw_rows: List[Dict], output_path: str | Path) -> pd.DataFrame:
    df = pd.DataFrame(raw_rows)
    comparisons = [("RDHO", algorithm) for algorithm in df["algorithm"].unique() if algorithm != "RDHO"]
    records = []
    pair_cols = ["scenario_id", "replicate_id"] if {"scenario_id", "replicate_id"} <= set(df.columns) else ["run_id"]
    key_cols = [*pair_cols, "algorithm"]
    duplicates = df.duplicated(key_cols, keep=False)
    if duplicates.any():
        duplicate_keys = df.loc[duplicates, key_cols].drop_duplicates().to_dict("records")
        raise ValueError(f"duplicate paired result rows: {duplicate_keys}")
    pivot = df.pivot(index=pair_cols, columns="algorithm", values="fitness")
    for left, right in comparisons:
        if left not in pivot or right not in pivot:
            continue
        paired = pivot[[left, right]].dropna()
        if paired.empty:
            continue
        differences = paired[left].to_numpy(dtype=float) - paired[right].to_numpy(dtype=float)
        nonzero = differences[~np.isclose(differences, 0.0)]
        if nonzero.size == 0:
            statistic = 0.0
            raw_p_value = 1.0
            rank_biserial = 0.0
        else:
            stat = wilcoxon(paired[left], paired[right], alternative="two-sided", zero_method="wilcox")
            statistic = float(stat.statistic)
            raw_p_value = float(stat.pvalue)
            ranks = rankdata(np.abs(nonzero))
            positive = float(ranks[nonzero > 0].sum())
            negative = float(ranks[nonzero < 0].sum())
            rank_biserial = (positive - negative) / float(ranks.sum())
        median_difference = float(np.median(differences))
        better_algorithm = left if median_difference < 0 else right if median_difference > 0 else "Tie"
        records.append(
            {
                "comparison": f"{left} vs {right}",
                "n_pairs": int(len(paired)),
                "statistic": statistic,
                "raw_p_value": raw_p_value,
                "median_difference": median_difference,
                "rank_biserial": float(rank_biserial),
                "better_algorithm": better_algorithm,
            }
        )

    if records:
        ordered = sorted(range(len(records)), key=lambda idx: records[idx]["raw_p_value"])
        running_max = 0.0
        total = len(records)
        for rank, idx in enumerate(ordered):
            adjusted = min(1.0, (total - rank) * records[idx]["raw_p_value"])
            running_max = max(running_max, adjusted)
            records[idx]["adjusted_p_value"] = running_max
        for record in records:
            record["p_value"] = record["adjusted_p_value"]
            record["significant"] = "Yes" if record["adjusted_p_value"] < 0.05 else "No"
    result = pd.DataFrame(records)
    ensure_parent(output_path)
    result.to_csv(output_path, index=False)
    return result


def export_task_parameters(config: dict, output_path: str | Path) -> None:
    experiment = config["experiment"]
    master_seed = int(experiment.get("master_seed", experiment["seed_start"]))
    seed = derive_scenario_seed(master_seed, 1, 1)
    system = build_system_from_config(config, seed)
    write_rows(output_path, task_parameter_rows(system.tasks))


def load_config(path: str | Path) -> dict:
    return load_yaml(path)


def parse_force_flag(argv: Iterable[str] | None = None) -> bool:
    arguments = list(sys.argv[1:] if argv is None else argv)
    unknown = [argument for argument in arguments if argument != "--force"]
    if unknown:
        raise ValueError(f"unsupported arguments: {unknown}")
    return "--force" in arguments


def ensure_fresh_run(output_paths: Iterable[str | Path], force: bool) -> None:
    existing = [Path(path) for path in output_paths if Path(path).exists()]
    if existing and not force:
        joined = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"formal outputs already exist ({joined}); rerun with --force")


def copy_artifact(source: str | Path, destination: str | Path) -> None:
    ensure_parent(destination)
    shutil.copy2(source, destination)


def backup_legacy_results(results_root: str | Path = "results") -> Path:
    root = Path(results_root)
    backup_root = root / "legacy_before_methodology_revision"
    backup_root.mkdir(parents=True, exist_ok=True)
    if not root.exists():
        return backup_root

    for source in root.iterdir():
        if source == backup_root:
            continue
        destination = backup_root / source.name
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
    return backup_root


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_legacy_snapshot(results_root: str | Path = "results") -> Path:
    root = Path(results_root)
    backup_root = root / "legacy_before_methodology_revision"
    manifest_path = backup_root / "legacy_snapshot_manifest.json"

    if not backup_root.exists() or not any(backup_root.iterdir()):
        backup_root = backup_legacy_results(root)

    snapshot_files = sorted(
        path for path in backup_root.rglob("*") if path.is_file() and path != manifest_path
    )
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for record in manifest.get("files", []):
            snapshot_file = backup_root / record["path"]
            if not snapshot_file.exists():
                raise RuntimeError(f"legacy snapshot file missing: {record['path']}")
            if _sha256_file(snapshot_file) != record["sha256"]:
                raise RuntimeError(f"legacy snapshot hash mismatch: {record['path']}")
        recorded = {record["path"] for record in manifest.get("files", [])}
        actual = {path.relative_to(backup_root).as_posix() for path in snapshot_files}
        if recorded != actual:
            raise RuntimeError("legacy snapshot file set does not match its manifest")
        return backup_root

    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": [
            {
                "path": path.relative_to(backup_root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
            for path in snapshot_files
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return backup_root


def _git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def capture_git_state() -> dict[str, str | bool]:
    status = _git_value("status", "--porcelain")
    return {
        "commit": _git_value("rev-parse", "HEAD"),
        "branch": _git_value("branch", "--show-current"),
        "dirty": bool(status and status != "unavailable"),
    }


def _dependency_versions() -> dict[str, str]:
    versions = {}
    for package in ("numpy", "pandas", "scipy", "matplotlib", "PyYAML"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def write_run_manifest(
    output_path: str | Path,
    *,
    config_path: str | Path,
    output_paths: Iterable[str | Path],
    command: Iterable[str],
    master_seed: int,
    max_evaluations: int | None,
    git_state: dict[str, str | bool] | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
) -> dict:
    config_file = Path(config_path)
    config_hash = hashlib.sha256(config_file.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "started_at": started_at or datetime.now(timezone.utc).isoformat(),
        "ended_at": ended_at or datetime.now(timezone.utc).isoformat(),
        "command": list(command),
        "config_path": str(config_path),
        "config_hash": config_hash,
        "master_seed": int(master_seed),
        "seed_policy": {
            "scenario_seed": "derive_seed(master_seed, 'scenario', scenario_id, replicate_id)",
            "algorithm_seed": "derive_seed(master_seed, 'algorithm', algorithm_name, scenario_id, replicate_id)",
        },
        "max_evaluations": max_evaluations,
        "output_paths": [str(path) for path in output_paths],
        "git": dict(git_state or capture_git_state()),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "dependencies": _dependency_versions(),
        },
    }
    ensure_parent(output_path)
    Path(output_path).write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return manifest
