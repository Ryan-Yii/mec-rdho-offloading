from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import secrets
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
SUBJECT = "RDHO-based capacity-feasible MEC optimisation framework with strictly controlled population-update evidence"
REPLY = (
    "已按意见保留并前置 RDHO 作为本文特色。标题、摘要、引言和贡献部分均提前说明 "
    "RDHO-based 框架。同时根据新增严格受控实验，将创新表述限定为完整 RDHO 求解框架，"
    "不再将端到端优势直接归因于混合人口算子。"
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


def paragraph_updates() -> dict[int, str]:
    main = read_rows(ROOT / "results/v2/summary/main_30_summary_mean_std.csv", "algorithm")
    population = read_rows(ROOT / "results/summary/controlled_population_stage_30_summary.csv", "method")
    pipeline = read_rows(ROOT / "results/summary/controlled_common_pipeline_30_summary.csv", "method")
    stats = read_statistics(ROOT / "results/statistics/controlled_evidence_effect_sizes.csv")
    a_rime = stats[("controlled_population_stage", "RIME")]
    a_dbo = stats[("controlled_population_stage", "DBO")]
    b_rime = stats[("controlled_common_pipeline", "RIME")]
    b_dbo = stats[("controlled_common_pipeline", "DBO")]
    rdho_main = main["RDHO"]
    return {
        0: TITLE,
        6: (
            "Mobile edge computing (MEC) complements resource-limited devices with nearby edge and remote cloud resources, but heterogeneous tasks couple discrete execution-node choice with continuous processor allocation. This paper develops an RDHO-based capacity-feasible framework for joint task offloading and computing resource allocation: legal-node encoding and physical CPU decoding are coupled with deterministic capacity repair, RDHO population search, fixed-objective incumbent tracking and optional coordinate refinement. Under the configured end-to-end procedures, RDHO-full achieves the lowest mean reporting fitness. However, strictly controlled experiments with common initialisation, a shared decoder and repair path, equal total evaluation budgets and, where applicable, common refinement show that RDHO significantly outperforms RIME but is significantly outperformed by DBO. The evidence therefore supports the RDHO-based integrated framework rather than universal superiority of the hybrid population operator. Conclusions are limited to the stated simulated model and implemented baselines."
        ),
        7: "Keywords: mobile edge computing; RDHO; joint task offloading; computing resource allocation; capacity feasibility; controlled evaluation.",
        12: (
            "To address this problem, this study develops an RDHO-based optimisation framework that adapts RIME- and DBO-inspired population movements to legal-node selection, physical CPU allocation and deterministic capacity repair. The framework treats the benefit of the hybrid population mechanism as an empirical question rather than an assumption."
        ),
        13: (
            "The contributions are threefold. First, the paper formulates a capacity-feasible three-tier MEC model with legal local, edge and cloud execution, physical CPU-cycle-rate allocation, per-node aggregate capacity, device-side energy, delay, periodic AoI, priority-weighted aggregate QoE and priority-neutral active-user fairness. Second, it develops an RDHO-based integrated framework with legal-node population encoding, physical-resource decoding, deterministic reassignment and capacity projection, RIME-DBO-inspired population updates, dynamic search guidance, fixed reporting incumbents and optional coordinate refinement. Third, it reports paired controlled experiments with equal NFE, common initialisation, common repair, common refinement, Wilcoxon tests, Holm correction, rank-biserial effect sizes and wins/ties/losses. These experiments distinguish complete-pipeline evidence from isolated population-update evidence and show RDHO better than RIME but not DBO under the stated controls."
        ),
        14: (
            f"Under the configured end-to-end procedures, RDHO-full obtains mean reporting fitness {float(rdho_main['fitness_mean']):.3f}. This configured comparison has unequal NFE and evaluates complete solvers, not an isolated RIME-DBO population operator. The strictly controlled results reported in Section 6 show the narrower population-stage and common-pipeline conclusions."
        ),
        15: "Section 2 reviews related work. Sections 3 and 4 define the physical system and P1. Section 5 presents the RDHO-based capacity-feasible optimisation framework. Section 6 separates configured end-to-end and controlled population-update evidence, and Section 7 concludes.",
        98: "5 RDHO-Based Capacity-Feasible Optimisation Framework",
        99: (
            "RIME-DBO hybrid optimisation (RDHO) is the focal solver in this study. It adapts RIME-inspired perturbation and DBO-inspired role-conditioned movements to the capacity-feasible MEC encoding, decoder and repair path. RDHO-full additionally uses configured seeding and deterministic coordinate refinement; the framework is evaluated both as a complete solver and under controls that isolate its population-update stage."
        ),
        100: (
            "RIME-inspired and DBO-inspired movements are described as algorithmic components, not as mechanisms presumed to be stronger in advance. Their independent contribution is evaluated under common initialisation, common repair, equal total NFE and common refinement in Section 6.3."
        ),
        102: "RDHO is assessed as a configured capacity-feasible search framework. Controlled experiments, rather than the hybrid label alone, determine which population-update claims are supported.",
        103: "5.1 Solution Encoding and Physical-Resource Decoding",
        107: "5.2 RDHO Population-Update Mechanism",
        115: "RDHO-full applies deterministic coordinate refinement and then reports the common fixed objective. In the controlled experiments, RDHO-specific local refinement is disabled and the same deterministic refinement is either omitted for every method or applied to every method. This separates complete-pipeline evidence from the population-update comparison.",
        117: "Algorithm 1. RDHO-based capacity-feasible joint task-offloading and physical CPU-allocation strategy.",
        119: "Algorithm 1 retains the RDHO population-update sequence while making its common decoder, deterministic capacity repair, fixed-reference incumbent tracking and optional refinement explicit.",
        120: "6 Performance Evaluation",
        121: "6.1 Experimental Setup and Reproducibility",
        122: (
            "The configured V2 end-to-end experiments and the additive strictly controlled experiments use the same fixed synthetic scenarios 20260701-20260730, legal-node encoding, physical CPU decoder, deterministic capacity repair, hard-feasibility checks and fixed reporting objective. The controlled artifacts are generated from immutable raw CSV files and audited separately; they do not regenerate or modify results/v2/."
        ),
        123: "The configured end-to-end suite compares RDHO-full, RIME, DBO, TLBO-HHO [21], CWTSSA [36] and Greedy-ED under the same model, utility, repair and fixed reporting objective.",
        124: "The configured end-to-end comparison intentionally retains each solver's configured procedure; NFE is therefore unequal (RDHO-full 10,232, population baselines 7,551 and Greedy-ED 681). It is reported as a complete-solver comparison and cannot isolate the contribution of RDHO's population-update mechanism.",
        129: "Table 4. Algorithm and reproducibility parameters for the configured end-to-end comparison and controlled experiments.",
        131: "6.2 Configured End-to-End Solver Comparison",
        135: "Table 5. Configured end-to-end solver comparison over 30 paired scenarios (mean +/- standard deviation; unequal NFE).",
        136: f"RDHO-full has the lowest configured mean reporting fitness ({float(rdho_main['fitness_mean']):.3f} +/- {float(rdho_main['fitness_std']):.3f}) and every returned solution is hard feasible. Because RDHO-full uses 10,232 NFE while the population baselines use 7,551, this result supports the configured end-to-end solver rather than isolated superiority of its hybrid population update.",
        153: "Configured-comparison statistics.",
        154: "Two-sided paired Wilcoxon tests use the 30 matched reporting-fitness values. Holm adjustment controls the family-wise error rate; median paired difference, signed rank-biserial correlation and wins/ties/losses report magnitude and consistency. In this subsection, they test complete configured procedures with unequal NFE.",
        155: "Table 6. Paired Wilcoxon tests for configured end-to-end solvers (unequal NFE).",
        156: "RDHO-full is lower in all 30 pairs against each configured main baseline. These tests concern complete procedures with their configured initialisation, population search, incumbent tracking and refinement; they do not prove an isolated hybrid-operator advantage.",
        157: "6.3 Controlled Evaluation of the RDHO Population Mechanism",
        158: (
            "Two strictly controlled paired experiments answer the attribution question directly. Every method receives one identical 50-by-40-by-2 initial population per scenario, follows the common legal-node decoder and deterministic repair path, reports the same fixed reporting fitness and is constrained by an exact total NFE budget. All 90 returns in each experiment are hard feasible. The primary endpoint is lower fixed reporting fitness; paired differences are defined as DeltaF = F_RDHO - F_parent, so negative values favour RDHO."
        ),
        159: "Table 7. Strictly controlled RDHO population-stage and common-pipeline evidence over 30 paired scenarios.",
        161: "Fig. 8. Reporting fitness and soft CSR for configured RDHO variants.",
        162: "The configured ablation remains descriptive for the end-to-end RDHO workflow. Coordinate refinement changes configured mean fitness from 1.240 to 0.947, so it is one component of the complete-pipeline result; the controlled experiments below are the evidence for population-update attribution.",
        163: "6.4 Component, Refinement, Scalability, and Sensitivity Analyses",
        164: (
            f"Equal-NFE population-stage control (Experiment A) uses common initialisation, decoder and repair, disables coordinate refinement, and fixes total NFE at 3,801 for every method. RDHO reports {mean_sd(population['RDHO-population-controlled'])}, RIME {mean_sd(population['RIME-population-controlled'])} and DBO {mean_sd(population['DBO-population-controlled'])}. RDHO versus RIME has median DeltaF {float(a_rime['median_paired_difference']):.6f}, Holm p={pvalue(a_rime['p_value_holm'])}, rank-biserial {float(a_rime['rank_biserial']):.3f} and W/T/L {a_rime['wins_rdho']}/{a_rime['ties']}/{a_rime['losses_rdho']}; RDHO versus DBO has median DeltaF {float(a_dbo['median_paired_difference']):+.6f}, Holm p={pvalue(a_dbo['p_value_holm'])}, rank-biserial {float(a_dbo['rank_biserial']):+.3f} and W/T/L {a_dbo['wins_rdho']}/{a_dbo['ties']}/{a_dbo['losses_rdho']}. Thus RDHO significantly improves on RIME but is significantly worse than DBO."
        ),
        165: "Table 8. RDHO scalability under 20-100 tasks.",
        168: "Common-pipeline control (Experiment B) additionally applies the same deterministic coordinate refinement to every method and fixes total NFE at 10,232. RDHO reports " + mean_sd(pipeline['RDHO-common-pipeline']) + ", RIME " + mean_sd(pipeline['RIME-common-pipeline']) + " and DBO " + mean_sd(pipeline['DBO-common-pipeline']) + ". RDHO versus RIME has median DeltaF " + f"{float(b_rime['median_paired_difference']):.6f}, Holm p={pvalue(b_rime['p_value_holm'])}, rank-biserial {float(b_rime['rank_biserial']):.3f} and W/T/L {b_rime['wins_rdho']}/{b_rime['ties']}/{b_rime['losses_rdho']}; RDHO versus DBO has median DeltaF {float(b_dbo['median_paired_difference']):+.6f}, Holm p={pvalue(b_dbo['p_value_holm'])}, rank-biserial {float(b_dbo['rank_biserial']):+.3f} and W/T/L {b_dbo['wins_rdho']}/{b_dbo['ties']}/{b_dbo['losses_rdho']}. RDHO again significantly improves on RIME but is significantly worse than DBO.",
        169: "Component and refinement interpretation.",
        170: "The controlled results indicate that the implemented RDHO population mechanism improves substantially over RIME but does not improve on DBO in the fixed V2 scenarios. The contribution of RDHO in this study is therefore interpreted at the integrated-framework level, not as evidence of a universally superior hybrid population operator. Common coordinate refinement reduces the absolute gaps, but it does not reverse the controlled RDHO-versus-DBO ordering.",
        173: "Table 9. Additional configured attribution and sensitivity records (not a substitute for the strict controls in Table 7).",
        182: "Scalability and sensitivity.",
        184: "Overall interpretation.",
        185: "Fig. 12. Strictly controlled paired reporting-fitness evidence. Panels A and B use 3,801 and 10,232 total NFE, respectively; negative RDHO-minus-parent differences favour RDHO.",
        186: "Figure 12 visualises both controlled experiments rather than hiding the adverse comparison: RDHO is lower than RIME in 29/30 population-stage pairs and 23/30 common-pipeline pairs, but it is lower than DBO in 0/30 and 10/30 pairs, respectively. The Holm-adjusted tests are significant in all four comparisons. The configured RDHO-full result therefore demonstrates the effectiveness of the complete RDHO-based framework under its configured procedure, whereas the isolated population-update evidence does not support superiority over DBO.",
        188: "This work formulated a capacity-feasible MEC joint task-offloading and physical CPU-allocation model and developed RDHO as its focal integrated solver framework. Each task selects one legal source-local, reachable-edge or reachable-cloud node, and deterministic repair enforces physical Hz bounds and per-node capacity.",
        189: f"In the configured end-to-end comparison, RDHO-full has the lowest mean fixed reporting fitness ({float(rdho_main['fitness_mean']):.3f}) with hard feasibility in every returned solution, but this comparison has unequal NFE and evaluates complete solver configurations. The strict controls disclose the narrower result: at 3,801 NFE without refinement, RDHO is significantly lower than RIME but significantly higher than DBO; at 10,232 NFE with common refinement, RDHO is again significantly lower than RIME but significantly higher than DBO. Accordingly, the evidence supports the RDHO-based capacity-feasible framework and its controlled evaluation methodology, not independent or universal superiority of the RIME-DBO population update.",
        190: "Limitations include synthetic offline tasks, fixed-rate communication, deterministic cloud relay selection, device-side rather than infrastructure energy, a periodic no-backlog AoI approximation, coupled objective terms, engineering utility coefficients and the fixed set of implemented algorithms and 30 scenarios. Future work can investigate adaptive operator selection or DBO-dominant RDHO variants, queue-aware arrivals, communication-resource optimisation, infrastructure energy, calibrated QoE and physical testbeds without claiming that the present hybrid operator has already surpassed DBO.",
        200: "Code, configurations, controlled raw results, summaries, paired statistics, NFE and initial-population audits, figures and reproduction commands are archived in the local research repository. The existing V2 result files remain byte-identical; all reported data are synthetic, and no proprietary, confidential or human-subject data were used.",
    }


def table_values() -> dict[int, list[list[str]]]:
    population = read_rows(ROOT / "results/summary/controlled_population_stage_30_summary.csv", "method")
    pipeline = read_rows(ROOT / "results/summary/controlled_common_pipeline_30_summary.csv", "method")
    stats = read_statistics(ROOT / "results/statistics/controlled_evidence_effect_sizes.csv")
    algorithm = [
        ["Algorithm 1. RDHO-based capacity-feasible joint offloading and physical CPU allocation", "Algorithm 1. RDHO-based capacity-feasible joint offloading and physical CPU allocation"],
        ["Require:", "Scenario, legal-node encoding, physical decoder, deterministic repair, objective weights, population size and iterations"],
        ["Ensure:", "Hard-feasible incumbent on the fixed reporting objective"],
        ["1", "Generate the configured RDHO population and optional seed candidates"],
        ["2", "Decode legal nodes; repair capacity; evaluate the base objective and soft CSR"],
        ["3", "for each configured iteration do"],
        ["4", "Evaluate parents with the current dynamic penalty and assign RDHO roles"],
        ["5", "Generate RIME-DBO-inspired producer, follower and scout candidates"],
        ["6", "Decode and deterministically repair every candidate"],
        ["7", "Compare parent and candidate under the same current penalty"],
        ["8", "Update the independent fixed-objective incumbent"],
        ["9", "end for"],
        ["10", "If configured, apply deterministic coordinate refinement"],
        ["11", "Re-evaluate with fixed reporting coefficient 1 and verify hard feasibility"],
        ["Return", "Node assignments, CPU frequencies and all reported metrics"],
        ["Note", "Controlled experiments replace RDHO-specific initialisation/refinement with the common procedure before comparing population updates"],
    ]
    controlled = [["Experiment", "Method", "Mean +/- SD", "Median", "NFE", "Runtime (s)"]]
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
                mean_sd(row),
                f"{float(row['reporting_fitness_median']):.4f}",
                str(int(float(row["total_nfe_mean"]))),
                f"{float(row['runtime_s_mean']):.3f}",
            ])
    controlled.append(["Paired tests", "RDHO comparison", "Median DeltaF [95% CI]", "Holm p", "r_rb", "W/T/L"])
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
        ])
    parameters = [
        ["Parameter", "Value"],
        ["Configured end-to-end population / iterations", "50 / 150"],
        ["Objective weights (energy, delay, AoI, QoE, fairness)", "0.15, 0.15, 0.20, 0.25, 0.25"],
        ["Reporting coefficient", "Fixed at 1"],
        ["Paired scenarios", "30 (seeds 20260701-20260730)"],
        ["Experiment A control", "Common initial population, decoder and repair; no refinement; 3,801 total NFE"],
        ["Experiment B control", "Common initial population, decoder, repair and deterministic refinement; 10,232 total NFE"],
        ["Controlled statistics", "Two-sided paired Wilcoxon, experiment-local Holm correction, rank-biserial effect size, W/T/L"],
        ["Compared population methods", "RDHO, RIME and DBO"],
    ]
    return {1: algorithm, 4: parameters, 7: controlled}


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
            "last_generated_commit": "2a8fa7f",
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
    set_table_column_widths(tables[1], [1700, 7400])
    set_table_column_widths(tables[4], [3000, 6100])
    set_table_column_widths(tables[7], [1100, 1100, 2000, 1100, 850, 950])
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
        "# Comment Reply Audit: RDHO Repositioning",
        "",
        f"Editing base: `{source.name}`",
        f"Editing-base SHA-256: `{hashlib.sha256(source.read_bytes()).hexdigest()}`",
        "",
        "Every original comment/thread/reply/anchor is preserved in the annotated deliverable. "
        "The eight existing RDHO/innovation/front-loading threads listed below receive an additional threaded reply; every new commentEx has w15:done=0.",
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
