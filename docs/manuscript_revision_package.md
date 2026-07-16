# Manuscript Revision Package

Target journal: *International Journal of Sensor Networks*.

This package aligns the manuscript with the implemented repository model and
the finalized formal artifacts. Numerical claims below are derived from the
committed raw CSV files; no result was selected or removed to preserve an
expected ranking.

## 1. Locked Terminology

| Canonical term | Meaning in the revised manuscript | Do not use as a synonym |
|---|---|---|
| base objective, `F_0` | Weighted five-indicator objective without feasibility penalty | final fitness |
| search objective, `F_search` | Iteration-dependent objective used only for optimizer comparisons | reported fitness |
| reported objective, `F_report` | Fixed-scale objective used for tables and statistics | final dynamic penalised fitness |
| QoE proxy | Priority-weighted analytical utility derived from delay, energy, and freshness | validated subjective QoE or MOS |
| freshness proxy | Single-epoch `0.5 u_i + T_i` quantity | general dynamic AoI process |
| task-level QoE fairness | Jain index across task QoE-proxy values | device-level or user-level fairness |
| soft CSR | Fraction of satisfied delay, battery-aware energy, and freshness conditions | hard feasibility guarantee |
| maximum NFE | Common cap of 15,050 evaluator calls | identical realized NFE |
| Greedy-ED | Deterministic lower-cost supplementary heuristic | equal-budget population baseline |

One-sentence paper argument: In an offline simulated MEC task-offloading
problem with fixed routing, RDHO-full attains the lowest reported objective
among the tested methods under a common maximum-NFE protocol, while the new
ablation shows that the evidence supports dual-source initialization and local
refinement but does not support positive claims for every proposed core
component.

## 2. Accurate Implemented Formulation

### 2.1 Decision Encoding and Normalized Indicators

For `N` tasks, the implemented decision is

```math
X = \{X_i\}_{i=1}^{N}, \qquad X_i=[m_i,r_i],
\tag{1}
```

where `m_i in {0,1,2}` denotes local, edge, or cloud execution and
`r_i in [0.2,1.0]` is the resource ratio. The three normalized cost indicators
are

```math
\bar E(X)=\frac{1}{N}\sum_{i=1}^{N}\frac{E_i(X)}{E_i^{\max}},\quad
\bar T(X)=\frac{1}{N}\sum_{i=1}^{N}\frac{T_i(X)}{T_i^{\max}},\quad
\bar A(X)=\frac{1}{N}\sum_{i=1}^{N}\frac{A_i(X)}{A_i^{\max}}.
\tag{2}
```

These definitions must replace any normalization equation that is inconsistent
with the code.

### 2.2 Priority-Weighted Exponential QoE Proxy

The implemented task utility is

```math
q_i(X)=\operatorname{clip}_{[0,1]}\!\left[
p_i\left(
0.45e^{-T_i(X)/T_i^{\max}}+
0.30e^{-E_i(X)/E_i^{\max}}+
0.25e^{-A_i(X)/A_i^{\max}}
\right)\right],
\tag{3}
```

and the aggregate QoE proxy is

```math
Q(X)=\frac{1}{N}\sum_{i=1}^{N}q_i(X).
\tag{4}
```

Here, `p_i` is the generated task-priority coefficient. Equations (3)-(4)
must replace the old sigmoid delay satisfaction, piecewise battery acceptance,
and binary completion construction. Because no MOS data or user study is used,
the quantity must be called a **QoE proxy** or **QoE-inspired utility**.

### 2.3 Freshness Proxy

The implemented single-epoch freshness quantity is

```math
A_i(X)=0.5u_i+T_i(X),
\tag{5}
```

where `u_i` is the task update interval. This is a single-epoch freshness proxy,
not a queue-history-based dynamic AoI process.

### 2.4 Battery-Aware Soft Constraint Satisfaction Rate

Define the three task-level satisfaction indicators as

```math
c_i^T=\mathbb{I}[T_i(X)\le T_i^{\max}],
\tag{6}
```

