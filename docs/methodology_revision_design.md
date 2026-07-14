# Methodology Revision Design Specification

This document fixes the experimental methodology contract for the SCI
methodology revision branch. It is intentionally conservative: the revised
implementation must remain compatible with the current repository model while
removing ambiguity in objective reporting, dynamic penalties, evaluation
budgets, random seeds, and baselines.

## 1. Scope and Non-Negotiable Compatibility

The revised code must preserve the repository's actual implemented system
model:

- Each task decision remains `X_i = [m_i, r_i]`.
- `m_i` selects only the execution mode: local, edge, or cloud.
- `r_i` is the continuous resource ratio clipped to the current range.
- Edge and cloud paths remain deterministic through the existing nearest
  edge/cloud routing functions.
- The current normalization definitions for energy, delay, and AoI remain in
  force.
- The revision must not introduce unsupported server-index decision variables.
- The revision must not introduce a fake CPU hard-capacity repair step that is
  not represented in the current model.

The purpose of this branch is to make the implemented experiments internally
consistent and reproducible, not to change the MEC model into a different
problem.

## 2. Objective Definitions

All optimization and reporting code must distinguish three objective layers.

### 2.1 Base Objective: `F0`

`F0` is the five-indicator objective without a penalty term:

```text
F0(X) =
  w_E * energy_norm(X)
+ w_D * delay_norm(X)
+ w_A * aoi_norm(X)
+ w_Q * (1 - qoe(X))
+ w_F * (1 - fairness(X))
```

The weights are read from configuration and must preserve the existing
normalization conventions. `F0` is recorded for decomposition and audit.

### 2.2 Search Objective: `F_search(X, t)`

`F_search` is used only for within-iteration search comparisons:

```text
F_search(X, t) = F0(X) + lambda(t) * (1 - csr(X))
```

For RDHO with dynamic penalty enabled:

```text
lambda(t) = lambda0 * (1 + 2t / Tmax)^alpha
```

For algorithms without dynamic penalty, `lambda(t)` is constant. The search
objective may change across iterations and must not be used as the final
cross-algorithm table value.

### 2.3 Reported Objective: `F_report(X)`

`F_report` is the only fitness value used in final tables, statistical tests,
cross-experiment comparison, and the legacy `fitness` output column:

```text
F_report(X) = F0(X) + 1.0 * (1 - csr(X))
```

The legacy field named `fitness` must always be an alias of
`reported_fitness`. It must never silently switch between `F_search` and
`F_report`.

### 2.4 Required Metric Fields

All raw result rows should include the following fields when applicable:

- `fitness`: alias of `reported_fitness`.
- `reported_fitness`: `F_report`.
- `base_fitness`: `F0`.
- `search_fitness`: `F_search` at the evaluation's current search penalty.
- `penalty_scale`: the scale used for `search_fitness`.
- `report_penalty_scale`: fixed at `1.0`.
- `search_penalty`: `penalty_scale * (1 - csr)`.
- `report_penalty`: `1.0 * (1 - csr)`.
- `energy_norm`, `delay_norm`, `aoi_norm`.
- `qoe`, `fairness`, `csr`.
- existing physical summaries: `energy`, `delay`, `aoi`, and `runtime`.

Summary tables may keep the compact columns, but raw CSV files must retain the
decomposition needed to audit the reported value.

## 3. Dynamic Penalty Consistency

Within each iteration, old population members and candidate population members
must be compared under the same current search penalty scale.

Required behavior:

- At iteration `t`, compute `lambda(t)`.
- Re-evaluate the old population under `lambda(t)`.
- Evaluate candidate solutions under `lambda(t)`.
- Accept candidates according to `F_search` values computed at the same scale.
- Maintain the cross-iteration/global best solution using `F_report`.
- Store the main convergence curve using `reported_fitness`.

This avoids comparing a candidate evaluated under a larger penalty with an old
population member evaluated under a smaller historical penalty.

## 4. NFE Budget

