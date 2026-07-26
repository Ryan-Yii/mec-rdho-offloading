# Submission-Readiness Revision

## Scope and Evidence Boundary

This revision is additive to the controlled-evidence manuscript. It does not modify `src/`, model parameters, raw V2 results, or anything under `results/v2/`. The reviewed DOCX starts from the prior 138-comment controlled manuscript, preserves every original comment, anchor, and reply, and adds eight unresolved threaded replies to the existing RDHO/innovation threads.

The fixed-return reporting-penalty check reads only:

- `results/raw/controlled_population_stage_30_raw_results.csv`
- `results/raw/controlled_common_pipeline_30_raw_results.csv`

It re-scores each already-returned solution as `F_lambda = B + lambda_ref * (1 - soft_CSR)` at `lambda_ref` 0.5, 1, and 2. It does not rerun a solver, reconstruct an alternative incumbent, or report an alternative-lambda optimisation. The raw files identify `search_fitness_not_reported=True`, which is why this limitation is explicit.

## Implemented Pre-submission Corrections

1. Section 5 defines RDHO dual-source initialisation, greedy seed, all three seed perturbations, diversity, role shares, elite treatment, producer/follower/scout updates, all random variables, clipping, refinement variants, exact controlled NFE counts, and time/space complexity.
2. Algorithm 2 is placed directly after the Section 3.2 repair equations and specifies deterministic legal-node reassignment, target ranking, ties, failure handling, bounded passes, and excess-only capacity projection. Failure means this deterministic order did not construct a reassignment for the decoded candidate; it is not a proof of scenario infeasibility. The current implementation propagates `ValueError` and aborts the affected run rather than assigning infinity, retaining a parent, or resampling. Reported controlled runs contain zero repair failures.
3. The abstract, Section 6.3, Figure 12 discussion, and conclusion distinguish DBO's clear Experiment-A advantage from its smaller but statistically significant Experiment-B advantage.
4. Table 7 reports reporting fitness, base objective, soft CSR, QoE, fairness, NFE, and runtime. The fixed-return lambda analysis is written with its non-re-optimisation boundary.
5. New prose and revised notation use allocated CPU-cycle rate and aggregate CPU-cycle capacity. It distinguishes effective local DVFS frequency from edge/cloud task computation service rate.
6. The model now states the negligible-result-size assumption, omitted downlink/result-return terms, independent sparse-link removal, and exact connectivity repair procedure.
7. Parameter provenance is disclosed as versioned heterogeneous synthetic settings, not hardware calibration. Representative MEC references [1,3,11,13] support order-of-magnitude reasonableness; capacity, SLA, and heterogeneity sensitivity coverage is also stated.
8. Related Work moves reference [12] to the learning-based class. Sections 6.3 and 6.4 are reordered logically, and duplicate legacy comparisons are removed from the main-text Table 9 location in favour of Algorithm 2 and a repository supplement reference.
9. The experimental environment and serial runner boundary are disclosed; Table 4 gives fixed RDHO and baseline parameters and their provenance.
10. Data Availability identifies the public GitHub repository, exact controlled paths, the lambda-analysis command, and the immutable `v2.0.0` release snapshot.
11. RDHO role counts are identified as nominal full-population thresholds with exact elite/producer/follower/scout `if/elif` precedence and deterministic truncation; the text clarifies that these thresholds are not guaranteed realised population proportions. Complexity now separates the practical repair cost from the `O(N^2 M L)` per-candidate worst case. The duplicate Problem Complexity paragraph is removed.
12. The abstract qualifies Experiment A as no-refinement and identifies common refinement as an Experiment-B condition, while retaining the prespecified `lambda_ref=1` qualification for Experiment B.
13. The Limitations section states that the current implementation aborts an optimiser run when deterministic candidate repair fails, and records that no such failure occurred in the controlled experiments. It also states that the incremental contribution of nested objective layers has not been isolated.

## Post-hoc Fixed-return Results

At `lambda_ref=1`, the tool verifies row-wise equality with the original reporting fitness before output. In Experiment A, DBO remains significantly lower than RDHO at all three reported lambda values (Holm-adjusted p at most `1.118e-08`). In Experiment B, DBO remains significantly lower for the fixed returns at lambda 0.5 (Holm `0.027326`) and 1 (Holm `0.026229`), but not at 2 (Holm `0.104840`). This is a robustness characterization of the returned solutions, not a claim about alternative-lambda optimisation.

## Remaining Author/Release Gates

- Confirm source citations if the paper is to describe parameters as hardware calibrated; this revision makes no such claim.
- Release `v2.0.0` is the immutable publication snapshot for the aligned manuscript and audited evidence.
- Confirm journal template, author metadata/double-blind policy, and final bibliography approval as listed in `docs/author_confirmation_required.md`.
