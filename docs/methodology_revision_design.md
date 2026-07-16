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

## 11. Pre-Submission Extension Contract

This section records the approved pre-submission extension to the methodology
revision. It supplements, and does not replace, Sections 1--10.

### 11.1 Core Hybrid-Mechanism Ablation

The formal ablation must contain exactly these seven variants:

- `RDHO-core`;
- `RDHO-core w/o hybrid RIME-DBO fusion`;
- `RDHO-core w/o dual-source initialization`;
- `RDHO-core w/o adaptive role allocation`;
- `RDHO-core w/o elite preservation`;
- `RDHO-core w/o dynamic penalty`;
- `RDHO-full`.

The hybrid-fusion ablation must set the existing `hybrid_update` option to
`False`. It therefore uses RDHO's predefined non-hybrid update path and must
not introduce an intentionally weak substitute operator. Every `RDHO-core`
variant, including the four other component removals, must use
`local_refinement=False`; only `RDHO-full` enables local refinement.

All variants must use identical scenario seeds, the same algorithm-seed rule,
the same maximum NFE, and the same `F_report` definition. The formal outputs
must include raw rows, mean and standard-deviation summaries, a Friedman
omnibus test, Holm-corrected paired Wilcoxon comparisons against `RDHO-core`,
rank-biserial effects, wins/ties/losses, paired-difference bootstrap confidence
intervals, a paper table, a figure, and provenance manifests.

### 11.2 Cross-Algorithm Weight Sensitivity

Each weight setting `S1`--`S5` must run these eight stochastic population
algorithms:

- `RDHO`, `RIME`, `DBO`, `TLBO-HHO`, `CWTSSA`, `GA`, `PSO`, and `DE`.

Within a setting, all algorithms must share scenarios, maximum NFE, pairing
rules, and `F_report`. Results must report mean plus or minus standard
deviation, within-setting ranks, a Friedman omnibus test, and Holm-corrected
paired comparisons of RDHO with the seven stochastic baselines. The ranking
figure must show the `weight setting x algorithm` relationship. Absolute
fitness values must not be interpreted across different weight settings
because each setting defines a different scalar objective.

`Greedy-ED` is excluded from the weight-sensitivity omnibus and ranking study.

### 11.3 Two-Level Inferential Statistics

The approved primary equal-budget inference includes only the eight stochastic
algorithms listed in Section 11.2. It must provide:

- a Friedman omnibus test;
- RDHO-versus-baseline paired Wilcoxon tests;
- Holm correction across the seven primary pairwise tests;
- rank-biserial effect sizes;
- wins, ties, and losses using an explicitly documented numerical tolerance;
- deterministic paired-difference 95% bootstrap confidence intervals.

Every omnibus and paired test must use the composite key
`scenario_id + replicate_id`. Row order must never define a pair.

`Greedy-ED` remains in the main raw data, descriptive tables, figures, and
runtime comparison. An RDHO-versus-Greedy paired Wilcoxon test may be reported
only as a supplementary effectiveness-versus-cost comparison. Its output and
manuscript interpretation must state that the scenarios and `F_report` are
shared but the computational budgets differ. It must not be mixed into the
equal-NFE family of significance claims or its Holm correction.

### 11.4 Main-Result Audit

The claim that RDHO outperforms every baseline in all 30 scenarios must be
audited directly from the raw main results. The audit must verify:

- uniqueness of `scenario_id + replicate_id + algorithm`;
- complete and identical paired scenario keys across algorithms;
- one common `scenario_seed` per paired scenario;
- distinct algorithm seeds for stochastic algorithms within a scenario;
- the expected algorithm counts and row counts;
- `fitness == reported_fitness`;
- recomputation of `base_fitness`, `report_penalty`, and `reported_fitness`
  from their decomposed columns;
- the actual per-baseline wins, ties, and losses without changing seeds.

The human-readable audit must be committed as `docs/main_result_audit.md`.

### 11.5 Checkpointed Formal Execution

The weight-sensitivity extension is long-running and must support safe
checkpoint/resume execution. A fresh formal run uses `--force`, creates a run
contract containing the config hash, code identity, seed policy, algorithms,
and output schema, and writes completed rows atomically. A resumed run may
reuse a row only when that contract matches exactly and its composite
experiment key is unique. A mismatch must fail closed instead of silently
mixing experiments.

Checkpointing must not alter experiment seeds, optimization behavior, or the
final result order. Finalized artifacts and their hashes are recorded in the
formal manifest.

### 11.6 Continuous Integration and Artifact Validation

The repository must provide `.github/workflows/ci.yml` for `push` and
`pull_request`. CI installs `requirements.txt`, runs `pytest`, compiles
`src`, `experiments`, and `tests`, runs `git diff --check`, and executes a fast
artifact validator. CI must validate committed artifacts and metadata without
rerunning the formal experiments.

### 11.7 Manuscript Revision Package

`docs/manuscript_revision_package.md` must be generated only after the formal
results are finalized. It must state the equations implemented by the code,
the model boundaries in Section 1, paper-ready English descriptions, exact
replacement tables and figures, and conservative conclusions supported by the
new statistics. It must explicitly remove unsupported claims about component
significance, device-level fairness, final dynamic-penalized fitness, and the
obsolete sigmoid/piecewise/completion QoE construction.
