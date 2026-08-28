"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Sequence

from .config import Settings, repository_root
from .approval import approve_job
from .jobs import JobError, create_job
from .pipeline import generate_job
from .provider import ProviderError
from .preview import create_preview
from .publish import publish_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="content", description="Source-faithful Xiaohongshu image/text workflow"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="create a content job")
    new_parser.add_argument("name")

    generate_parser = subparsers.add_parser("generate", help="generate canonical content and a post")
    generate_parser.add_argument("name")
    generate_parser.add_argument(
        "--style", required=True, choices=("personal", "knowledge", "concise")
    )

    preview_parser = subparsers.add_parser("preview", help="create a static HTML preview")
    preview_parser.add_argument("name")

    approve_parser = subparsers.add_parser("approve", help="approve the current publishable state")
    approve_parser.add_argument("name")

    publish_parser = subparsers.add_parser("publish", help="publish an approved job")
    publish_parser.add_argument("name")
    publish_parser.add_argument("--dry-run", action="store_true", help="verify and display only")

    subparsers.add_parser("doctor", help="run safe, non-destructive prerequisite checks")
    return parser


def _doctor(settings: Settings) -> int:
    provider_ready = settings.provider == "fake" or bool(settings.provider_api_key)
    powershell_path = shutil.which(settings.powershell)
    print(f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print(f"Provider: {settings.provider}")
    print(f"Provider model: {settings.provider_model}")
    print(f"Provider URL: {settings.provider_url}")
    print(f"Provider credential configured: {'yes' if provider_ready else 'no'}")
    print(f"PowerShell available: {'yes' if powershell_path else 'no'}")
    print(f"SAU home: {settings.sau_home}")
    print(f"SAU account: {settings.sau_account}")
    print("Doctor performs no network request and no publication.")
    return 0


def main(argv: Sequence[str] | None = None, *, root: Path | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    work_root = root if root is not None else repository_root()
    try:
        if args.command == "new":
            created = create_job(work_root, args.name)
            print(f"Created job: {created}")
            return 0
        if args.command == "doctor":
            return _doctor(Settings.from_environment())
        if args.command == "generate":
            canonical, post = generate_job(
                work_root, args.name, args.style, settings=Settings.from_environment()
            )
            print(f"Generated canonical topic: {canonical['topic']}")
            print(f"Generated {post['style']} post: {post['title']}")
            return 0
        if args.command == "preview":
            preview_path = create_preview(work_root, args.name)
            print(f"Created preview: {preview_path}")
            return 0
        if args.command == "approve":
            approval = approve_job(work_root, args.name)
            print(f"Approved hash: {approval['approval_hash']}")
            return 0
        if args.command == "publish":
            plan = publish_job(
                work_root,
                args.name,
                dry_run=args.dry_run,
                settings=Settings.from_environment(),
            )
            print(f"Approval hash: {plan.approval_hash}")
            print(f"Immutable package: {plan.package_path}")
            print(f"Windows staging target: {plan.windows_staging_target}")
            if plan.dry_run:
                print("Dry-run only: PowerShell and SAU were not invoked.")
                print("PowerShell command: " + json.dumps(list(plan.command), ensure_ascii=False))
            else:
                print("Publication command completed successfully.")
            return 0
        parser.error(f"unsupported command: {args.command}")
    except (JobError, ProviderError, ValueError) as exc:
        print(f"content: error: {exc}", file=sys.stderr)
        return 2
