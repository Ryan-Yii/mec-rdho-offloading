# ReproAudit v0.1.0 MEC Acceptance Case Design

## 1. Purpose

This design defines a reproducible, structured-consistency acceptance case for the current MEC main experiment. It tests whether the released ReproAudit v0.1.0 can audit configuration, raw runs, official summary statistics, and repository-native claims without changing MEC source assets, and whether controlled variants trigger the intended rules.

This does not prove that the simulation is scientifically correct, that the paper is fully reproducible, or that an algorithm is universally superior.

## 2. Non-goals and Boundaries

This commit contains design only. It adds no exporter, oracle, injector, runner, test, case package, report, downloaded wheel, or generated data. It does not execute an MEC experiment runner or modify files below `results/`, `paper_tables/`, `configs/`, or `src/`.

Future implementation is limited to an MEC case adapter, independent oracle, fault injector, acceptance runner, documentation, and tests. It excludes ReproAudit-core changes, PDF or Word parsing, OCR, LLM or agent features, web UI, databases, automatic repair, new MEC algorithms, new experiments, and manuscript rewriting.

## 3. Repository and Version Baseline

### Local Investigation Context

The safe existing base clone was `/Users/ryan_yi/Documents/MEC_paper_collection_2026-07-24/_review_current_main`. Its origin is `https://github.com/Ryan-Yii/mec-rdho-offloading.git`; it was clean and was not switched or edited. The design worktree is `/Users/ryan_yi/Documents/mec-rdho-reproaudit-design`, on `docs/reproaudit-mec-acceptance-design`, created from remote `main` commit `b8abb436f215a9b2f4d646cf5fc0cf048174b68d`.

Future committed case artifacts must not contain either local path, a local username, a temporary directory, or machine-specific timestamps.

| Item | Verified value |
| --- | --- |
| MEC remote/default branch | `Ryan-Yii/mec-rdho-offloading` / `main` |
| MEC design baseline | `b8abb436f215a9b2f4d646cf5fc0cf048174b68d` |
| ReproAudit remote | `Ryan-Yii/reproaudit` |
| ReproAudit tag/commit | `v0.1.0` / `1b6a9eb57529e4d92886fa7aa06dabbba5316105` |
| ReproAudit release | `https://github.com/Ryan-Yii/reproaudit/releases/tag/v0.1.0` |
| Release state | Published, non-draft, non-prerelease |
| Official wheel | `reproaudit-0.1.0-py3-none-any.whl`, SHA-256 `dfab966ed90b98620d0c6b4fbeb80b31b44879493e092d4ef9314c9812998b5c` |
| Other release assets | sdist and `SHA256SUMS` present |

The current README identifies `results/v2` as current evidence and explicitly marks `results/archive/v1.0-paper` as provenance-only. Source precedence is:

```text
configs/main_40tasks.yaml
  > results/v2/raw/main_30_raw_results.csv
  > results/v2/summary/main_30_summary_mean_std.csv
  > README.md current V2 table and stated conclusion
  > paper_tables/v2 mirror
  > archive/v1.0-paper and all other experiment families
```

`experiments/run_main_30.py` loads the selected configuration and writes the selected raw, then summary, files. `experiments/experiment_core.py` computes the summary from main raw rows. These scripts are provenance evidence only and must not run for this case.

## 4. MEC Source Inventory

The repository separates configuration in `configs/`, runners in `experiments/`, model and algorithms in `src/`, current V2 evidence in `results/v2/`, later strict control evidence in `results/raw`, `results/summary`, and `results/statistics`, manuscript table mirrors in `paper_tables/v2/`, historical material in `*/archive/v1.0-paper/`, and tests in `tests/`. Current CI is Python 3.11 `pytest -q` on pushes and pull requests to `main`.

