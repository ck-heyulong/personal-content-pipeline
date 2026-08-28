import copy
import json
from pathlib import Path
import tempfile
import unittest

from personal_content.approval import ApprovalError, approve_job, verify_approval
from personal_content.jobs import create_job


def write_post(path: Path, post: dict) -> None:
    (path / "xiaohongshu.json").write_text(
        json.dumps(post, ensure_ascii=False), encoding="utf-8"
    )


def base_post() -> dict:
    return {
        "schema_version": 1,
        "style": "personal",
        "title": "原始标题",
        "body": "原始正文",
        "tags": ["标签甲", "标签乙"],
        "images": ["images/a.png", "images/b.png"],
    }


class ApprovalTests(unittest.TestCase):
    def make_approved_job(self, root: Path) -> Path:
        path = create_job(root, "demo")
        (path / "images" / "a.png").write_bytes(b"a bytes")
        (path / "images" / "b.png").write_bytes(b"b bytes")
        write_post(path, base_post())
        approve_job(root, "demo")
        return path

    def test_valid_approval_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_approved_job(root)
            first = verify_approval(root, "demo")
            second = approve_job(root, "demo")
        self.assertEqual(first, second)
        self.assertEqual(len(first["approval_hash"]), 64)
        self.assertEqual(first["publishable"]["images"][0]["path"], "images/a.png")

    def test_every_required_mutation_invalidates_approval(self) -> None:
        mutations = {
            "title": lambda value: value.update(title="改过标题"),
            "body": lambda value: value.update(body="改过正文"),
            "tags": lambda value: value.update(tags=["标签甲", "新增"]),
            "tag order": lambda value: value.update(tags=list(reversed(value["tags"]))),
            "image order": lambda value: value.update(images=list(reversed(value["images"]))),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = self.make_approved_job(root)
                changed = copy.deepcopy(base_post())
                mutate(changed)
                write_post(path, changed)
                with self.assertRaisesRegex(ApprovalError, "stale"):
                    verify_approval(root, "demo")

    def test_image_byte_mutation_invalidates_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.make_approved_job(root)
            (path / "images" / "a.png").write_bytes(b"changed bytes")
            with self.assertRaisesRegex(ApprovalError, "stale"):
                verify_approval(root, "demo")

    def test_same_byte_image_identity_mutation_invalidates_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.make_approved_job(root)
            (path / "images" / "a.png").rename(path / "images" / "renamed.png")
            changed = base_post()
            changed["images"][0] = "images/renamed.png"
            write_post(path, changed)
            with self.assertRaisesRegex(ApprovalError, "stale"):
                verify_approval(root, "demo")

    def test_symlinked_approval_or_source_image_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.make_approved_job(root)
            approval = path / "approval.json"
            external = root / "outside.json"
            approval.rename(external)
            approval.symlink_to(external)
            with self.assertRaisesRegex(ApprovalError, "unsafe"):
                verify_approval(root, "demo")


if __name__ == "__main__":
    unittest.main()
