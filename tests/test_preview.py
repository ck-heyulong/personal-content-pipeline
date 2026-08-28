from pathlib import Path
from html import escape
import tempfile
import unittest

from personal_content.approval import approve_job
from personal_content.jobs import create_job
from personal_content.pipeline import generate_job
from personal_content.preview import create_preview
from personal_content.provider import FakeProvider


class PreviewTests(unittest.TestCase):
    def test_preview_contains_escaped_sources_draft_images_and_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = create_job(root, "preview")
            (path / "raw.md").write_text("原文 <script>alert(1)</script>", encoding="utf-8")
            (path / "images" / "a&b.png").write_bytes(b"image")
            _, post = generate_job(root, "preview", "personal", provider=FakeProvider())
            approve_job(root, "preview")
            preview_path = create_preview(root, "preview")
            document = preview_path.read_text(encoding="utf-8")
        self.assertIn("Raw source text", document)
        self.assertIn("Canonical interpretation", document)
        self.assertIn("Xiaohongshu draft", document)
        self.assertIn("Ordered images", document)
        self.assertIn("Approved:", document)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", document)
        self.assertNotIn("<script>alert(1)</script>", document)
        self.assertIn('src="images/a&amp;b.png"', document)
        self.assertIn(escape(post["body"]), document)

    def test_preview_reports_missing_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = create_job(root, "unapproved")
            (path / "raw.md").write_text("原文", encoding="utf-8")
            generate_job(root, "unapproved", "concise", provider=FakeProvider())
            document = create_preview(root, "unapproved").read_text(encoding="utf-8")
        self.assertIn("Not approved:", document)


if __name__ == "__main__":
    unittest.main()
