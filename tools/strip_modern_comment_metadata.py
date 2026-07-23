from __future__ import annotations

import argparse
import tempfile
import zipfile
from pathlib import Path

from lxml import etree


REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
COMMENT_PARTS = {
    "word/comments.xml",
    "word/commentsExtended.xml",
    "word/commentsIds.xml",
    "word/commentsExtensible.xml",
    "word/people.xml",
    "word/_rels/comments.xml.rels",
}


def xml_bytes(root: etree._Element) -> bytes:
    return etree.tostring(
        root,
        encoding="UTF-8",
        xml_declaration=True,
        standalone=True,
    )


def clean_relationships(payload: bytes) -> bytes:
    root = etree.fromstring(payload)
    for relation in list(root.findall(f"{{{REL}}}Relationship")):
        relation_type = relation.get("Type", "").lower()
        if "comment" in relation_type or relation_type.endswith("/people"):
            root.remove(relation)
    return xml_bytes(root)


def clean_content_types(payload: bytes) -> bytes:
    root = etree.fromstring(payload)
    targets = {f"/{part}" for part in COMMENT_PARTS}
    for override in list(root.findall(f"{{{CT}}}Override")):
        if override.get("PartName", "") in targets:
            root.remove(override)
    return xml_bytes(root)


def strip_metadata(path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="v2-clean-docx-") as temporary:
        replacement = Path(temporary) / path.name
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(replacement, "w", zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                name = info.filename
                if name in COMMENT_PARTS:
                    continue
                payload = source.read(name)
                if name == "word/_rels/document.xml.rels":
                    payload = clean_relationships(payload)
                elif name == "[Content_Types].xml":
                    payload = clean_content_types(payload)
                target.writestr(info, payload)
        replacement.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove modern orphan comment metadata after comments_strip.py")
    parser.add_argument("docx", type=Path)
    args = parser.parse_args()
    strip_metadata(args.docx.resolve())
    print(f"Removed modern comment metadata from {args.docx}")


if __name__ == "__main__":
    main()
