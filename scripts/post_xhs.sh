#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STYLE="${CONTENT_STYLE:-personal}"
JOB="${1:-post-$(date +%Y%m%d-%H%M%S)}"

case "$STYLE" in
    personal|knowledge|concise) ;;
    *)
        echo "error: CONTENT_STYLE 必须是 personal、knowledge 或 concise" >&2
        exit 1
        ;;
esac

if [[ ! "$JOB" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ || "$JOB" == "." || "$JOB" == ".." ]]; then
    echo "error: Job 名必须是 1-64 位 ASCII 字母、数字、点、下划线或连字符，且以字母或数字开头" >&2
    exit 1
fi

# ---------- 固定生产配置 ----------
export CONTENT_PROVIDER="${CONTENT_PROVIDER:-live}"
export CONTENT_PROVIDER_URL="${CONTENT_PROVIDER_URL:-https://api.deepseek.com/chat/completions}"
export CONTENT_PROVIDER_MODEL="${CONTENT_PROVIDER_MODEL:-deepseek-v4-flash-vision-exp}"
export CONTENT_PROVIDER_TIMEOUT="${CONTENT_PROVIDER_TIMEOUT:-60}"
export CONTENT_SAU_ACCOUNT="${CONTENT_SAU_ACCOUNT:-main}"

# 可选代理：尊重现有标准环境变量，不内置个人代理地址。
PROXY_URL="${CONTENT_PROXY_URL:-}"
if [[ -n "$PROXY_URL" ]]; then
    export HTTP_PROXY="${HTTP_PROXY:-$PROXY_URL}"
    export HTTPS_PROXY="${HTTPS_PROXY:-$PROXY_URL}"
    export ALL_PROXY="${ALL_PROXY:-$PROXY_URL}"
fi
[[ -n "${HTTP_PROXY:-}" ]] && export http_proxy="${http_proxy:-$HTTP_PROXY}"
[[ -n "${HTTPS_PROXY:-}" ]] && export https_proxy="${https_proxy:-$HTTPS_PROXY}"
[[ -n "${ALL_PROXY:-}" ]] && export all_proxy="${all_proxy:-$ALL_PROXY}"

export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,::1,api.deepseek.com}"
export no_proxy="$NO_PROXY"

# ---------- DeepSeek Key：只在第一次输入 ----------
KEY_DIR="$HOME/.config/personal-content"
KEY_FILE="$KEY_DIR/deepseek_api_key"

if [[ -z "${CONTENT_PROVIDER_API_KEY:-}" ]]; then
    if [[ -L "$KEY_DIR" || ( -e "$KEY_DIR" && ! -d "$KEY_DIR" ) ]]; then
        echo "error: DeepSeek API Key 目录不安全：$KEY_DIR" >&2
        exit 1
    fi
    mkdir -p "$KEY_DIR"
    chmod 700 "$KEY_DIR"
    if [[ -L "$KEY_FILE" || ( -e "$KEY_FILE" && ! -f "$KEY_FILE" ) ]]; then
        echo "error: DeepSeek API Key 路径不是安全的普通文件：$KEY_FILE" >&2
        exit 1
    fi
    if [[ -f "$KEY_FILE" ]]; then
        chmod 600 "$KEY_FILE"
        CONTENT_PROVIDER_API_KEY="$(cat "$KEY_FILE")"
        export CONTENT_PROVIDER_API_KEY
    else
        read -r -s -p "首次使用，请输入 DeepSeek API Key（以后不会再询问）: " CONTENT_PROVIDER_API_KEY
        echo
        if [[ -z "$CONTENT_PROVIDER_API_KEY" ]]; then
            echo "error: API Key 不能为空" >&2
            exit 1
        fi
        umask 077
        printf '%s' "$CONTENT_PROVIDER_API_KEY" > "$KEY_FILE"
        chmod 600 "$KEY_FILE"
        export CONTENT_PROVIDER_API_KEY
        echo "API Key 已保存到：$KEY_FILE"
    fi
fi

if [[ ! -x ./content ]]; then
    echo "error: 找不到 ./content：$ROOT/content" >&2
    exit 1
fi

RAW="jobs/$JOB/raw.md"
IMG_DIR="jobs/$JOB/images"
DRAFT="jobs/$JOB/xiaohongshu.json"
JOB_DIR="jobs/$JOB"

if [[ -L "$JOB_DIR" || ( -e "$JOB_DIR" && ! -d "$JOB_DIR" ) ]]; then
    echo "error: Job 目录不安全：$JOB_DIR" >&2
    exit 1
fi
if [[ -L "$DRAFT" ]]; then
    echo "error: 最终草稿不能是符号链接：$DRAFT" >&2
    exit 1
fi
if [[ -d "$JOB_DIR" ]]; then
    if [[ -L "$RAW" || ! -f "$RAW" || -L "$IMG_DIR" || ! -d "$IMG_DIR" ]]; then
        echo "error: Job 的 raw.md 或 images/ 布局不安全：$JOB_DIR" >&2
        exit 1
    fi
