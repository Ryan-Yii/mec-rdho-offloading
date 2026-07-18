# MEC RDHO Offloading Research Repository

This repository contains the reproducible implementation and experimental artefacts for the manuscript:

**RIME-DBO-Based QoE- and Fairness-Aware Task Offloading in Mobile Edge Computing**

The revision aligns the mathematical formulation, algorithm description, evaluation semantics, tables, and figures with the executable code.

## Implemented problem

For each generated MEC task, the optimiser selects:

- an execution mode: local, edge, or cloud; and
- a bounded normalised computation-control value in `[0.2, 1.0]`. The value is a simulation-level service-intensity control rather than an additive physical CPU share.

The access edge and mapped cloud are fixed by the simulated topology. Communication rates are scenario parameters rather than optimisation variables. Shared-node contention is represented by load-adjusted effective execution frequencies.

The reported objective combines:

- mobile-device energy;
- processing delay;
- a single-epoch Age of Information (AoI) surrogate;
- a priority-weighted QoE proxy; and
- Jain fairness over each active user's mean priority-weighted task QoE.

Soft delay, battery-adjusted energy, and AoI conditions are summarised by the soft constraint-satisfaction ratio (CSR).

## Fitness semantics

The implementation deliberately distinguishes three quantities:

1. `base_objective`: the five-metric weighted objective without a CSR penalty;
2. `search_fitness`: the base objective plus the iteration-dependent penalty used internally by RDHO; and
3. `reporting_fitness`: the base objective plus a common fixed reference penalty coefficient of `1.0`, used to compare final solutions across algorithms and sensitivity settings.

Parents and candidates are evaluated under the same current penalty coefficient during greedy selection. Convergence curves report the fixed-reference fitness of the incumbent solution, while the optional coordinate-wise local refinement is reported separately.

## RDHO implementation

RDHO combines:

- half-Gaussian/half-uniform initialisation;
- a greedy coordinate seed and small perturbations;
- adaptive producer, follower, and scout roles;
- RIME-inspired exploration and DBO-inspired role updates, including coordinate-specific follower bounds `L=(0,0.2)` and `U=(2,1)`;
- optional elite preservation;
- an iteration-dependent soft-CSR penalty; and
- optional coordinate-wise local refinement.

`RDHO-core` disables only the final local-refinement stage. The results support the complete configured solver; they do not isolate the RIME–DBO population operator from greedy seeding and coordinate refinement. The component-ablation variants keep local refinement enabled so that each variant removes one named search component at a time.

## Repository layout

```text
mec-rdho-offloading/
|-- configs/                 # experiment settings
|-- experiments/             # experiment and analysis entry points
|-- figures/                 # manuscript-facing figure copies
|-- paper_tables/            # manuscript-facing tables
|-- results/
|   |-- raw/                 # per-run outputs and convergence histories
|   |-- summary/             # aggregated results and statistical tests
|   |-- figures/             # generated main/ablation/scalability figures
|   `-- sensitivity/         # weight and penalty sensitivity outputs
|-- src/
|   |-- algorithms/          # RDHO and baselines
|   |-- metrics.py           # metrics and objective evaluation
|   |-- system_model.py      # MEC data structures
|   `-- task_generator.py    # seeded heterogeneous scenarios
|-- tests/                   # regression and alignment tests
|-- tools/                   # marked-manuscript generation and layout helpers
|-- data_availability.md
|-- requirements.txt
`-- README.md
```

## Environment

The final revision was verified with Python 3.13.5. The code uses Python 3.11-compatible language features and the dependency floors in `requirements.txt`.

```bash
python -m pip install -r requirements.txt
python -m pytest tests -q
```

## Reproducing the experiments

Main paired 30-run comparison:

```bash
python -m experiments.run_main_30
```

Component and local-refinement ablation:

```bash
python -m experiments.run_ablation_30
```

Scalability analysis:

```bash
python -m experiments.run_scalability
```

Objective-weight and dynamic-penalty sensitivity:

```bash
python -m experiments.run_sensitivity
```

All scripts use deterministic scenario seeds. For a given run ID, compared algorithms receive the same generated tasks and network configuration; algorithm-specific random streams are derived separately. RDHO component variants use the same base RDHO stream, and the ablation RDHO-full reference reuses the paired main-run RDHO rows so that Tables 5 and 7 report the same reference solutions.

## Main benchmark

Baseline-specific constants are fixed before the reported tests and are documented in `configs/baseline_parameters.yaml`; the executable implementations under `src/algorithms/` remain authoritative. No algorithm-specific tuning was performed on the reported test scenarios.


The main experiment uses 20 devices, 4 edge servers, 2 cloud servers, 40 heterogeneous tasks, a population of 50, 150 iterations, and 30 paired scenarios.

| Algorithm | Reporting fitness | QoE | Priority-aware fairness | Soft CSR | Runtime (s) | NFE |
|---|---:|---:|---:|---:|---:|---:|
| RDHO-full | 0.9571 | 0.3270 | 0.9388 | 0.7089 | 4.2626 | 9112 |
| RIME | 1.3858 | 0.2800 | 0.8972 | 0.5617 | 4.4626 | 7551 |
| DBO | 1.0276 | 0.3177 | 0.9360 | 0.6753 | 4.3956 | 7551 |
| TLBO-HHO | 1.0638 | 0.3164 | 0.9350 | 0.6450 | 4.3127 | 7551 |
| CWTSSA | 1.0258 | 0.3195 | 0.9383 | 0.6728 | 4.3180 | 7551 |
| Greedy-ED | 1.0420 | 0.3236 | 0.9389 | 0.6272 | 0.1995 | 361 |

RDHO-full achieves the lowest mean fixed-reference reporting fitness in this implemented suite. This is an overall weighted trade-off, not dominance on every raw metric: TLBO-HHO uses the least energy, Greedy-ED has the lowest delay, AoI, and runtime, and RDHO-full incurs more function evaluations because of its seeded construction and local refinement.

Paired two-sided Wilcoxon signed-rank tests compare RDHO-full with all five baselines. Holm-adjusted p-values, rank-biserial effect sizes, and wins/ties/losses are stored in `results/summary/wilcoxon_fitness_results.csv`.

## Key artefacts

- `results/raw/main_30_raw_results.csv`
- `results/raw/main_30_convergence.csv`
- `results/summary/main_30_summary_mean_std.csv`
- `results/summary/wilcoxon_fitness_results.csv`
- `results/raw/ablation_30_raw_results.csv`
- `results/summary/ablation_30_summary_mean_std.csv`
- `results/raw/scalability_raw_results.csv`
- `results/summary/scalability_summary_mean_std.csv`
- `results/sensitivity/raw/`
- `results/sensitivity/summary/`
- `paper_tables/`
- `figures/`

## Scope and interpretation

The study uses simulated, fixed-rate, fixed-association MEC scenarios. The QoE term is a model-based proxy rather than a human-subject MOS measurement. The results support comparative claims only for the stated objective, parameter ranges, seeds, implementations, and baseline suite. They do not establish universal superiority or hard satisfaction of every soft service threshold.

## Data and code availability

No proprietary or human-subject data are used. See `data_availability.md` for the generated data, code, result artefacts, and reproduction notes.

## License and provenance

The cleaned research artefact is released under the MIT License. See `LICENSE` and `NOTICE.md`.
