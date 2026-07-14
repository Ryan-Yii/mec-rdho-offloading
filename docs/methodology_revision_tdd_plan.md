# Methodology Revision TDD Implementation Plan

This plan implements the methodology revision through failing tests first,
then code changes, then verification. The implementation is expected to remain
on branch `sci-experiment-methodology-revision`.

## Phase 0: Design Commit

Status target for this commit:

- Add formal design specification.
- Add this TDD plan.
- Run existing tests to confirm the documentation-only commit does not alter
  behavior.
- Commit the design and plan before implementation.

Self-check:

- The design preserves the current `X_i = [m_i, r_i]` model.
- The design does not introduce unsupported server selection.
- The design does not introduce CPU hard-capacity repair.
- The design fixes ambiguity between `F0`, `F_search`, and `F_report`.
- The plan requires failing tests before implementation.

## Phase 1: Objective Decomposition Tests

Write failing tests for:

- `evaluate_solution` returns `base_fitness`, `reported_fitness`,
  `search_fitness`, `penalty_scale`, `search_penalty`, and `report_penalty`.
- legacy `metrics.fitness == metrics.reported_fitness`.
- `reported_fitness == base_fitness + 1.0 * (1 - csr)`.
- `search_fitness == base_fitness + penalty_scale * (1 - csr)`.
- changing search `penalty_scale` changes only `search_fitness` and
  `search_penalty`, not `reported_fitness`.
- `energy_norm`, `delay_norm`, and `aoi_norm` are exposed for audit.

Then implement:

- extend the `Metrics` dataclass;
- update `evaluate_solution`;
- preserve existing physical metric fields;
- update tests that assume the old dataclass shape.

Verification:

- targeted metrics tests;
- full pytest suite.

## Phase 2: Dynamic Penalty Search Consistency Tests

Write failing tests for:

- old population and candidate population are both evaluated at the same
  current penalty scale in a greedy acceptance step;
- the convergence history stores `reported_fitness`, not iteration-dependent
  `search_fitness`;
- cross-iteration best tracking is based on `reported_fitness`;
- `F_search` remains available for within-iteration acceptance.

Then implement:

- refactor optimizer evaluation into explicit reported/search evaluation
  paths;
- re-evaluate old population each iteration at the current search penalty;
- accept candidates according to same-scale search values;
- store reported convergence values.

Verification:

- targeted optimizer tests;
- existing experiment pipeline tests.

## Phase 3: Unified NFE Budget Tests

Write failing tests for:

- initialization population evaluations increase NFE;
- per-iteration old population re-evaluation increases NFE;
- candidate evaluation increases NFE;
- greedy seed construction consumes NFE;
- local refinement consumes NFE;
- all algorithms stop at or before `max_evaluations`;
- returned rows include `nfe_used` and `max_evaluations`.

Then implement:

- introduce an evaluation budget/counter object;
- route all `evaluate_solution` calls through the counter where algorithms are
  running;
- add `max_evaluations` to configs and run paths;
- stop algorithms cleanly when the budget is exhausted.

Verification:

- NFE-specific unit tests;
- short experiment smoke test with a small budget.

## Phase 4: Local Refinement Ablation Tests

Write failing tests for:

- local refinement is controlled by an explicit `local_refinement` flag;
- disabling any single RDHO core component does not implicitly disable local
  refinement;
- ablation factory can create `RDHO-core` and `RDHO-full`;
- core-component ablation variants can be run with local refinement disabled
  uniformly.

Then implement:

- add the explicit RDHO local refinement flag;
- update variant factory names and configuration;
- ensure ablation runners use the new design.

Verification:

- factory tests;
- ablation smoke test.

## Phase 5: Paired Scenario Seed Tests

Write failing tests for:

- same `scenario_id` and `replicate_id` produce identical systems for all
  algorithms;
- different algorithms receive different `algorithm_seed` values;
- raw result rows contain `scenario_id`, `replicate_id`, `scenario_seed`, and
  `algorithm_seed`;
- paired statistical tables group by scenario/replicate, not by accidental row
  order.

Then implement:

- seed policy helpers;
- experiment runner updates;
- raw CSV column updates;
- statistical pairing update.

Verification:

- seed tests;
- Wilcoxon pairing test.

## Phase 6: GA, PSO, and DE Baseline Tests

Write failing tests for:

- algorithm factory supports `GA`, `PSO`, and `DE`;
- each baseline uses the same solution shape and clipping rules;
- each baseline consumes the same evaluator and NFE budget;
- each baseline returns metrics with `fitness == reported_fitness`;
- Greedy factory remains compatible.

Then implement:

- add GA, PSO, and DE classes under `src/algorithms/`;
- update algorithm registry;
- add conservative default hyperparameters;
- avoid dataset-specific tuning.

Verification:

- factory tests;
- baseline smoke tests under a small budget;
- full test suite.

## Phase 7: Legacy Backup, Force Runs, and Manifest Tests

Write failing tests for:

- old result files can be copied to
  `results/legacy_before_methodology_revision/`;
- run scripts do not reuse old CSV files when `--force` is set;
- formal run writes a manifest;
- manifest records git hash, branch, dirty state, config hash, command, seeds,
  environment, max evaluations, and output paths.

Then implement:

- backup helper;
- `--force` CLI handling;
- manifest writer;
- run script integration.

Verification:

- manifest tests;
- dry-run or small forced run.

## Phase 8: Revised Experiment Execution

After all tests pass:

- back up old results;
- run revised formal experiments with `--force`;
- regenerate summaries, paper tables, and figures from revised CSV files;
- record manifests for each formal run;
- run final validation and inspect result consistency.

Integrity rule:

- Keep all generated outcomes. Do not tune, filter, or hide results if RDHO is
  not first or if local refinement explains most of the gain.

## Phase 9: Branch Push and Pull Request

After implementation and verification:

- commit implementation changes in coherent commits;
- push `sci-experiment-methodology-revision`;
- create an unmerged PR against `main`;
- summarize test evidence and any result changes honestly in the PR body.

