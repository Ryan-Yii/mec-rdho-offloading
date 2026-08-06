from __future__ import annotations

import argparse
from pathlib import Path

from scripts.reproaudit_case.faults import FaultScenario, inject_fault


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", type=Path, required=True)
    parser.add_argument("--fault", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    inject_fault(args.case_dir, FaultScenario(args.fault), args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
