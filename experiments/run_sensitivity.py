from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd

from experiments.analyze_results import generate_sensitivity_figures
from experiments.experiment_core import load_config, run_algorithm_suite, write_raw_and_summary


WEIGHT_RAW = "results/v2/sensitivity/raw/weight_sensitivity_raw_results.csv"
WEIGHT_SUMMARY = "results/v2/sensitivity/summary/weight_sensitivity_summary_mean_std.csv"
PENALTY_RAW = "results/v2/sensitivity/raw/dynamic_penalty_sensitivity_raw_results.csv"
PENALTY_SUMMARY = "results/v2/sensitivity/summary/dynamic_penalty_sensitivity_summary_mean_std.csv"
PHYSICAL_RAW = "results/v2/sensitivity/raw/physical_sensitivity_raw_results.csv"
PHYSICAL_SUMMARY = "results/v2/sensitivity/summary/physical_sensitivity_summary_mean_std.csv"
UTILITY_RAW = "results/v2/sensitivity/raw/utility_sensitivity_raw_results.csv"
UTILITY_SUMMARY = "results/v2/sensitivity/summary/utility_sensitivity_summary_mean_std.csv"


def _weights_sum_to_one(weights: dict[str, float]) -> bool:
    return abs(sum(float(value) for value in weights.values()) - 1.0) < 1.0e-9


def _format_weights(weights: dict[str, float]) -> str:
    return (
        f"({weights['energy']:.3f}, {weights['delay']:.3f}, {weights['aoi']:.3f}, "
        f"{weights['qoe']:.3f}, {weights['fairness']:.3f})"
    )


def _format_utility_weights(weights: dict[str, float]) -> str:
    return f"({weights['delay']:.3f}, {weights['energy']:.3f}, {weights['aoi']:.3f})"


def _completed_groups(path: str, columns: list[str], n_runs: int) -> set[tuple]:
    if not Path(path).exists():
        return set()
    frame = pd.read_csv(path)
    if any(column not in frame.columns for column in columns):
        return set()
    counts = frame.groupby(columns, dropna=False).size()
    return {key if isinstance(key, tuple) else (key,) for key, count in counts.items() if count == n_runs}


def _reusable_rows(path: str, columns: list[str], completed: set[tuple]) -> list[dict]:
    if not Path(path).exists() or not completed:
        return []
    frame = pd.read_csv(path)
    keys = frame[columns].apply(lambda row: tuple(row), axis=1)
    return frame[keys.isin(completed)].to_dict("records")


def _weight_raw_complete(path: str, settings: list[str], n_runs: int) -> bool:
    if not Path(path).exists():
        return False
    df = pd.read_csv(path)
    counts = df.groupby("setting").size().to_dict()
    return all(counts.get(setting) == n_runs for setting in settings)


def _penalty_raw_complete(path: str, lambdas: list[float], alphas: list[float], n_runs: int) -> bool:
    if not Path(path).exists():
        return False
    df = pd.read_csv(path)
    counts = df.groupby(["lambda0", "alpha"]).size().to_dict()
    expected = [(float(lambda0), float(alpha)) for lambda0 in lambdas for alpha in alphas]
    return all(counts.get(pair) == n_runs for pair in expected)