| Role | Repository-relative path | SHA-256 | Size / shape | Decision |
| --- | --- | --- | --- | --- |
| Canonical config | `configs/main_40tasks.yaml` | `d99ba17554e67f6d1ad9aef9bbec9a4470b5b6bde8c77309ed82951e159fe8c4` | 351 bytes | 20 devices, 4 edge, 2 cloud, 40 tasks, 30 runs, population 50, 150 iterations |
| Raw source | `results/v2/raw/main_30_raw_results.csv` | `f885d8dd171e277d351ef268449f0aa5179a26f6e9c66256d4596d37a360c639` | 51,525 bytes; 180 x 21 | Current canonical main source |
| Official summary | `results/v2/summary/main_30_summary_mean_std.csv` | `751a936d794c642f640d6d9ae0309b153d728932c27e077c5188861feafa28d6` | 6,734 bytes; 6 x 55 | Existing summary to audit, never regenerate first |
| Paper-table mirror | `paper_tables/v2/main_30_summary_mean_std.csv` | `751a936d794c642f640d6d9ae0309b153d728932c27e077c5188861feafa28d6` | 6,734 bytes; 6 x 55 | Byte-identical mirror, not a second authority |
| Structured claim source | `README.md` | `519b055257d1525806d0fbb3edf72f58848ee6ecc96112544158e93eb8f01cb6` | Markdown | Current V2 configuration prose, result table, and bounded conclusion |
| Protocol provenance | `docs/experiment_protocol_v2.md` | `c1db229a76a50c6269e1417a521135056cfbdfb29556d1c368d3e96a60a1fa42` | Markdown | Defines paired seeds and raw-row contents |

Raw columns are exactly:

```text
run_id, seed, algorithm, fitness, base_objective, penalty, search_fitness,
energy, delay, aoi, qoe, fairness, csr, hard_feasible,
capacity_utilisation_mean, capacity_utilisation_max, assignment_unique,
runtime, nfe, pre_refinement_fitness, local_refinement_gain
```

Official summary has `algorithm`, then each numeric metric's `_mean`, `_std`, and formatted metric string. Its 55 columns include `fitness_mean`, `fitness_std`, `csr_mean`, and `csr_std`.

The six exact source algorithms in order are `RDHO`, `RIME`, `DBO`, `TLBO-HHO`, `CWTSSA`, and `Greedy-ED`; every one has 30 rows. `run_id` is 1--30 and `seed` is 20260701--20260730. Each seed/run ID is shared by all algorithms. The protocol defines it as a paired generated scenario with separately derived deterministic algorithm RNG streams. The ReproAudit key is therefore `(seed, algorithm)`; `run_id` is retained as opaque trace metadata.

Source raw has no status column. All 180 rows contain finite `fitness` and `csr`, and the README reports hard-feasibility rate 1.0. The adapter maps a row to `success` only after validating these selected fields are present and finite. It stops conversion for absent/nonfinite values; it never infers a failure from result quality.

## 5. Source-of-Truth Decisions

Selected metrics are `fitness` (minimize; primary) and `csr` (maximize; secondary). Fitness is the fixed reporting objective and CSR is the soft constraint-satisfaction ratio. Other raw columns are excluded because v0.1 does not need them for this case; they are recorded in the manifest, not silently discarded.

The authoritative official summary remains `results/v2/summary/main_30_summary_mean_std.csv`. Its selected mean/std fields are copied to the adapted summary. Required `median` is calculated from selected raw values and `n` is the valid-success count. This structural completion does not overwrite, replace, or relabel the official mean/std.

The README current V2 table has rounded fitness and CSR means for all six algorithms. It is the reported-result claim source. It calls source `RDHO` "RDHO-full". The sole explicit label normalization is:

```text
README "RDHO-full" -> canonical raw/config/summary "RDHO"
```

No other name changes. README's sentence that RDHO-full beats each configured main baseline in all 30 paired scenarios is a repository-native fitness best-algorithm claim after this normalization. It is not a universal-superiority claim and does not make a CSR winner claim.

## 6. ReproAudit v0.1.0 Contract

ReproAudit requires exactly `experiment.yaml`, `claims.yaml`, `raw_results.csv`, and `summary_results.csv`. YAML models reject unknown fields. CSV headers are unique/nonempty and row widths are consistent. Names and cross-file references are case-sensitive and trimmed.

`experiment.yaml` requires `schema_version: "1.0"`, nonempty trimmed experiment name/task, positive strict-integer `execution.runs`, exactly `seed_column: seed`, a nonempty ordered unique algorithm list, nonempty scalar parameters, and nonempty metrics with `minimize` or `maximize` direction and exactly one primary boolean.

`claims.yaml` requires the same schema version. Its claim families are optional: positive strict-integer run claim, scalar parameter claims, finite mean and nonnegative finite std claims, best claim, and audit tolerances. Missing reported results, config claims, and best conclusion cause R103, R201, and R202 to SKIP. Default tolerances are absolute `0.000001` and relative `0.0001`.

