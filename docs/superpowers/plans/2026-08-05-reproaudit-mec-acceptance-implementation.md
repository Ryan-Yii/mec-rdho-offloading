# ReproAudit v0.1.0 MEC Acceptance Case Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, source-preserving acceptance case that validates ReproAudit v0.1.0 against the canonical MEC V2 main experiment, an independent statistical oracle, and controlled fault scenarios.

**Architecture:** The MEC repository owns the adapter, oracle, fault injector, acceptance runner, committed faithful baseline, manifests, expected matrices, and documentation. The final path consumes only the verified published ReproAudit v0.1.0 wheel; exporter and oracle logic are independent from ReproAudit internals.

**Tech Stack:** Python 3.11, pandas, PyYAML, standard-library csv/json/hashlib/math/statistics/venv/subprocess, pytest, ReproAudit v0.1.0 release wheel.

## Global Constraints

- Pin MEC to Ryan-Yii/mec-rdho-offloading main commit b8abb436f215a9b2f4d646cf5fc0cf048174b68d. Canonical precedence is configs/main_40tasks.yaml, results/v2/raw/main_30_raw_results.csv, results/v2/summary/main_30_summary_mean_std.csv, README.md, then docs/experiment_protocol_v2.md. Mirrors, historical and control evidence are not authority.
- Verify source SHA-256 values: config d99ba17554e67f6d1ad9aef9bbec9a4470b5b6bde8c77309ed82951e159fe8c4; raw f885d8dd171e277d351ef268449f0aa5179a26f6e9c66256d4596d37a360c639; summary 751a936d794c642f640d6d9ae0309b153d728932c27e077c5188861feafa28d6; README 519b055257d1525806d0fbb3edf72f58848ee6ecc96112544158e93eb8f01cb6; protocol c1db229a76a50c6269e1417a521135056cfbdfb29556d1c368d3e96a60a1fa42.
- Pin ReproAudit to published tag/commit v0.1.0 / 1b6a9eb57529e4d92886fa7aa06dabbba5316105. The sole runtime artifact is reproaudit-0.1.0-py3-none-any.whl, SHA-256 dfab966ed90b98620d0c6b4fbeb80b31b44879493e092d4ef9314c9812998b5c, verified against release SHA256SUMS.
- Keep exact algorithm order RDHO, RIME, DBO, TLBO-HHO, CWTSSA, Greedy-ED. Keep metric order fitness, csr: fitness is primary/minimize and CSR is secondary/maximize.
- Use (seed, algorithm) as the run key. Seeds 20260701 through 20260730 identify paired scenarios, not one universal RNG seed. Retain run_id only in manifest traceability.
- Canonical raw lacks status; map every canonical row to success without inspecting metrics. An explicit future status maps verbatim. Nonfinite success metrics remain success evidence for R005.
- Only README spelling normalization is RDHO-full to RDHO. Reject RDHO Full, rdho-full, whitespace variants, and unknown algorithms.
- Project raw to exactly seed,algorithm,status,fitness,csr. Project official 6 x 55 summary to 12 ordered algorithm,metric,mean,std,median,n rows; copy fitness_mean/std and csr_mean/std directly and derive only median/n from raw.
- Use sample standard deviation ddof=1, absolute tolerance 0.00005, relative tolerance 0, and inclusive comparison abs(actual-expected) <= max(abs_tol, rel_tol*abs(expected)).
- Faithful expected results are R001-R005, R101-R103, R201 PASS/INFO; R202 SKIP/INFO; exit 0. The README baseline sentence is traceable but has no metric-specific best semantics.
- The oracle cannot import reproaudit, its rules/tolerance helpers, exporter statistics helpers, or consume an audit report. It independently computes keys, coverage, status, finite eligibility, statistics, claims, config, directions and ties.
- Never rerun experiments or write below configs/, results/, paper_tables/, or src/. Hash sources before export, after each export, after every fault stage, and at completion. Reject output inside source or any overwrite.
- Fault packages, venvs, logs and dynamic reports are temporary. Commit compact adapted inputs, manifest, matrices, docs, tests and reports/.gitkeep only.
- JSON uses UTF-8, ensure_ascii=False, sort_keys=True, indent, finite values and trailing LF. YAML uses safe_dump, fixed insertion order, no Python tags, UTF-8/LF and trailing LF. CSV uses fixed order, UTF-8/LF, index=False, fixed quoting and round-trippable float format.
- Compare structured ReproAudit JSON: rule_id, rule_name, status, severity, message, evidence, summary pass/warning/error/skip and exit_code. Only named generated_at may be normalized; never recursively discard unknown time fields.
- PR CI is synthetic/offline and never downloads a release. A manual or scheduled real job may use REPROAUDIT_WHEEL_PATH or download once, verify hash, and fail hard if unavailable; it never falls back to local ReproAudit source.
- No PDF/Word/OCR/LLM/agent/UI/database/automatic repair/new algorithm/PyPI/DOI work is in scope.

