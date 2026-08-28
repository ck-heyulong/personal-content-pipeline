import copy
import unittest

from personal_content.canonical import CanonicalValidationError, validate_canonical


def valid_canonical() -> dict:
    return {
        "schema_version": 1,
        "topic": "在 WSL 里整理内容",
        "core_message": "保留原文，先确认事实。",
        "source_supported_points": [
            {
                "text": "保留原文",
                "source_references": [{"kind": "text", "path": "raw.md", "line": 1}],
            }
        ],
        "useful_original_phrases": [
            {
                "text": "先确认事实",
                "source_references": [{"kind": "text", "path": "raw.md", "line": 2}],
            }
        ],
        "image_interpretations": {
            "images/screen.png": {
                "visible_evidence": ["画面中可见终端窗口"],
                "source_references": [{"kind": "image", "path": "images/screen.png"}],
            }
        },
        "unknown_information": ["未提供具体日期"],
        "claims_not_to_invent": ["不要补充使用时长"],
    }


class CanonicalTests(unittest.TestCase):
    def test_valid_exact_schema(self) -> None:
        result = validate_canonical(
            valid_canonical(), image_paths=["images/screen.png"], raw_line_count=2
        )
        self.assertEqual(result["topic"], "在 WSL 里整理内容")

    def test_extra_or_missing_keys_are_rejected(self) -> None:
        for mutation in ("extra", "missing"):
            value = valid_canonical()
            if mutation == "extra":
                value["summary"] = "schema drift"
            else:
                del value["core_message"]
            with self.subTest(mutation=mutation), self.assertRaises(CanonicalValidationError):
                validate_canonical(value)

    def test_invalid_source_references_are_rejected(self) -> None:
        mutations = []
        wrong_line = valid_canonical()
        wrong_line["source_supported_points"][0]["source_references"][0]["line"] = 0
        mutations.append(wrong_line)
        unknown_image = valid_canonical()
        unknown_image["image_interpretations"]["images/screen.png"]["source_references"][0][
            "path"
        ] = "images/other.png"
        mutations.append(unknown_image)
        wrong_text_path = valid_canonical()
        wrong_text_path["useful_original_phrases"][0]["source_references"][0]["path"] = (
            "notes.md"
        )
        mutations.append(wrong_text_path)
        for value in mutations:
            with self.subTest(value=value), self.assertRaises(CanonicalValidationError):
                validate_canonical(
                    value, image_paths=["images/screen.png"], raw_line_count=2
                )

    def test_actual_images_must_match_exactly(self) -> None:
        value = valid_canonical()
        with self.assertRaisesRegex(CanonicalValidationError, "exactly match"):
            validate_canonical(
                value,
                image_paths=["images/screen.png", "images/second.jpg"],
                raw_line_count=2,
            )

    def test_nested_schema_drift_is_rejected(self) -> None:
        value = copy.deepcopy(valid_canonical())
        value["source_supported_points"][0]["confidence"] = 0.8
        with self.assertRaises(CanonicalValidationError):
            validate_canonical(value)

    def test_version_type_and_image_paths_are_strict(self) -> None:
        float_version = valid_canonical()
        float_version["schema_version"] = 1.0
        with self.assertRaises(CanonicalValidationError):
            validate_canonical(float_version)
        unsafe = valid_canonical()
        interpretation = unsafe["image_interpretations"].pop("images/screen.png")
        interpretation["source_references"][0]["path"] = "images/../screen.png"
        unsafe["image_interpretations"]["images/../screen.png"] = interpretation
        with self.assertRaises(CanonicalValidationError):
            validate_canonical(unsafe)


if __name__ == "__main__":
    unittest.main()
