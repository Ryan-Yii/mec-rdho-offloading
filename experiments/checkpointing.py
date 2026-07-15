from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Iterable, Mapping, Sequence


class CheckpointStore:
    def __init__(
        self,
        raw_path: str | Path,
        contract_path: str | Path,
        *,
        contract: Mapping[str, object],
        key_columns: Sequence[str],
    ) -> None:
        self.raw_path = Path(raw_path)
        self.contract_path = Path(contract_path)
        self.contract = dict(contract)
        self.key_columns = tuple(key_columns)
        self.rows: list[dict[str, object]] = []
        self._keys: set[tuple[str, ...]] = set()
        self._fieldnames: list[str] | None = None

    def _key(self, row: Mapping[str, object]) -> tuple[str, ...]:
        missing = [column for column in self.key_columns if column not in row]
        if missing:
            raise ValueError(f"checkpoint key columns are missing: {missing}")
        return tuple(str(row[column]) for column in self.key_columns)

    def initialize(self, *, force: bool = False, resume: bool = False) -> None:
        if force and resume:
            raise ValueError("force and resume are mutually exclusive")
        self.raw_path.parent.mkdir(parents=True, exist_ok=True)
        self.contract_path.parent.mkdir(parents=True, exist_ok=True)
        if force:
            self.raw_path.unlink(missing_ok=True)
            self.contract_path.unlink(missing_ok=True)
        elif resume:
            if not self.raw_path.exists() or not self.contract_path.exists():
                raise FileNotFoundError("resume requires both checkpoint data and contract")
            existing_contract = json.loads(self.contract_path.read_text(encoding="utf-8"))
            if existing_contract != self.contract:
                raise RuntimeError("checkpoint contract mismatch; refuse to mix formal runs")
            with self.raw_path.open("r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                self._fieldnames = list(reader.fieldnames or [])
                self.rows = [dict(row) for row in reader]
            for row in self.rows:
                key = self._key(row)
                if key in self._keys:
                    raise ValueError(f"duplicate checkpoint key in existing data: {key}")
                self._keys.add(key)
            return
        elif self.raw_path.exists() or self.contract_path.exists():
            raise FileExistsError("checkpoint already exists; use force or resume")

        self.contract_path.write_text(
            json.dumps(self.contract, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    def has_key(self, row: Mapping[str, object]) -> bool:
        return self._key(row) in self._keys

    def append(self, row: Mapping[str, object]) -> None:
        record = dict(row)
        key = self._key(record)
        if key in self._keys:
            raise ValueError(f"duplicate checkpoint key: {key}")
        columns = list(record)
        if self._fieldnames is None:
            self._fieldnames = columns
        elif columns != self._fieldnames:
            raise ValueError("checkpoint row schema mismatch")
        self.rows.append(record)
        self._keys.add(key)
        self._atomic_write()

    def replace_rows(self, rows: Iterable[Mapping[str, object]]) -> None:
        self.rows = []
        self._keys = set()
        self._fieldnames = None
        for row in rows:
            record = dict(row)
            key = self._key(record)
            if key in self._keys:
                raise ValueError(f"duplicate checkpoint key: {key}")
            if self._fieldnames is None:
                self._fieldnames = list(record)
            elif list(record) != self._fieldnames:
                raise ValueError("checkpoint row schema mismatch")
            self.rows.append(record)
            self._keys.add(key)
        self._atomic_write()

    def _atomic_write(self) -> None:
        temporary = self.raw_path.with_suffix(self.raw_path.suffix + ".tmp")
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            if self._fieldnames:
                writer = csv.DictWriter(handle, fieldnames=self._fieldnames)
                writer.writeheader()
                writer.writerows(self.rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.raw_path)
