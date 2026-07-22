# Experiment Protocol V2

All V2 raw outputs are regenerated from seeded configurations.  A run ID uses
one generated system instance shared by every compared solver; algorithm RNG
streams are derived deterministically from the run seed and algorithm label.
No V1 values, figures, or manually edited CSV cells are permitted.

## Primary benchmark

Thirty paired scenarios compare RDHO-full, RIME, DBO, TLBO-HHO, CWTSSA, and
Greedy-ED.  Population algorithms use the same population size and iteration
count.  The end-to-end comparison reports runtime and actual NFE; it does not
interpret an unequal NFE as an algorithm-only advantage.

## Controlled comparisons

An equal-NFE benchmark gives population algorithms the same evaluation budget.
A second controlled benchmark compares RIME and DBO with RDHO's common
dual-source initialisation, then with the same coordinate refinement, alongside
RDHO-core and RDHO-full.  Each ablation changes exactly one RDHO component
while sharing seeds, repair, fixed reporting objective, and nominal budget.

## Additional studies

Scalability covers 20, 40, 60, 80, and 100 tasks.  Sensitivity covers objective
weights, explicit physical-term / QoE objective compositions, dynamic-penalty
parameters, task-utility coefficients, CPU-capacity scaling, SLA threshold
scaling, and server heterogeneity.  Weight-specific objectives are only
compared inside their own setting; a fixed canonical reporting objective is
also recorded when cross-setting interpretation is needed.

## Reporting and statistics

Each raw row contains the seed, algorithm, fixed reporting fitness, objective
decomposition, device-side energy, mean delay, mean AoI, QoE, active-user
fairness, soft CSR, hard-feasibility indicators, capacity utilisation, runtime,
and NFE.  Primary paired comparisons use two-sided Wilcoxon signed-rank tests,
Holm adjustment, median paired difference, rank-biserial correlation, and
wins/ties/losses.  Figures and manuscript tables are regenerated solely from
the V2 raw and summary files.
