from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import re
import secrets
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Optional

from lxml import etree
import pypandoc


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "v2"
SOURCE = ROOT / "manuscript_source.docx"
OUTPUT_DIR = ROOT / "manuscript_outputs"
REVIEWED = OUTPUT_DIR / "0712_physical_model_v2_revised_with_comments.docx"
CLEAN_WITH_COMMENTS = OUTPUT_DIR / "0712_physical_model_v2_clean_with_comments.tmp.docx"
AUDIT_CSV = OUTPUT_DIR / "comment_reply_audit.csv"
AUDIT_MD = OUTPUT_DIR / "comment_reply_audit.md"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
W15 = "http://schemas.microsoft.com/office/word/2012/wordml"
W16CID = "http://schemas.microsoft.com/office/word/2016/wordml/cid"
W16CEX = "http://schemas.microsoft.com/office/word/2018/wordml/cex"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
DC = "http://purl.org/dc/elements/1.1/"
NS = {"w": W, "w14": W14, "w15": W15, "w16cid": W16CID, "w16cex": W16CEX, "r": R, "pr": PR, "a": A, "m": M}

MANUSCRIPT_TITLE = "RDHO-Based Joint Task Offloading and Computing Resource Allocation in Mobile Edge Computing"
MANUSCRIPT_SUBJECT = "Physical MEC offloading model V2 with fresh controlled experiments and synchronized reproducibility artifacts"


def qn(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def configure_paths(source: Path, output_dir: Path) -> None:
    global SOURCE, OUTPUT_DIR, REVIEWED, CLEAN_WITH_COMMENTS, AUDIT_CSV, AUDIT_MD
    SOURCE = source
    OUTPUT_DIR = output_dir
    REVIEWED = OUTPUT_DIR / "0712_physical_model_v2_revised_with_comments.docx"
    CLEAN_WITH_COMMENTS = OUTPUT_DIR / "0712_physical_model_v2_clean_with_comments.tmp.docx"
    AUDIT_CSV = OUTPUT_DIR / "comment_reply_audit.csv"
    AUDIT_MD = OUTPUT_DIR / "comment_reply_audit.md"


def read_rows(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row[key]: row for row in csv.DictReader(handle)}


def f(row: dict[str, str], name: str, digits: int = 3) -> str:
    return f"{float(row[name]):.{digits}f}"


def pm(row: dict[str, str], name: str, digits: int = 3) -> str:
    return f"{float(row[name + '_mean']):.{digits}f} ({float(row[name + '_std']):.{digits}f})"


def new_run(text: str, highlighted: bool, math: bool = False) -> etree._Element:
    run = etree.Element(qn(W, "r"))
    rpr = etree.SubElement(run, qn(W, "rPr"))
    fonts = etree.SubElement(rpr, qn(W, "rFonts"))
    family = "Cambria Math" if math else "Times New Roman"
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(W, attr), family)
    if highlighted:
        highlight = etree.SubElement(rpr, qn(W, "highlight"))
        highlight.set(qn(W, "val"), "yellow")
    node = etree.SubElement(run, qn(W, "t"))
    if text.startswith(" ") or text.endswith(" "):
        node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    node.text = text
    return run


def replace_paragraph(paragraph: etree._Element, text: str, highlighted: bool, math: bool = False) -> None:
    ppr = paragraph.find("w:pPr", namespaces=NS)
    starts = [deepcopy(node) for node in paragraph.xpath(".//w:commentRangeStart", namespaces=NS)]
    ends = [deepcopy(node) for node in paragraph.xpath(".//w:commentRangeEnd", namespaces=NS)]
    refs = []
    for run in paragraph.xpath(".//w:r[w:commentReference]", namespaces=NS):
        refs.append(deepcopy(run))
    for child in list(paragraph):
        paragraph.remove(child)
    if ppr is not None:
        paragraph.append(deepcopy(ppr))
    paragraph.extend(starts)
    paragraph.append(new_run(text, highlighted, math=math))
    paragraph.extend(ends)
    paragraph.extend(refs)


def replace_cell(cell: etree._Element, text: str, highlighted: bool) -> None:
    paragraphs = cell.xpath("./w:p", namespaces=NS)
    if not paragraphs:
        paragraphs = [etree.SubElement(cell, qn(W, "p"))]
    replace_paragraph(paragraphs[0], text, highlighted)
    for paragraph in paragraphs[1:]:
        replace_paragraph(paragraph, "", highlighted)


def remove_revision_highlights(root: etree._Element) -> None:
    for highlight in root.xpath(".//w:highlight", namespaces=NS):
        parent = highlight.getparent()
        if parent is not None:
            parent.remove(highlight)


def remove_forced_page_break(root: etree._Element, paragraph_text: str) -> None:
    for paragraph in root.xpath(".//w:body/w:p", namespaces=NS):
        text = "".join(paragraph.xpath(".//w:t/text()", namespaces=NS)).strip()
        if text != paragraph_text:
            continue
        for page_break in paragraph.xpath("./w:pPr/w:pageBreakBefore", namespaces=NS):
            page_break.getparent().remove(page_break)
        for rendered_break in paragraph.xpath(".//w:lastRenderedPageBreak", namespaces=NS):
            rendered_break.getparent().remove(rendered_break)
        return
    raise ValueError(f"paragraph not found for page-break removal: {paragraph_text}")


def update_core_properties(payload: bytes) -> bytes:
    root = etree.fromstring(payload)
    for name, value in (("title", MANUSCRIPT_TITLE), ("subject", MANUSCRIPT_SUBJECT)):
        node = root.find(qn(DC, name))
        if node is None:
            node = etree.SubElement(root, qn(DC, name))
        node.text = value
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")


EQUATION_SPECS = {
    31: (r"\tau_i=(b_i,c_i,\Delta_i,T_i^{\max},E_i^{\mathrm{bud}},A_i^{\max},\beta_i,\pi_i,d(i))", None),
    36: (r"f_i^{\mathrm{req}}=f_j^{\min}+r_i\left(F_j-f_j^{\min}\right),\quad 0\leq r_i\leq1,\quad x_{ij}=1", "1"),
    38: (r"\mathcal T_j=\{i\in\mathcal T:x_{ij}=1\},\quad n_j=\operatorname{card}(\mathcal T_j),\quad R_j=F_j-n_jf_j^{\min}", "2"),
    40: (r"\begin{gathered}q_i=\max\{f_i^{\mathrm{req}}-f_j^{\min},0\},\quad i\in\mathcal T_j,\\ f_i=f_j^{\min}+\begin{cases}q_i,&\sum_{k\in\mathcal T_j}q_k\leq R_j,\\ R_jq_i/\sum_{k\in\mathcal T_j}q_k,&\sum_{k\in\mathcal T_j}q_k>R_j.\end{cases}\end{gathered}", "3"),
    42: (r"T_i=\begin{cases}c_i/f_i,&z_i=\mathrm{local},\\ b_i/R_{d(i),s_i}+c_i/f_i+\delta_E,&z_i=\mathrm{edge},\\ b_i/R_{d(i),e_i^\star}+b_i/R_{e_i^\star,s_i}+c_i/f_i+\delta_C,&z_i=\mathrm{cloud},\end{cases}", "4"),
    45: (r"E_i=\kappa_{d(i)}c_if_i^2,\qquad z_i=\mathrm{local}", "5"),
    47: (r"E_i=P_{d(i)}\frac{b_i}{R_{d(i),e_i^\star}},\qquad z_i\in\{\mathrm{edge},\mathrm{cloud}\}", "6"),
    50: (r"A_i=\frac{\Delta_i}{2}+T_i", "7"),
    59: (r"S_i^T=\exp\left(-\frac{T_i}{T_i^{\max}}\right)", "8"),
    63: (r"S_i^E=\exp\left(-\frac{E_i}{E_i^{\mathrm{bud}}}\right)", "9"),
    67: (r"S_i^A=\exp\left(-\frac{A_i}{A_i^{\max}}\right)", "10"),
    70: (r"u_i=0.45S_i^T+0.30S_i^E+0.25S_i^A,\qquad 0<u_i\leq1", "11"),
    72: (r"Q=\frac{\sum_{i\in\mathcal T}\pi_i u_i}{\sum_{i\in\mathcal T}\pi_i}", "12"),
    76: (r"J=\frac{\left(\sum_{m\in\mathcal D_{\mathrm{act}}}U_m\right)^2}{N_{\mathrm{act}}\sum_{m\in\mathcal D_{\mathrm{act}}}U_m^2}", "13"),
    83: (r"B(X)=0.15E^{\mathrm{norm}}+0.15D^{\mathrm{norm}}+0.20A^{\mathrm{norm}}+0.25(1-Q)+0.25(1-J)", "14"),
    85: (r"\operatorname{CSR}(X)=\frac{1}{3N_T}\sum_{i\in\mathcal T}\left[\mathbf1(T_i\leq T_i^{\max})+\mathbf1(E_i\leq\max\{\beta_i,0.1\}E_i^{\mathrm{bud}})+\mathbf1(A_i\leq A_i^{\max})\right]", "15"),
    89: (r"\begin{gathered}\mathrm{P1}:\quad \min_X F_{\mathrm{report}}(X)=B(X)+\lambda_{\mathrm{ref}}[1-\operatorname{CSR}(X)]\\ \mathrm{s.t.}\quad \sum_{j\in\mathcal N}x_{ij}=1,\quad x_{ij}\in\{0,1\},\quad i\in\mathcal T,\\ x_{ij}=0,\quad j\notin\mathcal N_i,\\ \sum_{j\in\mathcal N}x_{ij}f_j^{\min}\leq f_i\leq\sum_{j\in\mathcal N}x_{ij}F_j,\quad i\in\mathcal T,\\ \sum_{i\in\mathcal T}x_{ij}f_i\leq F_j,\quad j\in\mathcal N,\quad \lambda_{\mathrm{ref}}=1.\end{gathered}", "16"),
    93: (r"F_{\mathrm{search}}(X,t)=B(X)+\lambda(t)\left[1-\operatorname{CSR}(X)\right]", "17"),
    94: (r"\lambda(t)=\lambda_0\left(1+\frac{2t}{T_{\max}}\right)^\alpha", "18"),
    98: (r"X_{\mathrm{report}}^{\star}=\arg\min_{X\in\mathcal C_{\mathrm{seen}}}F_{\mathrm{report}}(X)", "19"),
    125: (r"\omega(t)=0.8-0.6\frac{t}{T_{\max}}", "20"),
    126: (r"X_k^{\mathrm{new}}=\omega(t)X_k^{\mathrm{RIME}}+\left[1-\omega(t)\right]X_k^{\mathrm{DBO}}", "21"),
}