```math
c_i^E=\mathbb{I}[E_i(X)\le E_i^{\max}\max(b_i,0.1)],
\tag{7}
```

```math
c_i^A=\mathbb{I}[A_i(X)\le A_i^{\max}],
\tag{8}
```

where `b_i` is the task battery ratio. The soft constraint satisfaction rate is

```math
\operatorname{CSR}(X)=\frac{1}{3N}\sum_{i=1}^{N}
\left(c_i^T+c_i^E+c_i^A\right).
\tag{9}
```

CSR is a continuous aggregate fraction even though each constituent check is
binary. It is used as a soft penalty signal rather than a hard repair rule.

### 2.5 Task-Level QoE Jain Fairness

The implemented fairness index is

```math
J_Q(X)=\frac{\left(\sum_{i=1}^{N}q_i(X)\right)^2}
{N\sum_{i=1}^{N}q_i^2(X)}.
\tag{10}
```

Because the index is calculated across tasks, every abstract, introduction,
results, and conclusion statement must call it **task-level QoE fairness**.

### 2.6 Three Objective Layers

With weights `w_E+w_T+w_A+w_Q+w_J=1`, the base objective is

```math
F_0(X)=w_E\bar E(X)+w_T\bar T(X)+w_A\bar A(X)
+w_Q[1-Q(X)]+w_J[1-J_Q(X)].
\tag{11}
```

For RDHO with dynamic penalty enabled, the iteration-dependent penalty scale is

```math
\lambda(t)=\lambda_0\left(1+\frac{2t}{T_{\max}}\right)^{\alpha},
\tag{12}
```

and the search objective is

```math
F_{\mathrm{search}}(X,t)=F_0(X)+\lambda(t)[1-\operatorname{CSR}(X)].
\tag{13}
```

`F_search` is used only to compare old and candidate populations after both
have been evaluated under the same current penalty scale. Other optimizers use
their configured constant search-penalty scale.

The cross-run reporting objective is

```math
F_{\mathrm{report}}(X)=F_0(X)+1.0[1-\operatorname{CSR}(X)].
\tag{14}
```

All final tables, convergence curves, paired tests, and cross-algorithm claims
use Equation (14). The CSV field `fitness` is exactly an alias of
`reported_fitness`. It must not be described as the final value of Equation
(13).

## 3. Implemented Model Boundary

The revised manuscript must state all of the following:

- The decision variable is only `X_i=[m_i,r_i]`.
- `m_i` chooses local, edge, or cloud execution; it does not choose a server
  index.
- Edge routing is fixed by `e_i = source_device_i mod N_edge`.
- Cloud routing is fixed by `c_i = e_i mod N_cloud`.
- The model has no server-index decision variable.
- The load-dependent CPU expressions reduce effective frequency but do not
  implement a strict aggregate CPU hard-capacity constraint or a corresponding
  capacity-repair operator.
- Tasks are generated offline and evaluated in a simulated, fixed-configuration
  MEC scenario.
- Equation (5) is a single-epoch freshness proxy; there is no dynamic arrival
  queue, update history, or service-order AoI process.

## 4. Statistical Protocol to Report

**Primary equal-budget inference.** RDHO, RIME, DBO, TLBO-HHO, CWTSSA, GA,
PSO, and DE share a maximum NFE of 15,050. All tests are paired by
`scenario_id + replicate_id`. The primary analysis comprises an eight-method
Friedman test and seven RDHO-versus-baseline two-sided paired Wilcoxon tests,
with Holm correction, rank-biserial effect size, wins/ties/losses, and a
10,000-resample paired bootstrap 95% confidence interval for the mean
difference.

**Supplementary heuristic comparison.** Greedy-ED uses the same scenarios and
`F_report`, but its deterministic construction uses a much smaller realized
NFE and runtime. Its RDHO comparison is therefore an effectiveness-versus-cost
analysis and is not included in the primary Friedman or Holm family.

The common maximum NFE must not be described as identical realized NFE. In the
weight study, RDHO used 15,011 evaluations and the other stochastic algorithms
used 15,050 because the optimizer stops at a population-batch boundary.

