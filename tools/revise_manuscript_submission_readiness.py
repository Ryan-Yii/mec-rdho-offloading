from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import secrets
import subprocess
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path

from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
W15 = "http://schemas.microsoft.com/office/word/2012/wordml"
W16CID = "http://schemas.microsoft.com/office/word/2016/wordml/cid"
W16CEX = "http://schemas.microsoft.com/office/word/2018/wordml/cex"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W, "w14": W14, "w15": W15, "w16cid": W16CID, "w16cex": W16CEX, "r": R, "pr": PR}

TITLE = (
    "RDHO-Based Capacity-Feasible Joint Task Offloading and Computing Resource "
    "Allocation in Mobile Edge Computing: A Controlled Evaluation"
)
SUBJECT = "RDHO-based capacity-feasible MEC optimisation framework with reproducible update and repair definitions"
REPLY = (
    "已按本轮投稿前意见补充 RDHO 全部更新、角色分配、两种坐标精炼和 NFE 定义，"
    "并新增确定性合法节点重分配/容量投影算法、固定返回解惩罚稳健性、运行环境和基线参数说明。"
    "严格受控结论仍保留 DBO 在实验 A 的明显优势与实验 B 的小但统计显著优势；线程保持未解决。"
)
TARGET_COMMENT_IDS = ("0", "2", "7", "12", "50", "52", "56", "61")


def qn(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def text_of(node: etree._Element) -> str:
    return "".join(node.xpath(".//w:t/text()", namespaces=NS)).strip()


def new_run(text: str, highlighted: bool) -> etree._Element:
    run = etree.Element(qn(W, "r"))
    rpr = etree.SubElement(run, qn(W, "rPr"))
    fonts = etree.SubElement(rpr, qn(W, "rFonts"))
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(W, attr), "Times New Roman")
    if highlighted:
        etree.SubElement(rpr, qn(W, "highlight")).set(qn(W, "val"), "yellow")
    etree.SubElement(run, qn(W, "t")).text = text
    return run


def replace_paragraph(paragraph: etree._Element, text: str, highlighted: bool) -> None:
    ppr = paragraph.find(qn(W, "pPr"))
    starts = [deepcopy(node) for node in paragraph.xpath(".//w:commentRangeStart", namespaces=NS)]
    ends = [deepcopy(node) for node in paragraph.xpath(".//w:commentRangeEnd", namespaces=NS)]
    refs = [deepcopy(node) for node in paragraph.xpath(".//w:r[w:commentReference]", namespaces=NS)]
    for child in list(paragraph):
        paragraph.remove(child)
    if ppr is not None:
        paragraph.append(deepcopy(ppr))
    paragraph.extend(starts)
    if text:
        paragraph.append(new_run(text, highlighted))
    paragraph.extend(ends)
    paragraph.extend(refs)


def replace_cell(cell: etree._Element, text: str, highlighted: bool) -> None:
    paragraphs = cell.xpath("./w:p", namespaces=NS)
    if not paragraphs:
        paragraphs = [etree.SubElement(cell, qn(W, "p"))]
    replace_paragraph(paragraphs[0], text, highlighted)
    for paragraph in paragraphs[1:]:
        replace_paragraph(paragraph, "", highlighted)


def fill_table(table: etree._Element, values: list[list[str]], highlighted: bool) -> None:
    rows = table.xpath("./w:tr", namespaces=NS)
    if len(rows) < len(values):
        if not rows:
            raise ValueError("cannot extend an empty table")
        template = rows[-1]
        for _ in range(len(values) - len(rows)):
            table.append(deepcopy(template))
        rows = table.xpath("./w:tr", namespaces=NS)
    for row_index, row in enumerate(rows):
        cells = row.xpath("./w:tc", namespaces=NS)
        data = values[row_index] if row_index < len(values) else []
        for cell_index, cell in enumerate(cells):
            replace_cell(cell, data[cell_index] if cell_index < len(data) else "", highlighted)


def set_table_column_widths(table: etree._Element, widths: list[int]) -> None:
    grid = table.find(qn(W, "tblGrid"))
    if grid is None:
        grid = etree.Element(qn(W, "tblGrid"))
        table.insert(1, grid)
    for node in list(grid):
        grid.remove(node)
    for width in widths:
        col = etree.SubElement(grid, qn(W, "gridCol"))
        col.set(qn(W, "w"), str(width))
    for row in table.xpath("./w:tr", namespaces=NS):
        for cell, width in zip(row.xpath("./w:tc", namespaces=NS), widths):
            properties = cell.find(qn(W, "tcPr"))
            if properties is None:
                properties = etree.Element(qn(W, "tcPr"))
                cell.insert(0, properties)
            cell_width = properties.find(qn(W, "tcW"))
            if cell_width is None:
                cell_width = etree.SubElement(properties, qn(W, "tcW"))
            cell_width.set(qn(W, "type"), "dxa")
            cell_width.set(qn(W, "w"), str(width))


def collapse_rows_to_one_cell(table: etree._Element) -> None:
    """Turn the retained legacy table into a readable one-column algorithm block."""

    for row in table.xpath("./w:tr", namespaces=NS):
        cells = row.xpath("./w:tc", namespaces=NS)
        if not cells:
            continue
        first = cells[0]
        properties = first.find(qn(W, "tcPr"))
        if properties is None:
            properties = etree.Element(qn(W, "tcPr"))
            first.insert(0, properties)
        grid_span = properties.find(qn(W, "gridSpan"))
        if grid_span is None:
            grid_span = etree.SubElement(properties, qn(W, "gridSpan"))
        grid_span.set(qn(W, "val"), str(len(cells)))
        for cell in cells[1:]:
            row.remove(cell)


def remove_highlights(root: etree._Element) -> None:
    for node in root.xpath(".//w:highlight", namespaces=NS):
        node.getparent().remove(node)


def read_rows(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row[key]: row for row in csv.DictReader(handle)}


def read_statistics(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            (row["experiment"], row["comparison"].split(" vs ")[1].split("-")[0]): row
            for row in csv.DictReader(handle)
        }


def mean_sd(row: dict[str, str]) -> str:
    return f"{float(row['reporting_fitness_mean']):.4f} +/- {float(row['reporting_fitness_std']):.4f}"


def pvalue(value: str) -> str:
    numeric = float(value)
    return f"{numeric:.3e}" if numeric < 0.001 else f"{numeric:.6f}"


def update_core_properties(payload: bytes) -> bytes:
    root = etree.fromstring(payload)
    dc = "http://purl.org/dc/elements/1.1/"
    for name, value in (("title", TITLE), ("subject", SUBJECT)):
        node = root.find(qn(dc, name))
        if node is None:
            node = etree.SubElement(root, qn(dc, name))
        node.text = value
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")