INLINE_MATH_RE = re.compile(r"\[\[(.+?)\]\]")

OBSOLETE_EQUATION_PARAGRAPHS = {58, 61, 62, 65, 66, 69, 86, 88, 95, 99, 101, 103, 104, 105}


def generated_omath() -> dict[int, etree._Element]:
    markdown = "\n\n".join(f"$${latex}$$" for latex, _ in EQUATION_SPECS.values())
    with tempfile.TemporaryDirectory(prefix="v2-omml-") as temporary:
        generated = Path(temporary) / "equations.docx"
        pypandoc.convert_text(
            markdown,
            "docx",
            format="markdown+tex_math_dollars",
            outputfile=str(generated),
        )
        with zipfile.ZipFile(generated) as archive:
            root = etree.fromstring(archive.read("word/document.xml"))
    equations = root.xpath(".//m:oMath", namespaces=NS)
    if len(equations) != len(EQUATION_SPECS):
        raise ValueError(f"expected {len(EQUATION_SPECS)} generated equations, found {len(equations)}")
    return {index: deepcopy(equation) for index, equation in zip(EQUATION_SPECS, equations)}


def generated_inline_omath(latex_values: list[str]) -> dict[str, etree._Element]:
    markdown = "\n\n".join(f"$${latex}$$" for latex in latex_values)
    with tempfile.TemporaryDirectory(prefix="v2-inline-omml-") as temporary:
        generated = Path(temporary) / "inline.docx"
        pypandoc.convert_text(markdown, "docx", format="markdown+tex_math_dollars", outputfile=str(generated))
        with zipfile.ZipFile(generated) as archive:
            root = etree.fromstring(archive.read("word/document.xml"))
    equations = root.xpath(".//m:oMath", namespaces=NS)
    if len(equations) != len(latex_values):
        raise ValueError(f"expected {len(latex_values)} inline equations, found {len(equations)}")
    return {latex: deepcopy(equation) for latex, equation in zip(latex_values, equations)}


def apply_inline_math(paragraphs: list[etree._Element], highlighted: bool) -> None:
    latex_values = []
    for paragraph in paragraphs:
        for text in paragraph.xpath(".//w:t/text()", namespaces=NS):
            for latex in INLINE_MATH_RE.findall(text):
                if latex not in latex_values:
                    latex_values.append(latex)
    if not latex_values:
        return
    equations = generated_inline_omath(latex_values)
    for paragraph in paragraphs:
        for text_node in list(paragraph.xpath(".//w:t", namespaces=NS)):
            text = text_node.text or ""
            matches = list(INLINE_MATH_RE.finditer(text))
            if not matches:
                continue
            run = text_node.getparent()
            parent = run.getparent()
            if run.tag != qn(W, "r") or parent is None:
                raise ValueError("inline-math marker is not inside a normal Word run")
            position = parent.index(run)
            cursor = 0
            replacements = []
            for match in matches:
                if match.start() > cursor:
                    replacements.append(new_run(text[cursor:match.start()], highlighted))
                equation = deepcopy(equations[match.group(1)])
                if highlighted:
                    add_math_highlight(equation)
                replacements.append(equation)
                cursor = match.end()
            if cursor < len(text):
                replacements.append(new_run(text[cursor:], highlighted))
            parent.remove(run)
            for offset, replacement in enumerate(replacements):
                parent.insert(position + offset, replacement)


def add_math_highlight(equation: etree._Element) -> None:
    for math_run in equation.xpath(".//m:r", namespaces=NS):
        run_properties = math_run.find(qn(W, "rPr"))
        if run_properties is None:
            run_properties = etree.Element(qn(W, "rPr"))
            math_properties = math_run.find(qn(M, "rPr"))
            math_run.insert(1 if math_properties is not None else 0, run_properties)
        if run_properties.find(qn(W, "highlight")) is None:
            highlight = etree.SubElement(run_properties, qn(W, "highlight"))
            highlight.set(qn(W, "val"), "yellow")


def equation_paragraph_properties(paragraph: etree._Element, numbered: bool) -> etree._Element:
    properties = paragraph.find(qn(W, "pPr"))
    result = deepcopy(properties) if properties is not None else etree.Element(qn(W, "pPr"))
    for alignment in result.findall(qn(W, "jc")):
        result.remove(alignment)
    if numbered:
        tabs = result.find(qn(W, "tabs"))
        if tabs is None:
            tabs = etree.SubElement(result, qn(W, "tabs"))
        for tab in list(tabs):
            tabs.remove(tab)
        for value, position in (("center", "4860"), ("right", "9720")):
            tab = etree.SubElement(tabs, qn(W, "tab"))
            tab.set(qn(W, "val"), value)
            tab.set(qn(W, "pos"), position)
    else:
        alignment = etree.SubElement(result, qn(W, "jc"))
        alignment.set(qn(W, "val"), "center")
    return result


def tab_run() -> etree._Element:
    run = etree.Element(qn(W, "r"))
    etree.SubElement(run, qn(W, "tab"))
    return run


def replace_equation(paragraph: etree._Element, equation: etree._Element, number: Optional[str], highlighted: bool) -> None:
    starts = [deepcopy(node) for node in paragraph.xpath(".//w:commentRangeStart", namespaces=NS)]
    ends = [deepcopy(node) for node in paragraph.xpath(".//w:commentRangeEnd", namespaces=NS)]
    references = [deepcopy(run) for run in paragraph.xpath(".//w:r[w:commentReference]", namespaces=NS)]
    properties = equation_paragraph_properties(paragraph, number is not None)
    for child in list(paragraph):
        paragraph.remove(child)
    paragraph.append(properties)
    paragraph.extend(starts)
    if highlighted:
        add_math_highlight(equation)
    if number is None:
        math_paragraph = etree.Element(qn(M, "oMathPara"))
        math_properties = etree.SubElement(math_paragraph, qn(M, "oMathParaPr"))
        alignment = etree.SubElement(math_properties, qn(M, "jc"))
        alignment.set(qn(M, "val"), "center")
        math_paragraph.append(equation)
        paragraph.append(math_paragraph)
    else:
        paragraph.append(tab_run())
        paragraph.append(equation)
        paragraph.append(tab_run())
        paragraph.append(new_run(f"({number})", highlighted))
    paragraph.extend(ends)
    paragraph.extend(references)


def apply_professional_equations(paragraphs: list[etree._Element], highlighted: bool) -> None:
    generated = generated_omath()
    for index, equation in generated.items():
        replace_equation(paragraphs[index], equation, EQUATION_SPECS[index][1], highlighted)
    for index in sorted(OBSOLETE_EQUATION_PARAGRAPHS, reverse=True):
        paragraph = paragraphs[index]
        if paragraph.xpath(".//w:commentRangeStart|.//w:commentRangeEnd|.//w:commentReference", namespaces=NS):
            raise ValueError(f"obsolete equation paragraph {index} still contains comment anchors")
        paragraph.getparent().remove(paragraph)


NOTATION_ROWS = [
    (r"\mathcal T", "Task set"),
    (r"\mathcal N", "Unified device, edge and cloud execution-node set"),
    (r"\mathcal N_i", "Legal execution-node set of task i"),
    (r"d(i)", "Source device of task i"),
    (r"x_{ij}", "Binary assignment of task i to node j"),
    (r"r_i", "Internal normalised CPU coordinate"),
    (r"f_i^{\mathrm{req}}", "Tentative physical CPU request of task i (Hz)"),
    (r"f_i", "Repaired physical CPU allocation of task i (Hz)"),
    (r"f_j^{\min}", "Minimum allocatable CPU frequency of node j (Hz)"),
    (r"F_j", "Total CPU capacity of node j (Hz)"),
    (r"\mathcal T_j", "Tasks assigned to node j after reassignment"),
    (r"n_j", "Number of tasks assigned to node j"),
    (r"R_j", "CPU capacity remaining after minimum allocations"),
    (r"N_T", "Number of tasks in the decision epoch"),
    (r"N_{\mathrm{act}}", "Number of active source devices"),
    (r"U_m", "Mean base utility of active source device m"),
    (r"Q", "Priority-weighted aggregate QoE"),
    (r"J", "Jain fairness over active-user mean utilities"),
    (r"B(X)", "Fixed weighted base objective"),
    (r"\operatorname{CSR}(X)", "Soft threshold constraint-satisfaction ratio"),
    (r"F_{\mathrm{report}}(X)", "Fixed problem objective and cross-algorithm scale"),
    (r"F_{\mathrm{search}}(X,t)", "Iteration-specific internal search fitness"),
    (r"\lambda(t)", "Dynamic search penalty coefficient"),
    (r"\operatorname{NFE}", "Number of function evaluations"),
]


