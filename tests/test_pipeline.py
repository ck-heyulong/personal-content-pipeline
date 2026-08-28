import json
from pathlib import Path
import tempfile
import unittest

from personal_content.jobs import create_job
from personal_content.pipeline import generate_job
from personal_content.provider import FakeProvider


class FindingProvider(FakeProvider):
    def generate_post(self, canonical, style, prompt_text):
        post = super().generate_post(canonical, style, prompt_text)
        post["body"] = "值得一提的是，" + post["body"]
        return post


class PipelineTests(unittest.TestCase):
    def make_job(self, root: Path, name: str = "demo") -> Path:
        path = create_job(root, name)
        (path / "raw.md").write_text("保留这句原话\n第二个具体信息", encoding="utf-8")
        (path / "images" / "evidence.png").write_bytes(b"image evidence")
        return path

    def test_three_fake_styles_are_materially_different(self) -> None:
        posts = {}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for style in ("personal", "knowledge", "concise"):
                self.make_job(root, style)
                _, posts[style] = generate_job(root, style, style, provider=FakeProvider())
        self.assertEqual(len({item["title"] for item in posts.values()}), 3)
        self.assertEqual(len({item["body"] for item in posts.values()}), 3)
        self.assertEqual(len({tuple(item["tags"]) for item in posts.values()}), 3)
        self.assertIn("\n\n", posts["personal"]["body"])
        self.assertIn("• ", posts["knowledge"]["body"])
        self.assertIn(" / ", posts["concise"]["body"])

    def test_no_finding_skips_editor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.make_job(root)
            provider = FakeProvider()
            canonical, post = generate_job(root, "demo", "personal", provider=provider)
            self.assertEqual(provider.edit_calls, 0)
            self.assertEqual(provider.generate_calls, 1)
            self.assertEqual(
                json.loads((path / "canonical.json").read_text(encoding="utf-8")), canonical
            )
            self.assertEqual(
                json.loads((path / "xiaohongshu.json").read_text(encoding="utf-8")), post
            )

    def test_finding_allows_exactly_one_editor_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_job(root)
            provider = FindingProvider()
            _, post = generate_job(root, "demo", "personal", provider=provider)
        self.assertEqual(provider.edit_calls, 1)
        self.assertNotIn("值得一提的是", post["body"])

    def test_source_image_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = create_job(root, "linked")
            (path / "raw.md").write_text("原文", encoding="utf-8")
            external = root / "external.png"
            external.write_bytes(b"x")
            (path / "images" / "link.png").symlink_to(external)
            with self.assertRaisesRegex(ValueError, "symlinks"):
                generate_job(root, "linked", "personal", provider=FakeProvider())

    def test_source_wording_is_not_removed_as_formulaic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = create_job(root, "source-phrase")
            (path / "raw.md").write_text("最后一次记录\n保留这句话", encoding="utf-8")
            (path / "images" / "a.png").write_bytes(b"image")
            provider = FakeProvider()
            _, post = generate_job(
                root, "source-phrase", "personal", provider=provider
            )
        self.assertEqual(provider.edit_calls, 0)
        self.assertIn("最后一次记录", post["body"])

    def test_non_image_file_in_images_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = create_job(root, "wrong-type")
            (path / "raw.md").write_text("原文", encoding="utf-8")
            (path / "images" / "notes.txt").write_text("not an image", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-image"):
                generate_job(root, "wrong-type", "personal", provider=FakeProvider())


if __name__ == "__main__":
    unittest.main()