## Final Layout and Ownership

~~~text
case_studies/reproaudit_v0_1/
├── README.md
├── source_manifest.json
├── faithful_baseline/{experiment.yaml,claims.yaml,raw_results.csv,summary_results.csv}
├── expected/{baseline_expectations.json,fault_matrix.json}
└── reports/.gitkeep
scripts/reproaudit_case/
├── __init__.py
├── constants.py
├── serialization.py
├── source_inventory.py
├── export_case.py
├── extract_claims.py
├── oracle.py
├── faults.py
├── release_runtime.py
└── acceptance.py
scripts/{export_reproaudit_case.py,independently_verify_reproaudit_case.py,
         inject_reproaudit_fault.py,run_reproaudit_acceptance.py}
tests/reproaudit_case/
├── test_constants.py
├── test_source_inventory.py
├── test_export_case.py
├── test_extract_claims.py
├── test_oracle.py
├── test_faults.py
├── test_release_runtime.py
├── test_acceptance.py
└── fixtures/
~~~

Exporter maps and validates only. Oracle computes independently. Injector creates temporary variants only. Release runtime verifies, installs and invokes the wheel. Acceptance orchestrates and compares.

## Locked Types and Interfaces

~~~python
@dataclass(frozen=True)
class SourceFileRecord:
    path: str
    sha256: str
    size_bytes: int
    shape: tuple[int, int] | None = None
    columns: tuple[str, ...] = ()

@dataclass(frozen=True)
class SourceInventory:
    mec_commit: str
    files: tuple[SourceFileRecord, ...]
    algorithms: tuple[str, ...]
    metrics: tuple[str, ...]

@dataclass(frozen=True)
class ClaimTrace:
    claim_id: str
    claim_type: str
    source_path: str
    source_location: str
    source_text: str
    normalized: dict[str, str | int | float]
    rule_id: str
    disposition: str = "entered"

@dataclass(frozen=True)
class ExportResult:
    output_dir: Path
    manifest_path: Path
    source_inventory: SourceInventory
    claim_traces: tuple[ClaimTrace, ...]
    files: tuple[Path, ...]

@dataclass(frozen=True)
class OracleReport:
    case_dir: Path
    payload: dict[str, object]
    json_path: Path

@dataclass(frozen=True)
class FaultScenario:
    scenario_id: str
    mutation: str
    expected_findings: tuple[dict[str, str], ...]
    allowed_cascades: tuple[str, ...]
    forbidden_findings: tuple[str, ...]
    expected_exit_code: int

@dataclass(frozen=True)
class FaultResult:
    scenario: FaultScenario
    package_dir: Path
    oracle: OracleReport
    changed_files: tuple[str, ...]

@dataclass(frozen=True)
class AcceptanceResult:
    output_dir: Path
    baseline_report: dict[str, object]
    oracle_reports: tuple[OracleReport, ...]
    fault_results: tuple[FaultResult, ...]
    wheel_sha256: str
    source_hashes_before: tuple[SourceFileRecord, ...]
    source_hashes_after: tuple[SourceFileRecord, ...]
    exit_code: int
~~~

~~~python
def build_source_inventory(repo_root: Path) -> SourceInventory: ...
def export_experiment(repo_root: Path, destination: Path) -> Path: ...
def export_raw_results(repo_root: Path, destination: Path) -> Path: ...
def export_summary_results(repo_root: Path, destination: Path) -> Path: ...
def extract_claims(repo_root: Path, destination: Path) -> tuple[ClaimTrace, ...]: ...
def export_faithful_case(repo_root: Path, output_dir: Path) -> ExportResult: ...
def run_independent_oracle(case_dir: Path, output_dir: Path) -> OracleReport: ...
def inject_fault(case_dir: Path, scenario: FaultScenario, output_dir: Path) -> FaultResult: ...
def prepare_reproaudit_runtime(wheel: Path, temp_dir: Path) -> Path: ...
def run_reproaudit(runtime_python: Path, case_dir: Path, report_dir: Path) -> dict[str, object]: ...
def compare_baseline(report: dict[str, object], oracle: OracleReport, expected: Path) -> None: ...
def run_acceptance(repo_root: Path, wheel: Path, output_dir: Path) -> AcceptanceResult: ...
~~~

