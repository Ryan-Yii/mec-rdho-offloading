# MEC RDHO Offloading Experiments

This repository contains the experimental implementation, raw results, and generated figures for the manuscript "Hybrid RIME-DBO Optimization for QoE- and Fairness-Aware Task Offloading in Mobile Edge Computing".

The implementation was developed and extended from internal research code with permission from the project contributors. This repository is organized as a clean reproduction and extension artifact rather than a renamed copy of the earlier project workspace.

## Repository layout

```text
mec-rdho-offloading/
├── configs/
├── experiments/
├── paper_tables/
├── results/
│   ├── raw/
│   ├── summary/
│   └── figures/
├── src/
│   ├── algorithms/
│   ├── utils/
│   ├── metrics.py
│   ├── system_model.py
│   └── task_generator.py
└── tests/
```

## Reproduce the experiments

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the validation tests:

```bash
python -m pytest tests -q
```

Run the main 30-run comparison:

```bash
python -m experiments.run_main_30
```

Run the ablation study:

```bash
python -m experiments.run_ablation_30
```

Run the scalability study:

```bash
python -m experiments.run_scalability
```

## Included result files

- `results/raw/main_30_raw_results.csv`
- `results/summary/main_30_summary_mean_std.csv`
- `results/summary/wilcoxon_fitness_results.csv`
- `results/raw/ablation_30_raw_results.csv`
- `results/summary/ablation_30_summary_mean_std.csv`
- `results/raw/scalability_raw_results.csv`
- `results/summary/scalability_summary_mean_std.csv`
- `results/raw/task_parameters.csv`
- `results/raw/task_generation_ranges.csv`
- `results/figures/convergence_curve.png`
- `results/figures/energy_comparison.png`
- `results/figures/delay_comparison.png`
- `results/figures/aoi_comparison.png`
- `results/figures/qoe_fairness_comparison.png`
- `results/figures/csr_comparison.png`
- `results/figures/ablation_study_multicolor.png`
- `results/figures/scalability.png`
- `results/figures/radar_chart.png`

## Experimental setting

The main experiment uses 20 mobile devices, 4 edge servers, 2 cloud servers, 40 tasks, population size 50, maximum iterations 150, and 30 independent runs. For a fixed seed, all algorithms run on the same generated task set. Task-generation ranges are exported in `results/raw/task_generation_ranges.csv` and `paper_tables/task_generation_ranges.md`.

Compared methods:

- RDHO
- RIME
- DBO
- TLBO-HHO
- CWTSSA
- Greedy-ED

The one-sided paired Wilcoxon signed-rank test compares RDHO fitness against RIME, DBO, TLBO-HHO, and CWTSSA across the 30 paired runs, using the alternative hypothesis that RDHO obtains lower fitness.
