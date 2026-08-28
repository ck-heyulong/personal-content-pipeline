# Personal Content V1

## 1. Goal

Build a simple, reliable WSL-first personal content workflow that converts:

- fragmented personal text
- local source images

into a source-faithful Xiaohongshu image/text post.

The workflow must provide:

1. multimodal source understanding;
2. canonical factual representation;
3. three materially different Xiaohongshu writing styles;
4. bounded naturalness cleanup;
5. offline HTML preview;
6. explicit human approval;
7. deterministic approval hashing;
8. immutable publication packages;
9. WSL -> Windows PowerShell -> existing social-auto-upload integration.

No real publication may occur during automated development or tests.

---

# 2. Fixed AI provider

The production provider is fixed for V1.

Provider:
DeepSeek

Model:
deepseek-v4-flash-vision-exp

Endpoint:
https://api.deepseek.com/chat/completions

Protocol:
OpenAI-style Chat Completions over HTTPS.

Do not build a generic multi-provider framework.

A small provider boundary for testing is acceptable, but production configuration is DeepSeek Vision.

Use Python standard-library HTTP support.
Do not add:

- requests
- httpx
- deepseek SDK

Credentials must come only from environment variables.

Required live variables:

CONTENT_PROVIDER_API_KEY
CONTENT_PROVIDER_TIMEOUT

Defaults:

CONTENT_PROVIDER_MODEL=deepseek-v4-flash-vision-exp
CONTENT_PROVIDER_URL=https://api.deepseek.com/chat/completions
CONTENT_PROVIDER_TIMEOUT=60

The model and endpoint should work without requiring the user to configure them manually.

---

# 3. DeepSeek Vision multimodal protocol

Canonical analysis uses:

POST https://api.deepseek.com/chat/completions

Headers:

Authorization: Bearer <API key>
Content-Type: application/json
Accept: application/json

Request includes:

model = deepseek-v4-flash-vision-exp
stream = false

Canonical multimodal analysis:

Each local source image must be sent as an `image_url` content item using a Base64 data URL.

Raw text must also be included as a text content item.

Post generation and naturalness editing:

stream = false

Do not send model-specific thinking configuration by default.

Do not depend on provider-side structured-output enforcement.
Prompts must explicitly request exact JSON.

---

# 4. DeepSeek response compatibility

The provider may return an otherwise valid JSON object wrapped as:

```json
{
  ...
}
```

The response parser must accept:

1. bare JSON object;
2. exactly one complete `json` Markdown fenced object;
3. exactly one complete unlabelled Markdown fenced object.

Leading/trailing whitespace is allowed.

If a fence exists, it must encompass the entire trimmed model response.

After deterministic fence removal, use normal JSON parsing.

The parsed result must be a JSON object.

Reject:

- prose before JSON;
- prose after JSON;
- multiple fenced blocks;
- malformed JSON;
- JSON arrays;
- substring extraction;
- heuristic JSON repair.

Never "fix" missing commas, quotes, or braces.

---

# 5. Provider reliability

HTTP errors must remain secret-free but useful.

Do not reduce all failures to "request failed".

Where safe, expose:

- HTTP status
- provider error code
- provider error message

Never expose:

- API key
- Authorization header
- cookies
- full secret-bearing request headers

Use bounded retries only for transient failures:

- HTTP 429
- HTTP 502
- HTTP 503
- HTTP 504

Maximum:
3 attempts total.

Backoff:
2 seconds, then 4 seconds.

Do not retry:

- 400
- 401
- 403
- malformed successful responses

---

# 6. Job layout

Each content job lives at:

jobs/<safe-name>/

After `content new <name>`:

jobs/<name>/
  raw.md
  images/

Generated artifacts may include:

canonical.json
xiaohongshu.json
preview.html
approval.json
publish-result.json

Job names must be safe single filesystem components.

Real job data is ignored by Git.

---

# 7. Canonical schema

There is exactly one canonical schema.

Do not let prompts and application validation define different schemas.

Canonical JSON:

{
  "schema_version": 1,
  "topic": "string",
  "core_message": "string",
  "source_supported_points": [
    {
      "text": "string",
      "source_references": [
        {
          "kind": "text",
          "path": "raw.md",
          "line": 1
        }
      ]
    }
  ],
  "useful_original_phrases": [
    {
      "text": "string",
      "source_references": [
        {
          "kind": "text",
          "path": "raw.md",
          "line": 1
        }
      ]
    }
  ],
  "image_interpretations": {
    "images/example.png": {
      "visible_evidence": [
        "string"
      ],
      "source_references": [
        {
          "kind": "image",
          "path": "images/example.png"
        }
      ]
    }
  },
  "unknown_information": [
    "string"
  ],
  "claims_not_to_invent": [
    "string"
  ]
}

