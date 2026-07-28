# Manuscript Figure Mapping

The canonical V2 paper-facing figures are under `figures/paper/v2/`; their
source data, generator and SHA-256 values are recorded in
`paper_artifacts/manifest.csv`. Main-manuscript numbering ends at Figure 12.

The later strict controlled-evidence plots are under `analysis/`. Superseded
unversioned paper-facing copies, including the old normalised radar, are
classified under [`archive/v1.0-paper/`](archive/v1.0-paper/) to match the
fixed `v1.0-paper` tag. They are retained for historical traceability only and
do not define the current manuscript numbering.

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

Its sole data source is
`results/v2/raw/main_30_raw_results.csv`. The generator writes Figure S5 only
to `figures/paper/v2/`; it must not add files to the frozen `results/v2/`
evidence inventory.
