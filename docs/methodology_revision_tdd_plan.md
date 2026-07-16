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

## Phase 10: Hybrid-Fusion Ablation Extension

Write failing tests first for:

- the factory recognizes all seven approved ablation names;
- `RDHO-core w/o hybrid RIME-DBO fusion` sets `hybrid_update=False`;
- the no-hybrid variant follows the existing non-hybrid update path;
- every core variant has `local_refinement=False`;
- removing one component does not change any unrelated component flag;
- ablation configuration and analysis reject missing or duplicate variants.

Then implement the registry/configuration changes and run a small ablation
smoke test. Do not run the formal 30-scenario experiment until the tests pass.

## Phase 11: Statistical Analysis Extension

Write failing tests first for:

- Friedman input is aligned by `scenario_id + replicate_id` rather than row
  order;
- duplicate or incomplete pairing fails explicitly;
- the primary algorithm set excludes `Greedy-ED`;
- Holm correction is applied only within the seven primary comparisons;
- rank-biserial effects use the signed paired differences;
- wins/ties/losses honor the documented tolerance;
- paired bootstrap confidence intervals are deterministic under a dedicated
  statistics seed and bracket the observed mean paired difference;
- the supplementary Greedy comparison is labelled as unequal-budget and is
  stored separately from primary inference.

Then implement a reusable statistics module and generate independent main,
ablation, and weight-sensitivity statistical tables.

## Phase 12: Checkpointed Weight-Sensitivity Extension

Write failing tests first for:

- all five weight settings run the approved eight stochastic algorithms;
- Greedy is absent from the weight-sensitivity population ranking;
- scenarios and `scenario_seed` values are identical across algorithms within
  each setting;
- algorithm seeds are independent and deterministically derived;
- checkpoint rows are written atomically and uniquely keyed;
- resume skips only complete matching rows;
- resume rejects config, code-contract, seed-policy, algorithm-list, or schema
  mismatches;
- within-setting ranks are computed independently for every setting;
- no analysis aggregates absolute fitness across different weight settings.

Then implement the runner, checkpoint contract, summary, ranks, tests, paper
table, and rank figure. The official run starts with `--force`; interruption
recovery uses `--resume` with the unchanged contract.

## Phase 13: Main-Result Audit and Artifact Validator

Write failing tests first for:

- duplicate main-result keys are detected;
- incomplete scenario sets are detected;
- scenario-seed mismatch and stochastic algorithm-seed collisions are
  detected;
- `fitness`, `reported_fitness`, `base_fitness`, and report penalty are
  numerically recomputed and verified;
- the audit reports the exact observed wins/ties/losses for every baseline;
- the fast validator checks required files, CSV schemas, row uniqueness,
  manifest hashes, and primary statistical separation without launching an
  optimizer.

Then implement `docs/main_result_audit.md` generation and
`python -m experiments.validate_artifacts`.

## Phase 14: Continuous Integration

Add `.github/workflows/ci.yml` only after validator tests pass. Test the same
commands locally that CI will run:

```text
python -m pytest -q
python -m compileall -q src experiments tests
python -m experiments.validate_artifacts
git diff --check
```

CI must not invoke any formal experiment runner.

## Phase 15: Formal Runs and Manuscript Package

After all implementation tests pass:

- run the seven-variant ablation with `--force`;
- run S1--S5 for the eight stochastic algorithms with `--force`, using
  contract-verified `--resume` only after a genuine interruption;
- generate raw, summary, ranking, inferential, paper-table, figure, and
  manifest artifacts;
- regenerate the main statistical tables and main-result audit;
- inspect hybrid-fusion significance and RDHO rank under every weight setting
  before drafting any conclusion;
- load the academic-writing source manifest required by the writing workflow;
- create `docs/manuscript_revision_package.md` from the finalized artifacts.

No seed, setting, row, or algorithm may be removed or changed in response to
the observed ranking.

## Phase 16: Final Verification and Draft PR Update

Run the four required final commands from Phase 14, inspect generated tables
and figures, commit coherent changes, and push the existing branch. Confirm
GitHub Actions checks pass on Draft PR #4. Do not merge the PR and do not mark
it ready for review.
