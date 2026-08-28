# Personal Content V1 — Execution Plan

Statuses: `PENDING`, `IN PROGRESS`, `COMPLETE`. A phase becomes `COMPLETE` only after its commands pass.

## Phase 0 — Preconditions and repository inspection

- Objective: read governing files, inspect baseline/tooling, and freeze implementation contracts.
- Files likely to change: `SPEC.md`, `PLAN.md`.
- Acceptance criteria: baseline and Git state recorded; Python/WSL/PowerShell availability inspected safely; contracts preserve `PROJECT.md`.
- Verification commands: `git status --short --branch`; `git log -1 --oneline --decorate`; `python3 --version`; `bash --version`; `command -v powershell.exe`; `test -f SPEC.md && test -f PLAN.md`.
- Status: COMPLETE

## Phase 1 — Repository foundation and CLI

- Objective: add package, executable, safe job creation/lookup, configuration, and command skeletons.
- Files likely to change: `content`, `personal_content/__init__.py`, `personal_content/config.py`, `personal_content/jobs.py`, `personal_content/cli.py`, `tests/test_cli.py`, `tests/test_jobs.py`.
- Acceptance criteria: all fixed commands expose help; safe names create only `raw.md` and `images/`; unsafe/invalid jobs fail clearly; doctor is secret-free and non-destructive.
- Verification commands: `python3 -m unittest tests.test_cli tests.test_jobs -v`; `./content --help`; `./content generate --help`; `./content publish --help`.
- Status: COMPLETE

## Phase 2 — DeepSeek Vision provider and strict canonical content

- Objective: preserve the exact canonical contract, prompts, deterministic fake, strict response parsing, retry, and safe errors while using the DeepSeek Vision multimodal request.
- Files likely to change: `personal_content/canonical.py`, `personal_content/provider.py`, `personal_content/pipeline.py`, `personal_content/prompts/canonical.md`, `tests/test_canonical.py`, `tests/test_provider.py`.
- Acceptance criteria: one strict canonical shape is shared everywhere; Base64 data URL images and `stream: false` match protocol; no thinking configuration is required; parser/retries/diagnostics obey the frozen behavior; no automated network.
- Verification commands: `python3 -m unittest tests.test_canonical tests.test_provider -v`.
- Status: COMPLETE

## Phase 3 — Xiaohongshu styles and bounded naturalness

- Objective: generate and validate materially different styles and perform at most one bounded exact-replacement edit.
- Files likely to change: `personal_content/review.py`, `personal_content/pipeline.py`, `personal_content/prompts/personal.md`, `personal_content/prompts/knowledge.md`, `personal_content/prompts/concise.md`, `personal_content/prompts/naturalness.md`, `tests/test_review.py`, `tests/test_pipeline.py`.
- Acceptance criteria: exact post schema and style differences; deterministic findings; zero editor calls without findings and no more than one with findings; whole-field/ambiguous edits rejected.
- Verification commands: `python3 -m unittest tests.test_review tests.test_pipeline -v`.
- Status: COMPLETE

## Phase 4 — Preview, approval and deterministic hashing

- Objective: create safe offline preview and explicit approval bound to all publishable content and image identities/bytes.
- Files likely to change: `personal_content/preview.py`, `personal_content/approval.py`, `personal_content/cli.py`, `tests/test_preview.py`, `tests/test_approval.py`.
- Acceptance criteria: escaped complete preview; explicit metadata; title/body/tag/tag-order/image-order/image-byte mutations each invalidate approval.
- Verification commands: `python3 -m unittest tests.test_preview tests.test_approval -v`.
- Status: COMPLETE

## Phase 5 — Immutable package and Windows SAU bridge

- Objective: create/reuse verified full-hash packages and provide safe WSL-to-PowerShell-to-SAU invocation.
- Files likely to change: `personal_content/publish.py`, `scripts/publish_xiaohongshu.ps1`, `personal_content/cli.py`, `tests/test_publish.py`.
- Acceptance criteria: package self-containment and all path/symlink/digest defenses; dry-run never invokes publication; Windows command is exact; result success follows zero exit status only.
- Verification commands: `python3 -m unittest tests.test_publish -v`; `bash -n scripts/verify_v1.sh` (once present); safe PowerShell parser check if PowerShell is available.
- Status: COMPLETE

## Phase 6 — End-to-end offline validation and documentation

- Objective: document the WSL workflow and provide repository-owned complete offline verification.
- Files likely to change: `README.md`, `.gitignore`, `.env.example`, `scripts/verify_v1.sh`, `tests/test_e2e.py`.
- Acceptance criteria: fake-provider job completes through dry-run offline; README covers every required operational/security topic; verification script is safe and deterministic.
- Verification commands: `python3 -m unittest discover -s tests -v`; `./scripts/verify_v1.sh`; `python3 -m compileall -q personal_content tests`; `bash -n scripts/verify_v1.sh`; `git diff --check`; `git check-ignore .env jobs/example/raw.md publish-packages/example/manifest.json`.
- Status: COMPLETE

## Phase 7 — Final self-review

- Objective: inspect every change for frozen-scope, fidelity, secret, approval, package, and publication defects; fix anything found and rerun everything.
- Files likely to change: any affected V1 file and `PLAN.md`.
- Acceptance criteria: full diff/modules/prompts/tests/README reviewed; no schema mismatch, secret, bypass, hash omission, symlink escape, live test traffic/publication, scope creep, or inaccurate claim remains.
- Verification commands: `git diff 92569cd --`; `python3 -m unittest discover -s tests -v`; `./scripts/verify_v1.sh`; `./content --help`; `./content generate --help`; `./content publish --help`; `python3 -m compileall -q personal_content tests`; `bash -n scripts/verify_v1.sh`; `git diff --check`; `git status --short --branch`.
- Status: COMPLETE