def run_weight_sensitivity(config: dict) -> None:
    n_runs = int(config["experiment"]["independent_runs"])
    settings = [setting["setting"] for setting in config["weight_settings"]]
    group_cols = ["setting", "description", "weights", "w_energy", "w_delay", "w_aoi", "w_qoe", "w_fairness"]
    completed = _completed_groups(WEIGHT_RAW, ["setting"], n_runs)
    configured = {(setting,) for setting in settings}
    all_rows = _reusable_rows(WEIGHT_RAW, ["setting"], completed & configured)
    for setting in config["weight_settings"]:
        if (setting["setting"],) in completed:
            print(f"Reusing completed weight sensitivity {setting['setting']}...")
            continue
        weights = {key: float(value) for key, value in setting["weights"].items()}
        if not _weights_sum_to_one(weights):
            raise ValueError(f"{setting['setting']} weights must sum to 1.0: {weights}")

        print(f"Running weight sensitivity {setting['setting']} with {n_runs} runs...")
        run_config = deepcopy(config)
        run_config["weights"] = weights
        run_config.pop("penalty", None)
        rows, _ = run_algorithm_suite(run_config, ["RDHO"], n_runs=n_runs)
        for row in rows:
            row["experiment"] = "objective_weight"
            row["setting"] = setting["setting"]
            row["description"] = setting["description"]
            row["weights"] = _format_weights(weights)
            row["w_energy"] = weights["energy"]
            row["w_delay"] = weights["delay"]
            row["w_aoi"] = weights["aoi"]
            row["w_qoe"] = weights["qoe"]
            row["w_fairness"] = weights["fairness"]
        all_rows.extend(rows)

    write_raw_and_summary(
        WEIGHT_RAW,
        WEIGHT_SUMMARY,
        all_rows,
        group_cols=group_cols,
    )


def run_utility_sensitivity(config: dict) -> None:
    n_runs = int(config["experiment"]["independent_runs"])
    group_cols = ["setting", "description", "utility_weights", "u_delay", "u_energy", "u_aoi"]
    settings = [item["setting"] for item in config["utility_settings"]]
    completed = _completed_groups(UTILITY_RAW, ["setting"], n_runs)
    configured = {(setting,) for setting in settings}
    all_rows = _reusable_rows(UTILITY_RAW, ["setting"], completed & configured)
    for setting in config["utility_settings"]:
        if (setting["setting"],) in completed:
            print(f"Reusing completed utility sensitivity {setting['setting']}...")
            continue
        weights = {key: float(value) for key, value in setting["weights"].items()}
        if abs(sum(weights.values()) - 1.0) >= 1.0e-9 or any(value < 0.0 for value in weights.values()):
            raise ValueError(f"{setting['setting']} utility weights must be non-negative and sum to 1.0")
        print(f"Running utility sensitivity {setting['setting']} with {n_runs} runs...")
        run_config = deepcopy(config)
        run_config["utility_weights"] = weights
        rows, _ = run_algorithm_suite(run_config, ["RDHO"], n_runs=n_runs)
        for row in rows:
            row.update({
                "experiment": "utility_weight",
                "setting": setting["setting"],
                "description": setting["description"],
                "utility_weights": _format_utility_weights(weights),
                "u_delay": weights["delay"],
                "u_energy": weights["energy"],
                "u_aoi": weights["aoi"],
            })
        all_rows.extend(rows)
    write_raw_and_summary(UTILITY_RAW, UTILITY_SUMMARY, all_rows, group_cols=group_cols)


def run_penalty_sensitivity(config: dict) -> None:
    n_runs = int(config["experiment"]["independent_runs"])
    lambdas = [float(value) for value in config["penalty_grid"]["lambda0"]]
    alphas = [float(value) for value in config["penalty_grid"]["alpha"]]
    if _penalty_raw_complete(PENALTY_RAW, lambdas, alphas, n_runs):
        print(f"Reusing completed penalty sensitivity raw results from {PENALTY_RAW}...")
        rows = pd.read_csv(PENALTY_RAW).to_dict("records")
        write_raw_and_summary(PENALTY_RAW, PENALTY_SUMMARY, rows, group_cols=["lambda0", "alpha"])
        return

    all_rows = []
    for lambda0 in config["penalty_grid"]["lambda0"]:
        for alpha in config["penalty_grid"]["alpha"]:
            print(f"Running penalty sensitivity lambda0={float(lambda0):.1f}, alpha={float(alpha):.1f} with {n_runs} runs...")
            run_config = deepcopy(config)
            run_config["weights"] = deepcopy(config["weights"])
            run_config["penalty"] = {"lambda0": float(lambda0), "alpha": float(alpha)}
            rows, _ = run_algorithm_suite(run_config, ["RDHO"], n_runs=n_runs)
            for row in rows:
                row["experiment"] = "dynamic_penalty"
                row["lambda0"] = float(lambda0)
                row["alpha"] = float(alpha)
            all_rows.extend(rows)

    write_raw_and_summary(
        PENALTY_RAW,
        PENALTY_SUMMARY,
        all_rows,
        group_cols=["lambda0", "alpha"],
    )


