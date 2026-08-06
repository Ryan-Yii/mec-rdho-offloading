from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "case_studies/reproaudit_v0_1/README.md"


def test_case_readme_is_bounded_and_links_assets() -> None:
    text = README.read_text(encoding="utf-8")
    assert "structured consistency acceptance" in text
    assert "b8abb436f215a9b2f4d646cf5fc0cf048174b68d" in text
    assert "R202" in text and "SKIP/INFO" in text
    assert "reproaudit-0.1.0-py3-none-any.whl" in text
    assert "dfab966ed90b98620d0c6b4fbeb80b31b44879493e092d4ef9314c9812998b5c" in text
    assert "faithful_baseline/experiment.yaml" in text
    for forbidden in ("proves the paper is fully reproducible", "algorithm correctness", "third-party certification", "PyPI", "DOI"):
        assert forbidden.lower() not in text.lower()


def test_case_readme_uses_relative_paths_only() -> None:
    text = README.read_text(encoding="utf-8")
    assert "/Users/" not in text and "generated_at:" not in text