def apply_notation_math(table: etree._Element, highlighted: bool) -> None:
    markdown = "\n\n".join(f"$${latex}$$" for latex, _ in NOTATION_ROWS)
    with tempfile.TemporaryDirectory(prefix="v2-notation-omml-") as temporary:
        generated = Path(temporary) / "notation.docx"
        pypandoc.convert_text(markdown, "docx", format="markdown+tex_math_dollars", outputfile=str(generated))
        with zipfile.ZipFile(generated) as archive:
            root = etree.fromstring(archive.read("word/document.xml"))
    equations = root.xpath(".//m:oMath", namespaces=NS)
    rows = table.xpath("./w:tr", namespaces=NS)[1:]
    if len(equations) != len(NOTATION_ROWS) or len(rows) < len(NOTATION_ROWS):
        raise ValueError("notation table and generated OMML count differ")
    for row, equation in zip(rows, equations):
        paragraph = row.xpath("./w:tc[1]/w:p", namespaces=NS)[0]
        ppr = paragraph.find("w:pPr", namespaces=NS)
        for child in list(paragraph):
            paragraph.remove(child)
        if ppr is not None:
            paragraph.append(deepcopy(ppr))
        equation = deepcopy(equation)
        if highlighted:
            add_math_highlight(equation)
        paragraph.append(equation)


def fill_table(table: etree._Element, values: list[list[str]], highlighted: bool) -> None:
    rows = table.xpath("./w:tr", namespaces=NS)
    while len(values) > len(rows):
        table.append(deepcopy(rows[-1]))
        rows = table.xpath("./w:tr", namespaces=NS)
    for row_index, row in enumerate(rows):
        cells = row.xpath("./w:tc", namespaces=NS)
        data = values[row_index] if row_index < len(values) else []
        for col_index, cell in enumerate(cells):
            replace_cell(cell, data[col_index] if col_index < len(data) else "", highlighted)
        if row_index > 0:
            for keep_next in row.xpath("./w:tc/w:p/w:pPr/w:keepNext", namespaces=NS):
                keep_next.getparent().remove(keep_next)
    for row in rows[1:-1]:
        for bottom in row.xpath("./w:tc/w:tcPr/w:tcBorders/w:bottom", namespaces=NS):
            bottom.set(qn(W, "val"), "nil")


def set_table_column_widths(table: etree._Element, widths: list[int]) -> None:
    """Set fixed DXA widths and remove source-template surplus columns."""
    grid = table.find(qn(W, "tblGrid"))
    if grid is None:
        grid = etree.SubElement(table, qn(W, "tblGrid"))
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        column = etree.SubElement(grid, qn(W, "gridCol"))
        column.set(qn(W, "w"), str(width))
    properties = table.find(qn(W, "tblPr"))
    if properties is None:
        properties = etree.Element(qn(W, "tblPr"))
        table.insert(0, properties)
    table_width = properties.find(qn(W, "tblW"))
    if table_width is None:
        table_width = etree.SubElement(properties, qn(W, "tblW"))
    table_width.set(qn(W, "type"), "dxa")
    table_width.set(qn(W, "w"), str(sum(widths)))
    for row in table.xpath("./w:tr", namespaces=NS):
        cells = row.xpath("./w:tc", namespaces=NS)
        for cell in cells[len(widths):]:
            row.remove(cell)
        if len(cells) < len(widths):
            raise ValueError("table has fewer cells than requested widths")
        for cell, width in zip(row.xpath("./w:tc", namespaces=NS), widths):
            cell_properties = cell.find(qn(W, "tcPr"))
            if cell_properties is None:
                cell_properties = etree.Element(qn(W, "tcPr"))
                cell.insert(0, cell_properties)
            cell_width = cell_properties.find(qn(W, "tcW"))
            if cell_width is None:
                cell_width = etree.SubElement(cell_properties, qn(W, "tcW"))
            cell_width.set(qn(W, "type"), "dxa")
            cell_width.set(qn(W, "w"), str(width))


def comment_text(comment: etree._Element) -> str:
    return "\n".join(
        "".join(p.xpath(".//w:t/text()", namespaces=NS)).strip()
        for p in comment.xpath("./w:p", namespaces=NS)
        if "".join(p.xpath(".//w:t/text()", namespaces=NS)).strip()
    )


def comment_para_id(comment: etree._Element) -> str:
    """Return the paragraph ID used by commentsExtended for this comment."""

    para_ids = comment.xpath("./w:p/@w14:paraId", namespaces=NS)
    if not para_ids:
        raise ValueError("comment has no paragraph ID")
    return para_ids[-1]


def comment_has_para_id(comment: etree._Element, para_id: str) -> bool:
    return para_id in comment.xpath("./w:p/@w14:paraId", namespaces=NS)


COMMENT_ACTIONS = {
    "0": "The provisional title now names joint task offloading and computing-resource allocation; final wording remains for author confirmation.",
    "2": "The title no longer lists only QoE and fairness, and the five coupled terms are described in the abstract and formulation instead.",
    "3": "The manuscript consistently describes one weighted scalar optimisation problem rather than a Pareto multi-objective method.",
    "5": "The abstract reports the problem, method, controlled evidence and limits without a detailed table of numbers.",
    "7": "The abstract follows background, challenge, method, evidence and limitation order.",
    "9": "MEC, AoI, QoE, CSR and RDHO are expanded independently at first use in the abstract and main text.",
    "10": "Keywords use established retrieval terms and omit the self-created priority-aware label.",
    "12": "The Introduction follows the requested inverted-pyramid structure and closes with contributions and organisation.",
    "14": "Citations retain bracketed numbering and references remain ordered by first appearance.",
    "16": "An original editable architecture figure is placed in Section 3, not the Introduction.",
    "18": "The Introduction now begins from application demand and summarises the complete paper logic; TLBO-HHO appears only as prior work and a baseline.",
    "19": "All figures are placed near their discussion with readable labels; the architecture shows more devices than servers and uses model notation only in Section 3.",
    "20": "Scheduling terminology was removed from the core problem statement; the paper consistently uses task offloading and resource allocation.",
    "22": "Related Work was expanded while remaining compact for a research article.",
    "24": "Related Work uses solution methodology as its primary classification axis.",
    "26": "Optimisation, learning and metaheuristic studies are separated; objective dimensions are discussed only within each class.",
    "27": "The evolutionary relationship to the earlier chapter is omitted from Related Work; TLBO-HHO is treated as literature and a comparator.",
    "28": "Section 3 now contains the full cloud-edge-device model, node choice, physical CPU allocation, delay, energy and AoI assumptions.",
    "30": "The non-standard single-epoch surrogate wording was replaced by a periodic no-backlog average-AoI approximation with its scope stated.",
    "31": "Assumptions are integrated at the relevant network, path, communication and AoI descriptions.",
    "32": "The task tuple, unified node set, assignment variable and physical CPU variable are explicitly defined for later use.",
    "33": "Each formula is preceded or followed by modelling rationale and physical interpretation.",
    "34": "Each numbered equation occupies its own paragraph.",
    "36": "The obsolete core-service-rate term was removed; the paper now uses allocated physical CPU frequency in Hz.",
    "37": "Table 1 now contains exactly one professionally formatted variable per row; secondary notation is defined at first use in the text.",
    "39": "The notation table is limited to the variables required to read P1 and the metric definitions.",
    "41": "All subscripts and cardinality terms were rebuilt as native Word equations and verified in the final page render.",
    "43": "Equation paragraphs retain centred expressions with right-side numbers inherited from the review template.",
    "45": "The stray Fairness metric label was removed; fairness is defined directly from active users' mean base utility.",
    "46": "Section 4 now defines P1 directly on fixed reporting fitness, with conditional selected-node CPU bounds and aggregate node capacity.",
    "47": "Short sub-subsections were folded into continuous prose.",
    "49": "Problem complexity is retained as a short paragraph rather than a separate small subsection.",
    "50": "Section 5 is explicitly titled an RDHO-based task-offloading strategy.",
    "51": "Computation-control algorithm terminology was removed; the normalised resource coordinate is described only as an internal encoding.",
    "52": "Section 5.1 is written as algorithm design and solution representation, not program implementation commentary.",
    "53": "RDHO update equations and cross-references were renumbered consistently.",
    "55": "The algorithm section retains only two substantive second-level headings.",
    "56": "Algorithm 1 remains in the source-derived three-line table format.",
    "58": "Pseudocode actions are left aligned and use compact imperative statements.",
    "59": "All manuscript tables use the inherited three-line table style and consistent numeric precision.",
    "61": "Section 6 retains three second-level headings; statistics, scalability and sensitivity use inline labels.",
    "62": "References remain numbered from 1 in first-citation order.",
    "64": "Recent MEC surveys and representative vehicular, blockchain and cooperative-offloading studies are cited in standard scholarly language.",
}


LEGACY_REPLY_PARENTS = {
    "1": "0",
    "6": "5",
    "8": "7",
    "13": "12",
    "15": "14",
    "17": "16",
    "23": "22",
    "25": "24",
    "29": "28",
    "35": "34",
    "38": "37",
    "40": "39",
    "44": "43",
    "48": "47",
    "54": "53",
    "60": "59",
    "63": "62",
    "65": "64",
}


def comment_anchor_text(parts: dict[str, bytes], comments: etree._Element, extended: etree._Element) -> dict[str, str]:
    document = etree.fromstring(parts["word/document.xml"])
    direct: dict[str, str] = {}
    for paragraph in document.xpath(".//w:p[w:commentRangeStart]", namespaces=NS):
        text = "".join(paragraph.xpath(".//w:t/text()", namespaces=NS)).strip()
        for comment_id in paragraph.xpath(".//w:commentRangeStart/@w:id", namespaces=NS):
            direct[comment_id] = text[:240]

    para_to_comment: dict[str, str] = {}
    for comment in comments.xpath("./w:comment", namespaces=NS):
        for para_id in comment.xpath("./w:p/@w14:paraId", namespaces=NS):
            para_to_comment[para_id] = comment.get(qn(W, "id"))
    parent_by_comment: dict[str, str] = {}
    for node in extended.xpath("./w15:commentEx[@w15:paraIdParent]", namespaces=NS):
        child = para_to_comment.get(node.get(qn(W15, "paraId")))
        parent = para_to_comment.get(node.get(qn(W15, "paraIdParent")))
        if child is not None and parent is not None:
            parent_by_comment[child] = parent

    resolved = dict(direct)
    for comment_id in para_to_comment.values():
        current = comment_id
        visited = set()
        while current not in resolved and current in parent_by_comment and current not in visited:
            visited.add(current)
            current = parent_by_comment[current]
        if current in resolved:
            resolved[comment_id] = resolved[current]
    return resolved


