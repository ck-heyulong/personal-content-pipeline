from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from personal_content.cli import main


class CliTests(unittest.TestCase):
    def invoke(self, args: list[str], root: Path) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(args, root=root)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_new_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status, output, error = self.invoke(["new", "demo"], root)
            self.assertEqual(status, 0)
            self.assertIn("Created job", output)
            self.assertEqual(error, "")
            self.assertTrue((root / "jobs" / "demo" / "raw.md").is_file())

    def test_bad_name_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status, output, error = self.invoke(["new", "../bad"], Path(directory))
            self.assertEqual(status, 2)
            self.assertEqual(output, "")
            self.assertIn("job name", error)

    def test_doctor_does_not_print_api_key(self) -> None:
        secret = "do-not-print-this-key"
        environment = {
            "CONTENT_PROVIDER": "live",
            "CONTENT_PROVIDER_API_KEY": secret,
            "CONTENT_PROVIDER_TIMEOUT": "60",
        }
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, environment, clear=True
        ):
            status, output, error = self.invoke(["doctor"], Path(directory))
        self.assertEqual(status, 0)
        self.assertIn("credential configured: yes", output)
        self.assertNotIn(secret, output + error)
        self.assertIn("no publication", output)

    def test_generate_missing_job_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status, _, error = self.invoke(
                ["generate", "demo", "--style", "personal"], Path(directory)
            )
        self.assertEqual(status, 2)
        self.assertIn("job does not exist", error)


if __name__ == "__main__":
    unittest.main()
