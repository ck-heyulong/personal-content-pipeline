#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

python3 -m unittest discover -s tests -v
python3 -m compileall -q personal_content tests
./content --help >/dev/null
./content generate --help >/dev/null
./content publish --help >/dev/null
bash -n scripts/verify_v1.sh
bash -n scripts/post_xhs.sh
if ./scripts/post_xhs.sh '../unsafe-job' >/dev/null 2>&1; then
    echo "post_xhs.sh accepted an unsafe job name" >&2
    exit 1
fi
if CONTENT_STYLE=unsupported ./scripts/post_xhs.sh 'safe-job' >/dev/null 2>&1; then
    echo "post_xhs.sh accepted an unsupported content style" >&2
    exit 1
fi
git diff --check

mapfile -d '' repository_files < <(git ls-files --cached --others --exclude-standard -z)
if ((${#repository_files[@]} > 0)); then
    python3 -c 'import pathlib, sys
bad = []
for name in sys.argv[1:]:
    for number, line in enumerate(pathlib.Path(name).read_bytes().splitlines(), 1):
        if line.endswith((b" ", b"\t")):
            bad.append(f"{name}:{number}")
if bad:
    print("Trailing whitespace detected:\n" + "\n".join(bad), file=sys.stderr)
    raise SystemExit(1)' "${repository_files[@]}"
fi

git check-ignore -q .env
git check-ignore -q .env.local
git check-ignore -q jobs/example/raw.md
git check-ignore -q publish-packages/example/manifest.json
git check-ignore -q cookies/example.json
git check-ignore -q account_login_qrcode_1.png
git check-ignore -q example.log
git check-ignore -q htmlcov/index.html
test "$(git ls-files jobs)" = "jobs/.gitkeep"
test "$(sed -n 's/^CONTENT_PROVIDER_API_KEY=//p' .env.example)" = "your_deepseek_api_key_here"
test -f LICENSE
test -f SECURITY.md
test -f THIRD_PARTY_NOTICES.md
while IFS= read -r tracked_file; do
    case "$tracked_file" in
        .env|*/.env|jobs/*|publish-packages/*|cookies/*|cookie/*|*_login_qrcode_*.png|publish-result.json)
            if [[ "$tracked_file" == "jobs/.gitkeep" ]]; then
                continue
            fi
            echo "Sensitive tracked path detected: $tracked_file" >&2
            exit 1
            ;;
    esac
done < <(git ls-files)

python3 - "${repository_files[@]}" <<'PY'
import pathlib
import re
import sys

patterns = (
    ("API_KEY_SHAPE", re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{12,}")),
    ("GITHUB_TOKEN_SHAPE", re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("JWT_SHAPE", re.compile(rb"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("PRIVATE_KEY_BLOCK", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("PERSONAL_WINDOWS_PATH", re.compile(rb"C:\\Users\\(?!<user>\\|Public\\)[^\\\r\n]+", re.I)),
    ("PERSONAL_LINUX_PATH", re.compile(b"/" + rb"home/(?!<user>(?:/|\b))[^/\s]+(?:/|\b)")),
)

findings = []
for name in sys.argv[1:]:
    path = pathlib.Path(name)
    try:
        data = path.read_bytes()
    except OSError:
        continue
    if b"\0" in data[:8192]:
        continue
    for number, line in enumerate(data.splitlines(), 1):
        for kind, pattern in patterns:
            if pattern.search(line):
                findings.append(f"{name}:{number} [{kind}]")
if findings:
    print("Public-safety scan findings:\n" + "\n".join(findings), file=sys.stderr)
    raise SystemExit(1)
PY

if [[ "${CONTENT_VERIFY_POWERSHELL:-0}" == "1" ]]; then
    adapter_windows=$(wslpath -w "$repo_root/scripts/publish_xiaohongshu.ps1")
    powershell.exe -NoProfile -NonInteractive -Command \
        "\$tokens=\$null; \$errors=\$null; [void][System.Management.Automation.Language.Parser]::ParseFile('$adapter_windows', [ref]\$tokens, [ref]\$errors); if (\$errors.Count -ne 0) { \$errors | ForEach-Object { Write-Error \$_.Message }; exit 1 }; Write-Output 'PowerShell syntax OK'"
fi

echo "Personal Content V1 offline verification passed."
