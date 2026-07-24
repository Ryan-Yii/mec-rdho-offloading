# Controlled-Evidence Manuscript Execution Report

## Provenance

- Manuscript editing base: `work/manuscript_final_20260724/0712_physical_model_v2_revised_with_comments.docx`.
- Controlled evidence commit: `2a8fa7f` (`experiment: add controlled RDHO population evidence`).
- Frozen V2 tag and source of the configured end-to-end Table 5: `v2-paper-artifacts-2026-07` at `cf499f2`.
- Controlled evidence source files: `results/raw/controlled_population_stage_30_raw_results.csv`, `results/raw/controlled_common_pipeline_30_raw_results.csv`, `results/statistics/controlled_evidence_effect_sizes.csv`, and the audits in `results/audit/controlled_*`.

## Execution performed

1. Verified the additive controlled evidence with `MPLBACKEND=Agg .venv-v2/bin/python -m tools.verify_controlled_rdho_evidence`.
2. Generated `figures/paper/figure_12_controlled_rdho_evidence.{png,pdf,svg}` with `tools/generate_controlled_paper_figure.py`, which reads the two controlled raw CSV files.
3. Generated the annotated and clean DOCX files with `tools/revise_manuscript_controlled_evidence.py`. The script reads frozen V2 summaries for the configured end-to-end comparison and controlled summaries/statistics for the new controls.
4. Generated the clean PDF from the clean DOCX with the Documents skill renderer.
5. Verified comment/thread metadata and clean/annotated separation with `tools/verify_controlled_manuscript_revision.py`.

## Evidence checks

- Experiment A and B raw files each contain 90 records: 30 scenarios times RDHO, RIME and DBO.
- Common-initial-population audit: 180 method rows; every three-method scenario triplet shares exactly one SHA-256 population hash.
- Exact budgets: 3,801 NFE in Experiment A and 10,232 NFE in Experiment B for every method.
- Hard feasibility and unique assignment: 90/90 in each controlled experiment.
- `results/audit/controlled_evidence_v2_integrity.csv` records every protected V2 file as byte-identical.
- The manuscript structural verification confirms 130 preserved base comments, 138 annotated comments after eight new replies, unresolved `w15:done=0` state for every new reply, 1,869 yellow highlights in the annotated DOCX, and no comments or yellow highlights in the clean DOCX.
- The clean DOCX was rendered successfully to 20 PNG pages and a non-empty PDF. Every page, including the controlled Table 7/Figure 12 and conclusion pages, was visually inspected.

## Explicit non-actions

No model parameter, baseline implementation, old V2 CSV, V2 tag, remote branch, pull request or remote repository state was changed. No claim is based on manually entered controlled result numbers.