fi

# ---------- 已存在 Job：直接继续审核 ----------
if [[ -f "$DRAFT" ]]; then
    echo "继续已有 Job：$JOB"
else
    if [[ -e "jobs/$JOB" ]]; then
        echo "error: Job 已存在但尚无完整草稿：jobs/$JOB" >&2
        echo "请检查该目录，或换一个 Job 名。" >&2
        exit 1
    fi

    echo
    echo "========== 1/4 创建内容 =========="
    ./content new "$JOB"

    echo
    echo "请粘贴文字内容，完成后按 Ctrl-D："
    echo "----------------------------------------"
    cat > "$RAW"

    if [[ ! -s "$RAW" ]]; then
        echo "error: 文字内容为空" >&2
        exit 1
    fi

    echo
    echo "========== 2/4 添加图片 =========="
    echo "已打开 Windows 文件夹，请直接把图片拖进去/复制进去："
    echo "  $IMG_DIR"

    if command -v explorer.exe >/dev/null 2>&1; then
        explorer.exe "$(wslpath -w "$ROOT/$IMG_DIR")" >/dev/null 2>&1 || true
    fi

    read -r -p "图片放好后，回到这里按 Enter 继续..."

    IMAGE_COUNT="$(
        find "$IMG_DIR" -maxdepth 1 -type f \
          \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp' \) \
          | wc -l
    )"

    if [[ "$IMAGE_COUNT" -eq 0 ]]; then
        echo "error: images/ 中没有找到 png/jpg/jpeg/webp 图片" >&2
        exit 1
    fi

    echo "检测到图片：$IMAGE_COUNT 张"

    echo
    echo "========== 3/4 AI 生成 =========="
    ./content generate "$JOB" --style "$STYLE"

    # 保留原系统 preview 步骤，但不再打开浏览器。
    ./content preview "$JOB" >/dev/null
fi

show_draft() {
    echo
    echo "============================================================"
    echo "                    生成结果 / 请审核"
    echo "============================================================"

    python3 - "$DRAFT" <<'PY'
import json
import sys
from pathlib import Path

p = Path(sys.argv[1])
data = json.loads(p.read_text(encoding="utf-8"))

title = data.get("title", "")
body = data.get("body", "")
tags = data.get("tags", [])
images = data.get("images", [])

print("\n【标题】")
print(title)

print("\n【正文】")
print(body)

print("\n【标签】")
if isinstance(tags, list):
    print(" ".join(f"#{x}" for x in tags))
else:
    print(tags)

print("\n【图片】")
if isinstance(images, list):
    for i, item in enumerate(images, 1):
        if isinstance(item, dict):
            value = item.get("path") or item.get("source_path") or item.get("package_path") or str(item)
        else:
            value = str(item)
        print(f"{i}. {value}")
else:
    print(images)
PY

    echo
    echo "------------------------------------------------------------"
    echo "源文字：$RAW"
    echo "源图片：$IMG_DIR/"
    echo "最终草稿：$DRAFT"
    echo "------------------------------------------------------------"
}

while true; do
    show_draft

    echo
    echo "按键操作（无需 Enter）："
    echo "  y = 认可，批准并发布"
    echo "  e = 编辑最终草稿"
    echo "  r = 修改源文字/图片后重新生成"
    echo "  q = 暂停，不发布"
    echo

    IFS= read -r -s -n 1 key
    echo

    case "$key" in
        y|Y)
            echo
            echo "========== 4/4 批准并发布 =========="
            ./content approve "$JOB"
            ./content publish "$JOB" --dry-run
            ./content publish "$JOB"

            echo
            echo "发布流程完成。"
            echo "Job：$JOB"
            if [[ -f "jobs/$JOB/publish-result.json" ]]; then
                echo "结果：$ROOT/jobs/$JOB/publish-result.json"
            fi
            exit 0
            ;;

        e|E)
            echo "正在编辑最终草稿：$DRAFT"
            echo "建议只修改 title / body / tags 的值，不要破坏 JSON 结构。"
            "${EDITOR:-nano}" "$DRAFT"
            ;;

        r|R)
            echo "正在编辑源文字：$RAW"
            "${EDITOR:-nano}" "$RAW"

            if command -v explorer.exe >/dev/null 2>&1; then
                explorer.exe "$(wslpath -w "$ROOT/$IMG_DIR")" >/dev/null 2>&1 || true
            fi
            read -r -p "图片如需增删请在已打开文件夹中处理，完成后按 Enter 重新生成..."

            ./content generate "$JOB" --style "$STYLE"
            ./content preview "$JOB" >/dev/null
            ;;

        q|Q)
            echo "已停止，未批准、未发布。"
            echo "下次继续：./scripts/post_xhs.sh '$JOB'"
            exit 0
            ;;

        *)
            echo "无效按键，请按 y / e / r / q。"
            ;;
    esac
done
