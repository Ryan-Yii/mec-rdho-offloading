# Comment Requirements Audit

Source: `0726-revision_content_corrected.docx`

Source SHA-256: `1def9ee9e09aa0c8fbab37a75391dd855b9f82284a2ad78ad3c12e269f742f12`

The source contains 75 unresolved comments: 39 reviewer comments and 36 author
responses. Some author responses cover two adjacent reviewer comments attached
to the same passage. The release manuscript preserves every comment body,
author, date, and anchor exactly; no thread is marked resolved automatically.

| Reviewer comment IDs | Requirement | Verified manuscript response |
| --- | --- | --- |
| 0, 2 | Keep the title concise and avoid listing only selected criteria | The visible and metadata title is `RIME-DBO-Based Capacity-Feasible Task Offloading and Resource Allocation in Mobile Edge Computing`. |
| 4, 6, 8 | Do not mislabel the scalar problem as Pareto multi-objective; organise the abstract as background, challenge, method, and bounded result | The abstract uses a fixed weighted reporting objective, avoids detailed table dumps, and states the adverse DBO control result. |
| 10 | Use standard searchable keywords | The five keywords are mobile edge computing, task offloading, computing resource allocation, capacity feasibility, and controlled evaluation. |
| 12, 14, 16, 18, 20, 22 | Use a funnel-shaped Introduction, bracket citations, no architecture figure in the Introduction, and offloading rather than scheduling terminology | The Introduction follows the requested order; citations use `[x]`; Figure 1 is in Section 3.1; the problem is consistently task offloading. |
| 24, 26, 28, 30 | Expand Related Work using one primary classification axis and do not narrate thesis/paper lineage | Related Work is classified by solution method, with objective dimensions discussed inside each class; TLBO-HHO appears only as literature and a baseline. |
| 32, 34, 36, 38, 40 | Complete the system model, use established AoI wording, integrate assumptions, define tuples and explain modelling logic | Section 3 defines the three-tier model, legal nodes, physical CPU allocation, assumptions, task tuple, delay, energy, periodic no-backlog AoI approximation, scope, and limitations. |
| 42, 44, 46, 48, 49, 51, 53 | Keep equations readable and numbered, define allocated CPU-cycle rate, use a compact notation table, and remove priority-aware fairness | Equations are individually numbered; Table 1 is compact; fairness is active-user base-utility Jain fairness and priority is used only for aggregate QoE. |
| 55, 57, 58 | Present one overall optimisation problem with constraints and avoid over-fragmented short subsections | P1 contains the fixed reporting objective and hard constraints in Eq. (17); the brief complexity discussion remains inline. |
| 60, 61, 63, 65, 67 | Use a task-offloading strategy heading, describe algorithm design rather than programming, number formulas, and reduce small subsections | Section 5 and Algorithms 1-2 use the requested algorithm-design framing and compact hierarchy. |
| 69 | Use one consistent journal-style table format | Tables use a consistent three-line layout without vertical rules. |
| 71, 73 | Renumber references by first citation and add recent literature | References start at `[1]`, follow citation order, and include 2024-2025 MEC/offloading work. |

Evidence and comment boundaries are also checked by
`tools/verify_release_manuscript.py`. Submission-template, double-blind, author
metadata, bibliography approval, and hardware-calibration choices remain author
or journal decisions; they do not create a conflict with the released V2 data.
