from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from personal_content.config import Settings
from personal_content.provider import (
    DeepSeekProvider,
    FakeProvider,
    LocalImage,
    ProviderError,
    parse_json_object,
)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.data


def settings(secret: str = "secret-value") -> Settings:
    return Settings(
        provider="live",
        provider_url="https://api.deepseek.com/chat/completions",
        provider_model="deepseek-v4-flash-vision-exp",
        provider_api_key=secret,
        provider_timeout=60,
        sau_home=r"C:\Users\<user>\tools\social-auto-upload",
        sau_account="main",
        windows_staging_root=r"C:\Users\Public\personal-content-staging",
        powershell="powershell.exe",
    )


def canonical_response(image_path: str = "images/picture.png") -> dict:
    return {
        "schema_version": 1,
        "topic": "原始主题",
        "core_message": "原始内容",
        "source_supported_points": [
            {
                "text": "原始内容",
                "source_references": [{"kind": "text", "path": "raw.md", "line": 1}],
            }
        ],
        "useful_original_phrases": [
            {
                "text": "原始内容",
                "source_references": [{"kind": "text", "path": "raw.md", "line": 1}],
            }
        ],
        "image_interpretations": {
            image_path: {
                "visible_evidence": ["可见图片内容"],
                "source_references": [{"kind": "image", "path": image_path}],
            }
        },
        "unknown_information": [],
        "claims_not_to_invent": ["未提供的事实"],
    }


def chat_response(content: object) -> dict:
    return {"choices": [{"message": {"content": content}}]}


class JsonParserTests(unittest.TestCase):
    def test_accepts_bare_and_complete_fences(self) -> None:
        for text in ('{"a": 1}', '```json\n{"a": 1}\n```', '```\n{"a": 1}\n```'):
            with self.subTest(text=text):
                self.assertEqual(parse_json_object(text), {"a": 1})

    def test_rejects_prose_arrays_malformed_and_multiple_fences(self) -> None:
        values = (
            'before {"a": 1}',
            '{"a": 1} after',
            '[1, 2]',
            '{"a":}',
            '```json\n{"a": 1}\n```\n```json\n{"b": 2}\n```',
        )
        for text in values:
            with self.subTest(text=text), self.assertRaises(ProviderError):
                parse_json_object(text)