def append_replies(parts: dict[str, bytes]) -> list[dict[str, str]]:
    comments = etree.fromstring(parts["word/comments.xml"])
    extended = etree.fromstring(parts["word/commentsExtended.xml"])
    ids = etree.fromstring(parts["word/commentsIds.xml"])
    extensible = etree.fromstring(parts["word/commentsExtensible.xml"])
    used_ids = [int(value) for value in comments.xpath("./w:comment/@w:id", namespaces=NS)]
    next_id = max(used_ids) + 1
    comment_by_id = {comment.get(qn(W, "id")): comment for comment in comments.xpath("./w:comment", namespaces=NS)}
    extended_by_para = {
        node.get(qn(W15, "paraId")): node for node in extended.xpath("./w15:commentEx", namespaces=NS)
    }
    legacy_by_parent: dict[str, str] = {}
    for reply_id, parent_id in LEGACY_REPLY_PARENTS.items():
        reply = comment_by_id[reply_id]
        parent = comment_by_id[parent_id]
        reply_para = comment_para_id(reply)
        parent_para = comment_para_id(parent)
        extended_by_para[reply_para].set(qn(W15, "paraIdParent"), parent_para)
        legacy_by_parent[parent_id] = reply_id
    for node in extended.xpath("./w15:commentEx[@w15:paraIdParent]", namespaces=NS):
        child_para = node.get(qn(W15, "paraId"))
        parent_para = node.get(qn(W15, "paraIdParent"))
        child = next((comment for comment in comments.xpath("./w:comment", namespaces=NS) if comment_has_para_id(comment, child_para)), None)
        parent = next((comment for comment in comments.xpath("./w:comment", namespaces=NS) if comment_has_para_id(comment, parent_para)), None)
        if child is not None and parent is not None and child.get(qn(W, "author")) == "祎宝":
            legacy_by_parent.setdefault(parent.get(qn(W, "id")), child.get(qn(W, "id")))
    anchors = comment_anchor_text(parts, comments, extended)
    used_para = set(ids.xpath("./w16cid:commentId/@w16cid:paraId", namespaces=NS))
    used_durable = set(ids.xpath("./w16cid:commentId/@w16cid:durableId", namespaces=NS))
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    audit = []
    for comment in comments.xpath("./w:comment[@w:author='webuser']", namespaces=NS):
        cid = comment.get(qn(W, "id"))
        action = COMMENT_ACTIONS.get(cid, "The comment was rechecked against the V2 model and the corresponding wording was retained or revised consistently.")
        status = "author confirmation required" if cid in {"0", "2"} else "implemented; thread left open"
        parent_para = comment_para_id(comment)
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
        reply_text = "V2 reply: " + action
        reply = etree.SubElement(comments, qn(W, "comment"))
        reply.set(qn(W, "id"), str(next_id))
        reply.set(qn(W, "author"), "祎宝")
        reply.set(qn(W, "date"), now)
        reply.set(qn(W, "initials"), "")
        paragraph = etree.SubElement(reply, qn(W, "p"))
        paragraph.set(qn(W14, "paraId"), para_id)
        paragraph.set(qn(W14, "textId"), "77777777")
        paragraph.append(new_run(reply_text, highlighted=False))
        ex = etree.SubElement(extended, qn(W15, "commentEx"))
        ex.set(qn(W15, "paraId"), para_id)
        ex.set(qn(W15, "paraIdParent"), parent_para)
        ex.set(qn(W15, "done"), "0")
        id_node = etree.SubElement(ids, qn(W16CID, "commentId"))
        id_node.set(qn(W16CID, "paraId"), para_id)
        id_node.set(qn(W16CID, "durableId"), durable_id)
        ext_node = etree.SubElement(extensible, qn(W16CEX, "commentExtensible"))
        ext_node.set(qn(W16CEX, "durableId"), durable_id)
        ext_node.set(qn(W16CEX, "dateUtc"), now)
        audit.append({
            "original_comment_id": cid,
            "author": comment.get(qn(W, "author"), ""),
            "original_comment": comment_text(comment),
            "anchor": anchors.get(cid, "thread anchor inherited from parent"),
            "actual_revision": action,
            "legacy_reply_id": legacy_by_parent.get(cid, ""),
            "legacy_reply_status": "rethreaded with paraIdParent" if legacy_by_parent.get(cid) in LEGACY_REPLY_PARENTS else "existing threaded reply preserved",
            "thread_parent_para_id": parent_para,
            "reply_comment_id": str(next_id),
            "reply_para_id": para_id,
            "reply": reply_text,
            "status": status,
        })
        next_id += 1
    parts["word/comments.xml"] = etree.tostring(comments, xml_declaration=True, encoding="UTF-8", standalone="yes")
    parts["word/commentsExtended.xml"] = etree.tostring(extended, xml_declaration=True, encoding="UTF-8", standalone="yes")
    parts["word/commentsIds.xml"] = etree.tostring(ids, xml_declaration=True, encoding="UTF-8", standalone="yes")
    parts["word/commentsExtensible.xml"] = etree.tostring(extensible, xml_declaration=True, encoding="UTF-8", standalone="yes")
    return audit


