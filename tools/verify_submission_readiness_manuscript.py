from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from pathlib import Path

from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
W15 = "http://schemas.microsoft.com/office/word/2012/wordml"
W16CID = "http://schemas.microsoft.com/office/word/2016/wordml/cid"
W16CEX = "http://schemas.microsoft.com/office/word/2018/wordml/cex"
NS = {"w": W, "w14": W14, "w15": W15, "w16cid": W16CID, "w16cex": W16CEX}
TARGET_PARENTS = ("0", "2", "7", "12", "50", "52", "56", "61")
REPLY_FRAGMENT = "已按本轮投稿前意见补充 RDHO 全部更新"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def text_of(node: etree._Element) -> str:
    return "".join(node.xpath(".//w:t/text()", namespaces=NS)).strip()


def comment_maps(comments: etree._Element, extended: etree._Element) -> tuple[dict[str, etree._Element], dict[str, str]]:
    by_id = {node.get(f"{{{W}}}id"): node for node in comments.xpath("./w:comment", namespaces=NS)}
    para_to_id = {
        paragraph.get(f"{{{W14}}}paraId"): comment_id
        for comment_id, node in by_id.items()
        for paragraph in node.xpath("./w:p", namespaces=NS)
    }
    parent = {
        para_to_id.get(node.get(f"{{{W15}}}paraId")): para_to_id.get(node.get(f"{{{W15}}}paraIdParent"))
        for node in extended.xpath("./w15:commentEx[@w15:paraIdParent]", namespaces=NS)
    }
    return by_id, parent


