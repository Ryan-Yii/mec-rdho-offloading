# 0712--0722--V2 Model Comparison

| Item | 0712 / thesis evidence | 0722 quality baseline | V2 decision |
|---|---|---|---|
| Assignment | Unified device/edge/cloud node index and task assignment were described. | Fixed nearest-edge/cloud mapping was made explicit. | Restore a unified node assignment, but permit only source-local and linked remote nodes. |
| CPU resource | Task CPU frequency and node capacity were described. | A normalised computation-control coordinate was honestly labelled as an abstraction. | Use normalised `r` only internally and decode it to `f` in Hz with a deterministic capacity projection. |
| Node selection | Old code had node IDs and link dictionaries, but some cloud paths defaulted to the first edge. | Current code used nearest-edge/cloud, so it did not optimise a server choice. | Select legal edge/cloud nodes using complete generated rate matrices; use a recorded deterministic relay for cloud paths. |
| Load treatment | Old work mixed capacity, queue assumptions, and repair claims. | Current code uses `0.070`, `0.035`, and `0.020` load attenuation. | Remove both queueing and heuristic load attenuation.  Capacity is represented once through allocation repair. |
| Energy | Old code mixes device, edge, and cloud computation terms. | The current text is close to device-side framing. | Report device-side local DVFS or uplink energy only. |
| AoI | Periodic-update expression exists. | Correctly avoids peak/queue-level claims. | Retain `Delta/2 + T` as a one-period average-AoI approximation and state assumptions. |
| Objective | Old dynamic penalties could conflict with reported values. | Explicitly separates base, dynamic search, and fixed reporting fitness. | Preserve that separation and test same-lambda selection. |
| Fairness | Thesis frames fairness as user-facing. | Uses user-level aggregation. | Retain active-user mean base QoE before Jain fairness; priority is excluded from fairness inputs. |
| Evidence | Legacy values are not reusable. | 30 paired runs, Wilcoxon/Holm/effect sizes, NFE, and restrained claims are required. | Rerun every V2 experiment and generate all tables/figures from raw V2 outputs only. |

## Evidence checked

The WHITE repository's `src/models/system_model.py` contains physical node IDs,
CPU-frequency fields, and device-edge/edge-cloud rate dictionaries.  Its delay
and energy modules also reveal a cloud path that selected the first edge and
an optional queue model; neither is carried forward.  The pre-V2 Ryan
repository instead uses two coordinates (`mode`, `resource`), fixed
nearest-node maps, and heuristic load-adjusted frequencies.  Consequently its
existing results are archived and cannot support V2 statements.