Raw requires `seed`, `algorithm`, `status`, and every metric. Seeds are base-10 nonnegative integers; statuses are `success`, `failed`, `timeout`, or `cancelled`. A success row is usable only when every declared metric is finite. Summary requires `algorithm`, `metric`, `mean`, `std`, `median`, and `n`; keys are unique; `n >= 2` requires finite nonnegative sample std and `n == 1` an empty std.

Tolerant rules pass when `abs(actual - expected) <= max(abs_tol, rel_tol * abs(expected))`, inclusive. R101/R102 use `std(ddof=1)`. Missing/invalid input exits 3 without normal report. Completed audits exit 0 when only INFO/SKIP, 1 for highest WARNING, and 2 for any ERROR.

| Rule | Exact scope and faithful-baseline expectation |
| --- | --- |
| R001 | Declared algorithms each have 30 successful rows; PASS/INFO |
| R002 | Every raw `(seed, algorithm)` key is unique; PASS/INFO |
| R003 | Declared algorithms have common successful seeds; PASS/INFO |
| R004 | Observed algorithms equal declared algorithms; PASS/INFO |
| R005 | All rows success with finite selected metrics; PASS/INFO |
| R101 | Official mean matches usable raw per declared algorithm/metric; PASS/INFO |
| R102 | Official sample std matches usable raw per declared algorithm/metric; PASS/INFO |
| R103 | README rounded means match usable raw within tolerance; PASS/INFO |
| R201 | README run/config claims equal config; PASS/INFO |
| R202 | README-normalized RDHO is fitness-tied best among six; PASS/INFO |

Rules R001, R002, and R003 never SKIP and fail as ERROR. R004 never SKIPs;
missing declared algorithms fail as ERROR and undeclared raw algorithms as
WARNING, possibly in separate findings. R005 never SKIPs; non-success rows
fail as WARNING and invalid selected metrics in a success row as ERROR. R101
fails as ERROR for a missing/mismatched/nonfinite comparable summary mean and
SKIPs only when no declared algorithm/metric pair is comparable. R102 fails as
ERROR for missing/mismatched/nonfinite required sample std and SKIPs only when
no pair has at least two usable values. R103 fails as ERROR for a mismatched
stated statistic, insufficient claimed std, or nonfinite aggregate; it SKIPs
when no reported result exists or every stated check has a documented
skippable missing prerequisite. R201 fails as ERROR and SKIPs only with no
run/parameter claims. R202 fails as ERROR and SKIPs only without a best claim.

## 7. Four-File Mapping

The baseline is named `faithful_baseline`, never clean. It is a faithful schema conversion. A source finding is a real source-asset inconsistency after adapter checks pass. An adapter defect is a mapping/precision/type error causing a false finding and must be resolved before attributing anything to MEC.

| ReproAudit field | MEC source field | Transformation | Precision / unit | Missing treatment |
| --- | --- | --- | --- | --- |
| `experiment.name` | README V2 context | `MEC main 40-task paired benchmark` | text | Required documented adapter constant |
| `experiment.task` | README model scope | `MEC task offloading and CPU allocation` | text | Required documented adapter constant |
| `execution.runs` | config `experiment.independent_runs` | Direct 30 | runs | Stop if absent/nonpositive |
| `algorithms` | config `experiment.algorithms` | Preserve source order/names | text | Stop on duplicate/empty |
| `parameters.mobile_devices` | config `system.mobile_devices` | Direct 20 | count | Stop if absent |
| `parameters.edge_servers` | config `system.edge_servers` | Direct 4 | count | Stop if absent |
| `parameters.cloud_servers` | config `system.cloud_servers` | Direct 2 | count | Stop if absent |
| `parameters.task_count` | config `system.tasks` | Direct 40 | count | Stop if absent |
| `parameters.population_size` | config `experiment.population_size` | Direct 50 | count | Stop if absent |
| `parameters.max_iterations` | config `experiment.max_iterations` | Direct 150 | iterations | Stop if absent |
| `parameters.seed_start` | config `experiment.seed_start` | Direct 20260701 | seed | Stop if absent |
| `metrics.fitness` | raw `fitness`; summary `fitness_*` | Direct numeric | reporting objective | Stop if nonfinite |
| `metrics.csr` | raw `csr`; summary `csr_*` | Direct numeric | ratio | Stop if nonfinite |
| raw `seed` | raw `seed` | Base-10 integer serialization | paired scenario seed | Stop if malformed |
| raw `algorithm` | raw `algorithm` | Preserve exact name | text | Stop if unknown to config |
| raw `status` | no source column | `success` after finite-field validation | status | Stop on uncertainty/nonfinite |
| raw `run_id` | raw `run_id` | Opaque extra column | 1--30 index | Retain source text |
| summary `mean`, `std` | official selected `*_mean`, `*_std` | Direct decimal serialization | full source precision | Stop if absent/nonfinite |
| summary `median`, `n` | selected raw metrics | Deterministic median/count | decimal/count | Stop if no usable values |
| reported means | README V2 table | Four-decimal mean; normalize RDHO-full | display rounded | Omit R103 family if absent |
| best claim | README current conclusion | fitness / RDHO after normalization | text | Omit R202 claim if absent |

