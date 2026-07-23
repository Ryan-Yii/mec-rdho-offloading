from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
W15 = "http://schemas.microsoft.com/office/word/2012/wordml"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def qn(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def text_of(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter(qn(W, "t")))


def comment_records(archive: zipfile.ZipFile) -> tuple[list[dict[str, str]], dict[str, str], list[ET.Element]]:
    comments = ET.fromstring(archive.read("word/comments.xml"))
    extended = ET.fromstring(archive.read("word/commentsExtended.xml"))
    records = []
    para_to_id = {}
    for comment in comments.findall(qn(W, "comment")):
        paragraphs = comment.findall(qn(W, "p"))
        if not paragraphs:
            raise AssertionError("comment without paragraph")
        para_ids = tuple(paragraph.get(qn(W14, "paraId"), "") for paragraph in paragraphs)
        para_id = para_ids[-1]
        comment_id = comment.get(qn(W, "id"), "")
        for value in para_ids:
            para_to_id[value] = comment_id
        records.append({
            "id": comment_id,
            "author": comment.get(qn(W, "author"), ""),
            "date": comment.get(qn(W, "date"), ""),
            "initials": comment.get(qn(W, "initials"), ""),
            "para_id": para_id,
            "para_ids": para_ids,
            "text": text_of(comment),
        })
    return records, para_to_id, list(extended.findall(qn(W15, "commentEx")))


def verify_comments(source: Path, reviewed: Path) -> None:
    with zipfile.ZipFile(source) as source_zip, zipfile.ZipFile(reviewed) as reviewed_zip:
        original, _, _ = comment_records(source_zip)
        revised, para_to_id, extended = comment_records(reviewed_zip)
        if len(original) != 86 or len(revised) != 129:
            raise AssertionError(f"unexpected comment counts: source={len(original)}, reviewed={len(revised)}")
        original_by_id = {row["id"]: row for row in original}
        revised_by_id = {row["id"]: row for row in revised}
        for comment_id, expected in original_by_id.items():
            actual = revised_by_id[comment_id]
            for key in ("author", "date", "initials", "para_id", "para_ids", "text"):
                if actual[key] != expected[key]:
                    raise AssertionError(f"original comment {comment_id} changed field {key}")

        new_replies = [row for row in revised if row["text"].startswith("V2 reply:")]
        if len(new_replies) != 43:
            raise AssertionError(f"expected 43 V2 replies, found {len(new_replies)}")
        author_original = [row for row in revised if row["author"] == "祎宝" and row["id"] in original_by_id]
        web_para_ids = {
            para_id
            for row in revised if row["author"] == "webuser"
            for para_id in row["para_ids"]
        }
        parent_by_para = {
            node.get(qn(W15, "paraId"), ""): node.get(qn(W15, "paraIdParent"), "")
            for node in extended
        }
        if any(node.get(qn(W15, "done"), "0") != "0" for node in extended):
            raise AssertionError("at least one comment thread is marked resolved")
        if any(parent_by_para.get(row["para_id"], "") not in web_para_ids for row in author_original):
            raise AssertionError("an original author reply is not threaded to a supervisor comment")
        if any(parent_by_para.get(row["para_id"], "") not in web_para_ids for row in new_replies):
            raise AssertionError("a V2 reply is not threaded to a supervisor comment")
        if any(para_to_id.get(parent_by_para[row["para_id"]], "") == "" for row in new_replies):
            raise AssertionError("a V2 reply parent cannot be resolved")

        source_doc = ET.fromstring(source_zip.read("word/document.xml"))
        reviewed_doc = ET.fromstring(reviewed_zip.read("word/document.xml"))
        for tag in ("commentRangeStart", "commentRangeEnd", "commentReference"):
            source_count = sum(1 for _ in source_doc.iter(qn(W, tag)))
            reviewed_count = sum(1 for _ in reviewed_doc.iter(qn(W, tag)))
            if source_count != reviewed_count:
                raise AssertionError(f"comment anchor count changed for {tag}: {source_count} -> {reviewed_count}")


def verify_clean(clean: Path) -> None:
    with zipfile.ZipFile(clean) as archive:
        remaining_parts = [name for name in archive.namelist() if "comment" in name.lower() or name == "word/people.xml"]
        if remaining_parts:
            raise AssertionError(f"clean DOCX still contains comment metadata: {remaining_parts}")
        document = ET.fromstring(archive.read("word/document.xml"))
        for tag in ("commentRangeStart", "commentRangeEnd", "commentReference"):
            if any(True for _ in document.iter(qn(W, tag))):
                raise AssertionError(f"clean DOCX still contains {tag}")
        body_text = text_of(document).lower()
        if any(True for _ in document.iter(qn(W, "highlight"))):
            raise AssertionError("clean DOCX still contains revision highlights")
        obsolete = (
            "service intensity",
            "load-adjusted",
            "single-epoch surrogate",
            "priority-aware fairness",
            "computation-control",
            "directly deployable",
        )
        found = [term for term in obsolete if term in body_text]
        if found:
            raise AssertionError(f"obsolete manuscript terms remain: {found}")


def verify_equations(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
    math_paragraphs = [
        paragraph
        for paragraph in document.iter(qn(W, "p"))
        if any(True for _ in paragraph.iter(qn(M, "oMath")))
    ]
    if len(math_paragraphs) != 22:
        raise AssertionError(f"expected 22 professional equation paragraphs, found {len(math_paragraphs)}")
    labels = []
    for paragraph in math_paragraphs:
        visible_text = text_of(paragraph).strip()
        if visible_text:
            labels.append(visible_text)
    expected = [f"({index})" for index in range(1, 22)]
    if labels != expected:
        raise AssertionError(f"equation numbering mismatch: {labels}")


def verify_images(reviewed: Path, repo: Path) -> None:
    expected = {
        "word/media/image2.png": repo / "figures/paper/v2/system_architecture.png",
        "word/media/image3.png": repo / "results/v2/figures/convergence_curve.png",
        "word/media/image4.png": repo / "results/v2/figures/energy_comparison.png",
        "word/media/image5.png": repo / "results/v2/figures/delay_comparison.png",
        "word/media/image6.png": repo / "results/v2/figures/aoi_comparison.png",
        "word/media/image7.png": repo / "results/v2/figures/qoe_fairness_comparison.png",
        "word/media/image8.png": repo / "results/v2/figures/csr_comparison.png",
        "word/media/image9.png": repo / "results/v2/figures/ablation_study.png",
        "word/media/image10.png": repo / "results/v2/figures/scalability.png",
        "word/media/image11.png": repo / "results/v2/sensitivity/figures/weight_sensitivity_qoe_fairness_csr.png",
        "word/media/image12.png": repo / "results/v2/sensitivity/figures/penalty_sensitivity_heatmaps.png",
        "word/media/image13.png": repo / "results/v2/figures/radar_chart.png",
    }
    with zipfile.ZipFile(reviewed) as archive:
        for part, source in expected.items():
            if sha256(archive.read(part)) != sha256(source.read_bytes()):
                raise AssertionError(f"manuscript image differs from repository source: {part}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify V2 manuscript OOXML and repository-image alignment")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--reviewed", type=Path, required=True)
    parser.add_argument("--clean", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    verify_comments(args.source, args.reviewed)
    verify_clean(args.clean)
    verify_equations(args.reviewed)
    verify_equations(args.clean)
    verify_images(args.reviewed, args.repo)
    print("V2 manuscript verification passed")


if __name__ == "__main__":
    main()
