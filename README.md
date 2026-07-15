# MEC RDHO Offloading Research Repository

This repository contains the reproducible research artefact for the paper:

**Hybrid RIME-DBO Optimisation for QoE- and Fairness-Aware Task Offloading in
Mobile Edge Computing**

It includes the implemented MEC model, RDHO and baseline algorithms, formal
experiment configurations, tests, raw outputs, statistical results, run
manifests, and manuscript-facing figures.

## Implemented Model

Each task uses the decision vector `X_i = [m_i, r_i]`:

- `m_i` selects local, edge, or cloud execution;
- `r_i` is a continuous resource ratio clipped to `[0.2, 1.0]`;
- edge and cloud destinations follow the fixed nearest-edge and nearest-cloud
  mappings in `src/system_model.py`.

The implementation does not contain a server-index decision variable or a CPU
hard-capacity repair operator. Energy, delay, and freshness are evaluated with
the normalization rules in `src/metrics.py`. The reported QoE quantity is a
QoE-inspired utility proxy, fairness is the task-level Jain index of that
utility, and AoI is a single-epoch freshness proxy.

## Objective Contract

The revised methodology distinguishes three objective values:

```text
F0(X) = w_E E_norm + w_D D_norm + w_A A_norm
        + w_Q (1 - QoE) + w_F (1 - Fairness)

F_search(X, t) = F0(X) + lambda(t) (1 - CSR(X))

F_report(X) = F0(X) + 1.0 (1 - CSR(X))
```

For RDHO, `lambda(t) = lambda0 * (1 + 2t/Tmax)^alpha`. `F_search` is used only
for search decisions at the current iteration. Old and candidate populations
are re-evaluated at the same current scale. `F_report` is used for global-best
tracking, convergence curves, final tables, statistical tests, and
cross-experiment comparisons. The legacy CSV field `fitness` is always an
alias of `reported_fitness`.

Every raw result row records `base_fitness`, `search_fitness`,
`reported_fitness`, both penalty terms and scales, normalized objective
components, CSR, and NFE use, so the reported value can be recomputed directly.

## Repository Layout

```text
mec-rdho-offloading/
|-- configs/                   # Formal YAML experiment configurations
|-- docs/                      # Methodology specification and TDD plan
|-- experiments/               # Experiment runners and result analysis
|-- figures/                   # Manuscript-facing copies of original figures
|-- paper_tables/              # Generated paper-ready Markdown tables
|-- results/
|   |-- raw/                   # Main, ablation, and scalability raw records
|   |-- summary/               # Descriptive and inferential statistics
|   |-- figures/               # Generated source figures
|   |-- sensitivity/           # Sensitivity raw data, summaries, and figures
|   |-- manifests/             # Config hashes, seeds, versions, and commands
|   `-- legacy_before_methodology_revision/
|-- src/                       # MEC model, metrics, algorithms, and utilities
|-- tests/                     # Methodology and regression tests
|-- CITATION.cff
|-- LICENSE
|-- data_availability.md
|-- requirements.txt
`-- README.md
```

## Environment

The formal manifests record Python 3.12.7 and the exact installed dependency
versions. Install the declared dependencies with:

```bash
python -m pip install -r requirements.txt
```

Run the test suite before starting formal experiments:

```bash
python -m pytest -q
```

## Reproducing Experiments

Formal runners refuse to reuse existing output files unless `--force` is
provided. The immutable pre-revision result snapshot is verified before each
run.

```bash
python -m experiments.run_main_30 --force
python -m experiments.run_ablation_30 --force
python -m experiments.run_sensitivity --force
python -m experiments.run_scalability --force
```

Each runner writes a JSON manifest under `results/manifests/` containing the
command, configuration SHA-256 hash, git state, start/end timestamps, Python
and dependency versions, master seed policy, NFE cap, and output paths.
Generated summaries, tests, and figures can be rebuilt without rerunning the
optimizers:

```bash
python -m experiments.regenerate_analysis --force
```

`results/manifests/postrun_analysis_manifest.json` binds that analysis to the
committed analysis code and SHA-256 hashes of every input and output artifact.

## Experimental Protocol

The main benchmark uses 20 mobile devices, 4 edge servers, 2 cloud servers, 40
heterogeneous tasks, population size 50, 150 iterations, 30 paired scenarios,
and a common `max_evaluations=15050` cap. `scenario_seed` generates the shared
task and network instance; `algorithm_seed` controls optimizer randomness.
All algorithms in the same scenario therefore operate on identical MEC data.

Compared methods are RDHO, RIME, DBO, TLBO-HHO, CWTSSA, GA, PSO, DE, and
Greedy-ED. The stochastic algorithms use the same encoding, reporting
objective, paired scenarios, and NFE cap. Greedy-ED terminates after its
deterministic construction and therefore uses fewer evaluations.

Two-sided paired Wilcoxon signed-rank tests compare reported fitness by
`(scenario_id, replicate_id)`. Family-wise multiplicity is controlled with the
Holm procedure, and rank-biserial effect sizes are reported.

## Main Results

The revised 40-task, 30-scenario benchmark produced the following means:

