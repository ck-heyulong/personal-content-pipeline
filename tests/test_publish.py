import json
from pathlib import Path
import tempfile
import unittest

from personal_content.approval import approve_job
from personal_content.config import Settings
from personal_content.jobs import create_job
from personal_content.publish import (
    PublishError,
    build_or_reuse_package,
    construct_windows_command,
    publish_job,
    verify_package,
)


def test_settings() -> Settings:
    return Settings(
        provider="fake",
        provider_url="https://api.deepseek.com/chat/completions",
        provider_model="deepseek-v4-flash-vision-exp",
        provider_api_key=None,
        provider_timeout=60,
        sau_home=r"C:\Users\<user>\tools\social-auto-upload",
        sau_account="main",
        windows_staging_root=r"C:\Users\Public\personal-content-staging",
        powershell="powershell.exe",
    )


class Result:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


class PublishTests(unittest.TestCase):
    def make_approved(self, root: Path) -> Path:
        path = create_job(root, "demo")
        (path / "raw.md").write_text("真实原文", encoding="utf-8")
        (path / "images" / "a.png").write_bytes(b"same approved bytes")
        post = {
            "schema_version": 1,
            "style": "personal",
            "title": "真实标题",
            "body": "真实正文",
            "tags": ["记录", "原文"],
            "images": ["images/a.png"],
        }
        (path / "xiaohongshu.json").write_text(
            json.dumps(post, ensure_ascii=False), encoding="utf-8"
        )
        approve_job(root, "demo")
        return path

    def build(self, root: Path):
        self.make_approved(root)
        info = build_or_reuse_package(root, "demo")
        approval = approve_job(root, "demo")
        return info, approval

    def test_valid_immutable_package_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            info, _ = self.build(root)
            reused = build_or_reuse_package(root, "demo")
        self.assertFalse(info.reused)
        self.assertTrue(reused.reused)
        self.assertEqual(reused.path.name, reused.manifest["approval_hash"])
        self.assertEqual(len(reused.path.name), 64)

    def test_digest_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            info, approval = self.build(root)
            (info.path / "images" / "0000.png").write_bytes(b"changed")
            with self.assertRaisesRegex(PublishError, "digest mismatch"):
                verify_package(info.path, approval)

    def test_non_regular_required_package_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            info, approval = self.build(root)
            image = info.path / "images" / "0000.png"
            image.unlink()
            image.mkdir()
            with self.assertRaisesRegex(PublishError, "not a regular file"):
                verify_package(info.path, approval)

    def test_manifest_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            info, approval = self.build(root)
            manifest = info.path / "manifest.json"
            external = root / "manifest.json"
            manifest.rename(external)
            manifest.symlink_to(external)
            with self.assertRaisesRegex(PublishError, "symlink"):
                verify_package(info.path, approval)

    def test_intermediate_directory_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            info, approval = self.build(root)
            images = info.path / "images"
            external = root / "outside-images"
            images.rename(external)
            images.symlink_to(external, target_is_directory=True)
            with self.assertRaisesRegex(PublishError, "symlink"):
                verify_package(info.path, approval)

    def test_external_same_byte_file_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            info, approval = self.build(root)
            image = info.path / "images" / "0000.png"
            external = root / "same.png"
            external.write_bytes(image.read_bytes())
            image.unlink()
            image.symlink_to(external)
            with self.assertRaisesRegex(PublishError, "symlink"):
                verify_package(info.path, approval)

    def test_manifest_escape_path_is_rejected_even_with_same_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            info, approval = self.build(root)
            external = root / "same.png"
            external.write_bytes(b"same approved bytes")
            manifest_path = info.path / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["images"][0]["package_path"] = "../same.png"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(PublishError, "approved publishable state"):
                verify_package(info.path, approval)

    def test_dry_run_never_invokes_runner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_approved(root)
            (root / "scripts").mkdir()
            (root / "scripts" / "publish_xiaohongshu.ps1").write_text("# adapter")
            calls = []
            plan = publish_job(
                root,
                "demo",
                dry_run=True,
                settings=test_settings(),
                path_converter=lambda path: "WIN:" + path.name,
                runner=lambda *args, **kwargs: calls.append((args, kwargs)),
            )
        self.assertEqual(calls, [])
        self.assertTrue(plan.dry_run)
        self.assertTrue(plan.windows_staging_target.endswith(plan.approval_hash))
        self.assertIn("-File", plan.command)

    def test_windows_command_construction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "scripts" / "publish_xiaohongshu.ps1").write_text("# adapter")
            package = root / ("a" * 64)
            package.mkdir()
            command, staging = construct_windows_command(
                root,
                package,
                test_settings(),
                path_converter=lambda path: f"C:\\converted\\{path.name}",
            )
        self.assertEqual(command[0], "powershell.exe")
        self.assertEqual(command[command.index("-Account") + 1], "main")
        self.assertEqual(
            command[command.index("-SauHome") + 1],
            r"C:\Users\<user>\tools\social-auto-upload",
        )
        self.assertEqual(command[command.index("-PackagePath") + 1], "C:\\converted\\" + "a" * 64)
        self.assertEqual(staging, r"C:\Users\Public\personal-content-staging" + "\\" + "a" * 64)

    def test_failed_real_command_is_never_recorded_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = self.make_approved(root)
            (root / "scripts").mkdir()
            (root / "scripts" / "publish_xiaohongshu.ps1").write_text("# adapter")
            with self.assertRaisesRegex(PublishError, "exit code 7"):
                publish_job(
                    root,
                    "demo",
                    dry_run=False,
                    settings=test_settings(),
                    path_converter=lambda path: "WIN:" + path.name,
                    runner=lambda *args, **kwargs: Result(7),
                )
            self.assertFalse((job / "publish-result.json").exists())

    def test_unsafe_result_path_blocks_external_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = self.make_approved(root)
            (root / "scripts").mkdir()
            (root / "scripts" / "publish_xiaohongshu.ps1").write_text("# adapter")
            external = root / "external-result.json"
            external.write_text("outside", encoding="utf-8")
            (job / "publish-result.json").symlink_to(external)
            calls = []
            with self.assertRaisesRegex(PublishError, "publish-result.json is unsafe"):
                publish_job(
                    root,
                    "demo",
                    dry_run=False,
                    settings=test_settings(),
                    path_converter=lambda path: "WIN:" + path.name,
                    runner=lambda *args, **kwargs: calls.append((args, kwargs)),
                )
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