Allowed source-reference forms:

Text:

{
  "kind": "text",
  "path": "raw.md",
  "line": positive integer
}

Image:

{
  "kind": "image",
  "path": "images/<actual-relative-path>"
}

Validation must be strict enough to catch provider schema drift.

Do not weaken validation merely because the model returns a different shape.

---

# 8. Canonical content rules

Canonical is the factual source of truth.

Preserve source language.

For Chinese source material:

- topic should normally be Chinese;
- core_message should normally be Chinese;
- source-supported points should normally be Chinese;
- image interpretation should normally be Chinese;
- useful_original_phrases must preserve the original wording.

Technical names may naturally remain unchanged:

Git
WSL
Codex
API
Python
command names
model names

Never invent unsupported:

- experiences
- dates
- numbers
- statistics
- achievements
- expertise
- opinions
- events
- conclusions

Image interpretations must describe visible evidence only.

If information cannot be supported, place it in unknown_information or exclude it.

---

# 9. Xiaohongshu schema

Generated post JSON:

{
  "schema_version": 1,
  "style": "personal | knowledge | concise",
  "title": "string",
  "body": "string",
  "tags": [
    "string"
  ],
  "images": [
    "images/relative-path.png"
  ]
}

Image ordering matters.

All post factual content must be supported by canonical content.

---

# 10. Three writing styles

Exactly three selectable styles:

personal
knowledge
concise

They must differ materially.

## personal

Feels like a real person's own record.

Characteristics:

- retains useful original wording;
- natural pacing;
- concrete details;
- light structure;
- no forced tutorial tone.

## knowledge

Useful for knowledge sharing.

Characteristics:

- denser information;
- clearer organization;
- explicit relationships between concepts;
- still natural rather than academic/corporate.

## concise

Short and direct.

Characteristics:

- aggressively removes repetition;
- fewer transitions;
- minimal structure;
- preserves only useful information.

The styles must not simply be the same body with different titles.

---

# 11. Naturalness pass

Perform deterministic AI-writing checks after draft generation.

If no finding exists:
do not invoke the editor.

If findings exist:
allow at most ONE editor request.

Editor output schema:

{
  "replacements": [
    {
      "field": "title | body",
      "find": "exact existing substring",
      "replace": "replacement"
    }
  ]
}

Every replacement must be:

- local;
- bounded;
- source-faithful;
- applicable exactly once or rejected.

The editor must not replace the whole title/body as a workaround.

No second editor pass.

---

# 12. CLI

Provide executable:

./content

Commands:

content new <name>

content generate <name> --style personal|knowledge|concise

content preview <name>

content approve <name>

content publish <name>

content publish <name> --dry-run

content doctor

`content doctor` must be safe and non-destructive.

It may check:

- Python/runtime
- provider configuration presence
- PowerShell availability
- Windows SAU path
- expected account configuration

It must never print the API key.
It must never publish.

---

# 13. Preview

`content preview <name>` creates:

jobs/<name>/preview.html

Static HTML only.

No server.

Preview should show:

- raw source text;
- source images;
- canonical interpretation;
- selected style;
- title;
- body;
- tags;
- ordered images;
- approval status.

No external JavaScript dependency is required.

---

# 14. Explicit approval

`content approve <name>` means the human explicitly approves the current publishable state.

Approval hash MUST cover:

- title;
- body;
- tags in order;
- image paths/order;
- exact bytes of every ordered image.

Use SHA-256.

Store sufficient metadata in approval.json to verify the approval later.

Any mutation after approval must make publication fail until re-approved.

Tests must cover mutations to:

- title
- body
- tags
- tag order
- image order
- image bytes

---

# 15. Immutable publish package

Before publication, create or verify a package named by the full approval hash.

The package must be completely self-contained.

Package reuse must reject:

- symlinked manifest.json;
- symlinked image files;
- a symlink in ANY image path component;
- resolved paths escaping the hash-named package directory;
- non-regular package files;
- digest mismatches.

Every reused manifest/image path must resolve strictly beneath the expected package directory.

Tests must include:

- symlinked manifest;
- intermediate-directory symlink to an external directory;
- same-byte external-file escape attempt;
- valid package reuse.

Do not weaken these checks.

---

# 16. Windows Xiaohongshu publisher

Existing external dependency:

C:\Users\<user>\tools\social-auto-upload

Account alias:

main

Platform:

xiaohongshu

The existing SAU repository must NOT be modified.

Real publishing runs through:

