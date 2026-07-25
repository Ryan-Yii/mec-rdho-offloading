# Controlled RDHO Population Evidence Design

## Scope and provenance

This is an additive experiment on `research/rdho-controlled-evidence`, created from `cf499f2d1a0f37859cc045cf3c902815b81927f1`.
It does not regenerate, replace, or consume any existing `results/v2/` result file.
The V2 generator, decoder, deterministic capacity repair, hard-feasibility validation, weights, and fixed reporting fitness are reused unchanged.
The question is narrow: after equalising the initial population, physical evaluation path, and total number of objective evaluations, does the implemented RDHO population update outperform the implemented RIME and DBO updates in the 30 fixed V2 scenarios?
No result is assumed and parameters are not tuned against these scenarios.

## Pre-implementation audit

| Topic | Audited implementation | Controlled consequence |
|---|---|---|
| Equal-NFE runner | `experiments/run_controlled_30.py` gives five population algorithms 75 iterations and documents `50 * (1 + 75) + 1 = 3801`. | Its arithmetic is useful, but it does not enforce a shared hard budget manager. |
| Common initialisation | `experiments.experiment_core.common_initial_population()` makes a 50-by-40-by-2 uniform float64 array using `derive_seed(seed, "common-initialisation")`. | Reuse the generator once per scenario; hash its exact bytes before copying it to every method. |
| Common refinement | `MetaheuristicOptimizer.coordinate_refine()` visits tasks in ascending order and tests 5 node coordinates times 5 CPU coordinates. | Reuse this deterministic candidate order through the new shared budget manager; 40 tasks consume exactly `40 * 5 * 5 = 1000` NFE. |
| RDHO-core and RDHO-full | Core disables `local_refinement`; full retains it. The old factory gives core a common population, but full still uses RDHO dual-source initialisation. | Neither old label is a controlled method. New names identify the controlled conditions. |
| RDHO greedy seed | `RDHO.initialize_population()` builds a greedy seed and three perturbed descendants whenever dual-source initialisation is enabled; its evaluation calls increment NFE. | Controlled RDHO receives the shared population and uses `dual_source_initialization=False`; no greedy or perturbed seed is made. |
| Population initialisation | Default RDHO concatenates half normal and half uniform samples; RIME is normal and DBO uniform. | All controlled methods bypass their initialiser and receive copied common uniform populations. |
| Candidate counts | RIME, DBO, and RDHO each return one 50-member candidate population per generation. RDHO elite copies are still evaluated by the old base greedy acceptance. | Every complete controlled generation evaluates 50 candidates; a partial generation evaluates its deterministic leading subset only. |
| NFE semantics | `MetaheuristicOptimizer.evaluate_metrics()` increments once per `evaluate_solution()` call. Existing metrics are re-scored algebraically for lambda changes, candidate populations and the final search check are evaluated. | The new manager counts every evaluator call after the shared decoder and repair, separated by initial, candidate, refinement, and final stages. |
| Parent/candidate lambda | The base optimizer derives both parent and candidate search fitness at the same `penalty_scale(iteration)`. | Retain same-lambda comparison; maintain the reporting incumbent separately. |
| Fixed reporting incumbent | The base optimizer tracks reporting fitness independent of search fitness; reporting uses penalty scale 1.0. | The controlled runner does the same and counts one final reporting re-evaluation because the current optimizer counts that final call. |
| Decoder and repair | `evaluate_solution()` calls `decode_and_repair()` and validates legal nodes, CPU limits, aggregate capacity, and one assignment per task. | All three controlled methods use exactly this path, with no method-specific evaluator or cache. |

The old common-control result is not sufficient evidence for this question because it compares `RDHO-full` with RDHO-specific initialisation and local refinement against separately constructed RIME/DBO conditions, without exact shared total-NFE accounting.

## Experiment A: population-stage control

