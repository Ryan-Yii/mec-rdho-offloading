# Controlled RDHO Evidence Report

## Scope

This is an additive controlled experiment, not a manuscript revision. It ran
on local branch `research/rdho-controlled-evidence` from
`cf499f2d1a0f37859cc045cf3c902815b81927f1`, the unchanged target of
`v2-paper-artifacts-2026-07`. No document, old V2 result, remote branch, PR,
or tag was changed.

Question: after equalising the initial population, physical evaluation path,
and exact total NFE, does the implemented RDHO population stage independently
outperform the implemented RIME and DBO population stages in the 30 V2
scenarios?

## Design and execution

- Paired scenarios: seeds `20260701` through `20260730`, with unchanged V2
  task/network generation.
- Primary endpoint: fixed reporting fitness, lower is better. Search fitness
  is not reported in final result tables.
- All methods use the existing legal-node encoding, physical CPU decode,
  `decode_and_repair`, hard-feasibility checks, and `evaluate_solution`.
- One 50-by-40-by-2 float64 population is generated per scenario and copied to
  all methods. The audit has 180 method rows, 60 paired triplets, and 30
  distinct scenario-population hashes; every triplet has one identical hash.
- Experiment A disables RDHO dual-source/greedy/perturbation initialization and
  all coordinate refinement. It retains RDHO population updates, greedy
  selection, dynamic penalty, and independent reporting incumbent. All methods
  use exactly 3801 NFE: `50 initial + 3750 candidate + 1 final reporting`.
- Experiment B adds the same deterministic ascending-task 5-by-5 coordinate
  sweep to all methods and disables RDHO-specific local refinement. All methods
  use exactly 10232 NFE: `50 initial + 9181 candidate + 1000 refinement + 1
  final reporting`. The final generation evaluates 31 candidates, never over
  budget.
- `EvaluationBudgetManager` is the sole controlled evaluator entry point. It
  calls the shared evaluator after decode/repair, counts each call, has no
  cache, and rejects evaluations over budget. Parent fitness is algebraically
  re-scored at the same lambda(t) as candidates, without a hidden evaluation.

The smoke run covered 2 paired seeds before all 180 immutable per-method
checkpoints were run. The assembler refuses missing, mismatched-commit, or
mismatched-population-hash checkpoints.

## Environment and validation

Environment: Python 3.9.6, NumPy 2.0.2, pandas 2.3.3, SciPy 1.13.1,
Matplotlib 3.9.4 with Agg, macOS-26.5.2-arm64-arm-64bit. The exact record is
`results/audit/controlled_evidence_environment.json`.

- Both raw files contain 90 rows: 30 scenarios times 3 methods; no seed was removed.
- Every return is hard feasible and uniquely assigns all tasks: 90/90 for A and 90/90 for B.
- Every repair reassignment count and repair failure count is zero.
- `tools.verify_controlled_rdho_evidence` rebuilt summaries and statistics from raw: PASS.
- `pytest tests -q` under Agg: 47 passed; 14 existing Matplotlib/pyparsing warnings.
- The V2 hash audit passed for every protected V2 file; `results/v2/` has no changes.

## Primary results

### Experiment A: population-stage control, 3801 NFE

| Method | Fixed reporting fitness, mean +/- SD | Median |
|---|---:|---:|
| RDHO-population-controlled | 1.418845 +/- 0.161200 | 1.394605 |
| RIME-population-controlled | 1.683425 +/- 0.165119 | 1.659319 |
| DBO-population-controlled | 1.240930 +/- 0.124455 | 1.220827 |

`DeltaF = F_RDHO - F_baseline`; negative favours RDHO.

| Comparison | Median DeltaF [95% bootstrap CI] | Wilcoxon p; Holm p | Rank-biserial | W/T/L for RDHO |
|---|---:|---:|---:|---:|
| RDHO vs RIME | -0.278300 [-0.312822, -0.198123] | 1.304e-08; 1.304e-08 | -0.983 | 29/0/1 |
| RDHO vs DBO | +0.178910 [+0.112584, +0.225303] | 1.863e-09; 3.725e-09 | +1.000 | 0/0/30 |

RDHO is significantly lower than RIME and significantly higher than DBO.

### Experiment B: common-pipeline control, 10232 total NFE

| Method | Fixed reporting fitness, mean +/- SD | Median |
|---|---:|---:|
| RDHO-common-pipeline | 0.973205 +/- 0.124405 | 0.982735 |
| RIME-common-pipeline | 0.983591 +/- 0.120485 | 0.995016 |
| DBO-common-pipeline | 0.966404 +/- 0.123370 | 0.967566 |

| Comparison | Median DeltaF [95% bootstrap CI] | Wilcoxon p; Holm p | Rank-biserial | W/T/L for RDHO |
|---|---:|---:|---:|---:|
| RDHO vs RIME | -0.012281 [-0.024215, -0.001839] | 0.009932; 0.019863 | -0.531 | 23/0/7 |
| RDHO vs DBO | +0.008226 [+0.000775, +0.014349] | 0.026229; 0.026229 | +0.462 | 10/0/20 |

Under the same deterministic refinement, RDHO is significantly lower than
RIME and significantly higher than DBO.

## Secondary trade-offs

In A, DBO also has lower mean base objective (0.850375 versus 0.972734),
energy (85.139 versus 116.503), delay (2.708 versus 3.137), and AoI (3.031
versus 3.460) than RDHO. In B, RDHO has lower mean delay than DBO (1.845
versus 1.889), but higher primary reporting fitness (0.973205 versus
0.966404). These secondary measures do not replace the primary endpoint.

## Interpretation boundaries

The controlled experiment does not support independent superiority of the
RDHO population mechanism over both parent algorithms. In both controls, the
implemented RDHO update outperforms implemented RIME but is significantly
outperformed by implemented DBO on fixed reporting fitness.

This is not evidence of general superiority or inferiority outside the current
implemented methods and 30 fixed synthetic V2 scenarios. It does not justify
post-hoc parameter adjustment, seed selection, or a manuscript update.

## Evidence files

- Raw: `results/raw/controlled_population_stage_30_raw_results.csv` and
  `results/raw/controlled_common_pipeline_30_raw_results.csv`.
- Summaries: `results/summary/controlled_population_stage_30_summary.csv` and
  `results/summary/controlled_common_pipeline_30_summary.csv`.
- Statistics: `results/statistics/controlled_population_stage_wilcoxon.csv`,
  `results/statistics/controlled_common_pipeline_wilcoxon.csv`, and
  `results/statistics/controlled_evidence_effect_sizes.csv`.
- Audits: `results/audit/controlled_initial_population_audit.csv`, NFE audit
  CSVs, V2 integrity CSV, environment JSON, and SHA-256 manifest.
- Tables: the three `paper_tables/controlled_*` CSV and Markdown pairs.
- Analysis-only figures: `figures/analysis/controlled_*`; none is inserted into a manuscript.

The complete controlled-artifact manifest is
`results/audit/controlled_evidence_sha256.csv`.