All wrappers share --repo-root, --wheel, and --output-dir. REPROAUDIT_WHEEL_PATH is the only environment override and never bypasses hash verification. Raise CaseContractError for path, source, schema, serialization or runtime violations.

## Tasks

### Task 1: Constants and repository-relative path contract

**Files:**
- Create: scripts/reproaudit_case/__init__.py, scripts/reproaudit_case/constants.py, tests/reproaudit_case/test_constants.py.
- Modify: none.
- Test: constants and no-source-read cases.

**Interfaces:**
- Consumes: repository root only.
- Produces: paths, source/release hashes, ordering, directions, tolerances, schemas, resolve_source_path.

- [ ] Step 1: Write tests for pinned paths/hashes, algorithm/metric order, directions, tolerances, and rejection of absolute/outside-root paths.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_constants.py; expect RED because constants is absent.
- [ ] Step 3: Implement frozen tuples and resolve_source_path with Path.resolve().is_relative_to(repo_root.resolve()); do not read data.
- [ ] Step 4: Rerun focused test; expect GREEN for values and containment rejection.
- [ ] Step 5: Run python -m compileall -q scripts/reproaudit_case and git diff --check; expect no diagnostics.
- [ ] Step 6: Review imports and confirm no local or absolute path escapes.
- [ ] Step 7: Commit git add scripts/reproaudit_case tests/reproaudit_case && git commit -m "test: define ReproAudit case constants".

### Task 2: Source inventory and deterministic manifest foundation

**Files:**
- Create: scripts/reproaudit_case/source_inventory.py, tests/reproaudit_case/test_source_inventory.py and source fixtures.
- Modify: constants.py only for a missing immutable field.
- Test: hashes, size/shape/columns, commit and source-drift rejection.

**Interfaces:**
- Consumes: canonical files and pinned checkout.
- Produces: SourceFileRecord, SourceInventory, build_source_inventory(repo_root), timestamp-free manifest payload.

- [ ] Step 1: Test exact five hashes, raw (180,21), summary (6,55), exact headers and one-byte temporary-source mutation rejection.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_source_inventory.py; expect RED because build_source_inventory is missing.
- [ ] Step 3: Implement streaming SHA-256, stat sizes, pandas read-only schema checks, git -C root rev-parse HEAD and sorted manifest serialization with no host/path/time fields.
- [ ] Step 4: Rerun; expect GREEN and identical bytes for two manifests.
- [ ] Step 5: Run compile/diff checks; expect clean output.
- [ ] Step 6: Review all opens as read-only and ensure drift fails closed.
- [ ] Step 7: Commit git add scripts/reproaudit_case/source_inventory.py tests/reproaudit_case/test_source_inventory.py && git commit -m "feat: inventory MEC acceptance sources".

### Task 3: Experiment configuration export

**Files:**
- Create: configuration functions in export_case.py, YAML fixtures and configuration tests.
- Modify: none elsewhere.
- Test: schema, order, scalar type, unsupported-field and missing-key cases.

**Interfaces:**
- Consumes: configs/main_40tasks.yaml.
- Produces: export_experiment(repo_root, destination) and schema 1.0 experiment.yaml.

- [ ] Step 1: Test exact algorithms, 30 runs, seed column, parameters 20/4/2/40/50/150/20260701, two metrics and safe YAML.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_export_case.py -k experiment; expect RED because the function is missing.
- [ ] Step 3: safe_load only approved fields, build ordered mapping and safe_dump(sort_keys=False, allow_unicode=True, default_flow_style=False) plus one LF.
- [ ] Step 4: Rerun selection; expect parsed equality and no Python tags.
- [ ] Step 5: Run compile/diff checks; expect no diagnostics.
- [ ] Step 6: Review unrelated weights, historical configs and runners are excluded.
- [ ] Step 7: Commit git add scripts/reproaudit_case/export_case.py tests/reproaudit_case && git commit -m "feat: export ReproAudit experiment input".

### Task 4: Raw result export

**Files:**
- Create: raw fixtures and raw cases in test_export_case.py.
- Modify: export_case.py.
- Test: header, 180-row projection, sorting, status, source bytes.

**Interfaces:**
- Consumes: canonical 180 x 21 raw CSV and configured order.
- Produces: export_raw_results(repo_root, destination) with only seed,algorithm,status,fitness,csr.

