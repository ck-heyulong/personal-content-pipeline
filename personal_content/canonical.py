"""The single strict canonical-content contract."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence


CANONICAL_KEYS = {
    "schema_version",
    "topic",
    "core_message",
    "source_supported_points",
    "useful_original_phrases",
    "image_interpretations",
    "unknown_information",
    "claims_not_to_invent",
}

CANONICAL_SCHEMA_TEMPLATE: dict[str, Any] = {
    "schema_version": 1,
    "topic": "string",
    "core_message": "string",
    "source_supported_points": [
        {
            "text": "string",
            "source_references": [{"kind": "text", "path": "raw.md", "line": 1}],
        }
    ],
    "useful_original_phrases": [
        {
            "text": "string",
            "source_references": [{"kind": "text", "path": "raw.md", "line": 1}],
        }
    ],
    "image_interpretations": {
        "images/example.png": {
            "visible_evidence": ["string"],
            "source_references": [{"kind": "image", "path": "images/example.png"}],
        }
    },
    "unknown_information": ["string"],
    "claims_not_to_invent": ["string"],
}


class CanonicalValidationError(ValueError):
    """Canonical content does not conform to the frozen schema."""


def _object(value: Any, location: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise CanonicalValidationError(f"{location} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], location: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise CanonicalValidationError(
            f"{location} keys do not match schema (missing={missing}, extra={extra})"
        )


def _string(value: Any, location: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise CanonicalValidationError(f"{location} must be a non-empty string")
    return value


def _string_list(value: Any, location: str) -> list[str]:
    if not isinstance(value, list):
        raise CanonicalValidationError(f"{location} must be an array")
    for index, item in enumerate(value):
        _string(item, f"{location}[{index}]")
    return value


def _source_reference(
    value: Any,
    location: str,
    *,
    image_paths: set[str] | None,
    raw_line_count: int | None,
) -> None:
    reference = _object(value, location)
    kind = reference.get("kind")
    if kind == "text":
        _exact_keys(reference, {"kind", "path", "line"}, location)
        if reference["path"] != "raw.md":
            raise CanonicalValidationError(f"{location}.path must be raw.md")
        line = reference["line"]
        if isinstance(line, bool) or not isinstance(line, int) or line < 1:
            raise CanonicalValidationError(f"{location}.line must be a positive integer")
        if raw_line_count is not None and line > raw_line_count:
            raise CanonicalValidationError(f"{location}.line is outside raw.md")
    elif kind == "image":
        _exact_keys(reference, {"kind", "path"}, location)
        path = _string(reference["path"], f"{location}.path")
        if not _safe_image_path(path):
            raise CanonicalValidationError(f"{location}.path must be under images/")
        if image_paths is not None and path not in image_paths:
            raise CanonicalValidationError(f"{location}.path is not an actual source image")
    else:
        raise CanonicalValidationError(f"{location}.kind must be text or image")


def _referenced_items(
    value: Any,
    location: str,
    *,
    image_paths: set[str] | None,
    raw_line_count: int | None,
) -> None:
    if not isinstance(value, list):
        raise CanonicalValidationError(f"{location} must be an array")
    for index, item in enumerate(value):
        item_location = f"{location}[{index}]"
        entry = _object(item, item_location)
        _exact_keys(entry, {"text", "source_references"}, item_location)
        _string(entry["text"], f"{item_location}.text")
        references = entry["source_references"]
        if not isinstance(references, list) or not references:
            raise CanonicalValidationError(
                f"{item_location}.source_references must be a non-empty array"
            )
        for reference_index, reference in enumerate(references):
            _source_reference(
                reference,
                f"{item_location}.source_references[{reference_index}]",
                image_paths=image_paths,
                raw_line_count=raw_line_count,
            )


def validate_canonical(
    value: Any,
    *,
    image_paths: Sequence[str] | None = None,
    raw_line_count: int | None = None,
) -> dict[str, Any]:
    canonical = _object(value, "canonical")
    _exact_keys(canonical, CANONICAL_KEYS, "canonical")
    if type(canonical["schema_version"]) is not int or canonical["schema_version"] != 1:
        raise CanonicalValidationError("canonical.schema_version must be 1")
    _string(canonical["topic"], "canonical.topic")
    _string(canonical["core_message"], "canonical.core_message")
    allowed_images = set(image_paths) if image_paths is not None else None
    _referenced_items(
        canonical["source_supported_points"],
        "canonical.source_supported_points",
        image_paths=allowed_images,
        raw_line_count=raw_line_count,
    )
    _referenced_items(
        canonical["useful_original_phrases"],
        "canonical.useful_original_phrases",
        image_paths=allowed_images,
        raw_line_count=raw_line_count,
    )
    interpretations = _object(canonical["image_interpretations"], "canonical.image_interpretations")
    if allowed_images is not None and set(interpretations) != allowed_images:
        raise CanonicalValidationError(
            "canonical.image_interpretations keys must exactly match source images"
        )
    for path, interpretation_value in interpretations.items():
        if not isinstance(path, str) or not _safe_image_path(path):
            raise CanonicalValidationError("canonical.image_interpretations has an unsafe path")
        interpretation = _object(
            interpretation_value, f"canonical.image_interpretations[{path!r}]"
        )
        _exact_keys(
            interpretation,
            {"visible_evidence", "source_references"},
            f"canonical.image_interpretations[{path!r}]",
        )
        _string_list(
            interpretation["visible_evidence"],
            f"canonical.image_interpretations[{path!r}].visible_evidence",
        )
        references = interpretation["source_references"]
        expected_reference = [{"kind": "image", "path": path}]
        if references != expected_reference:
            raise CanonicalValidationError(
                f"canonical.image_interpretations[{path!r}].source_references "
                "must contain exactly its own image reference"
            )
        _source_reference(
            references[0],
            f"canonical.image_interpretations[{path!r}].source_references[0]",
            image_paths=allowed_images,
            raw_line_count=raw_line_count,
        )
    _string_list(canonical["unknown_information"], "canonical.unknown_information")
    _string_list(canonical["claims_not_to_invent"], "canonical.claims_not_to_invent")
    return dict(canonical)


def _safe_image_path(path: str) -> bool:
    relative = PurePosixPath(path)
    return (
        not relative.is_absolute()
        and len(relative.parts) >= 2
        and relative.parts[0] == "images"
        and all(part not in {"", ".", ".."} for part in relative.parts)
    )
