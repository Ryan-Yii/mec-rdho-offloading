# Comment Action Plan

The editing base is `0722-review_revised_SCI_with_comments.docx`, which contains
86 comments. The 0712 draft has 36 comments (24 reviewer comments), and the
intermediate 0722 draft has 63 (43 reviewer comments). Twenty 0712 reviewer
comments recur verbatim in 0722; the other four themes are covered by later
0722 instructions. Thus 0712 is not treated as an unused historical file, while
the revised 0722 source remains the sole structure-preserving base. The final
document must preserve all 86 source anchors, author/date data, and comment text.

## Global actions

1. Replace the abstract, model, problem formulation, algorithm, and evaluation
   claims only after V2 code and figures exist.  Highlight substantive revised
   manuscript text in yellow.
2. Retain 0722 corrections: scalar rather than Pareto "multi-objective" wording,
   abstract acronym expansion, offloading terminology, one classification axis
   in related work, no introduction architecture figure, compact headings, and
   formal equations/algorithm/tables.
3. Replace the obsolete abstract-control and heuristic load text with the V2
   physical node/CPU/capacity model.  Do not reuse numerical claims.
4. Audit all comments structurally.  Existing self-authored comments beginning
   with `回复` or `已按` are attached to their original comment only when their
   `paraIdParent` points to that original comment paragraph.  Otherwise they
   are converted into real threaded replies without deleting the original text.
5. Add a real threaded reply to every applicable unresolved supervisor comment,
   leave all threads unresolved, and produce CSV/Markdown audit records.

## Comment themes carried into V2

The V2 manuscript implements the requests for a complete system model,
in-model assumptions, a single formal optimisation problem with constraints,
physical CPU notation, readable original architecture figure in Section 3,
compact standard headings, source-ordered bracket citations, left-aligned
three-line pseudocode, and conservative performance interpretation.  The title
remains an author confirmation because the supervisor explicitly deferred it.
