from __future__ import annotations

import argparse
from pathlib import Path

from scripts.reproaudit_case.acceptance import run_acceptance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--wheelhouse-manifest", type=Path, required=True)
    args = parser.parse_args()
    return run_acceptance(
        args.repo_root,
        args.wheel,
        args.output_dir,
        args.requirements,
        args.wheelhouse,
        args.wheelhouse_manifest,
    ).exit_code


if __name__ == "__main__":
    raise SystemExit(main())