## 5. Paper-Ready English Text

### 5.1 Objective and Reporting Paragraph

> We distinguish the objective used during the search from the objective used
> for reporting. The base objective `F_0` combines normalized energy, delay,
> freshness, QoE-proxy loss, and task-level fairness loss. During RDHO search,
> constraint violations are weighted by the iteration-dependent scale in
> Equation (12); at each iteration, both the incumbent and candidate
> populations are re-evaluated under the same current scale. Final tables,
> convergence curves, and statistical tests instead use `F_report`, whose
> reporting penalty scale is fixed at 1.0. This separation makes fitness values
> comparable across iterations, algorithms, and sensitivity settings.

### 5.2 Main Experiment Paragraph

> Across 30 paired 40-task scenarios, RDHO obtained a mean reported objective
> of 0.996956 +/- 0.116808. DE was the closest stochastic baseline at
> 1.032838 +/- 0.117640, followed by CWTSSA at 1.068496 +/- 0.119158 and DBO at
> 1.069660 +/- 0.116734. RDHO achieved lower `F_report` than each of the seven
> stochastic baselines in all 30 paired scenarios. These results concern the
> implemented offline simulation and the scalar reporting objective; they do
> not establish superiority for every individual physical metric.

### 5.3 Primary and Supplementary Statistics Paragraph

> The equal-budget Friedman test detected an overall difference among the
> eight stochastic algorithms (`chi^2_F(7)=180.878`, `p=1.27e-35`). In the
> Holm-corrected paired analyses, RDHO outperformed each stochastic baseline in
> 30 wins, 0 ties, and 0 losses. The mean paired reduction relative to DE was
> 0.035882 (95% bootstrap CI: 0.031804 to 0.040157), and the rank-biserial
> effect was -1.0 under the `RDHO - baseline` difference convention. Greedy-ED
> achieved 1.088138 +/- 0.119198 in 0.216739 +/- 0.023129 s, whereas RDHO
> achieved 0.996956 +/- 0.116808 in 9.372593 +/- 0.564181 s. The paired
> RDHO-versus-Greedy comparison also favored RDHO in all 30 scenarios, but this
> result is reported separately because Greedy-ED does not use the same
> computational budget.

### 5.4 Ablation Paragraph

> The seven-variant ablation produced a significant omnibus difference
> (`chi^2_F(6)=114.157`, `p=2.74e-22`). Removing dual-source initialization
> degraded the reported objective from 1.012511 +/- 0.118987 to
> 1.137240 +/- 0.132601 (30/30 paired wins for RDHO-core; Holm-adjusted
> `p=1.12e-8`). Enabling local refinement improved the objective to
> 0.996734 +/- 0.115651 (RDHO-full better in 29/30 scenarios; adjusted
> `p=1.86e-8`). By contrast, disabling the hybrid RIME-DBO fusion improved the
> mean objective to 1.008006 +/- 0.116936 and outperformed RDHO-core in 23/30
> scenarios (adjusted `p=0.00687`). Adaptive role allocation, elite
> preservation, and dynamic penalty did not show significant paired effects
> after Holm correction (`p_adj=0.880`, `0.880`, and `0.760`, respectively).
> Thus, the current evidence supports dual-source initialization and local
> refinement, but it does not support a claim that every core component is
> beneficial; the implemented hybrid fusion requires redesign or additional
> validation.

### 5.5 Objective-Weight Sensitivity Paragraph

> Weight sensitivity was evaluated under five predefined objective-weight
> settings using the same eight stochastic algorithms, paired scenarios, and
> maximum NFE. RDHO ranked first in every setting with a mean paired rank of
> 1.00. The second-ranked method was DE, with mean ranks of 2.30, 2.73, 2.47,
> 2.40, and 2.57 for S1-S5, respectively. Each setting showed a significant
> Friedman result (`p<=6.68e-35`), and RDHO achieved 30 wins, 0 ties, and 0
> losses against every stochastic baseline within every setting; all
> Holm-adjusted pairwise `p` values were `1.30e-8`. Because each weight vector
> defines a different scalar objective, absolute fitness values were not
> compared across S1-S5.

