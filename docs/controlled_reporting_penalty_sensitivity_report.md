# Controlled Reporting-Penalty Sensitivity

This additive analysis rescored each already-returned solution from the immutable controlled raw CSVs as `F_lambda = B + lambda_ref * (1 - soft_CSR)` for lambda_ref in {0.5, 1, 2}.
It neither reruns a solver nor selects a new incumbent. The raw files record `search_fitness_not_reported=True`; therefore these are fixed-return post-hoc checks, not alternative-lambda re-optimisations.

At lambda_ref=1, the tool checks row-by-row equality with the original reporting fitness before writing any outputs.

## Interpretation boundary

The paired results retain the original 30 matched scenarios and use two-sided Wilcoxon tests with Holm correction over RDHO-versus-RIME and RDHO-versus-DBO within each experiment/lambda setting. They only assess ranking robustness of the fixed returned solutions; they cannot establish which method would have found a different incumbent under another reporting penalty.

Generated summary: `results/statistics/controlled_reporting_penalty_sensitivity.csv`.
Generated paired statistics: `results/statistics/controlled_reporting_penalty_sensitivity_paired.csv`.
