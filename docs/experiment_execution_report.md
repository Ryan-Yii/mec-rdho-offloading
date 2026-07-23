# V2 Experiment Execution Report

## Provenance

All numerical files were freshly generated from seeded V2 configurations after the physical CPU projection fix. Pre-fix outputs are outside the repository and are not consumed by any generator.

- Numerical experiment generation HEAD: `78c51c13ce7405654d488aea593d184be930e16a`.
- The generated numerical CSV artifacts first entered Git in `d2ca1139d325e21ab03f4db97a5e0c4e13149e8d`.
- Repository HEAD when this report was assembled: `72bc01105c45d29caf64218d5ffe820a00d62d2d`.
- Git diff check from numerical generation HEAD through report HEAD for `src/` and `configs/`: `PASS`.
- Git diff check from the numerical-artifact commit through report HEAD for raw experiment CSV paths: `PASS`.
- Publication reference: tag `v2-paper-artifacts-2026-07` on branch `research/physical-offloading-model-v2`.
- Git clean-check result captured before report assembly: PASS: worktree clean at phase-1 commit 72bc01105c45d29caf64218d5ffe820a00d62d2d before final report assembly.

## Execution commands

```bash
python -m experiments.run_main_30
python -m experiments.run_controlled_30
python -m experiments.run_ablation_30
python -m experiments.run_scalability
python -m experiments.run_sensitivity
python -m experiments.audit_task_id_neutrality
python -m experiments.generate_v2_artifacts
python -m pytest tests -q
```

## Environment and runtime

- Python: `3.9.6`; platform: `macOS-26.5.2-arm64-arm-64bit`.
- Dependencies: `numpy 2.0.2`, `pandas 2.3.3`, `scipy 1.13.1`, `matplotlib 3.9.4`, `PyYAML 6.0.3`.
- Accumulated solver timing across the nine raw experiment suites: `9994.534 s` (`2.776 h`). This is the sum of recorded per-run solver timings, not end-to-end wall-clock time.

## Validation

