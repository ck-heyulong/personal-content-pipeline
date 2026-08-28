# Personal Content V1 — Implementation Contracts

This document translates `PROJECT.md` into testable contracts. `PROJECT.md` remains authoritative.

## Runtime and storage

- Python 3.12+, standard library only. The executable is `./content`.
- Jobs are restricted to safe single-component names under `jobs/<name>/` and begin with `raw.md` plus `images/`.
- Real jobs, credentials, generated packages, and staging data remain untracked.
- Configuration comes from environment variables; the default live provider is DeepSeek model `deepseek-v4-flash-vision-exp` at `https://api.deepseek.com/chat/completions`.

## Provider

- Canonical analysis sends raw text and every ordered local image as `text` and Base64 data URL `image_url` content items, with `stream: false`.
- Post generation and the optional naturalness edit use the same Chat Completions protocol with `stream: false`.
- Live requests do not send model-specific thinking configuration by default.
- Successful responses are read only from `choices[0].message.content` and parsed by one strict parser.
- The parser accepts a bare JSON object or one whole-response fenced object (unlabelled or `json`); it rejects prose, arrays, partial/multiple fences, malformed JSON, and repairs.
- HTTP 429/502/503/504 receive at most three total attempts with deterministic 2- then 4-second backoff. Other HTTP and response errors are not retried.
- Diagnostics may expose HTTP status and provider error code/message but never credentials or request headers.
- Automated behavior uses a deterministic fake provider or mocked `urllib`; tests make no real network call.

## Schemas and fidelity

- One strict canonical validator implements exactly the schema in `PROJECT.md`, including exact object keys, positive text line numbers, actual job-relative image references, and visible-evidence-only image interpretation fields.
- The same schema contract drives prompts, fake output, pipeline validation, and tests. Provider drift is rejected.
- Post JSON has exact keys `schema_version`, `style`, `title`, `body`, `tags`, and ordered `images`; it uses exactly one of `personal`, `knowledge`, or `concise`.
- Canonical content is the factual source of truth. Prompts preserve source language and forbid unsupported experiences, dates, numbers, achievements, expertise, opinions, events, and conclusions.
- Fake image interpretation explicitly states that the fake provider did not visually interpret the image.

## Draft quality

- The three styles differ in structure, pacing, voice, and density, not only title.
- Deterministic findings detect the prohibited formulaic patterns defined by `PROJECT.md`.
- No findings means no editor call. Findings permit exactly one editor call.
- Each editor replacement targets `title` or `body`, matches exactly once, is locally bounded, and may not replace a whole field. Invalid replacement sets are rejected; no second pass occurs.

## Human review and approval

- Preview is static local HTML containing escaped raw source, source images, canonical data, style, draft, ordered tags/images, and current approval state.
- Approval is explicit and stores a deterministic SHA-256 binding title, body, ordered tags, ordered image identities, and exact ordered image bytes.
- Changing title, body, tags, tag order, image order, image identity, or image bytes invalidates approval.

## Publishing security

- Publishing first verifies current approval, then creates or reuses `publish-packages/<full-hash>/` containing a manifest and copied images.
- Reuse rejects symlinked manifests/images, symlinked intermediate path components, non-regular required files, resolution outside the expected full-hash directory, unexpected/dangerous paths, and digest mismatch.
- Dry-run verifies approval/package and prints safe Windows staging and command information without invoking PowerShell, SAU, login, or publication.
- Real publication is only after prior human approval and invokes the repository PowerShell adapter, which stages immutably, verifies the staged package, then calls external SAU as `sau xiaohongshu upload-note --account main ...`. Adapter or SAU failure cannot be recorded as success.
- The repository never modifies SAU and never automates QR, CAPTCHA, SMS, 2FA, risk controls, or human publication approval.

## Verification

- Deterministic unit/integration tests cover CLI, validation, provider protocol/errors/retries, styles/editor limits, preview, every approval mutation, package path/symlink/digest defenses, dry-run, and Windows command construction.
- Repository verification performs unit discovery, compilation, CLI help checks, shell syntax checks, whitespace checks, and secret/ignore guards without network or publication.
- Live DeepSeek multimodal generation, human artifact review, approved dry-run, and real Xiaohongshu publication remain manual acceptance steps.
