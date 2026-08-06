# ReproAudit MEC Acceptance Recovery Execution

This is a process-recovery record, not a replacement design or implementation
plan. The approved technical requirements remain authoritative in:

- `docs/superpowers/specs/2026-08-05-reproaudit-mec-acceptance-design.md`
- `docs/superpowers/plans/2026-08-05-reproaudit-mec-acceptance-implementation.md`

The design is pinned at `aa95a0fab25fc8fa648c9e7a978bf7717b116327` and the
implementation plan is pinned at `69928cc4124f9f1cf87e560847b66f99cec06ae4`.

## Recovery decision

The former implementation branch `feat/reproaudit-mec-acceptance-case` at
`<NONCOMPLIANT_WORKTREE>` is preserved as
an audit artifact. Commit `643e8a6deab782d4c866fd4410ae0fa6b0890ad5` bundled
Tasks 3-7, and its untracked Task 8 files were created before the required
TDD and review gates. Task 2 has no complete SDD evidence, and Task 1 has no
independently verifiable final post-fix reviewer verdict. Consequently no
implementation task is accepted as complete for recovery purposes.

Recovery starts from the approved plan commit `69928cc4124f9f1cf87e560847b66f99cec06ae4`.
Tasks 1-15 are reimplemented in order on branch
`feat/reproaudit-mec-acceptance-case-recovery` at
`<RECOVERY_WORKTREE>`.

The original task text is the sole technical specification. Each task gets a
fresh brief extracted from that plan, a fresh implementer, a RED/GREEN TDD
record, one or more task-scoped commits, a fresh reviewer with both spec and
quality verdicts, and a ledger completion entry before the next task begins.
Tasks 3-8 must not copy, cherry-pick, inspect as implementation references, or
otherwise reuse files from the former branch. The old branch and worktree are
never modified. The workflow decision is `workflow_dispatch` only; no schedule
is added. No push, PR, merge, reset, rebase, amend, force operation, or history
rewrite is authorized.

## Audit references

- Noncompliant branch: `feat/reproaudit-mec-acceptance-case`
- Noncompliant worktree: `<NONCOMPLIANT_WORKTREE>`
- Audit directory: `<RECOVERY_AUDIT_DIR>`
- Recovery base: `69928cc4124f9f1cf87e560847b66f99cec06ae4`
- Accepted completed tasks: none
- Tasks requiring reimplementation: 1-15

The new SDD workspace and ledger are keyed by this recovery-plan path and are
independent of the original implementation ledger.

## Human Adjudication: Deterministic JSON Indentation

The approved implementation plan required deterministic JSON with a fixed
indent but did not specify its integer value.

The human-approved recovery decision is:

- `indent=2`
- `ensure_ascii=False`
- `sort_keys=True`
- `allow_nan=False`
- UTF-8 encoding
- Unix LF line endings
- exactly one trailing LF

Canonical serialization:

```python
json.dumps(
    payload,
    ensure_ascii=False,
    sort_keys=True,
    indent=2,
    allow_nan=False,
) + "\n"
```

This adjudication resolves an implementation ambiguity only. It does not
change the schema, payload fields, source mappings, or acceptance criteria.

## Human Adjudication: Offline Runtime Dependency Wheelhouse

The official ReproAudit v0.1.0 wheel declares external runtime dependencies
and is not a self-contained executable artifact.

For final acceptance:

1. ReproAudit itself must be installed exclusively from the verified official
   GitHub Release wheel.
2. Third-party runtime dependencies may be acquired separately.
3. Dependency acquisition and acceptance execution are separate phases.
4. The acceptance phase must install dependencies from a local wheelhouse with
   `--no-index`.
5. The official ReproAudit wheel must then be installed with both `--no-index`
   and `--no-deps`.
6. No local, editable, source-tree, or fallback ReproAudit installation is
   permitted.
7. Exact dependency versions, wheel filenames, and SHA-256 values must be
   recorded in the temporary acceptance evidence.
8. Dependency wheels and virtual environments must not be committed.

This adjudication changes only the runtime provisioning contract. It does not
weaken official-wheel provenance, source immutability, deterministic case
generation, expected findings, or acceptance rules.
