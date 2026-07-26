from __future__ import annotations

import argparse
import tempfile
import zipfile
from pathlib import Path

from lxml import etree


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DC = "http://purl.org/dc/elements/1.1/"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W}

TITLE = (
    "RIME\u2013DBO-Based Capacity-Feasible Task Offloading and Resource Allocation "
    "in Mobile Edge Computing"
)
SUBJECT = (
    "Audited physical MEC offloading V2 manuscript aligned to experiment "
    "baseline 0264b6d"
)
OLD_AVAILABILITY = (
    "The project repository containing the implementation, versioned configurations, "
    "synthetic scenario generator, raw and summary result files, statistical-analysis "
    "outputs, manuscript tables, figures, and reproduction instructions is publicly "
    "available at https://github.com/Ryan-Yii/mec-rdho-offloading. A versioned GitHub "
    "release provides an immutable snapshot of the reproducibility materials. No "
    "proprietary, confidential, human-subject, or third-party restricted data were "
    "used; all study data were generated synthetically."
)
NEW_AVAILABILITY = (
    "The project repository containing the implementation, versioned configurations, "
    "synthetic scenario generator, raw and summary result files, statistical-analysis "
    "outputs, manuscript tables, figures, and reproduction instructions is publicly "
    "available at https://github.com/Ryan-Yii/mec-rdho-offloading. The v2.0.0 GitHub "
    "release provides an immutable snapshot of experiment baseline 0264b6d, the "
    "verification fixes, the aligned manuscript, and the reproducibility materials. "
    "No proprietary, confidential, human-subject, or third-party restricted data were "
    "used; all study data were generated synthetically."
)


def xml_bytes(root: etree._Element) -> bytes:
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )


def replace_paragraph_text(payload: bytes) -> tuple[bytes, int]:
    root = etree.fromstring(payload)
    replacements = 0
    for paragraph in root.xpath(".//w:p", namespaces=NS):
        text_nodes = paragraph.xpath(".//w:t", namespaces=NS)
        text = "".join(node.text or "" for node in text_nodes)
        if OLD_AVAILABILITY not in text:
            continue
        updated = text.replace(OLD_AVAILABILITY, NEW_AVAILABILITY)
        text_nodes[0].text = updated
        for node in text_nodes[1:]:
            node.text = ""
        replacements += 1
    return xml_bytes(root), replacements


def update_core_properties(payload: bytes) -> bytes:
    root = etree.fromstring(payload)
    for name, value in (("title", TITLE), ("subject", SUBJECT)):
        node = root.find(f"{{{DC}}}{name}")
        if node is None:
            node = etree.SubElement(root, f"{{{DC}}}{name}")
        node.text = value
    return xml_bytes(root)


def remove_highlights(payload: bytes) -> bytes:
    root = etree.fromstring(payload)
    for node in root.xpath(".//w:highlight", namespaces=NS):
        node.getparent().remove(node)
    return xml_bytes(root)


def used_media(archive: zipfile.ZipFile) -> set[str]:
    media: set[str] = set()
    for name in archive.namelist():
        if not name.startswith("word/_rels/") or not name.endswith(".rels"):
            continue
        root = etree.fromstring(archive.read(name))
        for relation in root.findall(f"{{{REL}}}Relationship"):
            target = relation.get("Target", "")
            if relation.get("Type", "").endswith("/image") and target.startswith("media/"):
                media.add("word/" + target)
    return media


def finalize(source: Path, output: Path, *, strip_highlights: bool) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rdho-release-docx-") as temporary:
        staged = Path(temporary) / output.name
        with zipfile.ZipFile(source) as source_zip:
            media = used_media(source_zip)
            document, replacements = replace_paragraph_text(
                source_zip.read("word/document.xml")
            )
            source_text = "".join(
                etree.fromstring(source_zip.read("word/document.xml")).xpath(
                    ".//w:t/text()", namespaces=NS
                )
            )
            if OLD_AVAILABILITY in source_text and replacements != 1:
                raise AssertionError("Data Availability replacement was not unique")
            if OLD_AVAILABILITY not in source_text and NEW_AVAILABILITY not in source_text:
                raise AssertionError("Data Availability paragraph was not recognised")
            if strip_highlights:
                document = remove_highlights(document)

            with zipfile.ZipFile(staged, "w", zipfile.ZIP_DEFLATED) as target_zip:
                for info in source_zip.infolist():
                    name = info.filename
                    if name.startswith("word/media/") and name not in media:
                        continue
                    payload = source_zip.read(name)
                    if name == "word/document.xml":
                        payload = document
                    elif name == "docProps/core.xml":
                        payload = update_core_properties(payload)
                    target_zip.writestr(info, payload)
        staged.replace(output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finalize the 0726 manuscript metadata and release statement."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--strip-highlights", action="store_true")
    args = parser.parse_args()
    finalize(args.source.resolve(), args.out.resolve(), strip_highlights=args.strip_highlights)
    print(f"release manuscript written: {args.out}")


if __name__ == "__main__":
    main()
