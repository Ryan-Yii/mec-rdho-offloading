from __future__ import annotations

import argparse
from pathlib import Path

from scripts.reproaudit_case.oracle import run_independent_oracle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run_independent_oracle(args.case_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
