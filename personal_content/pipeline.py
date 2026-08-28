"""Source-to-canonical-to-post generation pipeline."""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any

from .canonical import validate_canonical
from .config import Settings
from .jobs import job_path
from .provider import DeepSeekProvider, FakeProvider, LocalImage, load_prompt
from .review import apply_editor_replacements, naturalness_findings, validate_post


Provider = FakeProvider | DeepSeekProvider


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def source_images(path: Path) -> list[LocalImage]:
    images_root = path / "images"
    images: list[LocalImage] = []
    for candidate in sorted(images_root.rglob("*")):
        if candidate.is_symlink():
            raise ValueError(f"source images may not contain symlinks: {candidate}")
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise ValueError(f"source image is not a regular file: {candidate}")
        mime_type = mimetypes.guess_type(candidate.name)[0]
        if mime_type is None or not mime_type.startswith("image/"):
            raise ValueError(f"source images directory contains a non-image file: {candidate}")
        relative = candidate.relative_to(path).as_posix()
        images.append(LocalImage(relative, candidate))
    return images


def make_provider(settings: Settings) -> Provider:
    if settings.provider == "fake":
        return FakeProvider()
    return DeepSeekProvider(settings)


def generate_job(
    root: Path,
    name: str,
    style: str,
    *,
    provider: Provider | None = None,
    settings: Settings | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = job_path(root, name)
    raw_text = (path / "raw.md").read_text(encoding="utf-8")
    if not raw_text.strip():
        raise ValueError("raw.md must contain source text before generation")
    images = source_images(path)
    selected_provider = provider or make_provider(settings or Settings.from_environment())
    canonical = selected_provider.analyze(raw_text, images)
    canonical = validate_canonical(
        canonical,
        image_paths=[image.relative_path for image in images],
        raw_line_count=len(raw_text.splitlines()),
    )
    post = selected_provider.generate_post(
        canonical, style, load_prompt(f"{style}.md")
    )
    post = validate_post(
        post,
        expected_style=style,
        available_images=[image.relative_path for image in images],
    )
    protected_texts = [
        item["text"]
        for field in ("source_supported_points", "useful_original_phrases")
        for item in canonical[field]
    ]
    findings = naturalness_findings(post, protected_texts=protected_texts)
    if findings:
        editor_output = selected_provider.edit_post(
            post, findings, load_prompt("naturalness.md")
        )
        post = apply_editor_replacements(
            post, editor_output, protected_texts=protected_texts
        )
        post = validate_post(
            post,
            expected_style=style,
            available_images=[image.relative_path for image in images],
        )
    _write_json(path / "canonical.json", canonical)
    _write_json(path / "xiaohongshu.json", post)
    return canonical, post
