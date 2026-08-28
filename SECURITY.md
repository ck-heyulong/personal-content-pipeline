# Security and privacy

This repository must contain only source code, tests, public documentation, and
placeholder configuration. Do not commit real API keys, cookies, browser
profiles, login QR codes, personal drafts, images, previews, or publish results.

## Local secrets and accounts

- `scripts/post_xhs.sh` stores the DeepSeek key outside the repository at
  `~/.config/personal-content/deepseek_api_key` with file mode `600`. API keys
  must never be copied into `.env`, logs, jobs, or Git.
- Xiaohongshu cookies and browser credentials belong only to the separately
  installed Windows `social-auto-upload` (SAU) environment. Never copy its
  cookies, profile, `.venv`, or source tree into this repository.
- `jobs/` can contain real text and images, and `publish-packages/` can contain
  reviewed publishable content. Both are ignored by Git by default.
- QR login, CAPTCHA, SMS verification, 2FA, platform risk controls, and final
  publication approval are human-only steps. This project does not bypass them.

Do not enable debug output that records request headers, API keys, cookies,
tokens, or browser/session data. Follow Xiaohongshu's terms of service and all
applicable local laws.

## If a secret is committed

1. Revoke or rotate the exposed key, token, cookie, or session immediately.
2. Remove it from the current tree and audit every reachable Git commit.
3. Rewrite/replace the affected public history before publishing again; deleting
   only the current file is not sufficient.
4. Invalidate related browser sessions and credentials when applicable.

When reporting a potential leak, share only the path, commit, secret type, and a
short mask. Never paste the full secret into an issue or chat.