Raw output preserves source order: ascending `run_id`, then configured algorithm order. Summary output is configured algorithm order, then `fitness`, then `csr`. CSV uses UTF-8, LF, comma delimiter, and deterministic decimal serialization sufficient to round-trip source floats.

Claims include README-supported run/config values, twelve rounded means (six algorithms times two metrics), and the fitness best claim. README has no std claim, so R103 checks means only. If this pinned claim source is missing in a later source version, its claim family is omitted and R103/R202 SKIP; no claim is synthesized from raw or summary.

## 8. Tolerance and Baseline Statistics

The audit settings are absolute tolerance `0.00005` and relative tolerance `0.0`. Official full-precision summaries differ from independent raw calculation only by IEEE-754 noise: maximum fitness mean difference `4.440892098500626e-16`, fitness std `2.7755575615628914e-17`, CSR mean `2.220446049250313e-16`, and CSR std `1.3877787807814457e-17`. The fixed tolerance is for README's four-decimal values; it is not widened to mask a source mismatch.

| Algorithm | fitness mean | fitness std | CSR mean | CSR std |
| --- | ---: | ---: | ---: | ---: |
| RDHO | 0.9470392278303288 | 0.1201932547560797 | 0.7205555555555556 | 0.0546993407633850 |
| RIME | 1.5847950082273574 | 0.1541338145073450 | 0.5133333333333333 | 0.0530036505646552 |
| DBO | 1.1836517627101044 | 0.1904998527186591 | 0.6286111111111111 | 0.0699165941710930 |
| TLBO-HHO | 1.2263048231318803 | 0.2010088253970581 | 0.5988888888888889 | 0.0716102870097545 |
| CWTSSA | 1.2473242356211496 | 0.1513144080853995 | 0.5883333333333333 | 0.0567561835205301 |
| Greedy-ED | 1.0932457434014435 | 0.1703119736811905 | 0.6480555555555557 | 0.0621564632675149 |

No selected source inconsistency was found: all 180 keys are unique, all six seed sets match, selected values are finite, and official mean/std agree with raw. The expected baseline exit is 0 with ten PASS/INFO findings. This is an observed acceptance expectation, not grounds to call the source clean before a future run.

## 9. Source Manifest

`source_manifest.json` is sidecar provenance, not a ReproAudit input and never participates in rule computation. It uses UTF-8, sorted keys, canonical JSON separators, a trailing newline, repository-relative POSIX paths, no hostname, username, absolute path, temporary path, random UUID, or wall-clock generation time.

It records `case_id`, fixed exporter identifier/version, `generated_at_policy: omitted_for_byte_determinism`, MEC repository/commit, ReproAudit repository/tag/commit/release-wheel hash, ordered source paths/hashes, selected experiment/metrics, excluded columns, mapping version, README label normalization, rounding policy, and tolerance rationale. It proves source identity, not source validity.

## 10. Independent Oracle

The oracle uses Python 3.11, standard-library `csv`, `json`, `math`, and `statistics` (or independently written pandas grouping). It must not import `reproaudit`, ReproAudit rules/tolerance helpers, exporter statistics helpers, or consume a ReproAudit report.

Its `oracle-report.json` has sorted keys, UTF-8, trailing newline, and no timestamp. It independently records declarations; success counts; key multiplicities; seed sets/common union; missing/undeclared algorithms; non-success and nonfinite rows; usable values; mean/median/sample std; official-summary differences; README claims; exact config claims; directions; tolerance-aware ties; and normalized observable rule outcomes.

For finite `x_1...x_n`, mean is `sum(x)/n` and sample std is `sqrt(sum((x_i-mean)^2)/(n-1))` for `n >= 2`. It passes a numeric comparison iff absolute difference is at most `0.00005`. It independently finds the fitness minimum and CSR maximum and includes all values within tolerance.

