# Data and Code Availability

All tasks, node capacities, link rates, and service parameters in this study are generated synthetically from versioned configurations and the ranges implemented in `src/task_generator.py`. No proprietary, personal, confidential, or human-subject data are used.

The fresh physical-model results are stored exclusively under `results/v2/`:

- `raw/`: per-seed main, equal-NFE, common-control, ablation, scalability, task, and convergence records;
- `summary/`: generated mean and standard-deviation summaries;
- `statistics/`: paired two-sided Wilcoxon tests, Holm corrections, effect sizes, and wins/ties/losses;
- `sensitivity/`: objective, dynamic-penalty, task-utility, CPU-capacity, SLA, and server-heterogeneity studies;
- `figures/`: generated plots. Local execution logs are non-versioned diagnostics and are not treated as reproducibility evidence.

Every result row retains the seed, algorithm, reporting objective and decomposition, device-side energy, delay, AoI, QoE, active-user fairness, soft CSR, hard-feasibility indicator, active-node capacity utilisation, runtime, and NFE as applicable. The main and controlled experiment hard-feasibility rates are 1.0 because all algorithms share the same legal-node decoder and deterministic capacity repair. CPU utilisation is reported independently, so feasibility is not confused with forced node saturation.

Install `requirements.txt`, run `python -m pytest tests -q`, and execute the commands in `README.md`. `python -m experiments.generate_v2_artifacts` rebuilds `paper_tables/v2/`, `figures/paper/v2/`, `paper_artifacts/manifest.csv`, and the experiment execution report solely from V2 data. The manifest records the source data, generation script, output hash, and manuscript location.

The publication snapshot is the fixed tag `v2-paper-artifacts-2026-07`. Numerical experiments were generated with source-tree HEAD `78c51c13ce7405654d488aea593d184be930e16a`; the raw artifacts first entered Git at `d2ca113`, and result-affecting `src/`, `configs/`, and numerical raw CSV content are unchanged between that generation state and the publication snapshot.

The public repository is:

https://github.com/Ryan-Yii/mec-rdho-offloading
