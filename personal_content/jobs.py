"""Safe on-disk job operations."""

from __future__ import annotations

import re
from pathlib import Path


SAFE_JOB_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


class JobError(ValueError):
    """A job name or layout is invalid."""


def validate_job_name(name: str) -> str:
    if not SAFE_JOB_NAME.fullmatch(name) or name in {".", ".."}:
        raise JobError(
            "job name must be 1-64 ASCII letters, digits, '.', '_' or '-', "
            "start with a letter or digit, and be one filesystem component"
        )
    return name


def jobs_root(root: Path) -> Path:
    return root / "jobs"


def job_path(root: Path, name: str, *, must_exist: bool = True) -> Path:
    validate_job_name(name)
    parent = jobs_root(root)
    if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
        raise JobError("jobs directory is unsafe")
    path = parent / name
    if must_exist:
        if not path.is_dir() or path.is_symlink():
            raise JobError(f"job does not exist: {name}")
        raw = path / "raw.md"
        images = path / "images"
        if not raw.is_file() or raw.is_symlink():
            raise JobError(f"job raw.md is missing or unsafe: {name}")
        if not images.is_dir() or images.is_symlink():
            raise JobError(f"job images directory is missing or unsafe: {name}")
    return path


def create_job(root: Path, name: str) -> Path:
    path = job_path(root, name, must_exist=False)
    if path.exists() or path.is_symlink():
        raise JobError(f"job already exists: {name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir()
    (path / "raw.md").write_text("", encoding="utf-8")
    (path / "images").mkdir()
    return path
