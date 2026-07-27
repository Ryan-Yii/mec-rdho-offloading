# Manuscript Figure Mapping

The canonical V2 paper-facing figures are under `figures/paper/v2/`; their
source data, generator and SHA-256 values are recorded in
`paper_artifacts/manifest.csv`. Main-manuscript numbering ends at Figure 12.

The unversioned files directly under `figures/`, including
`fig11_normalized_multi_metric_radar.png`, are retained only for historical
traceability. They do not define the current manuscript numbering.

## Repository Supplement

| Item | Canonical file | Interpretation |
|---|---|---|
| Figure S1 | `paper/v2/figure_s1_convergence_curve.{png,svg}` | Equal-NFE convergence |
| Figure S2 | `paper/v2/figure_s2_convergence_curve.{png,svg}` | Common-control convergence |
| Figure S3 | `paper/v2/figure_s3_utility_sensitivity.{png,svg}` | Task-utility sensitivity |
| Figure S4 | `paper/v2/figure_s4_physical_sensitivity.{png,svg}` | Physical-input sensitivity |
| Figure S5 | `paper/v2/figure_s5_descriptive_main_comparison_radar.{png,svg}` | Descriptive main-comparison means |

Figure S5 applies min-max normalisation separately on each axis across the
displayed methods. Energy, delay and AoI are inverted so that higher displayed
scores are consistently better. It shows means only and conveys neither
uncertainty nor statistical significance; it is supplementary context, not a
replacement for the absolute-value tables, error-bar figures or controlled
attribution evidence in the main manuscript.