Methods are `RDHO-population-controlled`, `RIME-population-controlled`, and `DBO-population-controlled`.
They share initialisation, clipping, legal-node encoding, physical CPU decode, repair, evaluator, fixed reporting objective, and a hard total budget of 3801 NFE.
RDHO retains role-conditioned hybrid RIME/DBO movements, adaptive roles, elite preservation, greedy selection, dynamic penalty, and independent reporting incumbent.
It disables dual-source initialisation, greedy and perturbed seeds, coordinate refinement, and post-processing.
RIME and DBO retain their current `step()` implementations without added enhancement; no method refines coordinates.
The exact budget is 50 initial calls, 75 complete candidate populations of 50, and one final reporting call: `50 + 75*50 + 1 = 3801`.

## Experiment B: common-pipeline control

Methods are `RDHO-common-pipeline`, `RIME-common-pipeline`, and `DBO-common-pipeline`.
They have all Experiment A controls plus the same deterministic coordinate refinement candidate order.
RDHO has no RDHO-specific local refinement; common refinement is the only post-processing for every method.
The exact 10232-NFE budget comprises 1000 refinement calls and 9232 population-stage calls.
Population-stage accounting is 50 initial calls, 9181 candidates (183 full 50-candidate generations and one 31-candidate generation), and one final reporting call.
Thus `population_nfe=9232`, `refinement_nfe=1000`, and `total_nfe=10232` for all methods.

## Shared population, random streams, and evaluation control

The fixed V2 scenarios are seeds `20260701` through `20260730`.
For each scenario, create one system and one common initial population, then pass independent copies to all methods.
Each copied array must match the SHA-256 hash of the source population or execution fails.
Update streams are deterministic and method-specific: `derive_seed(scenario_seed, experiment_name + ":" + method_name)`.
No method receives a performance-dependent population, a distinct greedy seed, or a cache advantage.

`src/experiments/evaluation_budget.py` is the only evaluator entry point for controlled runs.
It clips, calls the shared evaluator (and therefore shared decoder and repair), increments one NFE, records the stage, and rejects calls over the fixed budget.
Search fitness from cached metrics is algebraic and has no objective call, so it is not miscounted as NFE.
The runner asserts exact totals and audits reassignments, repair exceptions, hard feasibility, legal nodes, CPU bounds, capacity, and assignment count for every returned solution.

## Endpoints, statistics, and files

The sole primary endpoint is fixed reporting fitness, where lower is better.
Secondary outputs are base objective, energy, delay, AoI, QoE, active-user fairness, soft CSR, feasibility, capacity utilisation, runtime, NFE components, and repair diagnostics.
Each experiment pairs RDHO against RIME and DBO over all 30 scenarios using `DeltaF = F_RDHO - F_baseline`; negative differences favour RDHO.
Each comparison reports mean plus sample standard deviation, median, median paired difference, two-sided paired Wilcoxon p-value, Holm adjustment over the two experiment-local comparisons, signed rank-biserial correlation, wins/ties/losses, and a deterministic 10,000-resample percentile bootstrap 95% confidence interval for median difference.
Non-significance is never claimed as superiority.

New evidence is written only under `results/raw/`, `results/summary/`, `results/statistics/`, `results/audit/`, `paper_tables/`, and `figures/analysis/`.
No `results/v2/` or manuscript path is written.
The runner writes raw data before derived files, refuses overwrite unless requested, emits a SHA-256 manifest, and verifies the existing V2 result files remain byte-identical.
Tests cover shared hashes, exact budgets, refinement isolation and identity, the shared physical evaluation path, feasibility, reporting-fitness definition, determinism, and output separation.
The full 30-scenario run follows a two-seed smoke run.

The conclusion applies only to the implemented methods and the fixed synthetic V2 scenarios.
Shared initialisation intentionally removes an initialisation advantage; dynamic penalty remains a population-stage RDHO feature in Experiment A; runtime is descriptive even under equal NFE.
