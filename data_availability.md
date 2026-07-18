# Data and Code Availability

This repository contains the code and generated experimental artefacts used for the revised RDHO mobile edge computing study.

## Data source

All task and network instances are generated synthetically by `src/task_generator.py` from the ranges documented in:

- `results/raw/task_generation_ranges.csv`
- `results/raw/task_parameters.csv`
- `paper_tables/task_generation_ranges.md`

No proprietary, confidential, personal, or human-subject data are used.

## Code

- `src/`: system data structures, task generation, metrics, objective evaluation, and algorithm implementations.
- `experiments/`: reproducible main, ablation, scalability, sensitivity, statistical-analysis, and figure-generation entry points.
- `configs/`: YAML settings for each experiment family.
- `tests/`: regression tests covering objective decomposition, fixed reporting semantics, same-iteration penalty comparison, user-level fairness, coordinate-specific follower bounds, ablation isolation, main/ablation reference reuse, result export, statistical outputs, and figure generation.
- `tools/revise_manuscript.py`: earlier manuscript-generation helper retained for regression coverage.

## Result artefacts

Per-run outputs, convergence histories, summaries, statistical tests, and figures are stored in:

- `results/raw/`
- `results/summary/`
- `results/figures/`
- `results/sensitivity/`
- `paper_tables/`
- `figures/`

The main tables report a fixed-reference reporting fitness with penalty coefficient `lambda_ref = 1.0`. The iteration-dependent dynamic penalty is used only to guide RDHO's search. Raw components, search fitness, reporting fitness, runtime, and number of function evaluations are retained in the CSV outputs.

## Reproduction

Install the dependencies in `requirements.txt`, run `python -m pytest tests -q`, and execute the commands listed in `README.md`. For each paired run, all algorithms receive the same generated MEC scenario; their stochastic search streams use deterministic algorithm-specific seeds. RDHO component variants share the same base RDHO stream, and the ablation RDHO-full row reuses the paired main-run result rather than a second independent execution.

Public repository location:

https://github.com/Ryan-Yii/mec-rdho-offloading