- [ ] Step 1: Test header, 180 rows, 30 per algorithm, unique keys, run-ID/algorithm order, all-success status, no target run_id and source unchanged.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_export_case.py -k raw; expect RED because function is missing.
- [ ] Step 3: Project fixed fields, map absent status to success, reject malformed seed/unknown name/duplicate key and write LF UTF-8 fixed-quote CSV with %.17g.
- [ ] Step 4: Rerun; expect GREEN and no metric-to-status inference.
- [ ] Step 5: Run compile/diff checks; expect clean.
- [ ] Step 6: Review no canonical file is writable.
- [ ] Step 7: Commit git add scripts/reproaudit_case/export_case.py tests/reproaudit_case && git commit -m "feat: export ReproAudit raw input".

### Task 5: Official summary export

**Files:**
- Create: summary fixtures and cases.
- Modify: export_case.py.
- Test: direct official fields, structural median/n, ordering and finite validation.

**Interfaces:**
- Consumes: canonical 6 x 55 summary and raw only for median/n.
- Produces: export_summary_results(repo_root, destination) with 12 x 6 long CSV.

- [ ] Step 1: Test exact full-precision fitness_mean/std and csr_mean/std, correct median/n, ordering, absent/nonfinite source failure.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_export_case.py -k summary; expect RED because function is missing.
- [ ] Step 3: Copy selected official fields directly; calculate only structural median/count and serialize deterministic rows.
- [ ] Step 4: Rerun; expect GREEN with 12 rows and no mean/std recomputation.
- [ ] Step 5: Run compile/diff checks; expect clean.
- [ ] Step 6: Review paper_tables/v2 is not authority.
- [ ] Step 7: Commit git add scripts/reproaudit_case/export_case.py tests/reproaudit_case && git commit -m "feat: export ReproAudit summary input".

### Task 6: README claims and traceability

**Files:**
- Create: extract_claims.py, test_extract_claims.py and README variants.
- Modify: constants only for claim names.
- Test: Decimal parsing, exact normalization, traces, absent best claim.

**Interfaces:**
- Consumes: Fresh V2 README prose/table.
- Produces: extract_claims(repo_root, destination), claims.yaml with seven config and twelve mean claims, plus non-entered CWIN-001.

- [ ] Step 1: Test RDHO-full acceptance and RDHO Full/rdho-full/unknown rejection; assert Decimal 0.9470, source line/text and no R202 entry.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_extract_claims.py; expect RED because function is missing.
- [ ] Step 3: Strictly parse known table/prose, preserve display values/line anchors, map only RDHO-full and omit unsupported families.
- [ ] Step 4: Rerun; expect GREEN with 19 entered traces, one R202-SKIP trace and illegal spelling failures.
- [ ] Step 5: Run compile/diff checks; expect clean.
- [ ] Step 6: Review no raw/summary value creates a claim and no best ranking is inferred.
- [ ] Step 7: Commit git add scripts/reproaudit_case/extract_claims.py tests/reproaudit_case && git commit -m "feat: extract ReproAudit claims".

### Task 7: Faithful baseline exporter

**Files:**
- Create: serialization.py, complete export_faithful_case, export_reproaudit_case.py and integration tests.
- Modify: .gitignore for runtime reports while retaining .gitkeep.
- Test: preflight, two-directory bytes, manifest and source hash lifecycle.

**Interfaces:**
- Consumes: Tasks 2-6 and absent/empty output.
- Produces: ExportResult, four inputs and source_manifest.json; wrapper uses --repo-root --output-dir.

- [ ] Step 1: Test nonempty/inside-source rejection, no overwrite, two exports byte equality, no timestamps/absolute paths and matching hashes.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_export_case.py -k faithful; expect RED because export_faithful_case is missing.
- [ ] Step 3: Preflight containment/no-overwrite, build in a sibling temp directory, atomically rename, and record generated_at_policy omitted_for_byte_determinism.
- [ ] Step 4: Run python scripts/export_reproaudit_case.py --repo-root /path/to/mec --output-dir /tmp/mec-case-a; expect inputs/manifest and hashes; repeat to case-b and compare.
- [ ] Step 5: Run exporter tests and git diff --check; expect pass/clean.
- [ ] Step 6: Review no paths, times, source copies or reports are emitted.
- [ ] Step 7: Commit git add .gitignore scripts/export_reproaudit_case.py scripts/reproaudit_case tests/reproaudit_case && git commit -m "feat: assemble faithful MEC case".

### Task 8: Independent oracle

