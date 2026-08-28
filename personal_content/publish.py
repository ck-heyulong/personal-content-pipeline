"""Immutable publication packages and the Windows PowerShell bridge."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat
import subprocess
from typing import Any, Callable, Mapping

from .approval import current_snapshot, verify_approval
from .config import Settings
from .jobs import job_path


MANIFEST_KEYS = {"schema_version", "approval_hash", "title", "body", "tags", "images"}
MANIFEST_IMAGE_KEYS = {"source_path", "package_path", "sha256", "size"}


class PublishError(ValueError):
    """An immutable package or publication operation is unsafe or failed."""


@dataclass(frozen=True)
class PackageInfo:
    path: Path
    manifest: dict[str, Any]
    reused: bool


@dataclass(frozen=True)
class PublishPlan:
    approval_hash: str
    package_path: Path
    windows_staging_target: str
    command: tuple[str, ...]
    dry_run: bool


def _package_image_path(index: int, source_path: str) -> str:
    suffix = Path(source_path).suffix.lower()
    if not suffix or not suffix[1:].isalnum():
        suffix = ".bin"
    return f"images/{index:04d}{suffix}"


def _expected_manifest(approval: Mapping[str, Any]) -> dict[str, Any]:
    publishable = approval["publishable"]
    return {
        "schema_version": 1,
        "approval_hash": approval["approval_hash"],
        "title": publishable["title"],
        "body": publishable["body"],
        "tags": list(publishable["tags"]),
        "images": [
            {
                "source_path": image["path"],
                "package_path": _package_image_path(index, image["path"]),
                "sha256": image["sha256"],
                "size": image["size"],
            }
            for index, image in enumerate(publishable["images"])
        ],
    }


def _safe_relative_path(text: str) -> PurePosixPath:
    relative = PurePosixPath(text)
    if relative.is_absolute() or not relative.parts or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise PublishError(f"unsafe package-relative path: {text}")
    return relative


def _secure_package_file(package: Path, relative_text: str) -> Path:
    relative = _safe_relative_path(relative_text)
    if package.is_symlink():
        raise PublishError("package directory may not be a symlink")
    try:
        package_stat = package.lstat()
    except OSError as exc:
        raise PublishError("package directory is missing") from exc
    if not stat.S_ISDIR(package_stat.st_mode):
        raise PublishError("package path is not a directory")
    current = package
    for index, part in enumerate(relative.parts):
        current = current / part
        try:
            item_stat = current.lstat()
        except OSError as exc:
            raise PublishError(f"required package path is missing: {relative_text}") from exc
        if stat.S_ISLNK(item_stat.st_mode):
            raise PublishError(f"package path contains a symlink: {relative_text}")
        if index < len(relative.parts) - 1 and not stat.S_ISDIR(item_stat.st_mode):
            raise PublishError(f"package intermediate path is not a directory: {relative_text}")
    try:
        resolved_package = package.resolve(strict=True)
        resolved_file = current.resolve(strict=True)
    except OSError as exc:
        raise PublishError(f"package path cannot be resolved safely: {relative_text}") from exc
    if not resolved_file.is_relative_to(resolved_package):
        raise PublishError(f"package path escapes the expected hash directory: {relative_text}")
    final_stat = current.lstat()
    if not stat.S_ISREG(final_stat.st_mode):
        raise PublishError(f"required package path is not a regular file: {relative_text}")
    return current


def _read_regular_file(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise PublishError(f"could not open package file safely: {path.name}") from exc
    try:
        item_stat = os.fstat(descriptor)
        if not stat.S_ISREG(item_stat.st_mode):
            raise PublishError(f"package file is not regular: {path.name}")
        chunks = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    finally:
        os.close(descriptor)


def verify_package(package: Path, approval: Mapping[str, Any]) -> dict[str, Any]:
    expected_hash = approval["approval_hash"]
    if package.name != expected_hash:
        raise PublishError("package directory must use the full approval hash")
    manifest_path = _secure_package_file(package, "manifest.json")
    manifest_bytes = _read_regular_file(manifest_path)
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublishError("package manifest is invalid JSON") from exc
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
        raise PublishError("package manifest does not match its schema")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise PublishError("package manifest schema version is invalid")
    images = manifest.get("images")
    if not isinstance(images, list) or any(
        not isinstance(image, dict) or set(image) != MANIFEST_IMAGE_KEYS for image in images
    ):
        raise PublishError("package manifest images do not match their schema")
    expected_manifest = _expected_manifest(approval)
    if manifest != expected_manifest:
        raise PublishError("package manifest does not match the approved publishable state")
    expected_files = {"manifest.json"}
    for image in manifest["images"]:
        relative_path = image["package_path"]
        image_path = _secure_package_file(package, relative_path)
        image_bytes = _read_regular_file(image_path)
        if len(image_bytes) != image["size"] or hashlib.sha256(image_bytes).hexdigest() != image["sha256"]:
            raise PublishError(f"package image digest mismatch: {relative_path}")
        expected_files.add(relative_path)
    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    for directory, directory_names, file_names in os.walk(package, followlinks=False):
        directory_path = Path(directory)
        for name in directory_names:
            candidate = directory_path / name
            if candidate.is_symlink():
                raise PublishError(f"package contains a symlinked directory: {name}")
            actual_directories.add(candidate.relative_to(package).as_posix())
        for name in file_names:
            candidate = directory_path / name
            if candidate.is_symlink():
                raise PublishError(f"package contains a symlinked file: {name}")
            actual_files.add(candidate.relative_to(package).as_posix())
    expected_directories = {"images"} if manifest["images"] else set()
    if actual_files != expected_files or actual_directories != expected_directories:
        raise PublishError("package contains unexpected or missing paths")
    return manifest


def build_or_reuse_package(root: Path, name: str) -> PackageInfo:
    approval = verify_approval(root, name)
    path = job_path(root, name)
    current_snapshot(path)
    packages_root = root / "publish-packages"
    if packages_root.is_symlink() or (packages_root.exists() and not packages_root.is_dir()):
        raise PublishError("publish-packages root is unsafe")
    packages_root.mkdir(parents=True, exist_ok=True)
    package = packages_root / approval["approval_hash"]
    if package.exists() or package.is_symlink():
        manifest = verify_package(package, approval)
        return PackageInfo(package, manifest, True)
    package.mkdir()
    expected_manifest = _expected_manifest(approval)
    if expected_manifest["images"]:
        (package / "images").mkdir()
    for image in expected_manifest["images"]:
        source_path = path / PurePosixPath(image["source_path"])
        source_bytes = source_path.read_bytes()
        destination = package / PurePosixPath(image["package_path"])
        with destination.open("xb") as output:
            output.write(source_bytes)
    with (package / "manifest.json").open("x", encoding="utf-8") as output:
        json.dump(expected_manifest, output, ensure_ascii=False, indent=2)
        output.write("\n")
    manifest = verify_package(package, approval)
    return PackageInfo(package, manifest, False)


def _wsl_to_windows(path: Path) -> str:
    result = subprocess.run(
        ["wslpath", "-w", str(path)], capture_output=True, text=True, check=False
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise PublishError("wslpath could not convert a repository path for PowerShell")
    return result.stdout.strip()


def construct_windows_command(
    root: Path,
    package: Path,
    settings: Settings,
    *,
    path_converter: Callable[[Path], str] = _wsl_to_windows,
) -> tuple[tuple[str, ...], str]:
    adapter = root / "scripts" / "publish_xiaohongshu.ps1"
    if adapter.is_symlink() or not adapter.is_file():
        raise PublishError("PowerShell publisher adapter is missing or unsafe")
    package_hash = package.name
    staging_target = str(PureWindowsPath(settings.windows_staging_root) / package_hash)
    command = (
        settings.powershell,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        path_converter(adapter),
        "-PackagePath",
        path_converter(package),
        "-StagingRoot",
        settings.windows_staging_root,
        "-SauHome",
        settings.sau_home,
        "-Account",
        settings.sau_account,
    )
    return command, staging_target


def publish_job(
    root: Path,
    name: str,
    *,
    dry_run: bool,
    settings: Settings | None = None,
    path_converter: Callable[[Path], str] = _wsl_to_windows,
    runner: Callable[..., Any] = subprocess.run,
) -> PublishPlan:
    selected_settings = settings or Settings.from_environment()
    package = build_or_reuse_package(root, name)
    command, staging_target = construct_windows_command(
        root, package.path, selected_settings, path_converter=path_converter
    )
    plan = PublishPlan(
        approval_hash=package.manifest["approval_hash"],
        package_path=package.path,
        windows_staging_target=staging_target,
        command=command,
        dry_run=dry_run,
    )
    if dry_run:
        return plan
    job = job_path(root, name)
    result_path = job / "publish-result.json"
    if result_path.is_symlink() or (result_path.exists() and not result_path.is_file()):
        raise PublishError("publish-result.json is unsafe")
    result = runner(list(command), check=False)
    if result.returncode != 0:
        raise PublishError(f"PowerShell/SAU publication failed with exit code {result.returncode}")
    result_path.write_text(
        json.dumps(
            {"schema_version": 1, "status": "published", "approval_hash": plan.approval_hash},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return plan
