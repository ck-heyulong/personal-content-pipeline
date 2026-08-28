from pathlib import Path
import tempfile
import unittest

from personal_content.jobs import JobError, create_job, job_path, validate_job_name


class JobTests(unittest.TestCase):
    def test_new_job_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = create_job(root, "first-note")
            self.assertEqual(path, root / "jobs" / "first-note")
            self.assertEqual((path / "raw.md").read_text(encoding="utf-8"), "")
            self.assertTrue((path / "images").is_dir())
            self.assertEqual(sorted(item.name for item in path.iterdir()), ["images", "raw.md"])

    def test_duplicate_job_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_job(root, "duplicate")
            with self.assertRaisesRegex(JobError, "already exists"):
                create_job(root, "duplicate")

    def test_unsafe_names_are_rejected(self) -> None:
        for name in ("", "../escape", "/absolute", "two/parts", ".hidden", "空 格"):
            with self.subTest(name=name), self.assertRaises(JobError):
                validate_job_name(name)

    def test_required_layout_and_job_symlinks_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            (root / "jobs").mkdir()
            (root / "jobs" / "linked").symlink_to(target, target_is_directory=True)
            with self.assertRaises(JobError):
                job_path(root, "linked")

    def test_symlinked_jobs_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            external = root / "external"
            external.mkdir()
            (root / "jobs").symlink_to(external, target_is_directory=True)
            with self.assertRaisesRegex(JobError, "jobs directory is unsafe"):
                create_job(root, "escape")


if __name__ == "__main__":
    unittest.main()
