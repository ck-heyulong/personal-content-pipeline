"""Explicit approval bound to publishable content and exact image bytes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .jobs import job_path
from .pipeline import source_images
from .review import validate_post


APPROVAL_KEYS = {"schema_version", "algorithm", "approval_hash", "publishable"}
PUBLISHABLE_KEYS = {"title", "body", "tags", "images"}


class ApprovalError(ValueError):
    """Approval is missing, malformed, or stale."""


def _load_json_file(path: Path, label: str) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ApprovalError(f"{label} is missing or unsafe")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApprovalError(f"{label} is not valid JSON") from exc


def _feed(hasher: Any, label: str, value: bytes) -> None:
    label_bytes = label.encode("utf-8")
    hasher.update(len(label_bytes).to_bytes(8, "big"))
    hasher.update(label_bytes)
    hasher.update(len(value).to_bytes(8, "big"))
    hasher.update(value)


def _snapshot(path: Path, post: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    available_images = source_images(path)
    validated = validate_post(
        post, available_images=[image.relative_path for image in available_images]
    )
    by_relative_path = {image.relative_path: image.path for image in available_images}
    hasher = hashlib.sha256()
    _feed(hasher, "format", b"personal-content-approval-v1")
    _feed(hasher, "title", validated["title"].encode("utf-8"))
    _feed(hasher, "body", validated["body"].encode("utf-8"))
    for index, tag in enumerate(validated["tags"]):
        _feed(hasher, f"tag:{index}", tag.encode("utf-8"))
    image_metadata = []
    for index, relative_path in enumerate(validated["images"]):
        image_path = by_relative_path[relative_path]
        image_bytes = image_path.read_bytes()
        digest = hashlib.sha256(image_bytes).hexdigest()
        _feed(hasher, f"image-path:{index}", relative_path.encode("utf-8"))
        _feed(hasher, f"image-bytes:{index}", image_bytes)
        image_metadata.append(
            {"path": relative_path, "sha256": digest, "size": len(image_bytes)}
        )
    publishable = {
        "title": validated["title"],
        "body": validated["body"],
        "tags": list(validated["tags"]),
        "images": image_metadata,
    }
    return hasher.hexdigest(), publishable


def current_snapshot(path: Path) -> tuple[dict[str, Any], str, dict[str, Any]]:
    post = _load_json_file(path / "xiaohongshu.json", "xiaohongshu.json")
    digest, publishable = _snapshot(path, post)
    return post, digest, publishable


def approve_job(root: Path, name: str) -> dict[str, Any]:
    path = job_path(root, name)
    _, digest, publishable = current_snapshot(path)
    approval = {
        "schema_version": 1,
        "algorithm": "sha256",
        "approval_hash": digest,
        "publishable": publishable,
    }
    approval_path = path / "approval.json"
    if approval_path.is_symlink() or (approval_path.exists() and not approval_path.is_file()):
        raise ApprovalError("approval.json is unsafe")
    approval_path.write_text(
        json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return approval


def verify_approval(root: Path, name: str) -> dict[str, Any]:
    path = job_path(root, name)
    approval = _load_json_file(path / "approval.json", "approval.json")
    if not isinstance(approval, dict) or set(approval) != APPROVAL_KEYS:
        raise ApprovalError("approval.json does not match the approval schema")
    if (
        type(approval["schema_version"]) is not int
        or approval["schema_version"] != 1
        or approval["algorithm"] != "sha256"
    ):
        raise ApprovalError("approval.json uses an unsupported format")
    if not isinstance(approval["publishable"], dict) or set(approval["publishable"]) != PUBLISHABLE_KEYS:
        raise ApprovalError("approval publishable snapshot is malformed")
    _, digest, publishable = current_snapshot(path)
    if approval["approval_hash"] != digest or approval["publishable"] != publishable:
        raise ApprovalError("approval is stale; content or image data changed")
    return approval


def approval_status(root: Path, name: str) -> str:
    try:
        approval = verify_approval(root, name)
    except ApprovalError as exc:
        return f"Not approved: {exc}"
    return f"Approved: {approval['approval_hash']}"