**Files:**
- Create: oracle.py, independently_verify_reproaudit_case.py and test_oracle.py.
- Modify: none.
- Test: independent stats, keys, coverage, claims, ties and import guard.

**Interfaces:**
- Consumes: four-file case and manifest, never ReproAudit report.
- Produces: run_independent_oracle(case_dir, output_dir) -> OracleReport and timestamp-free oracle-report.json.

- [ ] Step 1: Test import guard, sample formula, coverage/nonfinite behavior and maximum claim difference 0.0000482372898956.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_oracle.py; expect RED because oracle is missing.
- [ ] Step 3: Use independent csv/json/math/statistics grouping to record declarations, keys, statuses, usable values, mean/median/sample std, summary/claims/config differences, directions/ties and normalized observables.
- [ ] Step 4: Run python scripts/independently_verify_reproaudit_case.py --repo-root /path/to/mec --output-dir /tmp/oracle-a; expect deterministic JSON; repeat and cmp.
- [ ] Step 5: Run focused tests and diff checks; expect green/clean.
- [ ] Step 6: Run rg -n reproaudit scripts/reproaudit_case/oracle.py; expect no forbidden import or report consumption.
- [ ] Step 7: Commit git add scripts/reproaudit_case/oracle.py scripts/independently_verify_reproaudit_case.py tests/reproaudit_case/test_oracle.py && git commit -m "feat: add independent acceptance oracle".

### Task 9: Baseline report comparator

**Files:**
- Create: comparator in acceptance.py, test_acceptance.py JSON fixtures.
- Modify: none.
- Test: required fields, matrix, evidence and timestamp-only normalization.

**Interfaces:**
- Consumes: actual ReproAudit JSON, OracleReport and baseline expectations.
- Produces: compare_baseline(report, oracle, expected) -> None or explicit mismatch.

- [ ] Step 1: Test nine PASS/INFO plus R202 SKIP/INFO, exit 0, missing/wrong finding, summary mismatch and unknown-field preservation.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_acceptance.py -k comparator; expect RED because comparator is missing.
- [ ] Step 3: Parse findings and summary; normalize only top-level generated_at; compare rule_id/rule_name/status/severity/message/evidence and oracle normalized values.
- [ ] Step 4: Rerun; expect GREEN while console output is ignored.
- [ ] Step 5: Run compile/diff checks; expect clean.
- [ ] Step 6: Review no opaque whole-JSON or recursive timestamp filtering.
- [ ] Step 7: Commit git add scripts/reproaudit_case/acceptance.py tests/reproaudit_case/test_acceptance.py && git commit -m "test: validate baseline report contract".

### Task 10: Fixed fault specifications and temporary injector

**Files:**
- Create: faults.py, inject_reproaudit_fault.py, test_faults.py.
- Modify: expected/fault_matrix.json when assets are materialized.
- Test: one isolation case for each listed scenario.

**Interfaces:**
- Consumes: temporary faithful copy and FaultScenario.
- Produces: inject_fault(case_dir, scenario, output_dir) -> FaultResult; no source or committed mutation.

| ID | Fixed target and mutation | Required, allowed, forbidden | Exit |
| --- | --- | --- | ---: |
| F001 | RDHO/20260701 status success to failed | R001 ERROR; allow R003, R005 WARNING, R101/R102/R103 ERROR, R202 SKIP; forbid R002/R004/R201 | 2 |
| F002 | RDHO/20260702 seed to 20260701; only dependent summary/claims recomputed | R002 ERROR; allow R003 ERROR/R202 SKIP; forbid R001/R004/R005/R101/R102/R103/R201 | 2 |
| F003 | RDHO/20260730 seed to 20260731 | R003 ERROR; allow R202 SKIP; forbid R001/R002/R004/R005/R101/R102/R103/R201 | 2 |
| F004 | Add UNDECLARED-CONTROL, 30 copied finite Greedy-ED success rows/seeds and matching summary | R004 WARNING; allow R202 SKIP; forbid R001/R002/R003/R005/R101/R102/R103/R201 | 1 |
| F005A | RDHO/20260701 status success to timeout | R005 WARNING; allow R001/R003/R101/R102/R103 ERROR/R202 SKIP; forbid R002/R004/R201 | 2 |
| F005B | RDHO/20260701 fitness to literal NaN; status success | R005 ERROR; allow R101/R102/R103 ERROR/R202 SKIP; forbid R001/R002/R003/R004/R201 | 2 |
| F101 | RDHO fitness summary mean plus 0.01 | R101 ERROR; allow R202 SKIP; forbid R001-R005/R102/R103/R201 | 2 |
| F102 | RDHO fitness summary std plus 0.01 | R102 ERROR; allow R202 SKIP; forbid R001-R005/R101/R103/R201 | 2 |
| F103 | RDHO fitness claim 0.9470 to 0.9480 | R103 ERROR; allow R202 SKIP; forbid R001-R005/R101/R102/R201 | 2 |
| F201 | max_iterations claim 150 to 151 | R201 ERROR; allow R202 SKIP; forbid R001-R005/R101-R103 | 2 |
| F202 | Fixture-only best claim metric fitness, algorithm DBO, synthetic trace | R202 ERROR; forbid R001-R005/R101-R103/R201 | 2 |
| F900 | Remove temporary claims.yaml | input validation, no normal findings | 3 |

