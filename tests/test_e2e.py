from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from personal_content.cli import main


class OfflineEndToEndTests(unittest.TestCase):
    def invoke(self, root: Path, args: list[str]) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main(args, root=root)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_cli_workflow_through_approved_dry_run_is_offline(self) -> None:
        environment = {
            "CONTENT_PROVIDER": "fake",
            "CONTENT_PROVIDER_TIMEOUT": "60",
            "CONTENT_POWERSHELL": "powershell.exe",
        }
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, environment, clear=False
        ):
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "scripts" / "publish_xiaohongshu.ps1").write_text(
                "# test adapter; never executed", encoding="utf-8"
            )
            self.assertEqual(self.invoke(root, ["new", "offline"])[0], 0)
            job = root / "jobs" / "offline"
            (job / "raw.md").write_text("保留原句\n只使用来源中的事实", encoding="utf-8")
            (job / "images" / "source.png").write_bytes(b"offline image")

            status, output, error = self.invoke(
                root, ["generate", "offline", "--style", "knowledge"]
            )
            self.assertEqual((status, error), (0, ""))
            self.assertIn("Generated knowledge post", output)
            canonical = json.loads((job / "canonical.json").read_text(encoding="utf-8"))
            self.assertEqual(canonical["source_supported_points"][0]["text"], "保留原句")
            self.assertIn(
                "未对该图片进行视觉解读",
                canonical["image_interpretations"]["images/source.png"][
                    "visible_evidence"
                ][0],
            )

            self.assertEqual(self.invoke(root, ["preview", "offline"])[0], 0)
            self.assertIn("Not approved", (job / "preview.html").read_text(encoding="utf-8"))
            self.assertEqual(self.invoke(root, ["approve", "offline"])[0], 0)
            self.assertEqual(self.invoke(root, ["preview", "offline"])[0], 0)
            self.assertIn("Approved:", (job / "preview.html").read_text(encoding="utf-8"))

            status, output, error = self.invoke(
                root, ["publish", "offline", "--dry-run"]
            )
            self.assertEqual((status, error), (0, ""))
            self.assertIn("PowerShell and SAU were not invoked", output)
            approval_hash = json.loads(
                (job / "approval.json").read_text(encoding="utf-8")
            )["approval_hash"]
            package = root / "publish-packages" / approval_hash
            self.assertTrue((package / "manifest.json").is_file())
            self.assertFalse((job / "publish-result.json").exists())


if __name__ == "__main__":
    unittest.main()
