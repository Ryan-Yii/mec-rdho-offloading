# Capacity-Feasible MEC Task Offloading and CPU Allocation

**Manuscript:** *RDHO-Based Joint Task Offloading and Computing Resource Allocation in Mobile Edge Computing*
**Research branch:** `research/physical-offloading-model-v2`

This repository is the reproducibility package for a simulated three-tier cloud-edge-device MEC study. Each task selects exactly one legal local, edge, or cloud execution node and receives a physical CPU allocation in Hz. A deterministic common repair preserves feasible decoded CPU requests and proportionally projects only overloaded nodes, so every reported solution satisfies assignment, reachability, CPU-bound, and aggregate node-capacity constraints.

[![Tests](https://github.com/Ryan-Yii/mec-rdho-offloading/actions/workflows/tests.yml/badge.svg)](https://github.com/Ryan-Yii/mec-rdho-offloading/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Model Scope

- **Decisions:** execution node and per-task physical CPU frequency.
- **Legal paths:** local execution only at the source device; edge and cloud choices only through generated positive-rate links.
- **Fixed scenario parameters:** communication rates, transmit power, topology, and service overheads.
- **Reported criteria:** device-side energy, delay, periodic no-backlog average-AoI approximation, model-based QoE, active-user Jain fairness, and soft QoS CSR.
- **Hard feasibility:** unique legal assignment, finite CPU bounds, and total CPU capacity are enforced by the shared decoder and repair for every algorithm.
- **Excluded decisions:** bandwidth, power, association, routing, queue scheduling, and infrastructure energy.

The formal reporting objective is fixed across algorithms. RDHO's iteration-dependent penalty guides search only; parent and candidate solutions in one greedy comparison use the same coefficient.

## Fresh V2 Evidence

The canonical configuration uses 20 devices, 4 edge servers, 2 cloud servers, 40 tasks, population 50, 150 iterations, and 30 paired scenarios. All V2 raw results were rerun after the physical CPU-repair correction and are isolated under [`results/v2`](results/v2). Legacy results are not consumed by V2 generators.

| Algorithm | Reporting fitness | QoE | Per-user fairness | Soft CSR | Runtime (s) | NFE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| RDHO-full | 0.9470 | 0.4468 | 0.9244 | 0.7206 | 7.8306 | 10232 |
| RIME | 1.5848 | 0.3551 | 0.8385 | 0.5133 | 5.9657 | 7551 |
| DBO | 1.1837 | 0.4145 | 0.9161 | 0.6286 | 5.8198 | 7551 |
| TLBO-HHO | 1.2263 | 0.4070 | 0.9098 | 0.5989 | 5.7114 | 7551 |
| CWTSSA | 1.2473 | 0.4079 | 0.9140 | 0.5883 | 5.6783 | 7551 |
| Greedy-ED | 1.0932 | 0.4282 | 0.9164 | 0.6481 | 0.5069 | 681 |

All main-run hard-feasibility rates are 1.0. RDHO-full has mean active-node CPU utilisation 0.8189, which also verifies that feasible allocations are not silently saturated.

The paired end-to-end result must not be read as universal superiority of the hybrid population operator. At equal NFE (3801 evaluations), RDHO-core beats RIME but is worse than DBO, TLBO-HHO, and CWTSSA. With common initialisation and common coordinate refinement, RIME and DBO reach 0.9819 and 0.9671 mean fitness, respectively, close to RDHO-full at 0.9470. The complete pipeline, especially shared postprocessing, explains much of the end-to-end difference.

## Evidence Map

- [Main raw results](results/v2/raw/main_30_raw_results.csv), [summary](results/v2/summary/main_30_summary_mean_std.csv), [convergence](results/v2/raw/main_30_convergence.csv), and [paired statistics](results/v2/statistics/wilcoxon_fitness_results.csv)
- [Equal-NFE results](results/v2/summary/equal_nfe_30_summary_mean_std.csv) and [common-control results](results/v2/summary/common_control_30_summary_mean_std.csv)
- [Ablation](results/v2/summary/ablation_30_summary_mean_std.csv), [scalability](results/v2/summary/scalability_summary_mean_std.csv), and [sensitivity](results/v2/sensitivity)
- [Paper tables](paper_tables/v2), [paper figures](figures/paper/v2), and [artifact manifest](paper_artifacts/manifest.csv)
- [Model definition](docs/model_design_v2.md), [experiment protocol](docs/experiment_protocol_v2.md), and [execution report](docs/experiment_execution_report.md)

## Reproduction

Use Python 3.9 or later from the repository root:

```bash
python -m pip install -r requirements.txt
python -m pytest tests -q
```

Run every experiment family:

```bash
python -m experiments.run_main_30
python -m experiments.run_controlled_30
python -m experiments.run_ablation_30
python -m experiments.run_scalability
python -m experiments.run_sensitivity
python -m experiments.generate_v2_artifacts
```

The runners use deterministic scenario seeds. Algorithms compared within one run ID receive the same task and network instance while using separately derived, repeatable algorithm random streams. Full runs take substantial time; the committed logs and per-row seeds document the completed execution.

## Interpretation

The main paired Wilcoxon tests are two-sided and include Holm adjustment, median paired difference, rank-biserial effect size, and wins/ties/losses. RDHO-full beats each configured main baseline in all 30 paired scenarios, but its NFE differs from those baselines. The equal-NFE and common-postprocessing controls therefore carry equal weight in the scientific interpretation.

The one-factor ablation does not support claiming that every internal component independently improves performance. Removing coordinate refinement causes the large change; removing adaptive roles, elite preservation, or dynamic penalty has only a small mean effect in this configuration. Weight-specific fitness values are meaningful within their own objective setting and are not ranked across different weight vectors.

Results apply only to the supplied simulations, objective, parameter ranges, seeds, and baseline implementations. QoE is a model-based utility rather than human-subject MOS, AoI is a periodic no-backlog average approximation, CSR concerns soft thresholds rather than hard physical feasibility, and the radar plot uses min-max normalisation that can visually amplify small differences.

## Repository Structure

```text
configs/             Versioned experiment configurations
experiments/         Runners, statistics, plotting, and artifact generation
src/                 Physical model, decoder/repair, metrics, and algorithms
tests/               Formula, feasibility, control, and artifact regression tests
results/v2/          Fresh raw data, summaries, statistics, figures, and logs
paper_tables/v2/     Generated CSV and Markdown manuscript tables
figures/paper/v2/    Manuscript PNG and editable SVG figures
paper_artifacts/     Hash-linked manuscript artifact manifest
docs/                Model, protocol, audit, and execution documentation
```

See [data_availability.md](data_availability.md) for data provenance, [CITATION.cff](CITATION.cff) for citation metadata, and [NOTICE.md](NOTICE.md) for contributor and source provenance.
