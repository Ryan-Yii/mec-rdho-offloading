# Capacity-Feasible MEC Task Offloading and CPU Allocation

**Manuscript:** *RIME-DBO-Based Capacity-Feasible Task Offloading and Resource Allocation in Mobile Edge Computing*
**Audited experiment baseline:** `0264b6d35b52bae4ec871ddaf9653285d47a7783` on `main`
**Versioned release:** [`v2.0.0`](https://github.com/Ryan-Yii/mec-rdho-offloading/releases/tag/v2.0.0)

This repository is the reproducibility package for a simulated three-tier cloud-edge-device MEC study. Each task selects exactly one legal local, edge, or cloud execution node and receives a physical CPU allocation in Hz. A deterministic common repair reassigns minimum-frequency-infeasible tasks when necessary, preserves feasible decoded requests, and proportionally projects excess demand only on overloaded nodes, so every reported solution satisfies assignment, reachability, CPU-bound, and aggregate node-capacity constraints.

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

The paired end-to-end result must not be read as universal superiority of the hybrid population operator. In the strict population-stage control, one copied initial population and exactly 3,801 NFE give mean reporting fitness 1.4188 for RDHO, 1.6834 for RIME, and 1.2409 for DBO. With the same deterministic refinement and exactly 10,232 NFE, the means are 0.9732, 0.9836, and 0.9664, respectively. RDHO therefore beats RIME but is significantly worse than DBO in both strict controls. The configured V2 equal-NFE and common-control suites under `results/v2/` independently support the same bounded interpretation: common refinement explains much of the complete-pipeline difference.

## Evidence Map

- [Main raw results](results/v2/raw/main_30_raw_results.csv), [summary](results/v2/summary/main_30_summary_mean_std.csv), [convergence](results/v2/raw/main_30_convergence.csv), and [paired statistics](results/v2/statistics/wilcoxon_fitness_results.csv)
- [Equal-NFE results](results/v2/summary/equal_nfe_30_summary_mean_std.csv) and [common-control results](results/v2/summary/common_control_30_summary_mean_std.csv)
- [Strict controlled raw results](results/raw/controlled_population_stage_30_raw_results.csv), [common-pipeline results](results/raw/controlled_common_pipeline_30_raw_results.csv), and [paired statistics](results/statistics/controlled_evidence_effect_sizes.csv)
- [Ablation](results/v2/summary/ablation_30_summary_mean_std.csv), [scalability](results/v2/summary/scalability_summary_mean_std.csv), and [sensitivity](results/v2/sensitivity)
- [Paper tables](paper_tables/v2), [paper figures](figures/paper), including the editable [Figure 1 source](figures/paper/fig1_system_architecture.svg), and [artifact manifest](paper_artifacts/manifest.csv)
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
python -m experiments.audit_task_id_neutrality
python -m experiments.generate_v2_artifacts
```

The runners use deterministic scenario seeds. Algorithms compared within one run ID receive the same task and network instance while using separately derived, repeatable algorithm random streams. Full runs take substantial time; per-row seeds and the checksums in `docs/experiment_execution_report.md` document the completed execution.

The optional OOXML manuscript tools under `tools/` use `requirements-docs.txt` and a LibreOffice installation for DOCX/PDF rendering. They require an explicit source DOCX and output directory and contain no workstation-specific paths.

## Interpretation

The main paired Wilcoxon tests are two-sided and include Holm adjustment, median paired difference, rank-biserial effect size, and wins/ties/losses. RDHO-full beats each configured main baseline in all 30 paired scenarios, but its NFE differs from those baselines. The equal-NFE, common-initialisation, and common-refinement controls therefore carry equal weight in the scientific interpretation.

The one-factor ablation does not support claiming that every internal component independently improves performance. Removing coordinate refinement causes the large change; removing adaptive roles, elite preservation, or dynamic penalty has only a small mean effect in this configuration. Weight-specific fitness values are meaningful within their own objective setting and are not ranked across different weight vectors.

Results apply only to the configured simulations, objective, parameter ranges, seeds, and baseline implementations. QoE is a model-based utility rather than human-subject MOS, AoI is a periodic no-backlog average approximation, and CSR concerns soft thresholds rather than hard physical feasibility. The main paper reports explicit equal-NFE and common-initialisation/common-refinement controls.

## Repository Structure

```text
configs/             Versioned experiment configurations
experiments/         Runners, statistics, plotting, and artifact generation
src/                 Physical model, decoder/repair, metrics, and algorithms
tests/               Formula, feasibility, control, and artifact regression tests
results/v2/          Fresh raw data, summaries, statistics, and figures
paper_tables/v2/     Generated CSV and Markdown manuscript tables
figures/paper/       Figure 1 SVG/PNG/PDF and generated V2 figures
paper_artifacts/     Hash-linked manuscript artifact manifest
docs/                Model, protocol, audit, and execution documentation
```

See [data_availability.md](data_availability.md) for data provenance, [CITATION.cff](CITATION.cff) for citation metadata, and [NOTICE.md](NOTICE.md) for contributor and source provenance.
