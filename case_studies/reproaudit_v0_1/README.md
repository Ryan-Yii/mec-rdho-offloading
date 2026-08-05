# ReproAudit MEC V2 Acceptance Case

This case is a structured consistency acceptance for the specified MEC V2 main-experiment assets. It is not a claim that the entire paper is reproducible, that any algorithm is correct, or that an external party has certified or adopted the result.

## Frozen Source

The pinned MEC source commit is `b8abb436f215a9b2f4d646cf5fc0cf048174b68d`. The canonical configuration, raw results, official summary, README, and protocol are recorded in [`source_manifest.json`](source_manifest.json) with SHA-256 hashes. These source files are read-only during export and acceptance.

The faithful converted inputs are [`faithful_baseline/experiment.yaml`](faithful_baseline/experiment.yaml), [`faithful_baseline/claims.yaml`](faithful_baseline/claims.yaml), [`faithful_baseline/raw_results.csv`](faithful_baseline/raw_results.csv), and [`faithful_baseline/summary_results.csv`](faithful_baseline/summary_results.csv). The only algorithm label normalization is the exact lookup `RDHO-full -> RDHO`; other spellings are rejected.

## Claims and Rules

The claims file contains seven README configuration claims and twelve displayed fitness/CSR means. The README candidate sentence is retained in manifest traceability but is not entered as a metric-specific best claim. Therefore faithful baseline rule `R202` is `SKIP/INFO`; the other nine expected rules are `PASS/INFO`.

The fixed fault matrix in [`expected/fault_matrix.json`](expected/fault_matrix.json) covers F001-F005B, F101-F103, F201-F202, and F900. Faults are created in temporary directories and are never committed.

## Release Runtime

The real audit path uses only `reproaudit-0.1.0-py3-none-any.whl` with SHA-256 `dfab966ed90b98620d0c6b4fbeb80b31b44879493e092d4ef9314c9812998b5c`. Runtime venvs, wheel copies, reports, and fault packages remain outside Git. [`reports/`](reports/) is a marker-only directory for dynamic output.

## Reproduction

From the repository root, export a temporary faithful case:

```bash
python scripts/export_reproaudit_case.py --repo-root . --output-dir /tmp/reproaudit-mec-case
```

Run the independent oracle against that temporary case:

```bash
python scripts/independently_verify_reproaudit_case.py --case-dir /tmp/reproaudit-mec-case --output-dir /tmp/reproaudit-mec-oracle
```

Run the complete manual acceptance only with the verified official wheel:

```bash
python scripts/run_reproaudit_acceptance.py --repo-root . --wheel /path/to/reproaudit-0.1.0-py3-none-any.whl --output-dir /tmp/reproaudit-mec-acceptance
```

Two exports and two oracle reports must be byte-identical. The workflow must leave all canonical hashes and the source worktree unchanged. Conclusions are limited to consistency of these specified transformed assets and the observed rule matrix.
