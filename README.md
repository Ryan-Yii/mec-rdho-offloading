# MEC RDHO Offloading Research Repository

This repository contains the reproducible code, configuration files, raw
outputs, summary tables, and manuscript figures for the paper:

**Hybrid RIME-DBO Optimisation for QoE- and Fairness-Aware Task Offloading in
Mobile Edge Computing**

The repository is organised as a formal research artefact for the RDHO mobile
edge computing (MEC) task-offloading study. It includes the implementation of
the proposed Hybrid RIME-DBO Optimisation (RDHO) algorithm, baseline methods,
experiment scripts, generated results, and paper-ready figures.

## Overview

RDHO is a hybrid metaheuristic scheduler for joint task offloading and resource
allocation in a cloud-edge-device MEC system. The optimisation objective
combines five metrics:

- mobile-device energy consumption;
- processing delay;
- Age of Information (AoI);
- Quality of Experience (QoE);
- QoE-based Jain fairness.

RDHO combines RIME-style exploration with DBO-style role-adaptive exploitation.
It uses dual-source initialisation, adaptive producer/follower/scout roles,
elite preservation, greedy selection, repair-based hard-constraint handling,
and dynamic penalties for soft QoS-satisfaction conditions.

## Repository Layout

```text
mec-rdho-offloading/
|-- configs/
|   |-- main_40tasks.yaml
|   |-- ablation.yaml
|   |-- scalability.yaml
|   `-- sensitivity.yaml
|-- experiments/
|   |-- run_main_30.py
|   |-- run_ablation_30.py
|   |-- run_scalability.py
|   |-- run_sensitivity.py
|   `-- analyze_results.py
|-- figures/
|   |-- fig01_convergence_curve.png
|   |-- fig02_energy_comparison.png
|   |-- fig03_delay_comparison.png
|   |-- fig04_aoi_comparison.png
|   |-- fig05_qoe_fairness_comparison.png
|   |-- fig06_soft_csr_comparison.png
|   |-- fig07_ablation_study.png
|   |-- fig08_scalability.png
|   |-- fig09_weight_sensitivity_qoe_fairness_csr.png
|   |-- fig10_penalty_sensitivity_heatmaps.png
|   |-- fig11_normalized_multi_metric_radar.png
|   `-- supp_weight_sensitivity_fitness.png
|-- paper_tables/
|-- results/
|   |-- raw/
|   |-- summary/
|   |-- figures/
|   `-- sensitivity/
|       |-- raw/
|       |-- summary/
|       `-- figures/
|-- src/
|   |-- algorithms/
|   |-- utils/
|   |-- metrics.py
|   |-- system_model.py
|   `-- task_generator.py
|-- tests/
|-- CITATION.cff
|-- LICENSE
|-- NOTICE.md
|-- data_availability.md
|-- requirements.txt
`-- README.md
```

## Environment

The experiments were developed with Python 3.11. Install the required
dependencies with:

```bash
python -m pip install -r requirements.txt
```

Main dependencies:

- `numpy`
- `pandas`
- `scipy`
- `matplotlib`
- `PyYAML`
- `pytest`
- `tabulate`

## Reproducibility

Run the validation tests:

```bash
python -m pytest tests -q
```

Run the main 30-run comparison:

```bash
python -m experiments.run_main_30
```

Run the ablation study:

```bash
python -m experiments.run_ablation_30
```

Run the scalability analysis:

```bash
python -m experiments.run_scalability
```

Run the objective-weight and dynamic-penalty sensitivity analyses:

```bash
python -m experiments.run_sensitivity
```

All experiment scripts write generated artefacts to `results/` and
manuscript-ready tables to `paper_tables/`.

## Experimental Setting

The main benchmark uses:

- 20 mobile devices;
- 4 edge servers;
- 2 cloud servers;
- 40 heterogeneous tasks;
- population size 50;
- 150 maximum iterations;
- 30 independent runs.

For a fixed seed, all compared algorithms use the same generated task set and
network configuration. Task-generation ranges are reported in
`results/raw/task_generation_ranges.csv` and
`paper_tables/task_generation_ranges.md`.

Compared methods:

- RDHO;
- RIME;
- DBO;
- TLBO-HHO;
- CWTSSA;
- Greedy-ED.

The one-sided paired Wilcoxon signed-rank test compares RDHO fitness against
RIME, DBO, TLBO-HHO, and CWTSSA across the 30 paired runs, using the
alternative hypothesis that RDHO obtains lower comprehensive fitness.

## Main Results

In the 40-task, 30-run benchmark, RDHO obtains the lowest mean comprehensive
fitness among the compared methods:

| Algorithm | Fitness mean | QoE mean | Fairness mean | Soft CSR mean | Runtime mean (s) |
|---|---:|---:|---:|---:|---:|
| RDHO | 0.9734 | 0.3273 | 0.9000 | 0.7031 | 4.4486 |
| RIME | 1.4053 | 0.2804 | 0.8199 | 0.5653 | 3.7067 |
| DBO | 1.0200 | 0.3192 | 0.8971 | 0.6819 | 3.6710 |
| TLBO-HHO | 1.0692 | 0.3171 | 0.8998 | 0.6544 | 3.7055 |
| CWTSSA | 1.0307 | 0.3198 | 0.8996 | 0.6761 | 3.7537 |
| Greedy-ED | 1.0512 | 0.3238 | 0.8985 | 0.6275 | 0.1749 |

The result should be interpreted as a comprehensive user-centric trade-off:
RDHO is not the best method on every raw metric, but it achieves the best
penalised objective together with the highest QoE, QoE-based fairness, and
soft QoS satisfaction ratio in this benchmark.

Full summary files are available in:

- `results/summary/main_30_summary_mean_std.csv`
- `paper_tables/main_30_summary_mean_std.md`
- `results/summary/wilcoxon_fitness_results.csv`
- `paper_tables/wilcoxon_fitness_results.md`

## Sensitivity Analyses

The objective-weight sensitivity analysis evaluates RDHO under five weight
vectors:

- `S1`: `(w_E, w_D, w_A, w_Q, w_J) = (0.15, 0.15, 0.20, 0.25, 0.25)`, original setting.
- `S2`: `(0.20, 0.20, 0.20, 0.20, 0.20)`, equal weighting.
- `S3`: `(0.25, 0.25, 0.20, 0.15, 0.15)`, energy-delay priority.
- `S4`: `(0.10, 0.10, 0.15, 0.325, 0.325)`, QoE-fairness priority.
- `S5`: `(0.125, 0.125, 0.35, 0.20, 0.20)`, AoI-freshness priority.

The dynamic-penalty sensitivity analysis keeps the original objective weights
and varies `lambda0` in `{0.5, 1.0, 2.0}` and `alpha` in `{1.0, 2.0, 3.0}`.
The original setting is `lambda0=1.0, alpha=2.0`.

Sensitivity outputs are available in:

- `results/sensitivity/raw/`
- `results/sensitivity/summary/`
- `results/sensitivity/figures/`
- `paper_tables/weight_sensitivity_summary.md`
- `paper_tables/dynamic_penalty_sensitivity_summary.md`

## Figures

Paper-facing copies of the manuscript figures are available in `figures/`.
The result-generation copies are retained under `results/figures/` and
`results/sensitivity/figures/`.

See `figures/README.md` for the mapping between figure files and manuscript
figure numbers.

## Data and Code Availability

The experiments use simulated MEC task sets generated by this repository. No
proprietary, confidential, or human-subject data are used.

See `data_availability.md` for details on generated data, code, result
artefacts, and reproducibility notes.

## Citation

If you use this repository, please cite the associated manuscript and this
software artefact. A machine-readable citation file is provided in
`CITATION.cff`.

## License and Provenance

This cleaned research artefact is released under the MIT License. See
`LICENSE` for details.

The implementation was developed and extended from internal research code with
permission from the project contributors. See `NOTICE.md` for provenance
details.