def paragraph_updates() -> dict[int, str]:
    main = read_rows(RESULTS / "summary" / "main_30_summary_mean_std.csv", "algorithm")
    equal = read_rows(RESULTS / "summary" / "equal_nfe_30_summary_mean_std.csv", "algorithm")
    common = read_rows(RESULTS / "summary" / "common_control_30_summary_mean_std.csv", "algorithm")
    ablation = read_rows(RESULTS / "summary" / "ablation_30_summary_mean_std.csv", "algorithm")
    scale = read_rows(RESULTS / "summary" / "scalability_summary_mean_std.csv", "task_number")
    rdho = main["RDHO"]
    reductions = {name: 100.0 * (float(row["fitness_mean"]) - float(rdho["fitness_mean"])) / float(row["fitness_mean"]) for name, row in main.items() if name != "RDHO"}
    return {
        0: "RDHO-Based Joint Task Offloading and Computing Resource Allocation in Mobile Edge Computing",
        6: "Mobile edge computing (MEC) complements resource-limited devices with nearby edge and remote cloud resources, but heterogeneous tasks couple discrete execution-node choice with continuous processor allocation. This paper formulates a capacity-feasible cloud-edge-device model in which each task selects one legal local, edge, or cloud node and receives a physical CPU frequency. A deterministic repair preserves feasible requests and projects only overloaded nodes. Device-side energy, processing delay, a periodic no-backlog average Age of Information (AoI) approximation, a model-based Quality of Experience (QoE) utility, and active-user Jain fairness form one fixed weighted reporting objective, while a dynamic penalty guides search only. The complete RIME-DBO hybrid optimisation (RDHO) procedure gives the lowest mean reporting fitness in 30 paired end-to-end runs. Equal-evaluation and common-postprocessing controls substantially qualify this result: RDHO-core is worse than DBO, TLBO-HHO and CWTSSA at equal NFE, so the evidence supports the configured full pipeline rather than universal superiority of the hybrid population operator. Conclusions are limited to the stated simulated model and baseline implementations.",
        7: "Keywords: mobile edge computing; task offloading; computing resource allocation; Age of Information; metaheuristic optimisation.",
        9: "Latency-sensitive sensing, Internet of Things (IoT), fifth-generation (5G) and emerging sixth-generation services generate heterogeneous workloads close to users. Mobile edge computing (MEC) reduces service distance by supplementing devices with edge and cloud resources [1,2].",
        10: "A practical offloading decision must select a legal execution node and allocate finite processor capacity. The resulting categorical-continuous decisions interact through transmission paths, per-node CPU budgets, device-side energy and task-specific service thresholds.",
        11: "Existing studies primarily optimise energy and latency, while freshness-aware work adds Age of Information (AoI) and user-oriented work considers Quality of Experience (QoE) or fairness [3-7]. These criteria are related rather than statistically independent: in the present model AoI contains service delay and QoE transforms delay, energy and freshness into bounded utility.",
        12: "The study therefore evaluates a transparent scalar engineering preference rather than a Pareto method. RIME-DBO hybrid optimisation (RDHO) is treated as a complete solver configuration whose seeding, population updates and refinement must be distinguished experimentally.",
        13: "The contributions are threefold. First, the paper integrates capacity-feasible three-tier task offloading and physical CPU allocation with priority-weighted aggregate QoE and priority-neutral active-user fairness. Second, it designs an RDHO solution workflow with legal-node encoding, physical-frequency decoding, deterministic capacity repair, dynamic search guidance and fixed-objective incumbent tracking shared across the controlled solvers. Third, paired, equal-NFE, common-postprocessing, ablation, scalability and sensitivity experiments separate the evidence for the complete workflow from evidence for its individual search mechanisms.",
        14: f"Under the configured end-to-end procedures, RDHO-full obtains mean reporting fitness {f(rdho, 'fitness_mean')} and reductions of " + ", ".join(f"{reductions[name]:.1f}% versus {name}" for name in ("RIME", "DBO", "TLBO-HHO", "CWTSSA", "Greedy-ED")) + ". This is a full-pipeline result, not an equal-NFE claim for RIME-DBO fusion.",
        15: "Section 2 reviews related work. Sections 3 and 4 define the physical system and P1. Section 5 describes RDHO. Section 6 reports controlled evidence, and Section 7 concludes.",
        17: "Following MEC surveys, related work is organised by solution methodology: model-based optimisation, learning-based methods and metaheuristic search [8-10]. Objective dimensions are discussed within these classes.",
        18: "Model-based studies jointly allocate communication and computation resources or coordinate edge-cloud execution under explicit system constraints [3,11-14]. Legal collaboration topology and resource budgets must be represented before optimising task placement.",
        19: "Learning-based methods adapt policies to changing states and have been applied to online offloading, vehicular cooperation and blockchain-enabled edge-cloud systems [15-17]. Their training and data requirements motivate complementary transparent offline optimisation for a fixed decision epoch.",
        20: "Freshness-aware MEC incorporates AoI alongside service time [18-20]. The earlier TLBO-HHO method is included as an AoI-aware metaheuristic baseline [21]. QoE and fairness studies represent service acceptability and user balance [5-7,22-26].",
        21: "Metaheuristic methods search nonlinear mixed spaces without a learned policy. Relevant mechanisms include HHO, GA, TLBO, RIME, DBO and enhanced sparrow search [27-36]. A hybrid label alone does not establish benefit; seeding, evaluation budget and postprocessing require controlled comparisons.",
        22: "Representative studies on parking-edge cooperation, blockchain-enabled edge-cloud offloading, cooperative deep reinforcement learning and potential-game strategies show how collaboration topology, resource coupling and service requirements alter offloading decisions [37-40]. Existing MEC work already includes physical resource and capacity models; the specific gap addressed here is their integration with priority-weighted system QoE, priority-neutral active-user fairness and controlled attribution across initialisation, NFE and postprocessing.",
        23: "The present work addresses that combined methodological and evaluation gap for a simulated cloud-edge-device epoch; it does not claim that physical CPU modelling alone is novel, nor does it claim communication-resource optimisation, online queue scheduling or deployment validation.",
        26: "Consider devices [[\\mathcal D]], edge servers [[\\mathcal E]], cloud servers [[\\mathcal C]] and tasks [[\\mathcal T]] in the three-tier architecture of Fig. 1. Their union [[\\mathcal N=\\mathcal D\\cup\\mathcal E\\cup\\mathcal C]] uses global node IDs. We assume fixed topology and link rates during one decision epoch so that the optimisation focuses on execution-node choice and computing-resource allocation.",
        27: "Task [[i]] is generated by source device [[d(i)]]. Local execution is legal only at [[d(i)]]; reachable edge nodes have positive device-edge rates; a cloud node is legal only through at least one reachable edge with a positive backhaul rate. For a selected cloud, evaluation uses the legal relay with minimum task-specific transmission delay. This is deterministic path evaluation, not route or bandwidth optimisation.",
        29: "Fig. 1. Three-tier cloud-edge-device architecture, legal execution-node choices and physical CPU-capacity pools.",
        30: "Task [[i]] is represented by the following tuple, which records input bits, CPU cycles, period, service thresholds, battery ratio, priority and source device.",
        32: "Binary [[x_{ij}=1]] selects exactly one node [[j]]. The derived layer [[z_i]] is local, edge or cloud and [[s_i]] denotes the selected remote server. The physical allocation [[f_i]] is measured in Hz.",
        33: "Each search individual stores two normalised coordinates per task. The node coordinate indexes the sorted legal-node set, while [[r_i\\in[0,1]]] decodes to a tentative physical frequency. The normalised coordinate is internal algorithm encoding, not a system-level abstract control variable.",
        35: "For node [[j]] with minimum allocatable frequency [[f_j^{\\min}]] and capacity [[F_j]], the tentative request is",
        36: "f_i^req = f_j^min + r_i(F_j-f_j^min).                                                     (1)",
        37: "If minimum allocations overload a node, tasks are examined in descending semantic-neutral ID order and moved to a legal alternative with the largest remaining minimum-frequency slack; node ties use the smallest global ID. Task types are shuffled before IDs are assigned, and source device and priority are independently sampled. Across the 30 paired scenarios, the pooled ID audit finds no association with type, source or priority. This deterministic order is a reproducibility convention, not a task-importance rule.",
        38: "T_j={i:x_i,j=1}; n_j=card(T_j); R_j=F_j-n_j f_j^min.                            (2)",
        39: "Reassignment repeats for at most [[|\\mathcal T||\\mathcal N|]] passes and either reaches non-negative [[R_j]] for every node or fails explicitly. For a feasible assignment, the projection below applies only to [[i\\in\\mathcal T_j]]. A zero excess denominator necessarily selects the first branch, so no division is performed; feasible requests are retained and only overloaded excess is scaled.",
        40: "q_i=max(f_i^req-f_j^min,0); retain q_i when sum q<=R_j, otherwise allocate R_j q_i/sum q.  (3)",
        41: "Using fixed positive rates [[R_{d,e}]] and [[R_{e,c}]], end-to-end delay is defined separately for each execution layer.",
        42: "T_i = c_i/f_i (local); b_i/R_{d,e}+c_i/f_i+delta_E (edge); b_i/R_{d,e*}+b_i/R_{e*,c}+c_i/f_i+delta_C (cloud).  (4)",
        43: "No heuristic congestion attenuation or M/M/1 queue is added, because finite CPU capacity and repaired physical allocations already represent processor scarcity. Fixed edge/cloud overheads are stated simulation parameters.",
        44: "For local execution, device-side dynamic-voltage-and-frequency-scaling energy is",
        45: "E_i = kappa_{d(i)} c_i f_i^2.                                                         (5)",
        46: "For edge or cloud offloading, let [[e_i^\\star]] denote the selected edge or the fixed legal cloud relay. The reported device-side energy includes uplink transmission only:",
        47: "E_i = P_{d(i)} b_i/R_{d(i),e}.                                                       (6)",
        48: "Infrastructure computation and backhaul energy are outside the boundary; the manuscript therefore never labels this metric total system energy.",
        49: "We assume periodic update generation and no explicit queue backlog. The area of a delay-shifted sawtooth over one period gives the average approximation",
        50: "A_i = Delta_i/2 + T_i.                                                              (7)",
        51: "AoI is consequently delay-coupled, not independent. The model is not a queue-aware or peak-AoI formulation.",
        52: "Table 1 lists one core variable per row. Secondary symbols are defined at first use in the surrounding text to avoid an oversized notation table.",
        53: "The generated ranges ensure a feasible minimum-frequency assignment; all returned solutions are checked for unique assignment, legal nodes, finite frequencies, bounds and aggregate capacity.",
        56: "The study uses a model-based base utility [[u_i]] rather than a human-subject mean-opinion score. Delay, energy and freshness satisfaction are bounded exponential functions.",
        57: "Delay satisfaction is",
        58: "S_i^T = exp(-T_i/T_i^max).                                                           (8)",
        60: "Energy satisfaction is",
        62: "S_i^E = exp(-E_i/E_i^bud).                                                           (9)",
        64: "Freshness satisfaction is",
        66: "S_i^A = exp(-A_i/A_i^max).                                                          (10)",
        68: "The priority-neutral base task utility is",
        69: "u_i = 0.45 S_i^T + 0.30 S_i^E + 0.25 S_i^A,  with 0 <= u_i <= 1.                   (11)",
        71: "Task priority is used only for system QoE aggregation:",
        72: "Q = sum_i pi_i u_i / sum_i pi_i.                                                    (12)",
        73: "For each active source device [[m]], let [[U_m]] denote the mean base utility over tasks generated by [[m]].",
        74: "This ordering prevents task priority and the number of generated tasks from being counted again inside fairness.",
        75: "Let [[\\mathcal D_{\\mathrm{act}}]] contain only source devices that generate at least one task in the epoch, and let [[N_{\\mathrm{act}}]] be their count.",
        76: "J = (sum_{m in D_act} ubar_m)^2 / (|D_act| sum_{m in D_act} ubar_m^2).               (13)",
        77: "[[J=1]] indicates equal active-user mean base utility. It is QoE-outcome fairness, not equality of physical CPU allocations.",
        78: "The utility coefficients are engineering parameters applied identically to all algorithms; they are not claimed as subjective calibration and are varied in sensitivity analysis.",
        80: "P1 combines threshold-normalised device-side energy, delay and AoI with QoE and fairness deficits. These five terms are coupled, because QoE is derived from the first three and AoI contains delay.",
        81: "The components [[E^{\\mathrm{norm}}]], [[D^{\\mathrm{norm}}]] and [[A^{\\mathrm{norm}}]] are respectively the task means of device-side energy divided by its budget, delay divided by its maximum and AoI divided by its threshold.",
        82: "The fixed base objective is",
        83: "B = 0.15 ebar + 0.15 tbar + 0.20 abar + 0.25(1-Q) + 0.25(1-J).                       (14)",
        84: "Let [[N_T]] be the number of tasks. Soft delay, battery-adjusted energy and AoI checks are summarised by CSR; they do not replace the hard assignment and CPU constraints.",
        85: "CSR=(1/(3N_T)) sum_i [I(T_i<=T_i^max)+I(E_i<=E_i^bud max{beta_i,0.1})+I(A_i<=A_i^max)].  (15)",
        87: "The fixed optimisation problem is therefore defined directly on reporting fitness. The selected-node CPU bound is written as an assignment-weighted bound, so each [[f_i]] is constrained only by its chosen node.",
        88: "P1: minimise F_report=B+lambda_ref(1-CSR), lambda_ref=1, subject to unique legal assignment, selected-node CPU bounds and node capacity.  (16)",
        90: "The soft-violation rate is [[v=1-\\operatorname{CSR}]].",
        91: "The internal normalised coordinates satisfy [[0\\leq r_i\\leq1]] and select only the legal list; they are not additional physical constraints.",
        92: "The dynamic search fitness used by RDHO is",
        93: "F_search(t) = B + lambda(t)(1-CSR).                                                  (17)",
        94: "lambda(t)=lambda_0(1+2t/T)^alpha.                                                    (18)",
        96: "Parents and candidates in one greedy selection are evaluated with the same [[\\lambda(t)]]. This prevents comparison under incompatible penalty coefficients.",
        97: "The search process separately tracks the best fixed-objective candidate seen, denoted by [[\\mathcal C_{\\mathrm{seen}}]]:",
        98: "X_report^star=arg min_{X in C_seen} F_report(X).                                     (19)",
        100: "Search fitness guides optimisation; reporting fitness is the only cross-algorithm scale in tables and statistics.",
        102: "Thus P1 is one fixed constrained problem, [[F_{\\mathrm{search}}]] is only a penalty-continuation mechanism for solving it, and [[F_{\\mathrm{report}}]] is the sole ranking scale in tables and statistics.",
        107: "Problem complexity.",
        108: "Even without continuous allocation, legal node assignments grow combinatorially. Capacity coupling, exponential utility and indicator-based soft violations make P1 a nonlinear mixed discrete-continuous problem.",
        109: "The study does not claim a new proof of NP-hardness; it motivates a population search and evaluates empirical solution quality and cost.",
        110: "A returned incumbent consists of one repaired legal node and one physical CPU allocation per task.",
        111: "These characteristics motivate population search over legal categorical assignments and bounded physical CPU allocations; no deployment claim is made.",
        113: "RIME-DBO hybrid optimisation (RDHO) combines RIME-inspired perturbation with DBO-inspired role-conditioned movements [34,35]. RDHO-full additionally uses greedy seeding and deterministic coordinate refinement; RDHO-core omits final refinement.",
        114: "RIME contributes best-guided exploration and puncture updates, while DBO contributes rolling, foraging and theft-inspired candidates.",
        115: "All candidates use the same normalised two-coordinate encoding and are decoded through the common physical repair before evaluation.",
        116: "The hybrid is assessed as one configured search architecture. Controlled experiments, rather than the algorithm name, determine which claims are supported.",
        118: "Each individual is a [[|\\mathcal T|\\times2]] matrix (node coordinate, resource coordinate). The first coordinate indexes the sorted legal nodes; the second decodes to [[f_i^{\\mathrm{req}}]] in Eq. (1). Both are clipped to [0,1].",
        119: "Server selection is therefore an implemented decision with heterogeneous legal paths. The deterministic repair in Eqs. (2)-(3) is shared by RDHO and every baseline.",
        120: "A candidate evaluation returns [[B(X)]], [[\\operatorname{CSR}(X)]], dynamic search fitness, fixed reporting fitness, raw metrics, hard-feasibility flags and capacity utilisation.",
        122: "The RDHO population contains equal Gaussian and uniform subsets, a greedy coordinate seed and up to three perturbations. Role shares adapt to diversity, while the configured top 10% are retained as elites.",
        123: "Producer candidates combine RIME- and DBO-inspired updates through a weight decreasing from 0.8 to 0.2; followers use best-guided puncture or bound-aware foraging, and scouts use theft or a decaying Cauchy perturbation.",
        124: "The fusion weight is",
        125: "omega(t)=0.8-0.6t/T.                                                                (20)",
        126: "X_i^new = omega(t) X_i^RIME + (1-omega(t)) X_i^DBO.                               (21)",
        127: "The continuous update is an algorithmic neighbourhood only; every resulting assignment is interpreted through the task's legal-node list.",
        128: "Greedy replacement compares parent and candidate under the same current [[\\lambda(t)]]. A separate incumbent is tracked on [[F_{\\mathrm{report}}]].",
        129: "RDHO-full applies deterministic coordinate refinement and then reports the common fixed objective. RDHO-core and controlled RIME/DBO variants expose the contribution of postprocessing and initialisation; all NFE values are recorded.",
        130: "The complete procedure is summarised in Algorithm 1.",
        131: "Algorithm 1. RDHO joint task-offloading and physical CPU-allocation strategy.",
        133: "The pseudocode separates dynamic-penalty selection, fixed-reference incumbent tracking, common repair and optional refinement.",
        136: "All numerical V2 experiments were freshly executed with repository HEAD 78c51c13ce7405654d488aea593d184be930e16a using Python 3.9.6 on macOS. Scenario seeds 20260701-20260730 define paired task and network instances; algorithm streams are derived deterministically from scenario seed and label. Subsequent publication commits change audit, export, plotting and manuscript tooling only, not src/, configurations or numerical CSV values.",
        137: "The main suite compares RDHO-full, RIME, DBO, TLBO-HHO [21], CWTSSA [36] and Greedy-ED under the same model, utility, repair and fixed reporting objective.",
        138: f"Population size and iterations are common in the end-to-end suite, but NFE differs: RDHO-full uses {int(float(rdho['nfe_mean']))}, population baselines use 7551, and Greedy-ED uses {int(float(main['Greedy-ED']['nfe_mean']))}. Equal-NFE results use 3801 evaluations for every population method.",
        139: "Table 2. Physical system parameters used in the main experiment.",
        141: "Table 3. Task-generation ranges and sampling probabilities.",
        143: "Table 4. Algorithm and reproducibility parameters.",
        144: "No algorithm-specific tuning was performed on the reported scenarios. Configurations and exact baseline implementations are versioned with the raw results.",
        146: "Figure 2 reports fixed-reference incumbents during population search. RDHO's final coordinate refinement is not included in its curve, and Greedy-ED is a fixed reference.",
        148: "Fig. 2. Fixed-reference reporting-fitness convergence over 150 iterations.",
        149: "Table 5. End-to-end solver comparison over 30 paired scenarios (mean ± standard deviation).",
        150: f"RDHO-full has the lowest mean reporting fitness ({pm(rdho, 'fitness')}) and mean QoE {f(rdho, 'qoe_mean')}, fairness {f(rdho, 'fairness_mean')} and CSR {f(rdho, 'csr_mean')}. All hard-feasibility rates are 1.0. This supports the complete configured solver only.",
        151: "Metric-specific leaders differ: TLBO-HHO has the lowest device-side energy, RDHO-full has the lowest delay and AoI and the highest QoE and CSR, while Greedy-ED has the highest fairness by a small margin and is fastest. RDHO-full also consumes more NFE.",
        153: "Fig. 3. Mean device-side energy over 30 paired runs.",
        154: "TLBO-HHO is the energy leader; RDHO optimises energy as one component of the coupled reporting preference.",
        156: "Fig. 4. Mean processing delay over 30 paired runs.",
        157: "RDHO-full has the lowest mean delay under the configured end-to-end procedures.",
        159: "Fig. 5. Periodic no-backlog average-AoI approximation over 30 paired runs.",
        160: "RDHO-full has the lowest mean AoI approximation; the close ordering with delay follows Eq. (7).",
        162: "Fig. 6. Priority-weighted aggregate QoE and active-user base-utility fairness.",
        163: "RDHO-full has the highest mean QoE, whereas fairness differences are small and do not imply equality of CPU allocations.",
        165: "Fig. 7. Soft constraint-satisfaction ratio (CSR).",
        166: f"RDHO-full reaches mean CSR {f(rdho, 'csr_mean')}. CSR remains a binary threshold diagnostic; it does not imply that every task satisfies every soft threshold.",
        167: "Statistical analysis.",
        168: "Two-sided paired Wilcoxon tests use the 30 matched reporting-fitness values. Holm adjustment controls the family-wise error rate; median paired difference, signed rank-biserial correlation and wins/ties/losses report magnitude and consistency.",
        169: "Table 6. Paired Wilcoxon tests for the complete end-to-end solvers.",
        170: "RDHO-full is lower in all 30 pairs against each main baseline (Holm-adjusted [[p=9.31\\times10^{-9}]]; signed rank-biserial effect = -1). These tests concern complete procedures, not every raw metric or the isolated hybrid operator.",
        172: f"Equal-NFE controls change the interpretation. At 3801 evaluations, RDHO-core mean fitness {f(equal['RDHO-core'], 'fitness_mean')} is lower than RIME ({f(equal['RIME'], 'fitness_mean')}) but higher than DBO ({f(equal['DBO'], 'fitness_mean')}), TLBO-HHO ({f(equal['TLBO-HHO'], 'fitness_mean')}) and CWTSSA ({f(equal['CWTSSA'], 'fitness_mean')}). The latter three paired disadvantages are statistically significant.",
        173: "Table 7. One-factor RDHO configuration analysis over 30 paired scenarios.",
        175: "Fig. 8. Reporting fitness and soft CSR for RDHO variants.",
        176: f"Coordinate refinement changes mean fitness from {f(ablation['RDHO-core'], 'fitness_mean')} to {f(ablation['RDHO-full'], 'fitness_mean')}. Removing dual-source initialisation changes it to {f(ablation['RDHO-w/o dual-source initialization'], 'fitness_mean')}; removing adaptive roles, elite preservation or dynamic penalty changes the mean by less than 0.002, so no independent necessity is claimed without the paired test record.",
        177: "Common-initialisation and postprocessing controls.",
        178: f"With common initialisation alone, RIME and DBO obtain {f(common['RIME-common-init'], 'fitness_mean')} and {f(common['DBO-common-init'], 'fitness_mean')}. Adding the same refinement yields {f(common['RIME-common-init-refine'], 'fitness_mean')} and {f(common['DBO-common-init-refine'], 'fitness_mean')}, close to RDHO-full {f(common['RDHO-full'], 'fitness_mean')}. RDHO-full remains lower in the paired tests, but refinement explains a substantial part of the end-to-end gap.",
        179: "Table 8. RDHO scalability under 20-100 tasks.",
        181: "Fig. 9. Reporting fitness, soft CSR and runtime versus task count.",
        182: f"From 20 to 100 tasks, mean reporting fitness changes from {f(scale['20'], 'fitness_mean')} to {f(scale['100'], 'fitness_mean')}, CSR from {f(scale['20'], 'csr_mean')} to {f(scale['100'], 'csr_mean')}, and runtime from {f(scale['20'], 'runtime_mean')} s to {f(scale['100'], 'runtime_mean')} s. Hard feasibility remains 1.0; active-node mean utilisation rises from {f(scale['20'], 'capacity_utilisation_mean_mean')} to {f(scale['100'], 'capacity_utilisation_mean_mean')}.",
        183: "Sensitivity analysis.",
        184: "Table 9 makes the principal attribution controls explicit. Effects are ordered as the named RDHO reference minus the row method: a negative signed rank-biserial value means the reference has lower paired reporting fitness, while a positive value means it is higher. Equal-NFE rows use RDHO-core as reference, whereas common-refinement rows use RDHO-full.",
        185: "The final sensitivity ranges are generated directly from V2 CSV files; no value is manually entered into a paper table.",
        186: "Weight changes expose engineering preference rather than a universal optimum. Task-utility coefficient sensitivity checks the internal QoE construction, while CPU-capacity, SLA and server-heterogeneity scaling test load, threshold strictness and heterogeneous legal server choices.",
        187: "Table 9. Controlled attribution of reporting fitness under equal-NFE and common-refinement conditions.",
        189: "Fig. 10. Objective-weight sensitivity of QoE, active-user fairness and soft CSR.",
        190: "The penalty heatmaps compare returned solutions under a common [[\\lambda_{\\mathrm{ref}}=1]]; they do not alter the reporting definition.",
        191: "Table 10. Dynamic-penalty sensitivity under fixed reporting fitness.",
        194: "Fig. 11. Dynamic-penalty sensitivity heatmaps for soft CSR and reporting fitness.",
        195: "The nine penalty schedules are reported without post-hoc selection. Full objective-weight, task-utility, CPU-capacity, SLA and server-heterogeneity tables remain in the repository supplement and extend the sensitivity boundary without post-hoc tuning claims.",
        196: "Overall comparative interpretation.",
        198: "Fig. 12. Reporting fitness under equal-NFE and common-initialisation/refinement controls; lower is better.",
        199: "Figure 12 shows directly that RDHO-core is not universally best at equal NFE and that common refinement closes much of the RIME/DBO gap.",
        200: "RDHO-full supplies the lowest configured end-to-end reporting fitness, but the equal-NFE result rejects universal superiority of RDHO-core, common refinement closes much of the parent-algorithm gap, raw-metric leaders vary and not every ablation is independently important.",
        202: "This work formulated joint task offloading and physical CPU allocation for a simulated cloud-edge-device epoch. Each task selects one legal source-local, reachable-edge or reachable-cloud node, and deterministic repair enforces physical Hz bounds and per-node capacity.",
        203: f"Across 30 paired end-to-end runs, RDHO-full has the lowest mean fixed reporting fitness ({f(rdho, 'fitness_mean')}) with hard feasibility in every returned solution. Corrected paired tests support the complete solver. Equal-NFE and common-postprocessing controls prevent attributing this result to the hybrid operator alone.",
        204: "Limitations include synthetic offline tasks, fixed-rate communication, deterministic cloud relay selection, device-side rather than infrastructure energy, a periodic no-backlog AoI approximation, coupled objective terms, engineering utility coefficients, aggregate binary CSR and unequal NFE in the end-to-end comparison. Future work should study queue-aware arrivals, communication-resource optimisation, infrastructure energy, calibrated QoE, discrete server operators and physical testbeds.",
        214: "Code, configurations, tests, all fresh V2 per-run outputs, summaries, paired statistics, figures and reproduction commands are archived at tag v2-paper-artifacts-2026-07 in https://github.com/Ryan-Yii/mec-rdho-offloading. Numerical artifacts were generated at 78c51c13ce7405654d488aea593d184be930e16a; the tagged publication changes only audit, export, plotting and manuscript tooling thereafter. All data are synthetic, and the WHITE repository is provenance context only.",
    }