Acceptance compares rule ID, PASS/FAIL/SKIP, severity, affected algorithm/seed/metric, normalized expected/actual values, and exit class. It does not require identical messages or private evidence layout.

## 11. Fault-Injection Matrix

Faults are deterministic specifications applied only to a temporary `faithful_baseline` copy. Source and committed baseline never change; fault CSVs are never committed. A scenario updates dependent adapted summary/claim values only when explicitly stated to isolate the target rule.

| ID | Mutation | Required finding | Allowed cascades | Forbidden findings | Exit |
| --- | --- | --- | --- | --- | --- |
| F001 | RDHO seed 20260701 status becomes `failed` | R001 ERROR | R003, R005 WARNING, R101, R102, R103 ERROR | R002, R004, R201, R202 | 2 |
| F002 | RDHO seed 20260702 becomes 20260701; recompute only affected adapted summary and README-derived claim | R002 ERROR | R003 ERROR | R001, R004, R005, R101, R102, R103, R201, R202 | 2 |
| F003 | RDHO seed 20260730 becomes 20260731 | R003 ERROR | none | R001, R002, R004, R005, R101, R102, R103, R201, R202 | 2 |
| F004 | Add `UNDECLARED-CONTROL` with 30 copied finite Greedy-ED values, all source seeds, success status, matching summary | R004 WARNING | none | R001, R002, R003, R005, R101, R102, R103, R201, R202 | 1 |
| F005A | RDHO seed 20260701 status becomes `timeout` | R005 WARNING | R001, R003, R101, R102, R103 ERROR | R002, R004, R201, R202 | 2 |
| F005B | RDHO seed 20260701 fitness becomes literal `NaN`, status success | R005 ERROR | R101, R102, R103 ERROR | R001, R002, R003, R004, R201, R202 | 2 |
| F101 | Add 0.01 to RDHO/fitness summary mean only | R101 ERROR | none | R001-R005, R102, R103, R201, R202 | 2 |
| F102 | Add 0.01 to RDHO/fitness summary std only | R102 ERROR | none | R001-R005, R101, R103, R201, R202 | 2 |
| F103 | Change RDHO/fitness README-derived mean claim 0.9470 to 1.0470 | R103 ERROR | none | R001-R005, R101, R102, R201, R202 | 2 |
| F201 | Change parameter claim `max_iterations` from 150 to 151 | R201 ERROR | none | R001-R005, R101-R103, R202 | 2 |
| F202 | Change fitness best claim RDHO to DBO | R202 ERROR | none | R001-R005, R101-R103, R201 | 2 |
| F900 | Remove temporary `claims.yaml` | input validation error | no normal report | all normal findings | 3 |

F001/F005A intentionally overlap in data-quality effect but establish count versus non-success ownership. F002 preserves 30 RDHO rows but duplicates seed 20260701 and removes 20260702; dependent recalculation prevents a statistical mismatch masking R002/R003. F005B leaves 30 success statuses, so R001/R003 remain PASS while valid statistics exclude the bad metric. F202 ranks all six main candidates and never repurposes strict-control conclusions.

## 12. Determinism and Immutability

Exporter runs in two independent temporary directories from the same pinned source. All four inputs and manifest must be byte-identical. It has fixed source/field order, CSV LF, deterministic YAML/JSON/CSV serialization, no timestamp, and no platform path.

Oracle runs twice with byte-identical JSON. The official-wheel CLI runs twice in the same isolated venv. If its report has a generation timestamp, only that explicitly identified nonsemantic field is removed into a comparison copy; finding order, rule IDs, status, severity, evidence, counts, and exit code remain mandatory. No other field may be ignored.

Before export, after export, and after every fault/acceptance run, SHA-256 is recomputed for config, raw, official summary, README, and protocol. Values must match the manifest. The source worktree remains clean, reports/faults stay outside source directories, and no report goes below raw/summary paths.

## 13. Directory and Component Design

```text
case_studies/reproaudit_v0_1/
  README.md
  source_manifest.json
  faithful_baseline/
    experiment.yaml
    claims.yaml
    raw_results.csv
    summary_results.csv
  expected/
    baseline_expectations.json
    fault_matrix.json
  reports/
    .gitkeep
scripts/
  export_reproaudit_case.py
  independently_verify_reproaudit_case.py
  inject_reproaudit_fault.py
  run_reproaudit_acceptance.py
tests/
  test_reproaudit_case_export.py
  test_reproaudit_oracle.py
  test_reproaudit_faults.py
  test_reproaudit_acceptance.py
```

