from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

from tools.finalize_release_manuscript import NEW_AVAILABILITY, TITLE


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
DC = "http://purl.org/dc/elements/1.1/"
NS = {"w": W, "r": R, "pr": PR}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def document_text(payload: bytes) -> tuple[etree._Element, str]:
    root = etree.fromstring(payload)
    text = " ".join(value.strip() for value in root.xpath(".//w:t/text()", namespaces=NS) if value.strip())
    return root, " ".join(text.split())


def comment_records(payload: bytes) -> list[tuple[str, str, str, str]]:
    root = etree.fromstring(payload)
    records = []
    for node in root.xpath("./w:comment", namespaces=NS):
        records.append((
            node.get(f"{{{W}}}id", ""),
            node.get(f"{{{W}}}author", ""),
            node.get(f"{{{W}}}date", ""),
            "".join(node.xpath(".//w:t/text()", namespaces=NS)),
        ))
    return records


def comment_anchor_counts(root: etree._Element) -> dict[str, Counter[str]]:
    return {
        name: Counter(
            node.get(f"{{{W}}}id", "")
            for node in root.xpath(f".//w:{name}", namespaces=NS)
        )
        for name in ("commentRangeStart", "commentRangeEnd", "commentReference")
    }


def embedded_image_targets(archive: zipfile.ZipFile, document: etree._Element) -> list[str]:
    rels = etree.fromstring(archive.read("word/_rels/document.xml.rels"))
    targets = {
        node.get("Id"): "word/" + node.get("Target", "")
        for node in rels.findall(f"{{{PR}}}Relationship")
        if node.get("Type", "").endswith("/image")
    }
    relation_ids = document.xpath(".//*[@r:embed]/@r:embed", namespaces=NS)
    return [targets[relation_id] for relation_id in relation_ids]


def verify(source: Path, reviewed: Path, clean: Path) -> dict[str, object]:
    required_phrases = (
        TITLE,
        "Mobile edge computing (MEC) extends the computational capabilities",
        "Keywords: mobile edge computing; task offloading; computing resource allocation; capacity feasibility; controlled evaluation.",
        "Following MEC surveys, related work is organised by solution methodology",
        "3.1 MEC Network, Assumptions, and Task Model",
        "4 Problem Formulation",
        "5 RDHO-Based Task-Offloading Strategy",
        "Deterministic legal-node reassignment and excess-capacity projection shared by all solvers.",
        "6.3 Strictly Controlled RDHO Population Evidence",
        "1.4188",
        "1.6834",
        "1.2409",
        "0.9732",
        "0.9836",
        "0.9664",
        "3801",
        "10232",
        "significantly lower than RIME but significantly higher than DBO",
        "does not support superiority over DBO",
        "current implementation aborts an optimiser run if deterministic candidate repair fails",
        "no such failure occurred in the reported controlled experiments",
        NEW_AVAILABILITY,
    )

    with zipfile.ZipFile(source) as source_zip, zipfile.ZipFile(reviewed) as reviewed_zip:
        source_document, _ = document_text(source_zip.read("word/document.xml"))
        reviewed_document, reviewed_text = document_text(reviewed_zip.read("word/document.xml"))
        source_comments = comment_records(source_zip.read("word/comments.xml"))
        reviewed_comments = comment_records(reviewed_zip.read("word/comments.xml"))
        if len(source_comments) != 75 or reviewed_comments != source_comments:
            raise AssertionError("the 75 source comments were not preserved exactly")
        if comment_anchor_counts(reviewed_document) != comment_anchor_counts(source_document):
            raise AssertionError("comment anchors changed during release finalization")
        for phrase in required_phrases:
            if phrase not in reviewed_text:
                raise AssertionError(f"reviewed manuscript misses required text: {phrase}")
        if "release1" in reviewed_text.lower():
            raise AssertionError("reviewed manuscript contains release1 text")
        if reviewed_text.index("Fig. 1.") < reviewed_text.index("3 System Model"):
            raise AssertionError("Figure 1 appears before the System Model section")
        for number in range(1, 13):
            if reviewed_text.count(f"Fig. {number}.") != 1:
                raise AssertionError(f"Figure {number} caption is missing or duplicated")
        core = etree.fromstring(reviewed_zip.read("docProps/core.xml"))
        core_title = core.findtext(f"{{{DC}}}title")
        if core_title != TITLE:
            raise AssertionError("visible and metadata titles are not aligned")
        image_targets = embedded_image_targets(reviewed_zip, reviewed_document)
        if len(image_targets) != 12 or len(set(image_targets)) != 12:
            raise AssertionError("the manuscript must embed exactly Figures 1-12")
        media_files = {name for name in reviewed_zip.namelist() if name.startswith("word/media/")}
        comment_media = media_files - set(image_targets)
        if len(comment_media) != 1:
            raise AssertionError("the reviewed manuscript must retain one comment-image attachment")
        if reviewed_document.xpath(".//w:ins | .//w:del", namespaces=NS):
            raise AssertionError("reviewed manuscript contains tracked insertions/deletions")
        highlight_count = len(reviewed_document.xpath(".//w:highlight[@w:val='yellow']", namespaces=NS))
        if highlight_count == 0:
            raise AssertionError("reviewed manuscript lost revision highlights")

    with zipfile.ZipFile(clean) as clean_zip:
        clean_names = set(clean_zip.namelist())
        if any("comment" in name.lower() or name.endswith("people.xml") for name in clean_names):
            raise AssertionError("clean manuscript retains comment metadata")
        clean_document, clean_text = document_text(clean_zip.read("word/document.xml"))
        if clean_text != reviewed_text:
            raise AssertionError("clean and reviewed manuscript body text differs")
        if clean_document.xpath(
            ".//w:commentRangeStart | .//w:commentRangeEnd | .//w:commentReference | .//w:highlight",
            namespaces=NS,
        ):
            raise AssertionError("clean manuscript retains comments or highlights")

    return {
        "source_sha256": sha256_file(source),
        "reviewed_sha256": sha256_file(reviewed),
        "clean_sha256": sha256_file(clean),
        "preserved_comment_count": len(reviewed_comments),
        "reviewed_highlight_count": highlight_count,
        "embedded_figure_count": len(image_targets),
        "reviewed_comments_xml_sha256": sha256_bytes(
            zipfile.ZipFile(reviewed).read("word/comments.xml")
        ),
        "required_phrase_count": len(required_phrases),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the v2.0.0 release manuscript.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--reviewed", type=Path, required=True)
    parser.add_argument("--clean", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.source, args.reviewed, args.clean)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("release manuscript verification: PASS")


if __name__ == "__main__":
    main()
