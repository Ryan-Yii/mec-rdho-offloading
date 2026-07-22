# Model-Code-Paper Alignment Report

## Final model

V2 uses one simulated cloud-edge-device decision epoch.  Each task chooses one
legal source-local, reachable-edge, or reachable-cloud node and receives a
physical CPU allocation in Hz.  Communication rates and topology are scenario
parameters; bandwidth, power, association, routing, queue scheduling, and
infrastructure energy are outside the optimisation boundary.

| Contract | Code and configuration | Result evidence | Manuscript location |
|---|---|---|---|
| One legal node per task | `src/system_model.py`, `src/metrics.py::decode_and_repair` | `assignment_unique` in every V2 raw row | Sections 3-4; Eqs. (1)-(3), (15) |
| Source-only local execution and positive-rate remote paths | `SystemModel.legal_nodes_for_task` | hard feasibility and deterministic path tests | Section 3.1 |
| Physical CPU allocation in Hz | `DecodedSolution.frequencies_hz` | frequency tuples, utilisation fields, formula tests | Sections 3.2 and 5.1 |
| Aggregate CPU capacity | proportional excess projection in `decode_and_repair` | hard-feasibility rate 1.0; active-node utilisation retained | Eqs. (2)-(3) |
| Feasible requests are not saturated | projection branch preserves requests below capacity | regression test `test_repair_preserves_feasible_cpu_requests_without_saturating_nodes` | Section 3.2 |
| Layer-specific delay | local computation; edge uplink + computation; cloud uplink + backhaul + computation | formula tests and per-run delay | Eq. (4) |
| Device-side energy | local DVFS or uplink transmission | formula tests and per-run energy | Eqs. (5)-(6) |
| Periodic no-backlog average AoI | `0.5 * update_interval + delay` | formula tests and per-run AoI | Eq. (7) |
| Model-based QoE and active-user fairness | unweighted base utility, priority-weighted aggregate QoE, Jain fairness over active users | QoE range, aggregation, and edge-case tests | Eqs. (8)-(13) |
| One formal P1 | fixed base objective plus fixed reporting penalty | reporting-fitness regression tests | Eqs. (14)-(19) |
| Dynamic penalty is search-only | same-iteration rescoring in shared optimizer base | same-coefficient selection and fixed-history tests | Section 4 and Algorithm 1 |
| Shared model for all baselines | all solvers call the same evaluator and repair | paired main/equal-NFE/control raw files | Section 6 |

## Evidence alignment

The corrected main, controlled, ablation, scalability, and sensitivity runners
write only under `results/v2/`.  `experiments/generate_v2_artifacts.py` consumes
only those files and regenerates tables, figures, hashes, and the execution
report.  The manuscript generator reads the same V2 summaries and figures.
Legacy and pre-projection-fix results are not referenced by any V2 script.

The end-to-end benchmark supports RDHO-full as the lowest configured reporting-
fitness procedure in the 30 paired scenarios.  Equal-NFE results do not support
universal superiority of RDHO-core over DBO, TLBO-HHO, or CWTSSA, and common
refinement explains a substantial part of the full-pipeline gap.  The paper,
README, statistics, and tables use this same qualified interpretation.