Exporter only maps/validates sources; oracle only computes independent observations; injector only creates temporary variants; runner only orchestrates hashes, wheel, oracle, CLI, and comparison. `reports/` is ignored except `.gitkeep`; dynamic reports are never committed. Commit only compact transformed baseline data and manifest, never source copies or fault packages.

## 14. CI and Execution Source

The main acceptance path uses the official v0.1.0 release wheel, not local ReproAudit source. It downloads the named asset once or consumes prevalidated `REPROAUDIT_WHEEL_PATH`, verifies the specified SHA-256, creates an isolated Python 3.11 venv, installs exactly that wheel, and reports its hash. CI caches the verified wheel by tag/hash, preventing a network dependency on every test.

Existing MEC PR CI stays fast synthetic/unit coverage: exporter/oracle/injector fixtures do not download releases or use full MEC raw data. Add one manually dispatched or scheduled real-data job for faithful baseline and official wheel, with no secrets and no publication. This matches the repository's existing Python 3.11/Pytest CI while containing network cost.

## 15. Acceptance Criteria

| Area | Passing criterion |
| --- | --- |
| Source identity | Pinned commit and all manifest hashes match before and after execution |
| Mapping | Six algorithms, 180 rows, common seeds 20260701--20260730, two metrics, no undocumented transform |
| Baseline | Wheel CLI and oracle agree on ten PASS/INFO outcomes and exit 0 |
| Official summary | All 12 mean and 12 sample-std checks agree at the fixed tolerance |
| Claims | README-rounded means and normalized RDHO fitness conclusion are traceable and pass |
| Faults | Required findings/severities, allowed cascades only, forbidden-finding absence, stated exit |
| Determinism | Two exports, two oracle reports, and normalized audit reports agree |
| Hygiene | Source hashes/worktree unchanged; no source reports, committed faults, push, or PR |

Implementation fails if it silently changes source values, regenerates official summary before auditing it, fabricates claims, widens tolerance, treats a nonfinite row as usable, or calls the baseline clean before observing its report.

## 16. Expected Case-Study Report

The future case README reports purpose, pinned repositories/versions, source hashes, source selection, mapping, selected/excluded fields, tolerance, baseline, oracle, faults, determinism, immutability, real findings if any, limitations, reproduction, and only this conclusion: structured consistency acceptance for specified MEC main-experiment assets.

It must not claim complete paper reproducibility, algorithm correctness, universal RDHO superiority, zero errors without observed evidence, independent third-party validation, DOI, adoption, or citations.

## 17. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Raw/summary version mismatch | Pin commit/hashes; use main writer provenance; reject drift |
| Summary display rounding | Preserve full official values; fixed 0.00005 only for four-decimal README claims |
| Seed is scenario ID, not solver RNG | Document paired-scenario semantics; use source seed as key, retain run ID |
| Missing status | Map finite selected rows to success; stop on ambiguity, never invent failure |
| Algorithm naming mismatch | One explicit README RDHO-full to RDHO mapping |
| CSR definition drift | Pin config/protocol/commit; audit stored-value consistency only |
| Historical/control contamination | Source precedence excludes archive and non-main families |
| Missing claims | Omit unsupported family; documented R103/R202 SKIP |
| Ties/directions | Declare directions and use fixed tolerance-aware tie rule |
| Baseline real failure | Preserve/report after adapter verification; never repair source |
| Fault cascade | Matrix specifies allowed and forbidden findings |
| Time fields | Omit oracle time; normalize only named nonsemantic audit timestamp |
| Release download instability | Verified cache or explicit wheel path with mandatory hash |
| Repository bloat | Commit compact conversion only, not source copies/fault variants |

## 18. Implementation Boundaries

Begin implementation only after human review. Preserve these fixed decisions: V2 main source paths, `faithful_baseline`, fitness/CSR directions, `(seed, algorithm)` key, paired scenario seed semantics, constrained success mapping, `ddof=1`, absolute tolerance `0.00005`, README provenance/label normalization, official-summary preservation, sidecar manifest, independent oracle, listed faults, release-wheel path, ignored dynamic reports, and synthetic-PR/manual-real CI split.