- Pytest: PASS: 38 tests passed locally on 2026-07-23 (14 third-party dependency deprecation warnings). Tests cover formulas and metrics, legal-node decoding, CPU bounds/capacity repair, fixed reporting fitness, controlled NFE, reproducibility artifacts, and manuscript-output guards.
- Raw audit: `1580` rows across nine suites; hard feasibility `PASS`; unique assignment `PASS`.
- Manifest audit: `58` entries; generated-file SHA-256 verification `PASS`.
- CI: [PASS: Tests/test on phase-1 commit 72bc011](https://github.com/Ryan-Yii/mec-rdho-offloading/actions/runs/29993308799/job/89160920552).
- All manuscript tables and figures are generated from the listed V2 CSV files; no paper value is entered manually.

## Result files

- `results/v2/raw/ablation_30_raw_results.csv`: 180 data rows; SHA-256 `4ba52615c577c4753905dbfde9947f924cc2edec14f9dec8752d5a835bde7a24`
- `results/v2/raw/common_control_30_convergence.csv`: 27180 data rows; SHA-256 `d3c3cbf749582beb542467501099e0c08bc54d3c7de6adff6acfbdec31125093`
- `results/v2/raw/common_control_30_raw_results.csv`: 180 data rows; SHA-256 `db56ded3c6d33a3b7c2bc709eb4a815d7b7bc5132db985d30bde3ed90971ed2a`
- `results/v2/raw/equal_nfe_30_convergence.csv`: 11400 data rows; SHA-256 `be00eedb701872b385b76100eb3a123687d92e3394453fbc13b04ee1148e6e15`
- `results/v2/raw/equal_nfe_30_raw_results.csv`: 150 data rows; SHA-256 `2d02cb7840578798bac37508497a4e25e018fc65aa184e837961bc6de512120c`
- `results/v2/raw/main_30_convergence.csv`: 22680 data rows; SHA-256 `465c1c33794c1f2de224cfdea43da0d4fcf10e1b511c88b6be0a88f6191bb2f0`
- `results/v2/raw/main_30_raw_results.csv`: 180 data rows; SHA-256 `f885d8dd171e277d351ef268449f0aa5179a26f6e9c66256d4596d37a360c639`
- `results/v2/raw/scalability_raw_results.csv`: 50 data rows; SHA-256 `292039fbcc59e528e0234afec5c7bae476d1f5f2c1bd901fa3cc91533aa413fb`
- `results/v2/raw/task_generation_ranges.csv`: 4 data rows; SHA-256 `f56a378e4d940b874f8648f498a52aeb525ca333fb7c4f8c69b4de7de7ac80e7`
- `results/v2/raw/task_parameters.csv`: 40 data rows; SHA-256 `a965a1d7e41c63ebecd8c787ae6f7fc94b3f66d1c96f0a799efef3a6c98dcd54`
- `results/v2/sensitivity/raw/dynamic_penalty_sensitivity_raw_results.csv`: 270 data rows; SHA-256 `2d1d601c1e5410250bc1b91e741757334d80d70106bf8d9f4bd6f29db2c15af7`
- `results/v2/sensitivity/raw/physical_sensitivity_raw_results.csv`: 270 data rows; SHA-256 `18ec3ebb09d485182e40467a7066be761b331c357cca41356211b25bf951e8cc`
- `results/v2/sensitivity/raw/utility_sensitivity_raw_results.csv`: 90 data rows; SHA-256 `80413001112864a8d6290bf28d95b4715e0b9024e9b06d0372ebf7b8997d6577`
- `results/v2/sensitivity/raw/weight_sensitivity_raw_results.csv`: 210 data rows; SHA-256 `b7a39e880e11ab82e0aa781f47b20c8714c9e93a9698a139853f0672de79f6b5`
- `results/v2/sensitivity/summary/dynamic_penalty_sensitivity_summary_mean_std.csv`: 9 data rows; SHA-256 `171647a1dbe903ae4a2d14cd68628a413829a407679309af9ab860b3eec0486c`
- `results/v2/sensitivity/summary/physical_sensitivity_summary_mean_std.csv`: 9 data rows; SHA-256 `6644c5a2036a50303ae98c2334f71719b1766774f2c17084c416c58db99d13a8`
- `results/v2/sensitivity/summary/utility_sensitivity_summary_mean_std.csv`: 3 data rows; SHA-256 `68f4582804b2360259f3149b468483a6329bd5fc23e33dd01b1ad66eaffcf6d7`
- `results/v2/sensitivity/summary/weight_sensitivity_summary_mean_std.csv`: 7 data rows; SHA-256 `895e89614fc7b02b9e8461e11379d65efb7eebe0b395d99fb217282faa1d8968`
- `results/v2/statistics/common_control_wilcoxon.csv`: 5 data rows; SHA-256 `c8f5326bedfdc61c43246613decf103191a415e885b6205be47a68a87c5fd6fb`
- `results/v2/statistics/equal_nfe_wilcoxon.csv`: 4 data rows; SHA-256 `895a21d570ee66f5aece60aaf093061b30e979d0cfecca9ed43457fd3422f853`
- `results/v2/statistics/wilcoxon_fitness_results.csv`: 5 data rows; SHA-256 `329e0e4ac900efe15b6f9fa1c8c0cceb9be3f7cd737bb472f3e41cfdda12d565`
- `results/v2/summary/ablation_30_summary_mean_std.csv`: 6 data rows; SHA-256 `ee9676fcecba07718efe696a72399eda8da721ad0def5ded2e5f96d7b2296d44`
- `results/v2/summary/common_control_30_summary_mean_std.csv`: 6 data rows; SHA-256 `8b21cc0152a79766dbab8d8f761d3b5fb57f1ad34aca73dfcf199d08f6eaf46f`
- `results/v2/summary/controlled_attribution_summary.csv`: 8 data rows; SHA-256 `724ae7f77ec7aef28e86bf2c4716c49057f6c7fc4f1eb6f8557f1b9803db88a7`
- `results/v2/summary/equal_nfe_30_summary_mean_std.csv`: 5 data rows; SHA-256 `58f69221aa734e038b5d44025435c009a4d0543ff03cd4f811ceac0a3f7b9d42`
- `results/v2/summary/main_30_summary_mean_std.csv`: 6 data rows; SHA-256 `751a936d794c642f640d6d9ae0309b153d728932c27e077c5188861feafa28d6`
- `results/v2/summary/scalability_summary_mean_std.csv`: 5 data rows; SHA-256 `e6d6c95c905c8a1cb05083e5a8fbf74019612bf3ac71147f35a10c8758fc6621`
- `results/v2/validation/task_id_neutrality.csv`: 3 data rows; SHA-256 `70fc4b38937407b29d64c73da863acdd0469686f636fd9aed609acff636d6288`