### 5.6 Dynamic-Penalty Sensitivity Paragraph

> Across the nine predefined (`lambda_0`, `alpha`) combinations, mean
> `F_report` ranged from 0.994892 to 0.998355 and mean CSR ranged from 0.691389
> to 0.694722. The narrow variation indicates that the reported outcome is not
> tied to a single tested dynamic-penalty setting. This robustness should not
> be interpreted as evidence that the dynamic-penalty component improves
> RDHO-core, because its dedicated ablation was not significant.

### 5.7 Scalability Paragraph

> In the 10-run scalability study, the task count increased from 20 to 100
> under the same maximum-NFE configuration. Mean runtime increased from
> 4.688 +/- 0.216 s to 19.464 +/- 1.965 s, while mean CSR remained between
> 0.699 and 0.740 and mean `F_report` remained between 0.898 and 0.997. These
> results characterize computational scaling within the simulated offline
> model; they do not substitute for online-arrival or real-deployment tests.

### 5.8 Revised Limitation and Conclusion Text

> The objective-weight and dynamic-penalty sensitivity analyses indicate that
> the reported comparative result is not tied to a single tested weight vector
> or penalty-parameter setting. However, the present study remains limited to
> offline generated task sets and simulated MEC configurations with fixed
> edge/cloud routing. The freshness metric is a single-epoch proxy, and the
> fairness index is computed across tasks rather than devices. Moreover, the
> ablation does not provide positive support for every RDHO component: the
> hybrid-fusion removal performed significantly better than RDHO-core, while
> adaptive roles, elite preservation, and dynamic penalty were not
> significant. Future work should redesign and revalidate the fusion update,
> extend the model to dynamic online arrivals and time-varying resources, and
> evaluate device-level fairness and real edge deployment.

## 6. Replacement Tables

Use the committed files below as the authoritative table sources. Do not
retype values from an older manuscript version.

| Suggested no. | Recommended title | Authoritative source |
|---|---|---|
| Table 4 | Simulation configuration, objective weights, and maximum-NFE protocol | `configs/main_40tasks.yaml`, `paper_tables/task_generation_ranges.md`, `paper_tables/task_parameters.md` |
| Table 5 | Main comparison over 30 paired 40-task scenarios (mean +/- SD) | `paper_tables/main_30_summary_mean_std.md` |
| Table 6 | Primary equal-budget Friedman and Holm-corrected paired inference | `paper_tables/main_friedman_equal_budget.md`, `paper_tables/main_pairwise_equal_budget.md` |
| Table 7 | Seven-variant RDHO component and local-refinement ablation (mean +/- SD) | `paper_tables/ablation_30_summary_mean_std.md` |
| Table 8 | Holm-corrected paired ablation results with effect sizes and bootstrap CIs | `paper_tables/ablation_pairwise.md` |
| Table 9 | Within-setting algorithm ranks under S1-S5 objective weights | `paper_tables/weight_sensitivity_ranks.md` |
| Table 10 | Dynamic-penalty sensitivity for `lambda_0` and `alpha` | `paper_tables/dynamic_penalty_sensitivity_summary.md` |
| Table 11 | Scalability from 20 to 100 tasks (mean +/- SD over 10 runs) | `paper_tables/scalability_summary_mean_std.md` |

Greedy-ED must remain in Table 5 and runtime reporting. Its optional paired
test belongs in a separately labelled supplementary table sourced from
`paper_tables/main_greedy_supplementary.md`.

## 7. Replacement Figures

All manuscript figures must be inserted from these repository originals. Do
not use screenshots or images copied from an older Word file.

