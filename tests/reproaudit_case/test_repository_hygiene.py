from __future__ import annotations

import re
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".rst",
}
MACHINE_PATH_PATTERNS = (
    re.compile(r"/Users/[^/<\s]+/"),
    re.compile(r"/home/[^/<\s]+/"),
    re.compile(r"[A-Za-z]:\\Users\\[^\\<>\s]+\\"),
)


def test_tracked_text_has_no_machine_local_absolute_paths() -> None:
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
    ).split(b"\0")
    violations: list[str] = []
    for raw_path in tracked:
        if not raw_path:
            continue
        path = Path(raw_path.decode("utf-8"))
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(lines, start=1):
            for pattern in MACHINE_PATH_PATTERNS:
                match = pattern.search(line)
                if match:
                    violations.append(f"{path}:{line_number}: {match.group(0)}")
    assert not violations, "machine-local absolute paths found:\n" + "\n".join(violations)
