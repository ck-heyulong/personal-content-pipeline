"""Static, escaped HTML preview."""

from __future__ import annotations

from html import escape
import json
from pathlib import Path

from .approval import approval_status
from .canonical import validate_canonical
from .jobs import job_path
from .pipeline import source_images
from .review import validate_post


def _load_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"required artifact is missing or unsafe: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"required artifact is invalid JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"required artifact must be a JSON object: {path.name}")
    return value


def create_preview(root: Path, name: str) -> Path:
    path = job_path(root, name)
    raw_text = (path / "raw.md").read_text(encoding="utf-8")
    images = source_images(path)
    image_paths = [image.relative_path for image in images]
    canonical = validate_canonical(
        _load_json(path / "canonical.json"),
        image_paths=image_paths,
        raw_line_count=len(raw_text.splitlines()),
    )
    post = validate_post(
        _load_json(path / "xiaohongshu.json"), available_images=image_paths
    )
    status = approval_status(root, name)
    ordered_images = "\n".join(
        f'<figure><img src="{escape(image_path, quote=True)}" '
        f'alt="Source image: {escape(image_path, quote=True)}"><figcaption>'
        f'{escape(image_path)}</figcaption></figure>'
        for image_path in post["images"]
    ) or "<p>No source images.</p>"
    tags = " ".join(f"#{escape(tag)}" for tag in post["tags"])
    canonical_text = escape(json.dumps(canonical, ensure_ascii=False, indent=2))
    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'">
<title>{escape(post['title'])} — Personal Content Preview</title>
<style>
body {{ font-family: sans-serif; line-height: 1.6; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }}
section {{ border-top: 1px solid #ddd; padding: 1rem 0; }}
pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #f6f6f6; padding: 1rem; }}
img {{ max-width: 100%; max-height: 36rem; }}
.status {{ font-weight: 700; }}
</style>
</head>
<body>
<h1>{escape(post['title'])}</h1>
<p class="status">{escape(status)}</p>
<section><h2>Raw source text</h2><pre>{escape(raw_text)}</pre></section>
<section><h2>Canonical interpretation</h2><pre>{canonical_text}</pre></section>
<section><h2>Xiaohongshu draft</h2>
<p><strong>Style:</strong> {escape(post['style'])}</p>
<h3>{escape(post['title'])}</h3><pre>{escape(post['body'])}</pre>
<p>{tags}</p></section>
<section><h2>Ordered images</h2>{ordered_images}</section>
</body>
</html>
"""
    preview_path = path / "preview.html"
    if preview_path.is_symlink() or (preview_path.exists() and not preview_path.is_file()):
        raise ValueError("preview.html is unsafe")
    preview_path.write_text(document, encoding="utf-8")
    return preview_path