WSL
  -> powershell.exe
  -> repository-owned PowerShell adapter
  -> existing Windows SAU executable
  -> `sau xiaohongshu upload-note --account main ...`

If necessary, inspect SAU help safely to determine exact current upload-note arguments.

Do NOT perform a real upload during automated development.

---

# 17. Windows staging

Default:

C:\Users\Public\personal-content-staging

Stage each immutable job under its full approval hash.

Never overwrite an existing immutable package.

The Windows adapter must verify the staged package before invoking SAU.

Failure from PowerShell or SAU must never be recorded as success.

---

# 18. Dry run

`content publish <name> --dry-run` must:

1. verify explicit approval;
2. recompute and verify approval hash;
3. verify/build immutable package;
4. calculate Windows staging target;
5. construct the PowerShell/SAU invocation;
6. display safe information;
7. perform NO real publication.

Dry-run must not require Xiaohongshu login interaction.

---

# 19. Human boundaries

Never bypass or automate:

- QR login
- CAPTCHA
- SMS
- 2FA
- platform risk controls
- final approval

If real publication encounters one of these, stop and let the human handle it.

---

# 20. Networking

Do not hard-code the user's HTTP proxy into application code.

Respect standard environment proxy behavior.

Development environment may use:

HTTP_PROXY / HTTPS_PROXY / ALL_PROXY
for Codex and other external traffic.

api.deepseek.com may be placed in:

NO_PROXY

so DeepSeek can connect directly.

Document this in README.

---

# 21. Secrets

Never commit real credentials.

`.env` must be ignored.

Provide `.env.example` containing placeholders/default public configuration only.

It may document:

CONTENT_PROVIDER=live
CONTENT_PROVIDER_URL=https://api.deepseek.com/chat/completions
CONTENT_PROVIDER_MODEL=deepseek-v4-flash-vision-exp
CONTENT_PROVIDER_API_KEY=
CONTENT_PROVIDER_TIMEOUT=60

Do not require dotenv.

Standard environment variables are sufficient.

---

# 22. Fake provider and testing

Automated tests must never require a real API key.

Provide a deterministic FakeProvider or equivalent test boundary.

Fake image behavior must explicitly say it did not visually interpret the image.

Mock live urllib calls for protocol tests.

Tests must cover the live DeepSeek Vision protocol shape:

- endpoint configuration;
- Bearer authentication;
- model name;
- raw text;
- image_url Base64;
- no default thinking configuration;
- choices[0].message.content parsing;
- full-response JSON fence compatibility;
- malformed response rejection;
- HTTP error diagnostics;
- transient retry policy;
- secret-free errors.

---

# 23. Technology

Prefer:

Python 3.12+
standard library
argparse
pathlib
urllib.request
json
hashlib
html
unittest

Avoid external dependencies unless absolutely necessary.

No database.

No server.

No framework.

---

# 24. Repository target

Keep the implementation compact.

A reasonable shape is:

AGENTS.md
PROJECT.md
SPEC.md
PLAN.md
README.md
.env.example
.gitignore
content
personal_content/
  __init__.py
  cli.py
  config.py
  provider.py
  canonical.py
  pipeline.py
  review.py
  approval.py
  publish.py
  prompts/
    canonical.md
    personal.md
    knowledge.md
    concise.md
    naturalness.md
scripts/
  publish_xiaohongshu.ps1
  verify_v1.sh
tests/
jobs/
  .gitkeep

Do not create empty files merely to match this diagram.
Use fewer modules if that is simpler.

---

# 25. Fixed execution phases

Phase 0 — Preconditions and repository inspection

Phase 1 — Repository foundation and CLI

Phase 2 — DeepSeek Vision provider and strict canonical content

Phase 3 — Xiaohongshu styles and bounded naturalness

Phase 4 — Preview, approval and deterministic hashing

Phase 5 — Immutable package and Windows SAU bridge

Phase 6 — End-to-end offline validation and documentation

Phase 7 — Final self-review

Phases 0-7 must run continuously in one Codex session.

Do not ask the user to type "continue" between phases.

---

# 26. Completion requirements

Before declaring completion:

- inspect complete git diff;
- run every targeted test;
- run full unit test suite;
- run scripts/verify_v1.sh;
- compile Python;
- check shell syntax;
- perform git diff --check;
- confirm secrets/real jobs are ignored;
- confirm no real network requests occurred in tests;
- confirm no real Xiaohongshu publication occurred.

If a check fails:
fix it and rerun it.

Final report must use:

STATUS: PASS

Changed:
Verified:
Assumptions:
Remaining:

"Remaining" must explicitly mention that real DeepSeek API generation and real Xiaohongshu publication are manual acceptance steps if they were not actually performed.

Do not commit automatically.