All algorithms must obey the same `max_evaluations` budget. The budget is
measured as number of calls to the objective evaluator.

The NFE counter must include:

- initialization population evaluations;
- old population re-evaluation under the current penalty;
- candidate population evaluations;
- greedy seed construction evaluations;
- local refinement evaluations;
- all internal evaluations used by GA, PSO, DE, or other baselines;
- final reporting evaluation when it calls the evaluator.

The evaluation counter must be a shared object or equivalent accounting
mechanism passed into all objective evaluations. No algorithm may bypass it.

If an evaluation budget is exhausted, an algorithm must stop cleanly and return
the best reported solution found so far. It must not continue evaluating
solutions off-budget.

## 5. Local Refinement Policy

Local refinement is an explicit algorithm option independent of the other RDHO
components.

Required behavior:

- Removing one RDHO component must not automatically disable local refinement.
- Core component ablations must run with local refinement disabled for every
  variant.
- Add an explicit `RDHO-core` versus `RDHO-full` comparison:
  - `RDHO-core`: all core RDHO components enabled, local refinement disabled.
  - `RDHO-full`: core RDHO plus local refinement enabled.
- The local refinement contribution must be reported honestly, even if it is
  the main source of improvement.

## 6. Randomness and Paired Scenarios

Randomness is split into two layers:

- `scenario_seed`: generates the MEC scenario, tasks, and network parameters.
- `algorithm_seed`: controls algorithm stochastic updates.

For the same `scenario_id` and `replicate_id`, every algorithm must receive the
same generated system. Statistical tests must therefore be paired by scenario.

Recommended deterministic derivation:

```text
scenario_seed = derive_seed(master_seed, "scenario", scenario_id, replicate_id)
algorithm_seed = derive_seed(master_seed, "algorithm", algorithm_name,
                             scenario_id, replicate_id)
```

The exact derivation may use the repository's existing deterministic seed
helper, but the two seed roles must be exposed in raw results.

## 7. Standard Baselines

Add GA, PSO, and DE as standard baselines.

Baseline requirements:

- same decision encoding `X_i = [m_i, r_i]`;
- same clipping/rounding rules;
- same `F_search` and `F_report` definitions;
- same `max_evaluations`;
- same scenario pairing;
- no data-specific tuning to force RDHO to win.

Baseline hyperparameters should use conservative standard defaults and be
documented in configuration or code comments.

## 8. Legacy Results and Fresh Runs

Before revised experiments are generated, the old result artifacts must be
preserved under:

```text
results/legacy_before_methodology_revision/
```

Revised formal experiments must not silently reuse old CSV files. Official run
scripts must support `--force`, and final revised results must be generated
with `--force`.

Every formal run must write a manifest containing:

- git commit hash;
- branch name;
- dirty-worktree flag;
- configuration path and configuration hash;
- command line;
- start/end timestamps;
- Python version and platform;
- dependency versions where available;
- `master_seed`, `scenario_seed`, and `algorithm_seed` policy;
- `max_evaluations`;
- result output paths.

## 9. Reporting Integrity

The final results must be reported as generated. The revision must not filter,
hide, relabel, or modify results to preserve an expected RDHO ranking.

Required interpretation rules:

- If RDHO is not ranked first, report that result.
- If a component has no significant contribution, report that result.
- If local refinement dominates the gain, report that result.
- If GA, PSO, or DE performs competitively or better, report that result.

## 10. Manuscript Alignment Notes

The manuscript should be updated after the code and revised results settle.
The likely terminology changes are:

- `fitness` in tables means `F_report`.
- Dynamic penalty is described as a search mechanism, not the reported table
  objective.
- QoE should be described as a QoE-inspired utility or proxy unless external
  validation data are added.
- Current fairness is task-level QoE fairness unless a separate user-level
  aggregation is implemented.
- Current AoI is a single-epoch freshness proxy or peak-AoI approximation.

These manuscript notes do not change the code contract above; they prevent the
paper from overclaiming beyond the implemented model.

