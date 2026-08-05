from __future__ import annotations

import argparse
from pathlib import Path

from scripts.reproaudit_case.export_case import export_faithful_case


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    export_faithful_case(args.repo_root, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
