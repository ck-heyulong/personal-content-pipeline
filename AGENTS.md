# Personal Content V1 — Engineering Rules

## Required reading

Before implementation, read:

1. `AGENTS.md`
2. `PROJECT.md`

If `SPEC.md` and `PLAN.md` exist, read them before modifying application code.

## Priorities

In order:

1. Correctness
2. Source fidelity
3. Safety
4. Simplicity
5. Maintainability
6. Verifiable behavior

## Engineering rules

- Inspect existing files before modifying them.
- Implement the smallest solution that satisfies V1.
- Prefer Python standard library.
- Do not add frameworks unless PROJECT.md explicitly requires them.
- Use pathlib for filesystem operations.
- Use type hints where useful.
- Never hide broad exceptions.
- Never claim a check passed unless it was actually run.
- Never commit automatically.
- Never perform destructive Git operations.
- Never store credentials, cookies, tokens, or real personal content in Git.
- Automated tests must not make real network calls.
- Automated development must never publish a real Xiaohongshu post.

## Human-only boundaries

Never automate or bypass:

- QR login
- CAPTCHA
- SMS verification
- 2FA
- platform risk controls
- final publication approval

## Content fidelity

Canonical content is the factual source of truth.

Never invent:

- personal experiences
- dates
- statistics
- achievements
- expertise
- opinions
- events
- claims unsupported by source text or images

Preserve useful original wording and concrete details.

Source language must be preserved by default.
Chinese input should remain Chinese except technical terms that naturally remain in English.

Faithfulness is more important than fluency.

## Naturalness

Avoid formulaic AI writing:

- generic introductions
- generic conclusions
- unnecessary summaries
- excessive symmetry
- excessive headings
- "首先 / 其次 / 最后" when unnecessary
- corporate or academic rewriting
- clickbait
- empty motivational language
- excessive emoji
- phrases such as "值得一提的是"

Only one optional naturalness editing pass is allowed.

That pass must use bounded exact-text replacements.
It must never rewrite the whole post.

## Scope control

V1 is Xiaohongshu image/text only.

Do not implement:

- Douyin
- Bilibili
- video
- TTS
- AI video generation
- database
- web frontend
- web backend
- LangChain
- LangGraph
- agent frameworks
- queues/workers
- analytics
- plugin systems

## Verification

Every significant feature must have deterministic automated coverage.

Use fake/mocked provider behavior for tests.

Real DeepSeek integration and real Xiaohongshu publication are separate manual acceptance steps.