- [ ] Step 1: Test fresh temp copies, changed-file scope and unchanged canonical/committed hashes for every scenario.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_faults.py; expect RED because scenario/injector is missing.
- [ ] Step 3: Encode fixed values; every numeric mutation is at least 0.001 and is never selected from a report; only F002 recalculates dependent values.
- [ ] Step 4: Rerun; expect GREEN, F202 absent from faithful claims and F900 without normal report.
- [ ] Step 5: Run compile/diff checks; expect clean.
- [ ] Step 6: Review rule ownership, F001/F005A distinction, F005B retained-success semantics, cascades and forbidden findings.
- [ ] Step 7: Commit git add scripts/reproaudit_case/faults.py scripts/inject_reproaudit_fault.py tests/reproaudit_case/test_faults.py && git commit -m "feat: add controlled ReproAudit fault scenarios".

### Task 11: Official Release wheel runtime

**Files:**
- Create: release_runtime.py and test_release_runtime.py.
- Modify: none.
- Test: hash/name, isolated install, offline mode, CLI capture and no fallback.

**Interfaces:**
- Consumes: --wheel or REPROAUDIT_WHEEL_PATH and temporary root.
- Produces: prepare_reproaudit_runtime(wheel, temp_dir) -> Path; run_reproaudit(runtime_python, case_dir, report_dir) -> dict.

- [ ] Step 1: Test absent/wrong-name/wrong-hash wheel, no-index/no-deps install, CLI failure capture and local-source fallback prohibition.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_release_runtime.py; expect RED because runtime functions are missing.
- [ ] Step 3: Verify SHA, create Python 3.11 venv, install only the wheel with pip install --no-index --no-deps, and invoke python -m reproaudit.cli audit CASE --format all --output-dir REPORTS.
- [ ] Step 4: Rerun; expect GREEN and hard failure on missing Release artifact.
- [ ] Step 5: Run compile/diff checks; expect clean.
- [ ] Step 6: Review sys.path/cwd so neither MEC nor ReproAudit primary source can satisfy imports.
- [ ] Step 7: Commit git add scripts/reproaudit_case/release_runtime.py tests/reproaudit_case/test_release_runtime.py && git commit -m "feat: run ReproAudit release wheel".

### Task 12: Acceptance runner

**Files:**
- Create: orchestration in acceptance.py, run_reproaudit_acceptance.py and runner tests.
- Modify: none.
- Test: staged order, matrix comparison and hygiene.

**Interfaces:**
- Consumes: root, verified wheel and empty temp output.
- Produces: run_acceptance(repo_root, wheel, output_dir) -> AcceptanceResult; wrapper uses shared flags.

- [ ] Step 1: Test order hashes, export twice, byte comparison, oracle twice, wheel baseline twice, comparator, all faults and final hashes.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_acceptance.py -k runner; expect RED because runner is missing.
- [ ] Step 3: Stage outside source, retain hashes/reports, normalize only named generated_at and fail on any matrix mismatch.
- [ ] Step 4: Run python scripts/run_reproaudit_acceptance.py --repo-root /path/to/mec --wheel /path/to/reproaudit-0.1.0-py3-none-any.whl --output-dir /tmp/reproaudit-mec-acceptance; expect exit 0 only after every stage.
- [ ] Step 5: Run runner tests and git diff --check; expect pass/clean.
- [ ] Step 6: Review no experiment invocation, source writes or exit-0-only acceptance.
- [ ] Step 7: Commit git add scripts/reproaudit_case/acceptance.py scripts/run_reproaudit_acceptance.py tests/reproaudit_case/test_acceptance.py && git commit -m "feat: orchestrate ReproAudit MEC acceptance".

### Task 13: Committed baseline assets and expectations

