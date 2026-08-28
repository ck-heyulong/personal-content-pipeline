# Personal Content V1

Personal Content is a small, WSL-first workflow that turns source text and local
images into a source-faithful Xiaohongshu image/text post. DeepSeek Vision builds
a canonical factual record and a draft, a human reviews the result in the WSL
terminal, and a separately installed Windows publishing backend performs the
final browser operation only after explicit approval.

Automated tests are offline. They do not call DeepSeek or publish to
Xiaohongshu.

## Features

- One daily command: `./scripts/post_xhs.sh`
- DeepSeek `deepseek-v4-flash-vision-exp` multimodal generation
- Canonical source record that constrains unsupported claims
- `personal`, `knowledge`, and `concise` writing styles
- Title, body, tags, and ordered images shown directly in the WSL terminal
- Single-key human review: `y`, `e`, `r`, or `q`, without Enter
- SHA-256 approval binding and immutable publication packages
- Safe dry-run before the real WSL → PowerShell → SAU handoff
- Standard-library Python implementation with deterministic offline tests

## Architecture

```text
text + images
    → DeepSeek Vision
    → Canonical
    → Xiaohongshu draft
    → Human approval
    → SHA-256 approval hash
    → Immutable package
    → WSL PowerShell bridge
    → external Windows SAU
    → Microsoft Edge
    → Xiaohongshu
```

The canonical JSON is the factual source of truth. Approval covers the exact
title, body, ordered tags, ordered image paths, and image bytes. A later change
invalidates approval.

## Requirements

- WSL with Python 3.12+, Bash, Git, `wslpath`, and `explorer.exe` interop
- A DeepSeek API key for live generation
- Windows PowerShell and Microsoft Edge for real publication
- An independently installed
  [dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload)
  (SAU) with Xiaohongshu account alias `main`

No database, web server, frontend, framework, or dotenv package is required.

## Quick start

From the repository root:

```bash
./scripts/post_xhs.sh
```

On the first run only, enter the DeepSeek API key at the hidden prompt. Then:

1. Paste the source text and press Ctrl-D.
2. The script opens `jobs/<job>/images/` in Windows Explorer. Copy or drag the
   images into that folder, then return to WSL and press Enter.
3. Review the generated title, body, tags, and ordered images in the terminal.
4. Press `y` to approve, run the safe dry-run, and continue to real publication.

The normal workflow is simply text + images + terminal review + `y`.

## Daily usage

The default style is `personal`:

```bash
./scripts/post_xhs.sh
```

Select another supported style with an environment variable:

```bash
CONTENT_STYLE=knowledge ./scripts/post_xhs.sh
CONTENT_STYLE=concise ./scripts/post_xhs.sh
```

Review keys do not require Enter:

- `y` — approve, run `publish --dry-run`, then invoke the real publisher
- `e` — edit the final `jobs/<job>/xiaohongshu.json`
- `r` — edit source text/images and regenerate
- `q` — pause without approval or publication

Resume a paused or existing generated job by name:

```bash
./scripts/post_xhs.sh '<job-name>'
```

The lower-level `./content` commands remain available for inspection and
offline workflows; `./content --help` lists them. The supported daily entrypoint
for V1 is `scripts/post_xhs.sh`.

## DeepSeek configuration

The first-run prompt stores the key outside the repository at:

```text
~/.config/personal-content/deepseek_api_key
```

The directory uses mode `700` and the key file uses mode `600`. The script
reuses that file on later runs without echoing the key. A secret manager may
instead provide `CONTENT_PROVIDER_API_KEY` in the environment.

Production defaults are:

```text
CONTENT_PROVIDER=live
CONTENT_PROVIDER_URL=https://api.deepseek.com/chat/completions
CONTENT_PROVIDER_MODEL=deepseek-v4-flash-vision-exp
CONTENT_PROVIDER_TIMEOUT=60
```

`.env.example` is an optional configuration reference only. The application
does not load `.env` files. Never place a real key in `.env.example`, Git, job
files, logs, or shell scripts.

Standard proxy environment variables are respected. If needed, set
`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and `NO_PROXY` in the shell, or set
`CONTENT_PROXY_URL` for the wrapper. No personal proxy address is required by
the repository.

For offline generation and tests:

```bash
export CONTENT_PROVIDER=fake
unset CONTENT_PROVIDER_API_KEY
```

The fake provider does not visually interpret images and says so in generated
canonical data.

## Windows SAU installation

Install SAU separately on Windows by following its upstream documentation. A
typical external location is:

```text
C:\Users\<user>\tools\social-auto-upload
```

Do not copy the SAU repository, `.venv`, cookies, or browser profile into this
project. The default publisher resolves
`%USERPROFILE%\tools\social-auto-upload`; override it only when SAU is installed
elsewhere:

```bash
export CONTENT_SAU_HOME='D:\tools\social-auto-upload'
export CONTENT_SAU_ACCOUNT=main
```

The bridge invokes the external executable as `sau xiaohongshu upload-note
--account main ...`. SAU remains an external runtime dependency and is not
redistributed here.

## Microsoft Edge configuration

Microsoft Edge must be installed and usable by the external Windows SAU
installation. Configure the Xiaohongshu account alias `main` in SAU and complete
its login flow yourself before a real publication. Cookies and browser
credentials stay inside that external installation.

QR login, CAPTCHA, SMS verification, 2FA, and platform risk controls are always
human steps. If Edge or Xiaohongshu requests one, stop and handle it directly;
this project does not automate or bypass the check.

## Security and privacy

- API keys never belong in this Git repository.
- SAU cookies, sessions, and browser profiles never belong in this repository.
- `jobs/` may contain real text and images and is ignored by Git.
- `publish-packages/` may contain approved real content and is ignored by Git.
- Debug output must not record keys, Authorization headers, cookies, or tokens.
- Final publication always requires explicit human approval.
- Users are responsible for complying with Xiaohongshu's terms of service and
  applicable local laws.

See [SECURITY.md](SECURITY.md) for secret handling and accidental-commit
response guidance.

## Project structure

```text
content                         lower-level CLI
scripts/post_xhs.sh             V1 daily entrypoint
scripts/publish_xiaohongshu.ps1 Windows staging and external SAU bridge
scripts/verify_v1.sh            offline verification
personal_content/               standard-library Python implementation
tests/                          deterministic offline tests
jobs/                           ignored local source and generated content
publish-packages/               ignored immutable approved packages
```

## Automated verification

Run the complete offline suite:

```bash
./scripts/verify_v1.sh
```

When Windows PowerShell interop is available, optionally include its parser
check:

```bash
CONTENT_VERIFY_POWERSHELL=1 ./scripts/verify_v1.sh
```

Neither command performs a real DeepSeek request or Xiaohongshu publication.

## Acknowledgements and third-party software

Thanks to
[dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload)
and its contributors. Personal Content calls a separately installed SAU runtime
and does not claim or redistribute its source code.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for attribution and license
notes.

## Limitations

- V1 supports Xiaohongshu image/text posts only; it does not support video.
- Live DeepSeek generation requires network access and a user-supplied key.
- Publication depends on Windows, PowerShell, Edge, external SAU, and the current
  Xiaohongshu interface.
- AI output still requires source-fidelity review by a human.
- Real DeepSeek generation and real publication are manual acceptance steps and
  are intentionally excluded from automated verification.

## License

This repository's original code is licensed under the [MIT License](LICENSE).
Third-party software remains under its own license; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