| Algorithm | Reported fitness | QoE proxy | Task fairness | Soft CSR | Runtime (s) |
|---|---:|---:|---:|---:|---:|
| RDHO | 0.996956 | 0.324119 | 0.898544 | 0.692222 | 9.3726 |
| RIME | 1.460458 | 0.278139 | 0.818192 | 0.550000 | 9.6433 |
| DBO | 1.069660 | 0.314095 | 0.894576 | 0.661389 | 9.5430 |
| TLBO-HHO | 1.100124 | 0.313130 | 0.896350 | 0.628889 | 9.4637 |
| CWTSSA | 1.068496 | 0.316163 | 0.897088 | 0.654167 | 9.4473 |
| GA | 1.093163 | 0.310518 | 0.882083 | 0.653889 | 9.5202 |
| PSO | 1.466857 | 0.281577 | 0.830889 | 0.542500 | 9.4285 |
| DE | 1.032838 | 0.319635 | 0.899947 | 0.674167 | 9.6391 |
| Greedy-ED | 1.088138 | 0.321006 | 0.897016 | 0.606111 | 0.2167 |

RDHO has the lowest mean `F_report`, the highest mean QoE proxy, and the
highest mean CSR in this benchmark. DE has the highest mean task-level
fairness, while other methods lead individual physical metrics. RDHO is better
than each baseline in all 30 paired reported-fitness observations; every
comparison has two-sided raw `p=1.862645e-09` and Holm-adjusted
`p=1.490116e-08`.

Source files:

- `results/raw/main_30_raw_results.csv`
- `results/summary/main_30_summary_mean_std.csv`
- `results/summary/wilcoxon_fitness_results.csv`
- `results/manifests/main_30_manifest.json`

## Ablation Results

All core-component ablations disable local refinement. `RDHO-core` and
`RDHO-full` isolate the refinement contribution.

| Variant | Mean reported fitness | Difference from core |
|---|---:|---:|
| RDHO-core | 1.012511 | 0.000000 |
| RDHO-full | 0.996734 | -0.015778 |
| Without dual-source initialization | 1.120372 | +0.107861 |
| Without adaptive role allocation | 1.016804 | +0.004292 |
| Without elite preservation | 1.009914 | -0.002597 |
| Without dynamic penalty | 1.012491 | -0.000021 |

Paired two-sided Wilcoxon tests with Holm correction show a significant gain
for `RDHO-full` over `RDHO-core` (`adjusted p=1.490116e-08`) and a significant
loss when dual-source initialization is removed (`adjusted p=9.313226e-09`).
Adaptive roles, elite preservation, and dynamic penalty are not significant in
this 30-scenario ablation (`adjusted p=0.1215`, `0.3038`, and `0.9354`). The
slightly lower mean after removing elite preservation is therefore reported as
a non-significant numerical difference, not as evidence of improvement.

Source files:

- `results/raw/ablation_30_raw_results.csv`
- `results/summary/ablation_30_summary_mean_std.csv`
- `results/summary/ablation_wilcoxon_results.csv`
- `results/manifests/ablation_30_manifest.json`

## Sensitivity Results

Five objective-weight settings were evaluated over the same 30 paired
scenarios. Because each setting defines a different `F0`, fitness values across
weight settings are not interpreted as direct rankings. Across the settings,
mean QoE remains `0.323567-0.324119`, task-level fairness
`0.897965-0.899721`, and CSR `0.687222-0.693056`.

The penalty grid covers `lambda0 in {0.5, 1.0, 2.0}` and
`alpha in {1.0, 2.0, 3.0}`. The fixed-scale reported fitness remains
`0.994892-0.998355`, QoE `0.323787-0.324260`, fairness
`0.898310-0.898767`, and CSR `0.691389-0.694722`. These single-algorithm
experiments demonstrate RDHO's observed metric stability across the tested
settings; they do not establish that its ranking against every baseline is
preserved under each alternative setting.

Three original penalty-sensitivity wall-clock values crossed confirmed Windows
suspend intervals. Those exact rows were rerun with unchanged scenario,
algorithm, and configuration seeds. Every non-runtime field reproduced within
`1e-12`. The original raw file, executable repair command, input/output hashes,
and replacement timings are retained in `results/sensitivity/audit/` and
`results/manifests/sensitivity_runtime_repair.json`. The audit can be replayed
with `python -m experiments.repair_sensitivity_runtime --force`.

## Scalability Results

RDHO was evaluated on 20-100 tasks with 10 paired scenarios per size:

| Tasks | Reported fitness | Soft CSR | Runtime (s) |
|---:|---:|---:|---:|
| 20 | 0.898317 | 0.740000 | 4.6884 |
| 40 | 0.972353 | 0.705833 | 7.9866 |
| 60 | 0.974559 | 0.700556 | 11.8562 |
| 80 | 0.968657 | 0.707500 | 14.9493 |
| 100 | 0.997146 | 0.699000 | 19.4637 |

Runtime increases with task count, while reported fitness and CSR remain in a
relatively narrow range for these simulated offline scenarios.

## Figures and Data

Use the original PNG files under `figures/` for manuscript preparation. Their
generated source copies and file mapping are retained under `results/figures/`,
`results/sensitivity/figures/`, and `figures/README.md`.

No proprietary, confidential, human-subject, or external measurement data are
used. See `data_availability.md` for artefact provenance and limitations.

## Citation and License

A machine-readable citation is provided in `CITATION.cff`. The software is
released under the MIT License; see `LICENSE` and `NOTICE.md`.
