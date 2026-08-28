import unittest

from personal_content.review import (
    PostValidationError,
    apply_editor_replacements,
    naturalness_findings,
    validate_post,
)


def post() -> dict:
    return {
        "schema_version": 1,
        "style": "personal",
        "title": "一段真实记录",
        "body": "值得一提的是，这里保留原句。后面还有具体内容。",
        "tags": ["记录"],
        "images": ["images/a.png"],
    }


class ReviewTests(unittest.TestCase):
    def test_post_schema_and_images_are_strict(self) -> None:
        self.assertEqual(
            validate_post(post(), expected_style="personal", available_images=["images/a.png"])[
                "title"
            ],
            "一段真实记录",
        )
        invalid = post()
        invalid["summary"] = "drift"
        with self.assertRaises(PostValidationError):
            validate_post(invalid)
        wrong_images = post()
        wrong_images["images"] = ["images/other.png"]
        with self.assertRaises(PostValidationError):
            validate_post(wrong_images, available_images=["images/a.png"])

    def test_deterministic_findings(self) -> None:
        findings = naturalness_findings(post())
        self.assertEqual(findings, ["remove formulaic phrase: 值得一提的是"])

    def test_exact_local_replacement(self) -> None:
        edited = apply_editor_replacements(
            post(),
            {
                "replacements": [
                    {"field": "body", "find": "值得一提的是，", "replace": ""}
                ]
            },
        )
        self.assertEqual(edited["body"], "这里保留原句。后面还有具体内容。")
        self.assertEqual(edited["images"], post()["images"])

    def test_ambiguous_whole_field_and_expansive_edits_are_rejected(self) -> None:
        cases = (
            {"field": "body", "find": post()["body"], "replace": "重写"},
            {"field": "body", "find": "。", "replace": "x"},
            {"field": "body", "find": "值得一提的是", "replace": "x" * 60},
        )
        for replacement in cases:
            with self.subTest(replacement=replacement), self.assertRaises(PostValidationError):
                apply_editor_replacements(post(), {"replacements": [replacement]})

    def test_versions_paths_and_source_wording_are_protected(self) -> None:
        float_version = post()
        float_version["schema_version"] = 1.0
        with self.assertRaises(PostValidationError):
            validate_post(float_version)
        unsafe_path = post()
        unsafe_path["images"] = ["images/../a.png"]
        with self.assertRaises(PostValidationError):
            validate_post(unsafe_path)
        self.assertEqual(
            naturalness_findings(post(), protected_texts=["值得一提的是"]), []
        )
        with self.assertRaisesRegex(PostValidationError, "source wording"):
            apply_editor_replacements(
                post(),
                {
                    "replacements": [
                        {"field": "body", "find": "值得一提的是，", "replace": ""}
                    ]
                },
                protected_texts=["值得一提的是，"],
            )


if __name__ == "__main__":
    unittest.main()