**Files:**
- Create: faithful_baseline four files, source_manifest.json, expected baseline/fault JSON, reports/.gitkeep, test_committed_assets.py.
- Modify: .gitignore only if required.
- Test: shape/hash/matrix/no-dynamic artifact tests.

**Interfaces:**
- Consumes: one reviewed export from pinned clone and frozen matrices.
- Produces: compact committed conversion, never runtime evidence.

- [ ] Step 1: Test exact headers/shapes, source hashes/commit, ten baseline rules, twelve fault IDs and no dynamic report fields.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_committed_assets.py; expect RED because assets are absent.
- [ ] Step 3: Export once to staging, inspect every byte, copy only four inputs/manifest, serialize fixed expectation JSON, leave reports as .gitkeep.
- [ ] Step 4: Rerun; expect GREEN and marker-only reports.
- [ ] Step 5: Run git diff --check and git diff --stat; expect compact mapped files only.
- [ ] Step 6: Review paths/times/source copies/unsupported columns/fabricated claims.
- [ ] Step 7: Commit git add case_studies/reproaudit_v0_1 tests/reproaudit_case/test_committed_assets.py .gitignore && git commit -m "feat: commit faithful MEC case assets".

### Task 14: Case-study README

**Files:**
- Create: case_studies/reproaudit_v0_1/README.md and test_case_readme.py.
- Modify: root README only for one reviewed relative link.
- Test: links, pinned facts and bounded claims.

**Interfaces:**
- Consumes: manifest, matrices and wrappers.
- Produces: purpose, source hashes, mapping, claim traceability, expected/observed baseline, faults, determinism, immutability, limitations and reproduction.

- [ ] Step 1: Test links, commits/hashes, R202 SKIP/INFO, wheel facts, temporary-report policy and overclaim rejection.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_case_readme.py; expect RED because README is absent.
- [ ] Step 3: Write commands with shared flags and state that conclusion is only structured consistency acceptance for specified assets.
- [ ] Step 4: Rerun; expect GREEN and manifest-consistent documentation.
- [ ] Step 5: Run git diff --check; expect clean.
- [ ] Step 6: Review no scientific-correctness, universal-superiority, third-party-validation, adoption, DOI or unobserved-zero-error claims.
- [ ] Step 7: Commit git add case_studies/reproaudit_v0_1/README.md tests/reproaudit_case/test_case_readme.py README.md && git commit -m "docs: document ReproAudit MEC case study".

### Task 15: CI and final acceptance review

**Files:**
- Create: .github/workflows/reproaudit-mec-acceptance.yml and test_workflow.py.
- Modify: .github/workflows/tests.yml only for pytest discovery if required.
- Test: workflow static contract, complete repository tests and manual real command.

**Interfaces:**
- Consumes: synthetic fixtures in PR CI; official wheel and pinned source only in manual/scheduled job.
- Produces: no-secrets/no-publication manual real acceptance workflow.

- [ ] Step 1: Test Python 3.11, no PR Release download, manual SHA verification, no experiment invocation and required wrapper flags.
- [ ] Step 2: Run python -m pytest -q tests/reproaudit_case/test_workflow.py; expect RED because workflow is absent/invalid.
- [ ] Step 3: Add workflow_dispatch (optionally bounded schedule), checkout, requirements install, supplied/cached/downloaded official wheel, SHA check and acceptance command; retain fast offline push/PR pytest.
- [ ] Step 4: Run python -m pytest -q and ruby -e 'require "yaml"; YAML.load_file(".github/workflows/reproaudit-mec-acceptance.yml")'; expect all tests and YAML parse to pass. Dispatch only after approval.
- [ ] Step 5: Run git diff --check; use existing quality gate python -m pytest -q because this MEC checkout has no pyproject.toml, ruff or mypy entrypoint.
- [ ] Step 6: Review correctness, source immutability, oracle independence, fault isolation, claims traceability, wheel provenance, documentation honesty, CI cost/safety and acceptance mapping; fix every Critical/Important finding.
- [ ] Step 7: Commit git add .github/workflows/reproaudit-mec-acceptance.yml tests/reproaudit_case/test_workflow.py .github/workflows/tests.yml && git commit -m "ci: verify ReproAudit MEC acceptance".

## Fault, Report, Determinism and Hygiene Contract

Run every fault from a fresh faithful copy under a temporary root and record scenario_id, exact before/after mutation, changed files, oracle observation, every required/allowed/forbidden finding, summary counts, exit code, and source hashes. F900 records input-validation location and confirms no normal findings JSON. F202 has synthetic source text, fixed fixture ID and fault_fixture_only disposition and never enters faithful claims.