def table_values() -> list[list[list[str]]]:
    main = read_rows(RESULTS / "summary" / "main_30_summary_mean_std.csv", "algorithm")
    wilcoxon = list(csv.DictReader((RESULTS / "statistics" / "wilcoxon_fitness_results.csv").open(encoding="utf-8")))
    ablation = read_rows(RESULTS / "summary" / "ablation_30_summary_mean_std.csv", "algorithm")
    scale = read_rows(RESULTS / "summary" / "scalability_summary_mean_std.csv", "task_number")
    controlled = list(csv.DictReader((RESULTS / "summary" / "controlled_attribution_summary.csv").open(encoding="utf-8")))
    penalty = list(csv.DictReader((RESULTS / "sensitivity" / "summary" / "dynamic_penalty_sensitivity_summary_mean_std.csv").open(encoding="utf-8")))
    notation = [["Symbol", "Definition"], *[[latex, definition] for latex, definition in NOTATION_ROWS]]
    algorithm = [["Algorithm 1. RDHO joint offloading and physical CPU allocation", "Algorithm 1. RDHO joint offloading and physical CPU allocation"], ["Require:", "Scenario, objective weights, initial penalty, growth exponent, population size and iterations"], ["Ensure:", "Repaired best assignment and CPU allocation on the fixed reporting objective"], ["1", "Generate Gaussian and uniform population subsets"], ["2", "Insert greedy seed and configured perturbations"], ["3", "Decode legal nodes; repair CPU capacity; evaluate the base objective and soft CSR"], ["4", "for each configured iteration do"], ["5", "Evaluate parents with the current dynamic penalty"], ["6", "Assign roles and preserve configured elites"], ["7", "Generate producer RIME-DBO fusion candidates"], ["8", "Generate follower puncture/foraging candidates"], ["9", "Generate scout theft/Cauchy candidates"], ["10", "Decode and repair every candidate"], ["11", "Compare parent and candidate under the same current penalty"], ["12", "Update the independent fixed-objective incumbent"], ["13", "end for"], ["14", "If full mode, apply deterministic coordinate refinement"], ["15", "Re-evaluate with fixed reporting coefficient 1 and verify hard feasibility"], ["Return", "Node assignments, CPU frequencies and all reported metrics"], ["Note", "Dynamic search fitness is never tabled as final fitness"]]
    system = [["Parameter", "Value and interpretation"], ["Devices / edge / cloud", "20 / 4 / 2"], ["Tasks", "40 heterogeneous tasks"], ["Node CPU capacity", "Device 2.2-3.0; edge 18-28; cloud 55-75 GHz"], ["Minimum allocatable CPU", "Device 0.2; edge 0.8; cloud 1.5 GHz"], ["Transmit power", "0.2-0.8 W"], ["Device-edge rate", "8-30 Mbit/s; 10% sparse links, connectivity repaired"], ["Edge-cloud rate", "60-150 Mbit/s; 5% sparse links, connectivity repaired"], ["Energy coefficient", "(0.8-1.4) × 10⁻²⁷ J s² cycle⁻³"], ["Fixed overhead", "Edge 0.010 s; cloud 0.055 s"], ["Cloud relay", "Fastest legal fixed relay for each selected cloud"], ["Excluded controls", "Bandwidth, power, association, routing and queue scheduling"]]
    task_ranges = [["Parameter", "Compute-intensive", "Data-intensive", "Real-time", "Lightweight"], ["Sampling probability", "0.28", "0.24", "0.28", "0.20"], ["Input data (MB)", "8-35", "30-90", "2-15", "0.5-5"], ["CPU cycles (Gcycles)", "1.8-4.5", "0.8-2.2", "0.5-1.8", "0.1-0.8"], ["Maximum delay (s)", "1.5-3.0", "2.5-5.0", "0.35-1.0", "0.8-2.0"], ["AoI threshold (s)", "2.0-3.0", "3.0-5.0", "0.5-1.0", "1.0-2.0"], ["Energy budget (J)", "2.5-6.0", "2.0-5.0", "1.0-3.5", "0.5-2.0"], ["Battery ratio", "0.45-1.0", "0.40-0.95", "0.55-1.0", "0.50-1.0"], ["Priority / interval (s)", "0.60-0.90 / 0.50-1.00", "0.50-0.80 / 0.80-1.50", "0.80-1.00 / 0.10-0.30", "0.40-0.70 / 0.30-0.60"]]
    parameters = [["Parameter", "Value"], ["Population / iterations", "50 / 150"], ["Objective weights (energy, delay, AoI, QoE, fairness)", "0.15, 0.15, 0.20, 0.25, 0.25"], ["Dynamic penalty", "Initial value 1; growth exponent 2"], ["Reporting coefficient", "Fixed at 1"], ["Main paired runs", "30"], ["Equal-NFE budget", "3801 per population method"], ["Scalability", "20, 40, 60, 80, 100 tasks; 10 runs each"], ["Compared methods", "RDHO, RIME, DBO, TLBO-HHO, CWTSSA, Greedy-ED"]]
    main_table = [["Alg.", "Reporting fitness", "Device energy (J)", "Delay (s)", "AoI (s)", "QoE", "Fairness", "Soft CSR", "Time (s)", "NFE"]]
    for name in ("RDHO", "RIME", "DBO", "TLBO-HHO", "CWTSSA", "Greedy-ED"):
        row = main[name]
        main_table.append(["RDHO-full" if name == "RDHO" else name, pm(row, "fitness"), pm(row, "energy", 2), pm(row, "delay"), pm(row, "aoi"), pm(row, "qoe"), pm(row, "fairness"), pm(row, "csr"), pm(row, "runtime"), str(int(float(row["nfe_mean"])))])
    stat_table = [["Comparison", "[[W]]", "Two-sided [[p]]", "Holm [[p]]", "Median diff.", "Signed [[r_{rb}]]", "W/T/L"]]
    for row in wilcoxon:
        stat_table.append([row["comparison"].replace("RDHO", "RDHO-full", 1), f"{float(row['w_statistic']):.0f}", f"{float(row['p_value']):.2e}", f"{float(row['p_holm']):.2e}", f"{float(row['median_difference']):.4f}", f"{float(row['rank_biserial']):.3f}", f"{row['wins']}/{row['ties']}/{row['losses']}"])
    ablation_table = [["Variant", "Reporting fitness", "QoE", "Fairness", "Soft CSR", "Time (s)", "NFE"]]
    for name in ("RDHO-full", "RDHO-core", "RDHO-w/o dual-source initialization", "RDHO-w/o adaptive role allocation", "RDHO-w/o elite preservation", "RDHO-w/o dynamic penalty"):
        row = ablation[name]
        label = name.replace("RDHO-w/o ", "w/o ").replace("initialization", "init.").replace("preservation", "")
        ablation_table.append([label, pm(row, "fitness"), pm(row, "qoe"), pm(row, "fairness"), pm(row, "csr"), pm(row, "runtime"), str(int(float(row["nfe_mean"])))])
    scale_table = [["Tasks", "Reporting fitness", "Soft CSR", "Time (s)", "NFE"]]
    for count in ("20", "40", "60", "80", "100"):
        row = scale[count]
        scale_table.append([count, pm(row, "fitness"), pm(row, "csr"), pm(row, "runtime"), str(int(float(row["nfe_mean"])))])
    controlled_table = [["Method", "Equal NFE", "Common init.", "Common refine.", "Reporting fitness, mean (SD)", "Effect size (reference - row)"]]
    for row in controlled:
        method = row["method"].replace(" + common refinement", " + refine")
        equal_nfe = row["equal_nfe"].replace("3801", "3,801").replace("10232", "10,232")
        controlled_table.append([method, equal_nfe, row["common_initialisation"], row["common_refinement"], row["reporting_fitness_mean_sd"], row["paired_effect"]])
    penalty_table = [["Initial penalty", "Growth exponent", "Reporting fitness", "QoE", "Fairness", "Soft CSR", "Time (s)"]]
    for row in penalty:
        penalty_table.append([f"{float(row['lambda0']):.1f}", f"{float(row['alpha']):.1f}", pm(row, "fitness"), pm(row, "qoe"), pm(row, "fairness"), pm(row, "csr"), pm(row, "runtime")])
    return [notation, algorithm, system, task_ranges, parameters, main_table, stat_table, ablation_table, scale_table, controlled_table, penalty_table]