def machine_environment() -> str:
    """Return the observed local platform without implying a strict CPU affinity."""

    try:
        output = subprocess.check_output(["system_profiler", "SPHardwareDataType"], text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return "The local runtime platform could not be queried automatically; see the execution environment record."
    values = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        if key in {"Chip", "Total Number of Cores", "Memory"}:
            values[key] = value
    return "; ".join(f"{key}: {values[key]}" for key in ("Chip", "Total Number of Cores", "Memory") if key in values)


def penalty_rows() -> tuple[dict[tuple[str, float, str], dict[str, str]], dict[tuple[str, float, str], dict[str, str]]]:
    # Method labels repeat at every lambda/experiment, so construct the needed composite keys.
    with (ROOT / "results/statistics/controlled_reporting_penalty_sensitivity.csv").open(newline="", encoding="utf-8") as handle:
        summary_rows = {
            (row["experiment"], float(row["lambda_ref"]), row["method"]): row for row in csv.DictReader(handle)
        }
    with (ROOT / "results/statistics/controlled_reporting_penalty_sensitivity_paired.csv").open(newline="", encoding="utf-8") as handle:
        paired_rows = {
            (row["experiment"], float(row["lambda_ref"]), row["comparison"]): row for row in csv.DictReader(handle)
        }
    return summary_rows, paired_rows


def paragraph_updates() -> dict[int, str]:
    main = read_rows(ROOT / "results/v2/summary/main_30_summary_mean_std.csv", "algorithm")
    population = read_rows(ROOT / "results/summary/controlled_population_stage_30_summary.csv", "method")
    pipeline = read_rows(ROOT / "results/summary/controlled_common_pipeline_30_summary.csv", "method")
    stats = read_statistics(ROOT / "results/statistics/controlled_evidence_effect_sizes.csv")
    sensitivity, sensitivity_pairs = penalty_rows()
    a_rime = stats[("controlled_population_stage", "RIME")]
    a_dbo = stats[("controlled_population_stage", "DBO")]
    b_rime = stats[("controlled_common_pipeline", "RIME")]
    b_dbo = stats[("controlled_common_pipeline", "DBO")]
    rdho_main = main["RDHO"]
    a_dbo_low = sensitivity_pairs[("controlled_population_stage", 0.5, "RDHO vs DBO")]
    a_dbo_high = sensitivity_pairs[("controlled_population_stage", 2.0, "RDHO vs DBO")]
    b_dbo_low = sensitivity_pairs[("controlled_common_pipeline", 0.5, "RDHO vs DBO")]
    b_dbo_high = sensitivity_pairs[("controlled_common_pipeline", 2.0, "RDHO vs DBO")]
    return {
        0: TITLE,
        6: (
            "Mobile edge computing (MEC) complements resource-limited devices with nearby edge and remote cloud resources, but heterogeneous tasks couple discrete execution-node choice with allocated CPU-cycle-rate decisions. This paper develops an RDHO-based capacity-feasible framework: legal-node encoding and allocated CPU-cycle-rate decoding are coupled with deterministic capacity repair, RDHO population search, fixed-objective incumbent tracking and optional coordinate refinement. Under configured end-to-end procedures, RDHO-full achieves the lowest mean reporting fitness. Strict controls with common initialisation, decoder/repair path, exact NFE and common refinement show DBO clearly outperforms RDHO in Experiment A; at the prespecified reporting coefficient lambda_ref=1, DBO retains a smaller but statistically significant advantage in Experiment B. The smaller Experiment-B difference is sensitive to the fixed reporting-penalty coefficient. The evidence supports the integrated RDHO framework rather than universal superiority of its hybrid population update."
        ),
        7: "Keywords: mobile edge computing; RDHO; joint task offloading; computing resource allocation; capacity feasibility; controlled evaluation.",
        12: (
            "To address this problem, this study develops an RDHO-based optimisation framework that adapts RIME- and DBO-inspired population movements to legal-node selection, allocated CPU-cycle-rate decisions and deterministic capacity repair. The framework treats the benefit of the hybrid population mechanism as an empirical question rather than an assumption."
        ),
        13: (
            "The contributions are threefold. First, the paper formulates a capacity-feasible three-tier MEC model with legal local, edge and cloud execution, allocated CPU-cycle-rate decisions, aggregate node capacity, device-side energy, delay, periodic AoI, priority-weighted aggregate QoE and priority-neutral active-user fairness. Second, it develops an RDHO-based integrated framework with legal-node population encoding, allocated-rate decoding, deterministic reassignment and projection, RIME-DBO-inspired updates, dynamic search guidance, fixed reporting incumbents and optional refinement. Third, it reports paired controls with equal NFE, common initialisation/repair/refinement, Wilcoxon tests, Holm correction, rank-biserial effects and wins/ties/losses."
        ),
        14: (
            f"Under the configured end-to-end procedures, RDHO-full obtains mean reporting fitness {float(rdho_main['fitness_mean']):.3f}. This configured comparison has unequal NFE and evaluates complete solvers, not an isolated RIME-DBO population operator. The strictly controlled results reported in Section 6 show the narrower population-stage and common-pipeline conclusions."
        ),
        15: "Section 2 reviews related work. Sections 3 and 4 define the physical system and P1. Section 5 presents the RDHO-based capacity-feasible optimisation framework. Section 6 separates configured end-to-end and controlled population-update evidence, and Section 7 concludes.",
        18: "Model-based studies jointly allocate communication and computation resources or coordinate edge-cloud execution under explicit system constraints [3,11,13,14]. Legal collaboration topology and resource budgets must be represented before optimising task placement.",
        19: "Learning-based methods adapt policies to changing states and have been applied to online offloading, vehicular cooperation and blockchain-enabled edge-cloud systems [12,15-17]. Their training and data requirements motivate complementary transparent offline optimisation for a fixed decision epoch.",
        22: "Representative studies on parking-edge cooperation, blockchain-enabled edge-cloud offloading, cooperative deep reinforcement learning and potential-game strategies show how collaboration topology, resource coupling and service requirements alter offloading decisions [37-40]. A remaining methodological gap is a reproducible framework that combines capacity-feasible allocated CPU-cycle-rate decisions with priority-weighted system QoE and priority-neutral active-user fairness, while experimentally separating initialisation, evaluation budget, population updates and refinement.",
        23: "The present work addresses that combined methodological and evaluation gap for a simulated cloud-edge-device epoch; it does not claim that allocated CPU-cycle-rate modelling alone is novel, nor does it claim communication-resource optimisation, online queue scheduling or deployment validation.",
        26: "Consider devices, edge servers, cloud servers and tasks in a three-tier architecture. Their union uses global node IDs. Fixed topology and link rates are assumed during one decision epoch so that the optimisation focuses on execution-node choice and allocated CPU-cycle-rate decisions. Figure 1 illustrates the legal choices and shared aggregate CPU-cycle-capacity pools.",
        29: "Fig. 1. Three-tier cloud-edge-device architecture with legal execution-node choices and shared aggregate CPU-cycle-capacity pools.",
        30: "Task i is generated by source device d(i). Local execution is legal only at d(i); reachable edge nodes have positive device-edge rates; a cloud node is legal only through at least one reachable edge with a positive backhaul rate. For a selected cloud, evaluation uses the legal relay with minimum task-specific input-transmission delay. This is deterministic path evaluation, not route or bandwidth optimisation.",
        32: "Binary x_ij selects exactly one node j. The derived layer is local, edge or cloud, and f_i is the allocated CPU-cycle rate of task i (cycles/s), not an independently additive processor clock. F_j is the aggregate CPU-cycle capacity of node j. For local DVFS f_i is an effective execution frequency; at edge/cloud it is a computation service rate allocated to the task.",
        33: "Each search individual stores two normalised coordinates per task. The node coordinate indexes the sorted legal-node set, while internal resource coordinate r_i decodes to a tentative allocated CPU-cycle rate. Both coordinates are clipped to [0,1]; r_i is an algorithmic coordinate, not a physical resource unit.",
        35: "For node j with minimum allocatable CPU-cycle rate f_j^min and aggregate capacity F_j, the tentative request is f_i^req=f_j^min+r_i(F_j-f_j^min).",
        37: "Algorithm 2 defines complete deterministic repair. At each pass it computes minimum-rate use, visits overloaded nodes in ascending global ID, then visits their assigned task indices in descending order. For each task it considers only legal alternatives other than its current node that can accept that task at the alternative node minimum rate.",
        39: "Among feasible alternatives, Algorithm 2 selects the node with largest post-move residual minimum-rate slack, breaking ties by the smallest global node ID. It recomputes use after the move in the next pass. At most N times the number of nodes passes are allowed. If this deterministic order cannot construct a feasible minimum-rate reassignment for the decoded candidate, evaluation raises ValueError; this does not prove that the entire scenario has no feasible assignment under another move sequence. The exception propagates and aborts the affected optimiser run: the implementation does not assign +infinity, retain the parent, or resample. The controlled evaluator records the repair failure before re-raising; all reported controlled runs have repair_failure_count=0. Targets are already minimum-rate feasible, preventing an overload cycle within a completed repair.",
        41: "Once every minimum allocation fits, each node retains decoded requests if their total excess over task minima fits its residual capacity; otherwise only that excess is proportionally projected. Thus every allocated CPU-cycle rate remains no lower than the selected node minimum, and no non-overloaded request is silently saturated.",
        43: "No heuristic congestion attenuation or M/M/1 queue is added, because finite CPU capacity and repaired allocated CPU-cycle rates represent processor scarcity. Fixed edge/cloud overheads are synthetic simulation parameters.",
        46: "For edge or cloud offloading, the selected edge or legal cloud relay is fixed by the decoded path. The reported device-side energy includes uplink transmission only; infrastructure computation and backhaul energy are outside the boundary and this metric is never labelled total system energy.",
        48: "The task-result size is assumed negligible relative to the input size; result-return delay and downlink energy are omitted. Device-edge rates are independently sampled U(8,30) Mbit/s then independently removed with probability 0.10; edge-cloud rates are independently sampled U(60,150) Mbit/s then independently removed with probability 0.05. If a device has no positive edge link, one uniformly selected edge is resampled from U(8,30); if a cloud has no incoming positive backhaul link, one uniformly selected edge is resampled from U(60,150). Repair changes only the absent link and does not alter existing sampled rates.",
        72: "The parameter ranges are synthetic heterogeneous settings designed to generate capacity-constrained MEC instances; they are not claimed as direct hardware calibration. Their orders of magnitude are consistent with representative MEC system and joint resource-allocation studies [1,3,11,13]. The same versioned ranges are applied to every algorithm and are examined through capacity, SLA and heterogeneity sensitivity analyses.",
        96: "A returned incumbent consists of one repaired legal node and one allocated CPU-cycle rate per task.",
        97: "These characteristics motivate population search over legal categorical assignments and bounded allocated CPU-cycle-rate decisions; no deployment claim is made.",
        98: "5 RDHO-Based Capacity-Feasible Optimisation Framework",
        99: (
            "RIME-DBO hybrid optimisation (RDHO) is the focal solver in this study. It adapts RIME-inspired perturbation and DBO-inspired role-conditioned movements to the capacity-feasible MEC encoding, decoder and Algorithm-2 repair path. RDHO-full additionally uses configured seeding and local coordinate refinement; the framework is evaluated both as a complete solver and under controls that isolate its population-update stage. The definitions below reproduce the implemented RDHO rather than requiring the reader to infer its operations from source code."
        ),
        100: (
            "RIME-inspired and DBO-inspired movements are described as algorithmic components, not as mechanisms presumed to be stronger in advance. Their independent contribution is evaluated under common initialisation, common repair, equal total NFE and common refinement in Section 6.3."
        ),
        102: "RDHO is assessed as a configured capacity-feasible search framework. Controlled experiments, rather than the hybrid label alone, determine which population-update claims are supported.",
        103: "5.1 Solution Encoding, Initialisation, and Capacity Decoding",
        104: "Individual X has N rows x_i=(u_i,r_i), with u_i and r_i in [0,1]. u_i maps by floor(u_i times the number of sorted legal nodes) to a legal node, and r_i decodes to the tentative allocated CPU-cycle rate above. Every generated coordinate is clipped component-wise to [0,1] before Algorithm 2, metric evaluation and hard-feasibility checks.",
        105: "With population P=50, the first floor(P/2) members are Gaussian: node coordinates are independent N(0.55,0.25) and resource coordinates independent N(0.60,0.20); the remainder are independent U(0,1). RDHO replaces member 0 with a greedy seed: begin every task at (0.5,0.5), visit task indices in ascending order, test the 16 pairs {0.08,0.35,0.62,0.90} times {0.20,0.50,0.80,1.00}, and retain only a strict fixed-reporting-fitness improvement. Members 1, 2 and 3, when present, are the seed plus independent N(0,0.08) perturbations, then clipped. These are the three perturbations; no additional trigger is used.",
        107: "5.2 RDHO Population-Update Mechanism",
        108: "At iteration t, p=t/T_max and diversity D is the mean over all 2N coordinates of their population standard deviation. Adaptive producer and scout shares are rho_P=clip(0.28-0.10p+0.08D,0.14,0.34) and rho_S=clip(0.08+0.08D+0.04p,0.08,0.20); rho_F=max(0.40,1-rho_P-rho_S). Nominal counts n_P, n_F and n_S are max(1,floor(P rho_role)) and are computed from the full P; they are not renormalised to P-n_E after n_E=max(1,floor(0.10P)) elites are reserved. The ranked loop applies deterministic branch precedence: an elite is copied; otherwise rank<n_P gives producer, else rank<n_P+n_F gives follower, else rank>=P-n_S gives scout, else the member receives N(0,0.04(1-p)) noise. Thus elites truncate nominal roles, and if follower/scout thresholds overlap the earlier follower branch takes precedence; no member is assigned twice.",
        109: "For producer current x, search-best x_b and search-worst x_w, draw beta~N(0,1) per coordinate, theta~U(0,2pi) per coordinate, k~U(-1,1) per coordinate and b~U(0,1). Define R=x_b+beta cos(theta)2(1-p)0.28 and D=x+(1-p)k x+b|x-x_w|. The update is x'=wR+(1-w)D with w=0.5+0.3 cos(pi p), decreasing from 0.8 to 0.2.",
        110: "For a follower, q=min(1,2 exp(-(4p)^2)). With probability q, draw one Bernoulli(0.20) mask per task and replace both coordinates of every masked task by x_b (RIME-inspired puncture). Otherwise draw independent c1,c2~U(0,1) per coordinate and use x'=x_b+c1 x+c2(x-1), then clip to [0,1] (bound-aware DBO-inspired foraging).",
        111: "For scout rank r, set x_L to the member at ranked index floor(0.35r). If its current search fitness exceeds the current best, draw theta~U(-pi/4,pi/4) per coordinate and use theft x'=x_L+tan(theta)|x-x_L|. Otherwise draw standard Cauchy noise z per coordinate and use x'=x_b+0.035(1-p)z. The Cauchy scale is exactly 0.035(1-p).",
        112: "All stated random variables are independent unless their shared task mask is stated. The continuous updates define only a neighbourhood: after clipping, u_i is decoded through that task's legal list and Algorithm 2 always precedes evaluation.",
        113: "Parents and candidates are evaluated under the same iteration search penalty before strict greedy acceptance. Separately, the reporting incumbent is replaced only by a strict improvement in F_report=B+1(1-CSR); dynamic search fitness is not reported as a final cross-algorithm result.",
        114: "Configured RDHO local refinement uses a seeded random permutation of task indices, up to two sweeps, node grid {0.08,0.28,0.48,0.68,0.88}, resource grid {0.10,0.30,0.55,0.80,1.00}, and strict fixed-reporting improvement; it stops after a sweep with no improvement. Controlled common refinement instead uses ascending task order and exactly one 5-by-5 sweep for every method: 25 evaluations per task, or 1,000 NFE for 40 tasks. Experiment A has 50+3,750+1=3,801 NFE; Experiment B has 50+9,181+1,000+1=10,232 NFE.",
        115: "For N tasks, M execution nodes, population P, iterations T_max, average legal-node count L and refinement cost R, initialisation is O(PN) plus O(16N) greedy tests, role updates are O(PN), and ordinary decoding/evaluation is approximately O(PNL). A typical repair pass is O(NL); retaining this practical cost gives O(PN+T_max PNL+RNL) time and O(PN+NL) space. In the worst case repair may execute up to NM passes, so one candidate can require O(N^2 M L) repair work and the population-search upper bound includes O(T_max P N^2 M L). This conservative worst case is distinct from the observed zero-failure controlled runs and is not an optimality guarantee.",
        117: "Algorithm 1. Reproducible RDHO-based capacity-feasible joint task-offloading and allocated CPU-cycle-rate strategy.",
        119: "Algorithm 1 summarises the fully specified update sequence; Algorithm 2 specifies common deterministic legal-node reassignment and excess-capacity projection used by every solver.",
        120: "6 Performance Evaluation",
        121: "6.1 Experimental Setup and Reproducibility",
        122: (
            "The configured V2 end-to-end experiments and additive strictly controlled experiments use the same fixed synthetic scenarios 20260701-20260730, legal-node encoding, allocated-CPU-cycle-rate decoder, deterministic repair, hard-feasibility checks and fixed reporting objective. Controlled artifacts are generated from immutable raw CSV files and audited separately; they do not regenerate or modify results/v2/. The recorded local environment was macOS 26.5.2 on Apple M5 (10 cores, 32 GB memory), Python 3.9.6, NumPy 2.0.2, pandas 2.3.3 and SciPy 1.13.1. Experiment loops use no Python multiprocessing and no explicit thread pinning; all compared methods use the same serial runner configuration. Runtime is a local implementation-cost observation, not a cross-platform benchmark."
        ),
        123: "The configured end-to-end suite compares RDHO-full, RIME, DBO, TLBO-HHO [21], CWTSSA [36] and Greedy-ED under the same model, utility, repair and fixed reporting objective. RIME, DBO, TLBO-HHO and CWTSSA constants are listed in Table 4 from executable versioned defaults; they remain fixed over every reported scenario, and no algorithm-specific tuning was performed on the reporting scenarios.",
        124: "The configured end-to-end comparison intentionally retains each solver's configured procedure; NFE is therefore unequal (RDHO-full 10,232, population baselines 7,551 and Greedy-ED 681). It is reported as a complete-solver comparison and cannot isolate the contribution of RDHO's population-update mechanism.",
        129: "Table 4. Reproducibility, RDHO, and baseline parameter settings (fixed across reported scenarios).",
        131: "6.2 Configured End-to-End Solver Comparison",
        135: "Table 5. Configured end-to-end solver comparison over 30 paired scenarios (mean +/- standard deviation; unequal NFE).",
        136: f"RDHO-full has the lowest configured mean reporting fitness ({float(rdho_main['fitness_mean']):.3f} +/- {float(rdho_main['fitness_std']):.3f}) and every returned solution is hard feasible. Because RDHO-full uses 10,232 NFE while the population baselines use 7,551, this result supports the configured end-to-end solver rather than isolated superiority of its hybrid population update.",
        153: "Configured-comparison statistics.",
        154: "Two-sided paired Wilcoxon tests use the 30 matched reporting-fitness values. Holm adjustment controls the family-wise error rate; median paired difference, signed rank-biserial correlation and wins/ties/losses report magnitude and consistency. In this subsection, they test complete configured procedures with unequal NFE.",
        155: "Table 6. Paired Wilcoxon tests for configured end-to-end solvers (unequal NFE).",
        156: "RDHO-full is lower in all 30 pairs against each configured main baseline. These tests concern complete procedures with their configured initialisation, population search, incumbent tracking and refinement; they do not prove an isolated hybrid-operator advantage.",
        157: "6.3 Strictly Controlled RDHO Population Evidence",
        158: (
            "Two strictly controlled paired experiments answer the attribution question directly. Every method receives one identical 50-by-40-by-2 initial population per scenario, follows the common legal-node decoder and Algorithm-2 repair, reports the same fixed reporting fitness and is constrained by an exact total NFE budget. All 90 returns in each experiment are hard feasible. Table 7 reports reporting fitness, base objective B, soft CSR, QoE, fairness, NFE and runtime. The primary endpoint is lower fixed reporting fitness; paired differences DeltaF=F_RDHO-F_parent are negative when RDHO is lower. Experiment A (no refinement, 3,801 NFE) gives DBO a clear advantage: RDHO versus DBO median DeltaF={:+.6f}, Holm p={} and W/T/L={}/{}/{}. At the prespecified lambda_ref=1, Experiment B (common refinement, 10,232 NFE) gives DBO a smaller but statistically significant advantage: means {:.4f} versus {:.4f}, difference {:.6f}; median DeltaF={:+.6f}, Holm p={} and W/T/L={}/{}/{}. RDHO remains lower than RIME in both controls."
        ).format(
            float(a_dbo["median_paired_difference"]), pvalue(a_dbo["p_value_holm"]), a_dbo["wins_rdho"], a_dbo["ties"], a_dbo["losses_rdho"],
            float(pipeline["RDHO-common-pipeline"]["reporting_fitness_mean"]), float(pipeline["DBO-common-pipeline"]["reporting_fitness_mean"]),
            float(pipeline["RDHO-common-pipeline"]["reporting_fitness_mean"]) - float(pipeline["DBO-common-pipeline"]["reporting_fitness_mean"]),
            float(b_dbo["median_paired_difference"]), pvalue(b_dbo["p_value_holm"]), b_dbo["wins_rdho"], b_dbo["ties"], b_dbo["losses_rdho"],
        ),
        159: "Table 7. Strictly controlled fixed-return evidence over 30 paired scenarios: reporting fitness and components, QoE, fairness, NFE and runtime.",
        161: "Fig. 8. Reporting fitness and soft CSR for configured RDHO variants.",
        162: "The configured ablation remains descriptive for the end-to-end RDHO workflow. Coordinate refinement changes configured mean fitness from 1.240 to 0.947, so it is one component of the complete-pipeline result; population-update attribution is reported in Table 7 above, not inferred from this configured ablation.",
        163: "6.4 Component, Refinement, Scalability, and Sensitivity Analyses",
        164: "Configured component/refinement analysis begins here. It is descriptive for the complete RDHO workflow, whereas Table 7 provides the formal common-initialisation, common-decoder, common-repair, exact-NFE and common-refinement attribution evidence. The full legacy configured-comparison rows previously presented as Table 9 are moved to the repository supplement to prevent confusion with the strict controls.",
        165: "Table 8. RDHO scalability under 20-100 tasks.",
        168: "Scalability and configured sensitivity describe the RDHO framework outside the strict attribution controls. They do not override Table 7. Dynamic-search-penalty sensitivity changes only search guidance; fixed reporting fitness remains B+1(1-CSR).",
        169: "Component and refinement interpretation.",
        170: "The controlled results indicate that the implemented RDHO population mechanism improves substantially over RIME but not DBO in the fixed V2 scenarios. The contribution is therefore interpreted at the integrated-framework level, not as universal population-update superiority. Common refinement reduces the absolute DBO gap but does not reverse it at lambda_ref=1.",
        173: "Algorithm 2. Deterministic legal-node reassignment and excess-capacity projection shared by all solvers.",
        182: "Scalability and sensitivity.",
        184: "Fixed-return reporting-penalty robustness and overall interpretation.",
        185: "Fig. 12. Strictly controlled paired reporting-fitness evidence. Panels A and B use 3,801 and 10,232 total NFE, respectively; negative RDHO-minus-parent differences favour RDHO.",
        186: "Figure 12 visualises both controls rather than hiding the adverse comparison: RDHO is lower than RIME in 29/30 population-stage pairs and 23/30 common-pipeline pairs, but lower than DBO in 0/30 and 10/30 pairs. For fixed returned solutions, post-hoc rescoring F_lambda=B+lambda_ref(1-CSR) at lambda_ref in 0.5, 1 and 2 does not re-optimise or select another incumbent. DBO remains significantly lower than RDHO in Experiment A at all three values (Holm p <= {}); in Experiment B it remains significant at 0.5 (Holm p={}) and 1 (Holm p={}), but not at 2 (Holm p={}). Thus the small Experiment-B DBO advantage is penalty-definition-sensitive for fixed returns, while Experiment-A is robust. The configured RDHO-full result demonstrates the complete framework; isolated population-update evidence does not support superiority over DBO."
        .format(pvalue(a_dbo_low["p_value_holm"]), pvalue(b_dbo_low["p_value_holm"]), pvalue(b_dbo["p_value_holm"]), pvalue(b_dbo_high["p_value_holm"])),
        188: "This work formulated a capacity-feasible MEC joint task-offloading and allocated CPU-cycle-rate model and developed RDHO as its focal integrated solver framework. Each task selects one legal source-local, reachable-edge or reachable-cloud node, and deterministic repair enforces allocated-rate bounds and aggregate CPU-cycle capacity.",
        189: f"In the configured end-to-end comparison, RDHO-full has the lowest mean fixed reporting fitness ({float(rdho_main['fitness_mean']):.3f}) with hard feasibility in every returned solution, but this comparison has unequal NFE and evaluates complete solver configurations. The strict controls disclose the narrower result: at 3,801 NFE without refinement, RDHO is significantly lower than RIME but significantly higher than DBO; at 10,232 NFE with common refinement, RDHO is again significantly lower than RIME but significantly higher than DBO. Accordingly, the evidence supports the RDHO-based capacity-feasible framework and its controlled evaluation methodology, not independent or universal superiority of the RIME-DBO population update.",
        190: "Limitations include synthetic offline tasks, fixed-rate communication, deterministic cloud relay selection, device-side rather than infrastructure energy, a periodic no-backlog AoI approximation, coupled objective terms, engineering utility coefficients and the fixed set of implemented algorithms and 30 scenarios. Energy, delay and AoI also enter QoE, while delay enters AoI and all three reappear in CSR; the current study does not isolate the incremental contribution of each nested objective layer. Future work can investigate objective-layer ablation, adaptive operator selection or DBO-dominant RDHO variants, queue-aware arrivals, communication-resource optimisation, infrastructure energy, calibrated QoE and physical testbeds without claiming that the present hybrid operator has already surpassed DBO.",
        200: "Code and synthetic data are available at https://github.com/Ryan-Yii/mec-rdho-offloading. The controlled fixed-return raw CSVs are results/raw/controlled_population_stage_30_raw_results.csv and results/raw/controlled_common_pipeline_30_raw_results.csv; reproduce the penalty check with python -m tools.analyze_controlled_reporting_penalty_sensitivity. A public immutable GitHub tag/release containing this submission-readiness revision and manuscript artifacts must be created before formal submission; this local revision is not represented as an already-published release. Existing results/v2/ files remain byte-identical, and no proprietary, confidential or human-subject data were used.",
    }


def table_values() -> dict[int, list[list[str]]]:
    population = read_rows(ROOT / "results/summary/controlled_population_stage_30_summary.csv", "method")
    pipeline = read_rows(ROOT / "results/summary/controlled_common_pipeline_30_summary.csv", "method")
    stats = read_statistics(ROOT / "results/statistics/controlled_evidence_effect_sizes.csv")
    algorithm = [
        ["Algorithm 1. Reproducible RDHO joint offloading and allocated CPU-cycle-rate allocation", "Algorithm 1. Reproducible RDHO joint offloading and allocated CPU-cycle-rate allocation"],
        ["Require:", "Scenario, legal-node encoding, Algorithm 2 repair, objective weights, P, T_max and a seeded RNG"],
        ["Ensure:", "Hard-feasible fixed-reporting incumbent"],
        ["1", "Generate Gaussian/uniform subpopulations; insert greedy seed and exactly three N(0,0.08) seed perturbations when positions 1-3 exist"],
        ["2", "Decode legal nodes, run Algorithm 2, and evaluate B, CSR, current search fitness and fixed reporting fitness"],
        ["3", "for each configured iteration do"],
        ["4", "Compute diversity, adaptive role counts and current search ranking; preserve the top 10% elites"],
        ["5", "Generate the stated producer fusion, follower puncture/foraging, scout theft/Cauchy, or remaining Gaussian candidates; clip to [0,1]"],
        ["6", "Run the shared decoder and Algorithm 2 for every candidate; an unrepaired candidate raises ValueError and aborts the run (no +infinity, parent retention or resampling)"],
        ["7", "Strictly compare parent and candidate under the same current search penalty"],
        ["8", "Strictly update the independent fixed-reporting incumbent"],
        ["9", "end for"],
        ["10", "If configured, apply seeded two-sweep RDHO refinement; controls instead use one common ascending 5-by-5 sweep or none"],
        ["11", "Re-evaluate with lambda_ref=1 and verify unique legal assignment, allocated-rate bounds and aggregate capacity"],
        ["Return", "Node assignments, allocated CPU-cycle rates and all reported metrics"],
        ["Control", "Controlled experiments replace RDHO-specific initialisation/refinement with common procedures before population-update comparison"],
    ]
    controlled = [["Experiment", "Method", "F_report / B / CSR (mean)", "QoE", "Fairness", "NFE", "Runtime (s)"]]
    for experiment, names in (
        ("A: population stage", ("RDHO-population-controlled", "RIME-population-controlled", "DBO-population-controlled")),
        ("B: common pipeline", ("RDHO-common-pipeline", "RIME-common-pipeline", "DBO-common-pipeline")),
    ):
        source = population if experiment.startswith("A") else pipeline
        for name in names:
            row = source[name]
            controlled.append([
                experiment,
                name.split("-")[0],
                f"{float(row['reporting_fitness_mean']):.4f} / {float(row['base_objective_mean']):.4f} / {float(row['soft_csr_mean']):.4f}",
                f"{float(row['qoe_mean']):.4f}",
                f"{float(row['fairness_mean']):.4f}",
                str(int(float(row["total_nfe_mean"]))),
                f"{float(row['runtime_s_mean']):.3f}",
            ])
    controlled.append(["Paired tests", "RDHO comparison", "Median DeltaF [95% CI]", "Holm p", "r_rb", "W/T/L", ""])
    for experiment, baseline in (
        ("controlled_population_stage", "RIME"),
        ("controlled_population_stage", "DBO"),
        ("controlled_common_pipeline", "RIME"),
        ("controlled_common_pipeline", "DBO"),
    ):
        row = stats[(experiment, baseline)]
        controlled.append([
            "A" if experiment.endswith("stage") else "B",
            f"RDHO vs {baseline}",
            f"{float(row['median_paired_difference']):+.6f} [{float(row['median_difference_ci95_low']):+.6f}, {float(row['median_difference_ci95_high']):+.6f}]",
            pvalue(row["p_value_holm"]),
            f"{float(row['rank_biserial']):+.3f}",
            f"{row['wins_rdho']}/{row['ties']}/{row['losses_rdho']}",
            "",
        ])
    parameters = [
        ["Parameter", "Value"],
        ["Configured end-to-end population / iterations", "50 / 150"],
        ["Objective weights (energy, delay, AoI, QoE, fairness)", "0.15, 0.15, 0.20, 0.25, 0.25"],
        ["Reporting coefficient", "Fixed lambda_ref=1; fixed-return post-hoc checks at 0.5, 1, 2 only"],
        ["Paired scenarios", "30 (seeds 20260701-20260730)"],
        ["Experiment A control", "Common initial population, decoder and repair; no refinement; 3,801 total NFE"],
        ["Experiment B control", "Common initial population, decoder, repair and deterministic refinement; 10,232 total NFE"],
        ["Controlled statistics", "Two-sided paired Wilcoxon, experiment-local Holm correction, rank-biserial effect size, W/T/L"],
        ["Compared population methods", "RDHO, RIME and DBO"],
        ["RDHO Gaussian source", "Node N(0.55,0.25); resource N(0.60,0.20); other half U(0,1)"],
        ["RDHO greedy seed / perturbations", "16 grid pairs in ascending task order; seed plus N(0,0.08) at positions 1-3"],
        ["RDHO role / elite constants", "producer clip(0.28-0.10p+0.08D,0.14,0.34); scout clip(0.08+0.08D+0.04p,0.08,0.20); elite 10%"],
        ["RDHO producer / follower", "w=0.5+0.3cos(pi p); RIME scale 0.28; puncture q=min(1,2exp(-(4p)^2)), mask 0.20"],
        ["RDHO scout / remaining", "theft angle U(-pi/4,pi/4); Cauchy scale 0.035(1-p); remaining N(0,0.04(1-p))"],
        ["RIME baseline", "normal initialisation; h=2(1-p); exploration scale 0.30; puncture noise 0.035; repository default"],
        ["DBO baseline", "rolling/breeding/foraging/theft 0.20/0.20/0.40/0.20; rolling decay 1-p; repository default"],
        ["TLBO-HHO baseline", "teaching threshold 0.55; learner-HHO threshold 0.80; teaching factors {1,2}; HHO energy 2(1-p); repository default"],
        ["CWTSSA baseline", "producer/scout 0.20/0.10; inertia 0.9-0.5p; t df=3, scale=0.12; Cauchy p=0.20, scale=0.025; repository default"],
        ["Parameter provenance", "Synthetic heterogeneous settings from versioned generator/configuration; not hardware calibrated; no scenario-specific tuning"],
    ]
    repair = [
        ["Algorithm 2. Deterministic Legal-Node Reassignment and Capacity Projection"],
        ["Require: decoded legal node IDs and requested allocated CPU-cycle rates; node minima and aggregate capacities."],
        ["1. For at most N times number-of-nodes passes, compute minimum-rate use of each node."],
        ["2. Visit overloaded nodes in ascending global ID; visit their currently assigned task indices in descending order."],
        ["3. For a task, consider legal nodes other than its current node; retain only targets that remain within capacity after receiving that task at the target minimum rate."],
        ["4. Move the task to the feasible target with largest post-move residual slack; break ties by smallest global node ID. Recompute use on the next pass."],
        ["5. If the deterministic order cannot construct a feasible minimum-rate reassignment for this decoded candidate, raise ValueError and abort the affected optimiser run; do not infer global scenario infeasibility, assign +infinity, retain the parent or resample."],
        ["6. When minima fit, set every task to its node minimum. Retain requested excess if total excess fits residual capacity; otherwise proportionally scale only the excess."],
        ["Ensure: legal unique assignments, allocated rates within selected-node bounds and aggregate capacity; repair targets are pre-feasible, so no overload cycle is introduced."],
    ]
    return {1: algorithm, 4: parameters, 7: controlled, 9: repair}


def comment_text(comment: etree._Element) -> str:
    return "\n".join(text_of(paragraph) for paragraph in comment.xpath("./w:p", namespaces=NS) if text_of(paragraph))


def comment_para_id(comment: etree._Element) -> str:
    values = comment.xpath("./w:p/@w14:paraId", namespaces=NS)
    if not values:
        raise ValueError("comment has no paraId")
    return values[-1]


def make_reply(
    comments: etree._Element,
    extended: etree._Element,
    ids: etree._Element,
    extensible: etree._Element,
    parent: etree._Element,
    next_id: int,
    used_para: set[str],
    used_durable: set[str],
) -> dict[str, str]:
    while True:
        para_id = secrets.token_hex(4).upper()
        if para_id not in used_para:
            used_para.add(para_id)
            break
    while True:
        durable_id = secrets.token_hex(4).upper()
        if durable_id not in used_durable:
            used_durable.add(durable_id)
            break
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    reply = etree.SubElement(comments, qn(W, "comment"))
    reply.set(qn(W, "id"), str(next_id))
    reply.set(qn(W, "author"), "祎宝")
    reply.set(qn(W, "date"), now)
    reply.set(qn(W, "initials"), "")
    paragraph = etree.SubElement(reply, qn(W, "p"))
    paragraph.set(qn(W14, "paraId"), para_id)
    paragraph.set(qn(W14, "textId"), "77777777")
    paragraph.append(new_run(REPLY, highlighted=False))
    ex = etree.SubElement(extended, qn(W15, "commentEx"))
    ex.set(qn(W15, "paraId"), para_id)
    ex.set(qn(W15, "paraIdParent"), comment_para_id(parent))
    ex.set(qn(W15, "done"), "0")
    cid = etree.SubElement(ids, qn(W16CID, "commentId"))
    cid.set(qn(W16CID, "paraId"), para_id)
    cid.set(qn(W16CID, "durableId"), durable_id)
    cex = etree.SubElement(extensible, qn(W16CEX, "commentExtensible"))
    cex.set(qn(W16CEX, "durableId"), durable_id)
    cex.set(qn(W16CEX, "dateUtc"), now)
    return {
        "parent_comment_id": parent.get(qn(W, "id"), ""),
        "parent_author": parent.get(qn(W, "author"), ""),
        "parent_comment": comment_text(parent),
        "parent_para_id": comment_para_id(parent),
        "reply_comment_id": str(next_id),
        "reply_para_id": para_id,
        "reply": REPLY,
        "resolved": "false",
    }


def append_targeted_replies(parts: dict[str, bytes]) -> list[dict[str, str]]:
    comments = etree.fromstring(parts["word/comments.xml"])
    extended = etree.fromstring(parts["word/commentsExtended.xml"])
    ids = etree.fromstring(parts["word/commentsIds.xml"])
    extensible = etree.fromstring(parts["word/commentsExtensible.xml"])
    by_id = {node.get(qn(W, "id")): node for node in comments.xpath("./w:comment", namespaces=NS)}
    next_id = max(int(value) for value in by_id) + 1
    used_para = set(ids.xpath("./w16cid:commentId/@w16cid:paraId", namespaces=NS))
    used_durable = set(ids.xpath("./w16cid:commentId/@w16cid:durableId", namespaces=NS))
    rows = []
    for comment_id in TARGET_COMMENT_IDS:
        parent = by_id.get(comment_id)
        if parent is None:
            raise ValueError(f"missing required original comment {comment_id}")
        row = make_reply(comments, extended, ids, extensible, parent, next_id, used_para, used_durable)
        rows.append(row)
        next_id += 1
    parts["word/comments.xml"] = etree.tostring(comments, xml_declaration=True, encoding="UTF-8", standalone="yes")
    parts["word/commentsExtended.xml"] = etree.tostring(extended, xml_declaration=True, encoding="UTF-8", standalone="yes")
    parts["word/commentsIds.xml"] = etree.tostring(ids, xml_declaration=True, encoding="UTF-8", standalone="yes")
    parts["word/commentsExtensible.xml"] = etree.tostring(extensible, xml_declaration=True, encoding="UTF-8", standalone="yes")
    return rows


COMMENT_PARTS = {
    "word/comments.xml",
    "word/commentsExtended.xml",
    "word/commentsExtensible.xml",
    "word/commentsIds.xml",
    "word/people.xml",
}


def strip_comments(path: Path, output: Path) -> None:
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            if info.filename in COMMENT_PARTS or info.filename == "word/_rels/comments.xml.rels":
                continue
            payload = source.read(info.filename)
            if info.filename.endswith(".xml") or info.filename == "word/_rels/document.xml.rels":
                root = etree.fromstring(payload)
                if info.filename == "word/document.xml":
                    for node in root.xpath(".//w:commentRangeStart | .//w:commentRangeEnd | .//w:commentReference", namespaces=NS):
                        node.getparent().remove(node)
                elif info.filename == "word/_rels/document.xml.rels":
                    for node in list(root):
                        if "comment" in node.get("Type", "").lower() or node.get("Type", "").endswith("/people"):
                            root.remove(node)
                elif info.filename == "[Content_Types].xml":
                    for node in list(root):
                        if "comment" in node.get("PartName", "").lower() or "people" in node.get("PartName", "").lower():
                            root.remove(node)
                payload = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")
            target.writestr(info, payload)


def update_manifest(output: Path) -> None:
    rows = []
    assets = [
        ("Table 7", "Strict controlled evidence", "results/raw/controlled_population_stage_30_raw_results.csv; results/raw/controlled_common_pipeline_30_raw_results.csv", "paper_tables/controlled_evidence_statistics.csv", "Section 6.3"),
        ("Penalty robustness", "Fixed-return reporting-penalty sensitivity", "results/raw/controlled_population_stage_30_raw_results.csv; results/raw/controlled_common_pipeline_30_raw_results.csv", "results/statistics/controlled_reporting_penalty_sensitivity_paired.csv", "Section 6.3"),
        ("RDHO parameters", "Reproducible update and refinement definitions", "src/algorithms/rdho.py; src/algorithms/base.py", "configs/baseline_parameters.yaml", "Section 5 and Table 4"),
        ("Figure 12", "Strictly controlled RDHO evidence", "tools/generate_controlled_paper_figure.py", "figures/paper/figure_12_controlled_rdho_evidence.png", "Section 6.3 and 6.6"),
        ("Figure 12", "Strictly controlled RDHO evidence", "tools/generate_controlled_paper_figure.py", "figures/paper/figure_12_controlled_rdho_evidence.pdf", "Section 6.3 and 6.6"),
        ("Figure 12", "Strictly controlled RDHO evidence", "tools/generate_controlled_paper_figure.py", "figures/paper/figure_12_controlled_rdho_evidence.svg", "Section 6.3 and 6.6"),
        ("Revision report", "RDHO framework repositioning", "results/statistics/controlled_evidence_effect_sizes.csv", "docs/framework_repositioning_report.md", "Delivery documentation"),
        ("Execution report", "Controlled-evidence manuscript execution", "results/audit/controlled_initial_population_audit.csv; results/audit/controlled_*_nfe_audit.csv", "docs/controlled_manuscript_execution_report.md", "Delivery documentation"),
    ]
    for item, title, source, generated, location in assets:
        path = ROOT / generated
        rows.append({
            "manuscript_item": item,
            "title": title,
            "source": source,
            "generated_file": generated,
            "file_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
            "last_generated_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "inserted_manuscript_location": location,
        })
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build(source: Path, output_dir: Path) -> None:
    source = source.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    reviewed = output_dir / "RDHO_capacity_feasible_controlled_evaluation_with_comments.docx"
    clean_with_comments = output_dir / "RDHO_capacity_feasible_controlled_evaluation_clean_with_comments.tmp.docx"
    clean = output_dir / "RDHO_capacity_feasible_controlled_evaluation_clean.docx"
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        parts = {info.filename: archive.read(info.filename) for info in infos}
    parts["docProps/core.xml"] = update_core_properties(parts["docProps/core.xml"])
    root = etree.fromstring(parts["word/document.xml"])
    paragraphs = root.xpath(".//w:body//w:p[not(ancestor::w:tbl)]", namespaces=NS)
    if len(paragraphs) != 243:
        raise ValueError(f"expected 243 body paragraphs, found {len(paragraphs)}")
    for index, text in paragraph_updates().items():
        replace_paragraph(paragraphs[index], text, highlighted=True)
    tables = root.xpath("./w:body/w:tbl", namespaces=NS)
    if len(tables) != 11:
        raise ValueError(f"expected 11 tables, found {len(tables)}")
    for table_index, values in table_values().items():
        fill_table(tables[table_index], values, highlighted=True)
    notation_updates = {
        7: "Tentative allocated CPU-cycle-rate request of task i (cycles/s)",
        8: "Repaired allocated CPU-cycle rate of task i (cycles/s)",
        9: "Minimum allocatable CPU-cycle rate of node j (cycles/s)",
        10: "Aggregate CPU-cycle capacity of node j (cycles/s)",
        13: "CPU-cycle capacity remaining after minimum allocations",
    }
    for row_index, value in notation_updates.items():
        replace_cell(tables[0].xpath("./w:tr", namespaces=NS)[row_index].xpath("./w:tc", namespaces=NS)[1], value, highlighted=True)
    system_updates = {
        3: "Aggregate CPU-cycle capacity: device 2.2-3.0; edge 18-28; cloud 55-75 Gcycles/s",
        4: "Minimum allocated CPU-cycle rate: device 0.2; edge 0.8; cloud 1.5 Gcycles/s",
    }
    for row_index, value in system_updates.items():
        replace_cell(tables[2].xpath("./w:tr", namespaces=NS)[row_index].xpath("./w:tc", namespaces=NS)[1], value, highlighted=True)
    collapse_rows_to_one_cell(tables[9])
    set_table_column_widths(tables[1], [1700, 7400])
    set_table_column_widths(tables[4], [3000, 6100])
    set_table_column_widths(tables[7], [1100, 900, 2650, 700, 750, 750, 750])
    set_table_column_widths(tables[9], [9100])
    # Algorithm 2 originates from the former Table 9 slot but belongs beside
    # the repair equations, before delay modelling and all later references.
    algorithm_two_caption = paragraphs[173]
    repair_equation_end = paragraphs[40]
    repair_equation_end.addnext(algorithm_two_caption)
    algorithm_two_caption.addnext(tables[9])
    parts["word/document.xml"] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")
    parts["word/media/image13.png"] = (ROOT / "figures/paper/figure_12_controlled_rdho_evidence.png").read_bytes()
    audit_rows = append_targeted_replies(parts)
    with zipfile.ZipFile(reviewed, "w", zipfile.ZIP_DEFLATED) as target:
        for info in infos:
            target.writestr(info, parts[info.filename])
        for name, payload in parts.items():
            if name not in {item.filename for item in infos}:
                target.writestr(name, payload)

    clean_parts = dict(parts)
    clean_root = etree.fromstring(clean_parts["word/document.xml"])
    remove_highlights(clean_root)
    clean_parts["word/document.xml"] = etree.tostring(clean_root, xml_declaration=True, encoding="UTF-8", standalone="yes")
    with zipfile.ZipFile(clean_with_comments, "w", zipfile.ZIP_DEFLATED) as target:
        for info in infos:
            target.writestr(info, clean_parts[info.filename])
        for name, payload in clean_parts.items():
            if name not in {item.filename for item in infos}:
                target.writestr(name, payload)
    strip_comments(clean_with_comments, clean)

    with (output_dir / "comment_reply_audit.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(audit_rows)
    audit_lines = [
        "# Comment Reply Audit: RDHO Submission-Readiness Revision",
        "",
        f"Editing base: `{source.name}`",
        f"Editing-base SHA-256: `{hashlib.sha256(source.read_bytes()).hexdigest()}`",
        "",
        "Every original comment/thread/reply/anchor is preserved in the annotated deliverable. "
        "The eight existing RDHO/innovation/front-loading threads listed below receive an additional threaded reply; every new commentEx has w15:done=0. "
        "The editing base already contains the prior eight replies, so this revision preserves 138 base comments and adds eight new replies.",
        "",
        "| Parent ID | Reply ID | Parent paraId | Resolved | Reply |",
        "| ---: | ---: | --- | --- | --- |",
    ]
    for row in audit_rows:
        audit_lines.append(f"| {row['parent_comment_id']} | {row['reply_comment_id']} | `{row['parent_para_id']}` | {row['resolved']} | {row['reply']} |")
    (output_dir / "comment_reply_audit.md").write_text("\n".join(audit_lines) + "\n", encoding="utf-8")
    update_manifest(output_dir / "paper_artifact_manifest.csv")
    print(reviewed)
    print(clean)
    print(output_dir / "comment_reply_audit.csv")
    print(output_dir / "paper_artifact_manifest.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description="Revise the latest annotated MEC manuscript from audited controlled evidence.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output_dir)


if __name__ == "__main__":
    main()
