# Main Result Audit

Status: **PASS**

Pairing key: `scenario_id + replicate_id`.
Audited rows: 270; paired scenarios: 30.

## Scope

Primary equal-budget algorithms: RDHO, RIME, DBO, TLBO-HHO, CWTSSA, GA, PSO, DE.
Greedy-ED is retained only as a supplementary deterministic, lower-NFE heuristic comparison.

## Checks

- No duplicate `scenario_id + replicate_id + algorithm` rows.
- Every algorithm uses the same paired scenario keys and scenario seed within a pair.
- Stochastic algorithm seeds are distinct within each paired scenario.
- All eight stochastic algorithms share the same maximum NFE.
- `fitness == reported_fitness` for every row.
- `base_fitness`, `report_penalty`, and `reported_fitness` were recomputed from raw columns.

## RDHO Outcomes

| Baseline | Wins | Ties | Losses |
|---|---:|---:|---:|
| RIME | 30 | 0 | 0 |
| DBO | 30 | 0 | 0 |
| TLBO-HHO | 30 | 0 | 0 |
| CWTSSA | 30 | 0 | 0 |
| GA | 30 | 0 | 0 |
| PSO | 30 | 0 | 0 |
| DE | 30 | 0 | 0 |
| Greedy-ED | 30 | 0 | 0 |

Wins and losses use reported fitness (lower is better) with a tie tolerance of `1e-12`.