class ProviderTests(unittest.TestCase):
    def test_default_live_url_and_model(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            configured = Settings.from_environment()
        self.assertEqual(configured.provider, "live")
        self.assertEqual(
            configured.provider_url, "https://api.deepseek.com/chat/completions"
        )
        self.assertEqual(configured.provider_model, "deepseek-v4-flash-vision-exp")
        self.assertEqual(
            configured.sau_home, r"%USERPROFILE%\tools\social-auto-upload"
        )

    def test_canonical_multimodal_request_shape_and_base64(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            fenced = "```json\n" + json.dumps(canonical_response(), ensure_ascii=False) + "\n```"
            return FakeResponse(chat_response(fenced))

        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "picture.png"
            image_path.write_bytes(b"png-bytes")
            provider = DeepSeekProvider(
                settings(), urlopen=fake_urlopen, sleep=lambda _: None
            )
            result = provider.analyze(
                "原始内容", [LocalImage("images/picture.png", image_path)]
            )
        request = captured["request"]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, settings().provider_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-value")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(payload["model"], "deepseek-v4-flash-vision-exp")
        self.assertIs(payload["stream"], False)
        self.assertNotIn("thinking", payload)
        user_content = payload["messages"][1]["content"]
        self.assertEqual(user_content[0], {"type": "text", "text": "原始内容"})
        self.assertEqual(
            user_content[1],
            {"type": "text", "text": "Source image path (use exactly): images/picture.png"},
        )
        self.assertEqual(
            user_content[2]["image_url"]["url"], "data:image/png;base64,cG5nLWJ5dGVz"
        )
        self.assertIn('"schema_version": 1', payload["messages"][0]["content"])
        self.assertEqual(result["topic"], "原始主题")
        self.assertEqual(captured["timeout"], 60)

    def test_generation_and_editor_do_not_request_thinking(self) -> None:
        payloads = []

        def fake_urlopen(request, timeout):
            payloads.append(json.loads(request.data.decode("utf-8")))
            return FakeResponse(chat_response('{"ok": true}'))

        provider = DeepSeekProvider(settings(), urlopen=fake_urlopen)
        provider.generate_post({"canonical": True}, "personal", "post prompt")
        provider.edit_post({"title": "x"}, ["finding"], "editor prompt")
        self.assertTrue(all("thinking" not in item for item in payloads))
        self.assertTrue(all(item["stream"] is False for item in payloads))

    def test_malformed_chat_response_is_rejected_without_retry(self) -> None:
        calls = 0

        def fake_urlopen(request, timeout):
            nonlocal calls
            calls += 1
            return FakeResponse({"unexpected": []})

        provider = DeepSeekProvider(settings(), urlopen=fake_urlopen)
        with self.assertRaisesRegex(ProviderError, "malformed Chat Completions"):
            provider.generate_post({}, "personal", "prompt")
        self.assertEqual(calls, 1)

    def test_transient_errors_retry_with_fixed_backoff(self) -> None:
        calls = 0
        sleeps = []

        def fake_urlopen(request, timeout):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise urllib.error.HTTPError(
                    request.full_url, 503, "busy", {}, BytesIO(b'{"error":{"code":"busy","message":"later"}}')
                )
            return FakeResponse(chat_response('{"ok": true}'))

        provider = DeepSeekProvider(
            settings(), urlopen=fake_urlopen, sleep=sleeps.append
        )
        self.assertEqual(provider.generate_post({}, "personal", "prompt"), {"ok": True})
        self.assertEqual(calls, 3)
        self.assertEqual(sleeps, [2, 4])

    def test_all_frozen_transient_statuses_have_three_attempt_limit(self) -> None:
        for status in (429, 502, 504):
            calls = 0
            sleeps = []

            def fake_urlopen(request, timeout):
                nonlocal calls
                calls += 1
                raise urllib.error.HTTPError(
                    request.full_url,
                    status,
                    "transient",
                    {},
                    BytesIO(b'{"error":{"message":"busy"}}'),
                )

            provider = DeepSeekProvider(
                settings(), urlopen=fake_urlopen, sleep=sleeps.append
            )
            with self.subTest(status=status), self.assertRaisesRegex(
                ProviderError, f"HTTP {status}"
            ):
                provider.generate_post({}, "personal", "prompt")
            self.assertEqual(calls, 3)
            self.assertEqual(sleeps, [2, 4])

    def test_non_transient_error_has_safe_diagnostics_and_no_retry(self) -> None:
        secret = "highly-secret"
        calls = 0

        def fake_urlopen(request, timeout):
            nonlocal calls
            calls += 1
            body = json.dumps(
                {"error": {"code": "bad_auth", "message": f"Bearer {secret} rejected"}}
            ).encode()
            raise urllib.error.HTTPError(request.full_url, 401, "unauthorized", {}, BytesIO(body))

        provider = DeepSeekProvider(settings(secret), urlopen=fake_urlopen)
        with self.assertRaises(ProviderError) as caught:
            provider.generate_post({}, "personal", "prompt")
        message = str(caught.exception)
        self.assertIn("HTTP 401", message)
        self.assertIn("code=bad_auth", message)
        self.assertIn("message=Bearer [REDACTED]", message)
        self.assertNotIn(secret, message)
        self.assertEqual(calls, 1)

    def test_fake_provider_preserves_source_and_disclaims_image_analysis(self) -> None:
        provider = FakeProvider()
        image = LocalImage("images/a.jpg", Path("unused"))
        result = provider.analyze("原句一\n原句二", [image])
        self.assertEqual(result["topic"], "原句一")
        self.assertEqual(result["source_supported_points"][1]["text"], "原句二")
        self.assertIn(
            "未对该图片进行视觉解读",
            result["image_interpretations"]["images/a.jpg"]["visible_evidence"][0],
        )
        self.assertEqual(result["claims_not_to_invent"], ["不要添加来源中没有的事实。"])
        self.assertEqual(provider.analyze_calls, 1)


if __name__ == "__main__":
    unittest.main()