def run_physical_sensitivity(config: dict) -> None:
    n_runs = int(config["experiment"]["independent_runs"])
    expected = []
    expected.extend(("cpu_capacity", f"capacity_{scale}") for scale in config.get("capacity_scales", []))
    expected.extend(("sla_strictness", f"sla_{scale}") for scale in config.get("sla_scales", []))
    expected.extend(("server_heterogeneity", f"heterogeneity_{scale}") for scale in config.get("server_heterogeneity_scales", []))
    completed = _completed_groups(PHYSICAL_RAW, ["experiment", "setting"], n_runs)
    configured = set(expected)
    rows = _reusable_rows(PHYSICAL_RAW, ["experiment", "setting"], completed & configured)
    for row in rows:
        row.setdefault("server_heterogeneity_scale", 1.0)
    for scale in config.get("capacity_scales", []):
        if ("cpu_capacity", f"capacity_{scale}") in completed:
            print(f"Reusing completed CPU-capacity sensitivity scale={scale}...")
            continue
        print(f"Running CPU-capacity sensitivity scale={scale} with {n_runs} runs...")
        result, _ = run_algorithm_suite(config, ["RDHO"], n_runs=n_runs, cpu_capacity_scale=float(scale))
        for row in result:
            row.update({"experiment": "cpu_capacity", "setting": f"capacity_{scale}", "cpu_capacity_scale": float(scale), "sla_scale": 1.0, "server_heterogeneity_scale": 1.0})
        rows.extend(result)
    for scale in config.get("sla_scales", []):
        if ("sla_strictness", f"sla_{scale}") in completed:
            print(f"Reusing completed SLA sensitivity scale={scale}...")
            continue
        print(f"Running SLA sensitivity scale={scale} with {n_runs} runs...")
        result, _ = run_algorithm_suite(config, ["RDHO"], n_runs=n_runs, sla_scale=float(scale))
        for row in result:
            row.update({"experiment": "sla_strictness", "setting": f"sla_{scale}", "cpu_capacity_scale": 1.0, "sla_scale": float(scale), "server_heterogeneity_scale": 1.0})
        rows.extend(result)
    for scale in config.get("server_heterogeneity_scales", []):
        if ("server_heterogeneity", f"heterogeneity_{scale}") in completed:
            print(f"Reusing completed server-heterogeneity sensitivity scale={scale}...")
            continue
        print(f"Running server-heterogeneity sensitivity scale={scale} with {n_runs} runs...")
        result, _ = run_algorithm_suite(config, ["RDHO"], n_runs=n_runs, server_heterogeneity_scale=float(scale))
        for row in result:
            row.update({"experiment": "server_heterogeneity", "setting": f"heterogeneity_{scale}", "cpu_capacity_scale": 1.0, "sla_scale": 1.0, "server_heterogeneity_scale": float(scale)})
        rows.extend(result)
    write_raw_and_summary(
        PHYSICAL_RAW,
        PHYSICAL_SUMMARY,
        rows,
        group_cols=["experiment", "setting", "cpu_capacity_scale", "sla_scale", "server_heterogeneity_scale"],
    )


def main() -> None:
    config = load_config("configs/sensitivity.yaml")
    run_weight_sensitivity(config)
    run_penalty_sensitivity(config)
    run_utility_sensitivity(config)
    run_physical_sensitivity(config)
    generate_sensitivity_figures(
        WEIGHT_RAW,
        PENALTY_RAW,
        "results/v2/sensitivity/figures",
        utility_raw_csv=UTILITY_RAW,
        physical_raw_csv=PHYSICAL_RAW,
    )


if __name__ == "__main__":
    main()
