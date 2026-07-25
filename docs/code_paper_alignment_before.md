# Pre-Implementation Code--Paper Alignment Audit

Audit date: 2026-07-22.  This is an evidence audit, not an experimental result.

| Claimed/modelled item | Current Ryan implementation | Status before V2 |
|---|---|---|
| Local/edge/cloud execution | Present as modes 0/1/2. | Partial: execution layer exists. |
| Specific edge/cloud choice | `nearest_edge` / `nearest_cloud` are deterministic modulo mappings. | Missing optimisation decision. |
| Actual CPU frequency | Second coordinate is clipped to 0.2--1.0. | Abstract control, not Hz. |
| Node CPU capacity | No aggregate capacity calculation. | Missing. |
| Capacity repair | No projection/reassignment. | Missing. |
| Load model | Frequency divided by ad hoc count-based attenuation. | Must be removed. |
| Communication path | Full rate matrices are generated but only nearest links are used. | Under-used and inconsistent with server-choice claim. |
| Delay/energy/AoI | Present, but energy includes selected fixed terms and AoI is an approximation. | Must be made physically scoped and documented. |
| QoE/fairness | Present; fairness is already aggregated per source user. | Retain with priority removed from base per-task utility. |
| Search vs reporting objective | Present and tested. | Retain. |
| Statistics | Paired Wilcoxon/Holm/effect/W-T-L present. | Retain and regenerate. |
| Results | Existing CSVs, figures, and paper tables use the abstract model. | Legacy only; never consumed by V2 scripts. |

The new implementation must make the V2 decoder the only route from an
algorithm vector to metrics.  No algorithm may directly implement a separate
mode mapping, capacity rule, or reporting objective.