def architecture_png() -> bytes:
    return (ROOT / "figures" / "paper" / "v2" / "system_architecture.png").read_bytes()


SUPPLIED_REFERENCES = [
    "[37] Ma, C., Zhu, J., Liu, M., Zhao, H., Liu, N. and Zou, X. (2021) 'Parking edge computing: parked-vehicle-assisted task offloading for urban VANETs', IEEE Internet of Things Journal, Vol. 8, No. 11, pp.9344-9358, doi: 10.1109/JIOT.2021.3056396.",
    "[38] Wu, H., Wolter, K., Jiao, P., Deng, Y., Zhao, Y. and Xu, M. (2021) 'EEDTO: an energy-efficient dynamic task offloading algorithm for blockchain-enabled IoT-edge-cloud orchestrated computing', IEEE Internet of Things Journal, Vol. 8, No. 4, pp.2163-2176, doi: 10.1109/JIOT.2020.3033521.",
    "[39] Feng, J., Yu, F.R., Pei, Q., Chu, X., Du, J. and Zhu, L. (2020) 'Cooperative computation offloading and resource allocation for blockchain-enabled mobile-edge computing: a deep reinforcement learning approach', IEEE Internet of Things Journal, Vol. 7, No. 7, pp.6214-6228, doi: 10.1109/JIOT.2019.2961707.",
    "[40] Yuan, X., Tian, H., Wang, H., Su, H., Liu, J. and Taherkordi, A. (2020) 'Edge-enabled WBANs for efficient QoS provisioning healthcare monitoring: a two-stage potential game-based computation offloading strategy', IEEE Access, Vol. 8, pp.92718-92730, doi: 10.1109/ACCESS.2020.2992639.",
]


