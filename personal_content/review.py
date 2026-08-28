"""Strict post validation and one-pass naturalness cleanup."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence


STYLES = ("personal", "knowledge", "concise")
POST_KEYS = {"schema_version", "style", "title", "body", "tags", "images"}
REPLACEMENT_KEYS = {"field", "find", "replace"}
FORMULAIC_PHRASES = (
    "大家好，今天",
    "让我们一起来",
    "首先",
    "其次",
    "最后",
    "值得一提的是",
    "总的来说",
    "综上所述",
    "希望对你有所帮助",
)
EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF]", flags=re.UNICODE
)


class PostValidationError(ValueError):
    """A generated post or edit does not satisfy its strict contract."""


def _exact_keys(value: Mapping[str, Any], keys: set[str], location: str) -> None:
    if set(value) != keys:
        raise PostValidationError(f"{location} keys do not match schema")


def _nonempty_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PostValidationError(f"{location} must be a non-empty string")
    return value


def validate_post(
    value: Any,
    *,
    expected_style: str | None = None,
    available_images: Sequence[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PostValidationError("post must be an object")
    _exact_keys(value, POST_KEYS, "post")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise PostValidationError("post.schema_version must be 1")
    style = value["style"]
    if style not in STYLES or (expected_style is not None and style != expected_style):
        raise PostValidationError("post.style does not match the requested style")
    _nonempty_string(value["title"], "post.title")
    _nonempty_string(value["body"], "post.body")
    tags = value["tags"]
    if not isinstance(tags, list) or not tags:
        raise PostValidationError("post.tags must be a non-empty array")
    if any(not isinstance(tag, str) or not tag.strip() for tag in tags):
        raise PostValidationError("every post tag must be a non-empty string")
    if len(set(tags)) != len(tags):
        raise PostValidationError("post tags must not contain duplicates")
    images = value["images"]
    if not isinstance(images, list):
        raise PostValidationError("post.images must be an array")
    if any(not isinstance(path, str) or not _safe_image_path(path) for path in images):
        raise PostValidationError("every post image must be a job-relative images/ path")
    if len(set(images)) != len(images):
        raise PostValidationError("post images must not contain duplicates")
    if available_images is not None and set(images) != set(available_images):
        raise PostValidationError("post images must exactly match the source images")
    return dict(value)


def _safe_image_path(path: str) -> bool:
    relative = PurePosixPath(path)
    return (
        not relative.is_absolute()
        and len(relative.parts) >= 2
        and relative.parts[0] == "images"
        and all(part not in {"", ".", ".."} for part in relative.parts)
    )


def naturalness_findings(
    post: Mapping[str, Any], *, protected_texts: Sequence[str] = ()
) -> list[str]:
    combined = f"{post['title']}\n{post['body']}"
    findings = [
        f"remove formulaic phrase: {phrase}"
        for phrase in FORMULAIC_PHRASES
        if phrase in combined and not any(phrase in protected for protected in protected_texts)
    ]
    heading_count = sum(
        1 for line in str(post["body"]).splitlines() if line.lstrip().startswith("#")
    )
    if heading_count >= 4:
        findings.append(f"excessive headings: {heading_count}")
    emoji_count = len(EMOJI_PATTERN.findall(combined))
    if emoji_count > 2:
        findings.append(f"excessive emoji: {emoji_count}")
    return findings


def apply_editor_replacements(
    post: Mapping[str, Any], editor_output: Any, *, protected_texts: Sequence[str] = ()
) -> dict[str, Any]:
    if not isinstance(editor_output, dict):
        raise PostValidationError("editor output must be an object")
    _exact_keys(editor_output, {"replacements"}, "editor output")
    replacements = editor_output["replacements"]
    if not isinstance(replacements, list) or len(replacements) > 8:
        raise PostValidationError("editor replacements must be an array of at most 8 items")
    result = dict(post)
    for index, replacement_value in enumerate(replacements):
        if not isinstance(replacement_value, dict):
            raise PostValidationError(f"replacement[{index}] must be an object")
        _exact_keys(replacement_value, REPLACEMENT_KEYS, f"replacement[{index}]")
        field = replacement_value["field"]
        find = replacement_value["find"]
        replace = replacement_value["replace"]
        if field not in {"title", "body"}:
            raise PostValidationError(f"replacement[{index}].field is invalid")
        if not isinstance(find, str) or not find:
            raise PostValidationError(f"replacement[{index}].find must be non-empty")
        if not isinstance(replace, str) or find == replace:
            raise PostValidationError(f"replacement[{index}].replace is invalid")
        current = str(result[field])
        if current.count(find) != 1:
            raise PostValidationError(
                f"replacement[{index}].find must occur exactly once in {field}"
            )
        if find == current or len(find) > 120 or len(find) * 2 > len(current):
            raise PostValidationError(f"replacement[{index}] is not a bounded local edit")
        if any(find in protected for protected in protected_texts):
            raise PostValidationError(f"replacement[{index}] would alter source wording")
        if len(replace) > len(find) + 40:
            raise PostValidationError(f"replacement[{index}] expands text beyond its bound")
        result[field] = current.replace(find, replace, 1)
        _nonempty_string(result[field], f"edited post.{field}")
    return result