All committed JSON/YAML/CSV omit generated_at, local paths and machine data. Runtime reports use the real ReproAudit JSON schema and compare rule_id, rule_name, status, severity, message, evidence, summary counts and exit; only named generated_at is normalized. Dynamic reports, fault packages, venv, logs and wheel are outside Git. On failure retain temporary path for diagnosis but still check final source hashes.

## Fresh Verification and Acceptance Matrix

Use a Python 3.11 environment with requirements.txt installed:

~~~bash
python -m pytest -q
python -m pytest -q tests/reproaudit_case
git diff --check
python scripts/export_reproaudit_case.py --repo-root /path/to/mec --output-dir /tmp/mec-export-a
python scripts/export_reproaudit_case.py --repo-root /path/to/mec --output-dir /tmp/mec-export-b
cmp /tmp/mec-export-a/faithful_baseline/raw_results.csv /tmp/mec-export-b/faithful_baseline/raw_results.csv
cmp /tmp/mec-export-a/faithful_baseline/summary_results.csv /tmp/mec-export-b/faithful_baseline/summary_results.csv
cmp /tmp/mec-export-a/source_manifest.json /tmp/mec-export-b/source_manifest.json
python scripts/independently_verify_reproaudit_case.py --repo-root /path/to/mec --output-dir /tmp/mec-oracle-a
python scripts/independently_verify_reproaudit_case.py --repo-root /path/to/mec --output-dir /tmp/mec-oracle-b
cmp /tmp/mec-oracle-a/oracle-report.json /tmp/mec-oracle-b/oracle-report.json
python scripts/run_reproaudit_acceptance.py --repo-root /path/to/mec --wheel /path/to/reproaudit-0.1.0-py3-none-any.whl --output-dir /tmp/reproaudit-mec-acceptance
sha256sum /path/to/reproaudit-0.1.0-py3-none-any.whl
git -C /path/to/mec status --short
~~~

Also invoke the injector for F001, F002, F003, F004, F005A, F005B, F101, F102, F103, F201, F202 and F900; compare all exact outcomes, check README links, parse workflow YAML, and compare source hashes before/after each phase. Missing/download-failed wheel is a failure, never a local-source fallback.

| Category | Check | Expected |
| --- | --- | --- |
| Source | commit and five canonical hashes | unchanged |
| Export | independent directories | all four inputs and manifest byte-identical |
| Baseline | wheel exit | 0 |
| Baseline | R001-R005/R101-R103/R201 | PASS/INFO |
| Baseline | R202 | SKIP/INFO |
| Oracle | counts, keys, coverage, 12 mean/std, claims | agreement at abs 0.00005, rel 0 |
| Faults | F001-F900 | exact required/allowed/forbidden matrix |
| Determinism | oracle and normalized reports | byte/semantic identical |
| Runtime | wheel filename/hash | official published v0.1.0 |
| Hygiene | MEC and ReproAudit worktrees/source files | clean and unchanged |
| Documentation | links/conclusion | valid and bounded |
| CI | PR/manual split | offline synthetic/manual real |

If implementation observes facts inconsistent with the approved design, stop and revise design; never alter source, widen tolerance, or weaken expected outcomes.

## Future Commit Sequence, Review and Self-Checks

Future implementation commits, one per task, are:

~~~text
test: define ReproAudit case constants
feat: inventory MEC acceptance sources
feat: export ReproAudit experiment input
feat: export ReproAudit raw input
feat: export ReproAudit summary input
feat: extract ReproAudit claims
feat: assemble faithful MEC case
feat: add independent acceptance oracle
test: validate baseline report contract
feat: add controlled ReproAudit fault scenarios
feat: run ReproAudit release wheel
feat: orchestrate ReproAudit MEC acceptance
feat: commit faithful MEC case assets
docs: document ReproAudit MEC case study
ci: verify ReproAudit MEC acceptance
~~~

Before implementation approval, review correctness, source immutability, oracle independence, fault isolation, claims traceability, wheel provenance, documentation honesty, CI cost/safety and criterion-to-task mapping. Scan this plan for banned placeholders using a pattern assembled from fragments so the scanner does not match its own command. Verify all locked type/function names, flags, file paths, JSON fields and scenario IDs with rg; require no inconsistent spellings. Confirm design coverage for inventory, mapping, manifest, oracle, faults, wheel, determinism, immutability, CI, README and matrix. The planning branch contains only this document and must stop for human review.