def append_supplied_references(root: etree._Element, paragraphs: list[etree._Element], highlighted: bool) -> None:
    body = root.find("w:body", namespaces=NS)
    if body is None:
        raise ValueError("document body is missing")
    template_ppr = paragraphs[-1].find("w:pPr", namespaces=NS)
    section = body.find("w:sectPr", namespaces=NS)
    insert_at = len(body) if section is None else body.index(section)
    for reference in SUPPLIED_REFERENCES:
        paragraph = etree.Element(qn(W, "p"))
        if template_ppr is not None:
            paragraph.append(deepcopy(template_ppr))
        paragraph.append(new_run(reference, highlighted))
        body.insert(insert_at, paragraph)
        insert_at += 1


def write_docx(path: Path, highlighted: bool, replies: bool) -> list[dict[str, str]]:
    required = [RESULTS / "summary" / "common_control_30_summary_mean_std.csv", RESULTS / "sensitivity" / "summary" / "dynamic_penalty_sensitivity_summary_mean_std.csv"]
    missing = [str(item) for item in required if not item.is_file()]
    if missing:
        raise FileNotFoundError("missing completed experiment artifacts: " + ", ".join(missing))
    with zipfile.ZipFile(SOURCE) as source_zip:
        infos = source_zip.infolist()
        parts = {info.filename: source_zip.read(info.filename) for info in infos}
    parts["docProps/core.xml"] = update_core_properties(parts["docProps/core.xml"])
    root = etree.fromstring(parts["word/document.xml"])
    paragraphs = root.xpath(".//w:body//w:p[not(ancestor::w:tbl)]", namespaces=NS)
    if len(paragraphs) != 253:
        raise ValueError(f"expected 253 body paragraphs, found {len(paragraphs)}")
    equations = {36,38,40,42,45,47,50,58,62,66,69,72,76,83,85,88,93,94,98,125,126}
    for index, text in paragraph_updates().items():
        replace_paragraph(paragraphs[index], text, highlighted, math=index in equations)
    apply_inline_math(paragraphs, highlighted)
    apply_professional_equations(paragraphs, highlighted)
    append_supplied_references(root, paragraphs, highlighted)
    tables = root.xpath("./w:body/w:tbl", namespaces=NS)
    if len(tables) != 11:
        raise ValueError(f"expected 11 tables, found {len(tables)}")
    for table, values in zip(tables, table_values()):
        fill_table(table, values, highlighted)
    set_table_column_widths(tables[5], [892, 1250, 1050, 980, 1050, 900, 1050, 900, 1000, 1104])
    set_table_column_widths(tables[6], [2700, 650, 1400, 1400, 1400, 1400, 940])
    set_table_column_widths(tables[9], [1500, 1300, 1300, 1300, 1800, 1595])
    set_table_column_widths(tables[10], [1000, 1200, 1650, 1300, 1400, 1400, 1383])
    apply_inline_math(root.xpath(".//w:p", namespaces=NS), highlighted)
    apply_notation_math(tables[0], highlighted)
    for caption in (
        "Table 1. Main Notation",
        "Table 3. Task-generation ranges and sampling probabilities.",
    ):
        remove_forced_page_break(root, caption)
    if not highlighted:
        remove_revision_highlights(root)
    parts["word/document.xml"] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")
    replacements = {
        "word/media/image2.png": architecture_png(),
        "word/media/image3.png": (RESULTS / "figures" / "convergence_curve.png").read_bytes(),
        "word/media/image4.png": (RESULTS / "figures" / "energy_comparison.png").read_bytes(),
        "word/media/image5.png": (RESULTS / "figures" / "delay_comparison.png").read_bytes(),
        "word/media/image6.png": (RESULTS / "figures" / "aoi_comparison.png").read_bytes(),
        "word/media/image7.png": (RESULTS / "figures" / "qoe_fairness_comparison.png").read_bytes(),
        "word/media/image8.png": (RESULTS / "figures" / "csr_comparison.png").read_bytes(),
        "word/media/image9.png": (RESULTS / "figures" / "ablation_study.png").read_bytes(),
        "word/media/image10.png": (RESULTS / "figures" / "scalability.png").read_bytes(),
        "word/media/image11.png": (RESULTS / "sensitivity" / "figures" / "weight_sensitivity_qoe_fairness_csr.png").read_bytes(),
        "word/media/image12.png": (RESULTS / "sensitivity" / "figures" / "penalty_sensitivity_heatmaps.png").read_bytes(),
        "word/media/image13.png": (RESULTS / "figures" / "controlled_attribution.png").read_bytes(),
    }
    parts.update(replacements)
    audit = append_replies(parts) if replies else []
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as target:
        written = set()
        for info in infos:
            target.writestr(info, parts[info.filename])
            written.add(info.filename)
        for name, payload in parts.items():
            if name not in written:
                target.writestr(name, payload)
    return audit


def write_audit(rows: list[dict[str, str]]) -> None:
    with AUDIT_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    rethreaded = sum(row["legacy_reply_status"].startswith("rethreaded") for row in rows)
    lines = [
        "# Comment Reply Audit",
        "",
        f"Reviewed source SHA-256: `{hashlib.sha256(SOURCE.read_bytes()).hexdigest()}`",
        "",
        f"Original supervisor comments replied to: {len(rows)}",
        f"Legacy stand-alone replies rethreaded: {rethreaded}",
        "All original and V2 reply threads remain unresolved.",
        "",
        "| Original ID | Anchor | Actual revision | Legacy reply | V2 reply ID | Parent paraId | Status |",
        "| ---: | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in rows:
        anchor = row["anchor"].replace("|", "/").replace("\n", " ")
        lines.append(
            f"| {row['original_comment_id']} | {anchor} | {row['actual_revision'].replace('|', '/')} | "
            f"{row['legacy_reply_id']} ({row['legacy_reply_status']}) | {row['reply_comment_id']} | "
            f"`{row['thread_parent_para_id']}` | {row['status']} |"
        )
    AUDIT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V2 reviewed and intermediate clean manuscripts")
    parser.add_argument("--source", type=Path, required=True, help="0722 comments-preserving DOCX editing base")
    parser.add_argument("--output-dir", type=Path, required=True, help="destination directory")
    args = parser.parse_args()
    configure_paths(args.source.resolve(), args.output_dir.resolve())
    audit = write_docx(REVIEWED, highlighted=True, replies=True)
    write_docx(CLEAN_WITH_COMMENTS, highlighted=False, replies=False)
    write_audit(audit)
    print(REVIEWED)
    print(CLEAN_WITH_COMMENTS)
    print(AUDIT_CSV)


if __name__ == "__main__":
    main()
