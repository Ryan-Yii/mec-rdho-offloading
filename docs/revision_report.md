# V2 Revision Report

## Changes from the 0712 direction

The unified node and physical CPU allocation direction is retained, but V2 does
not copy its code paths or numerical results.  V2 restricts local execution to
the source device, represents remote legality with complete positive-rate link
matrices, selects a deterministic fastest legal cloud relay, removes duplicate
queue/load attenuation, scopes energy to the device side, and tests a
deterministic minimum-frequency/capacity repair.  All results were regenerated.

## Quality retained from the 0722 revision

The reconstruction preserves the distinction among base objective, dynamic
search fitness, and fixed reporting fitness; same-coefficient parent/candidate
comparison; 30 paired scenarios; two-sided Wilcoxon tests with Holm correction,
effect size and wins/ties/losses; NFE disclosure; active-user fairness; and
restrained claims about metrics, ablations, baselines, and deployment scope.

## Code and experiment reconstruction

- Added physical node assignment, CPU decoding, deterministic reassignment and
  proportional overload projection shared by all algorithms.
- Added legal-path delay, device-side energy, periodic average-AoI, model-based
  utility, active-user fairness, and aligned hard/soft constraint reporting.
- Added regression tests for formulae, bounds, capacity, deterministic repair,
  unsaturated feasible requests, reporting semantics, utility coefficients,
  and server heterogeneity.
- Added fresh main, equal-NFE, common-initialisation/postprocessing, one-factor
  ablation, scalability, objective-composition, dynamic-penalty, task-utility,
  CPU-capacity, SLA, and server-heterogeneity experiments.
- Added CSV/Markdown paper tables, PNG/SVG paper figures, SHA-256 artifact
  manifest, execution report, and V2-specific reproduction documentation.

## Scientific interpretation

RDHO-full is the lowest-fitness complete procedure in all 30 paired main
comparisons and every returned main solution is hard feasible.  This finding is
qualified by unequal NFE, equal-NFE losses of RDHO-core against three baselines,
and the strong effect of common coordinate refinement.  The ablation does not
support claiming that every RDHO component independently contributes.

## Manuscript and review handling

The final reviewed DOCX is generated from
`0722-review_revised_SCI_with_comments.docx`.  Substantive revised paragraphs
and tables are highlighted, all original comments and anchors are retained,
one true threaded V2 reply is added to each supervisor comment, and no thread
is resolved.  A separate clean DOCX and PDF remove comments and highlighting.