def verify(source: Path, reviewed: Path, clean: Path, audit: Path) -> dict[str, object]:
    with zipfile.ZipFile(source) as base_zip, zipfile.ZipFile(reviewed) as reviewed_zip:
        base_names = set(base_zip.namelist())
        reviewed_names = set(reviewed_zip.namelist())
        required = {
            "word/comments.xml",
            "word/commentsExtended.xml",
            "word/commentsIds.xml",
            "word/commentsExtensible.xml",
            "word/people.xml",
        }
        if not required.issubset(reviewed_names):
            raise AssertionError("annotated manuscript is missing modern comment parts")
        base_comments = etree.fromstring(base_zip.read("word/comments.xml"))
        reviewed_comments = etree.fromstring(reviewed_zip.read("word/comments.xml"))
        reviewed_extended = etree.fromstring(reviewed_zip.read("word/commentsExtended.xml"))
        reviewed_ids = etree.fromstring(reviewed_zip.read("word/commentsIds.xml"))
        reviewed_cex = etree.fromstring(reviewed_zip.read("word/commentsExtensible.xml"))
        base_ids = etree.fromstring(base_zip.read("word/commentsIds.xml"))
        base_cex = etree.fromstring(base_zip.read("word/commentsExtensible.xml"))
        base_by_id, _ = comment_maps(base_comments, etree.fromstring(base_zip.read("word/commentsExtended.xml")))
        reviewed_by_id, parent_map = comment_maps(reviewed_comments, reviewed_extended)
        if len(reviewed_by_id) != len(base_by_id) + len(TARGET_PARENTS):
            raise AssertionError("annotated comment count is not base plus targeted threaded replies")
        for comment_id, node in base_by_id.items():
            if comment_id not in reviewed_by_id or text_of(reviewed_by_id[comment_id]) != text_of(node):
                raise AssertionError(f"original comment was altered or removed: {comment_id}")
        reply_ids = []
        for parent_id in TARGET_PARENTS:
            matches = [
                comment_id
                for comment_id, candidate_parent in parent_map.items()
                if candidate_parent == parent_id and REPLY_FRAGMENT in text_of(reviewed_by_id[comment_id])
            ]
            if len(matches) != 1:
                raise AssertionError(f"missing or duplicated new threaded reply for parent {parent_id}")
            reply_ids.extend(matches)
        para_to_extended = {node.get(f"{{{W15}}}paraId"): node for node in reviewed_extended.xpath("./w15:commentEx", namespaces=NS)}
        for reply_id in reply_ids:
            paragraph = reviewed_by_id[reply_id].xpath("./w:p", namespaces=NS)[0]
            para_id = paragraph.get(f"{{{W14}}}paraId")
            if para_to_extended[para_id].get(f"{{{W15}}}done") != "0":
                raise AssertionError(f"new reply {reply_id} is marked resolved")
            if not reviewed_ids.xpath(f"./w16cid:commentId[@w16cid:paraId='{para_id}']", namespaces=NS):
                raise AssertionError(f"new reply {reply_id} is missing comment ID metadata")
        if len(reviewed_ids) != len(base_ids) + len(TARGET_PARENTS):
            raise AssertionError("comment ID metadata does not preserve the base plus new replies")
        if len(reviewed_cex) != len(base_cex) + len(TARGET_PARENTS):
            raise AssertionError("comment identity metadata count is inconsistent")
        document = etree.fromstring(reviewed_zip.read("word/document.xml"))
        text = "\n".join(document.xpath(".//w:t/text()", namespaces=NS))
        for required_text in (
            "RDHO-Based Capacity-Feasible Joint Task Offloading and Computing Resource Allocation",
            "Algorithm 2 defines complete deterministic repair",
            "does not prove that the entire scenario has no feasible assignment",
            "does not assign +infinity, retain the parent, or resample",
            "At iteration t, p=t/T_max and diversity D",
            "Nominal counts n_P, n_F and n_S",
            "no member is assigned twice",
            "one candidate can require O(N^2 M L)",
            "nominal role thresholds rather than guaranteed realised population proportions",
            "For fixed returned solutions, post-hoc rescoring",
            "DBO a clear advantage",
            "together with common refinement in Experiment B",
            "prespecified reporting coefficient lambda_ref=1",
            "common fixed reporting coefficient lambda_ref=1",
            "smaller but statistically significant advantage",
            "does not isolate the incremental contribution of each nested objective layer",
            "current implementation aborts an optimiser run if deterministic candidate repair fails",
            "public immutable GitHub tag/release",
            "allocated CPU-cycle rate",
            "result-return delay and downlink energy are omitted",
            "Model-based studies jointly allocate",
            "[3,11,13,14]",
            "[12,15-17]",
            "Experiment loops use no Python multiprocessing",
        ):
            if required_text not in text:
                raise AssertionError(f"manuscript misses required controlled framing: {required_text}")
        if text.index("Algorithm 2. Deterministic Legal-Node Reassignment") > text.index("5 RDHO-Based Capacity-Feasible"):
            raise AssertionError("Algorithm 2 must appear before the RDHO population method that references it")
        duplicate = "A returned incumbent consists of one repaired legal node and one allocated CPU-cycle rate per task."
        if text.count(duplicate) != 1:
            raise AssertionError("problem-complexity incumbent sentence is duplicated or missing")
        reviewed_yellow_count = len(document.xpath(".//w:highlight[@w:val='yellow']", namespaces=NS))
        if reviewed_yellow_count == 0:
            raise AssertionError("annotated manuscript contains no yellow revised text")

    with zipfile.ZipFile(clean) as clean_zip:
        names = set(clean_zip.namelist())
        if any("comment" in name.lower() or name.endswith("people.xml") for name in names):
            raise AssertionError("clean manuscript retains comments metadata")
        document = etree.fromstring(clean_zip.read("word/document.xml"))
        if document.xpath(".//w:commentRangeStart | .//w:commentRangeEnd | .//w:commentReference", namespaces=NS):
            raise AssertionError("clean manuscript retains comment anchors")
        if document.xpath(".//w:highlight[@w:val='yellow']", namespaces=NS):
            raise AssertionError("clean manuscript retains yellow revision highlighting")

    audit_rows = list(csv.DictReader(audit.open(encoding="utf-8")))
    if len(audit_rows) != len(TARGET_PARENTS):
        raise AssertionError("comment audit does not list all targeted replies")
    expected_reply_ids = {row["reply_comment_id"] for row in audit_rows}
    if expected_reply_ids != set(reply_ids):
        raise AssertionError("comment audit reply IDs disagree with OOXML")
    return {
        "source_sha256": sha256(source),
        "reviewed_sha256": sha256(reviewed),
        "clean_sha256": sha256(clean),
        "base_comment_count": len(base_by_id),
        "reviewed_comment_count": len(reviewed_by_id),
        "new_threaded_reply_ids": reply_ids,
        "yellow_highlight_count": reviewed_yellow_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the RDHO controlled-evidence manuscript DOCX structure.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--reviewed", type=Path, required=True)
    parser.add_argument("--clean", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = verify(args.source, args.reviewed, args.clean, args.audit)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print("controlled manuscript revision verification: PASS")


if __name__ == "__main__":
    main()