| Suggested no. | Recommended caption | Repository original |
|---|---|---|
| Figure 1 | Mean convergence of reported fitness over 30 paired scenarios | `figures/fig01_convergence_curve.png` |
| Figure 2 | Total energy consumption by algorithm | `figures/fig02_energy_comparison.png` |
| Figure 3 | Mean task delay by algorithm | `figures/fig03_delay_comparison.png` |
| Figure 4 | Mean single-epoch freshness proxy by algorithm | `figures/fig04_aoi_comparison.png` |
| Figure 5 | QoE proxy and task-level QoE fairness | `figures/fig05_qoe_fairness_comparison.png` |
| Figure 6 | Soft constraint satisfaction rate | `figures/fig06_soft_csr_comparison.png` |
| Figure 7 | Seven-variant RDHO ablation under a common maximum NFE | `figures/fig07_ablation_study.png` |
| Figure 8 | Scalability of `F_report`, CSR, and runtime with task count | `figures/fig08_scalability.png` |
| Figure 9 | Within-setting mean algorithm ranks for S1-S5 | `figures/fig09_weight_sensitivity_algorithm_ranks.png` |
| Figure 10 | Dynamic-penalty sensitivity of CSR and `F_report` | `figures/fig10_penalty_sensitivity_heatmaps.png` |
| Figure 11 | Normalized multi-metric comparison | `figures/fig11_normalized_multi_metric_radar.png` |

## 8. Old Claims That Must Be Deleted or Rewritten

1. Delete any statement that adaptive roles, elite preservation, and dynamic
   penalty all receive significant ablation support. None was significant in
   the finalized core ablation.
2. Delete any statement that the implemented hybrid RIME-DBO fusion is
   empirically validated as beneficial. Its removal was significantly better.
3. Do not call Jain fairness device-level, user-level, or fairness across
   users. Use **task-level QoE fairness**.
4. Do not call table fitness the final dynamic penalised objective. It is
   `F_report` with a fixed reporting penalty scale of 1.0.
5. Remove the old sigmoid delay, piecewise battery-energy acceptance, and
   completion-indicator QoE equations. Replace them with Equations (3)-(4).
6. Do not describe the QoE proxy as validated subjective experience, MOS, or
   user-reported QoE.
7. Do not describe Equation (5) as a general dynamic AoI scheduling model.
8. Do not claim server selection or strict CPU-capacity repair; neither is
   implemented.
9. Do not combine Greedy-ED with the primary equal-budget Friedman or Holm
   family.
10. Do not compare absolute `F_report` values across S1-S5; report within-setting
    ranks and paired tests instead.

## 9. Claim-Evidence Map

| Claim | Evidence | Status |
|---|---|---|
| RDHO ranks first among the eight stochastic algorithms in the main setting | Main raw CSV, Friedman, seven paired tests | Supported within the implemented benchmark |
| Comparative ranking is stable across S1-S5 | Five complete 30x8 paired blocks; RDHO mean rank 1.00 in each | Supported for the five predefined weight vectors |
| Reported outcomes are stable across tested penalty settings | Nine penalty combinations; narrow `F_report` and CSR ranges | Supported as sensitivity, not component efficacy |
| Dual-source initialization contributes positively | 30/30 core wins; adjusted `p=1.12e-8` | Supported |
| Local refinement contributes positively | RDHO-full wins 29/30; adjusted `p=1.86e-8` | Supported |
| Hybrid fusion contributes positively | No-hybrid variant wins 23/30; adjusted `p=0.00687` | Contradicted by current ablation |
| Adaptive roles contribute positively | Adjusted `p=0.880` | Not supported |
| Elite preservation contributes positively | Adjusted `p=0.880` | Not supported |
| Dynamic penalty contributes positively | Adjusted `p=0.760` | Not supported |
| Fairness is equitable across users/devices | Jain index is computed across tasks | Not supported; rewrite as task-level fairness |

## 10. Reproducibility Anchors

- Main audit: `docs/main_result_audit.md`.
- Formal ablation manifest: `results/manifests/ablation_30_manifest.json`.
- Formal weight manifest: `results/manifests/weight_sensitivity_manifest.json`.
- Unified analysis manifest: `results/manifests/postrun_analysis_manifest.json`.
- Raw main results: `results/raw/main_30_raw_results.csv`.
- Raw ablation results: `results/raw/ablation_30_raw_results.csv`.
- Raw weight results:
  `results/sensitivity/raw/weight_sensitivity_raw_results.csv`.
