"""Fixed DeepSeek Vision provider and deterministic fake."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import mimetypes
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping, Sequence
import urllib.error
import urllib.request

from .canonical import CANONICAL_SCHEMA_TEMPLATE, validate_canonical
from .config import Settings


TRANSIENT_HTTP_STATUSES = {429, 502, 503, 504}
BACKOFF_SECONDS = (2, 4)
FENCED_JSON = re.compile(r"\A```(?:json)?[ \t]*\r?\n(?P<body>[\s\S]*?)\r?\n```[ \t]*\Z")


class ProviderError(RuntimeError):
    """A secret-free provider failure."""


@dataclass(frozen=True)
class LocalImage:
    relative_path: str
    path: Path


def parse_json_object(response_text: str) -> dict[str, Any]:
    trimmed = response_text.strip()
    match = FENCED_JSON.fullmatch(trimmed)
    candidate = match.group("body") if match else trimmed
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"provider response is not a valid JSON object: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ProviderError("provider response must be a JSON object")
    return value


def load_prompt(name: str, *, schema: Mapping[str, Any] | None = None) -> str:
    path = Path(__file__).parent / "prompts" / name
    text = path.read_text(encoding="utf-8")
    if schema is not None:
        text = text.replace(
            "{{CANONICAL_SCHEMA}}",
            json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=False),
        )
    return text


def _redact(text: str, secret: str | None) -> str:
    sanitized = text.replace(secret, "[REDACTED]") if secret else text
    return re.sub(r"(?i)Bearer\s+[^\s\"']+", "Bearer [REDACTED]", sanitized)[:500]


class DeepSeekProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        urlopen: Callable[..., Any] = urllib.request.urlopen,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not settings.provider_api_key:
            raise ProviderError("CONTENT_PROVIDER_API_KEY is required for the live provider")
        self.settings = settings
        self._urlopen = urlopen
        self._sleep = sleep

    def analyze(self, raw_text: str, images: Sequence[LocalImage]) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "text", "text": raw_text}]
        for image in images:
            if image.path.is_symlink() or not image.path.is_file():
                raise ProviderError(f"source image is missing or unsafe: {image.relative_path}")
            mime_type = mimetypes.guess_type(image.path.name)[0] or "application/octet-stream"
            encoded = base64.b64encode(image.path.read_bytes()).decode("ascii")
            content.append(
                {
                    "type": "text",
                    "text": f"Source image path (use exactly): {image.relative_path}",
                }
            )
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                }
            )
        response = self._chat(
            messages=[
                {
                    "role": "system",
                    "content": load_prompt("canonical.md", schema=CANONICAL_SCHEMA_TEMPLATE),
                },
                {"role": "user", "content": content},
            ],
        )
        return validate_canonical(
            response,
            image_paths=[image.relative_path for image in images],
            raw_line_count=len(raw_text.splitlines()),
        )

    def generate_post(
        self, canonical: Mapping[str, Any], style: str, prompt_text: str
    ) -> dict[str, Any]:
        return self._chat(
            messages=[
                {"role": "system", "content": prompt_text},
                {
                    "role": "user",
                    "content": json.dumps(canonical, ensure_ascii=False, sort_keys=True),
                },
            ],
        )

    def edit_post(
        self, post: Mapping[str, Any], findings: Sequence[str], prompt_text: str
    ) -> dict[str, Any]:
        return self._chat(
            messages=[
                {"role": "system", "content": prompt_text},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"post": post, "findings": list(findings)},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
        )

    def _chat(self, *, messages: list[dict[str, Any]]) -> dict[str, Any]:
        payload = json.dumps(
            {
                "model": self.settings.provider_model,
                "messages": messages,
                "stream": False,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            self.settings.provider_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.settings.provider_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        for attempt in range(3):
            try:
                with self._urlopen(request, timeout=self.settings.provider_timeout) as response:
                    response_bytes = response.read()
                return self._parse_chat_response(response_bytes)
            except urllib.error.HTTPError as exc:
                detail = self._http_error_detail(exc)
                if exc.code in TRANSIENT_HTTP_STATUSES and attempt < 2:
                    self._sleep(BACKOFF_SECONDS[attempt])
                    continue
                raise ProviderError(detail) from exc
            except urllib.error.URLError as exc:
                reason = _redact(str(exc.reason), self.settings.provider_api_key)
                raise ProviderError(f"provider connection failed: {reason}") from exc
        raise AssertionError("unreachable retry state")

    def _parse_chat_response(self, response_bytes: bytes) -> dict[str, Any]:
        try:
            envelope = json.loads(response_bytes.decode("utf-8"))
            content = envelope["choices"][0]["message"]["content"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("provider returned a malformed Chat Completions response") from exc
        if not isinstance(content, str):
            raise ProviderError("provider message content must be a string")
        return parse_json_object(content)

    def _http_error_detail(self, error: urllib.error.HTTPError) -> str:
        code: Any = None
        message: Any = None
        try:
            body = error.read(64 * 1024)
            payload = json.loads(body.decode("utf-8"))
            error_object = payload.get("error", payload) if isinstance(payload, dict) else {}
            if isinstance(error_object, dict):
                code = error_object.get("code")
                message = error_object.get("message")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
        parts = [f"provider HTTP {error.code}"]
        if code is not None:
            parts.append(f"code={_redact(str(code), self.settings.provider_api_key)}")
        if message is not None:
            parts.append(f"message={_redact(str(message), self.settings.provider_api_key)}")
        return "; ".join(parts)


class FakeProvider:
    """Deterministic, offline provider used for development and tests."""

    def __init__(self) -> None:
        self.analyze_calls = 0
        self.generate_calls = 0
        self.edit_calls = 0

    def analyze(self, raw_text: str, images: Sequence[LocalImage]) -> dict[str, Any]:
        self.analyze_calls += 1
        lines = [(index, line.strip()) for index, line in enumerate(raw_text.splitlines(), 1)]
        meaningful = [(index, line) for index, line in lines if line]
        if not meaningful:
            raise ProviderError("raw.md must contain source text")
        first_line_number, first_line = meaningful[0]
        is_chinese = bool(re.search(r"[\u3400-\u9fff]", raw_text))
        image_disclaimer = (
            "FakeProvider 未对该图片进行视觉解读。"
            if is_chinese
            else "FakeProvider did not visually interpret this image."
        )
        claim_guard = (
            "不要添加来源中没有的事实。"
            if is_chinese
            else "Do not add claims absent from the supplied sources."
        )
        referenced = [
            {
                "text": line,
                "source_references": [{"kind": "text", "path": "raw.md", "line": index}],
            }
            for index, line in meaningful
        ]
        canonical: dict[str, Any] = {
            "schema_version": 1,
            "topic": first_line,
            "core_message": "\n".join(line for _, line in meaningful),
            "source_supported_points": referenced,
            "useful_original_phrases": [
                {
                    "text": first_line,
                    "source_references": [
                        {"kind": "text", "path": "raw.md", "line": first_line_number}
                    ],
                }
            ],
            "image_interpretations": {
                image.relative_path: {
                    "visible_evidence": [image_disclaimer],
                    "source_references": [
                        {"kind": "image", "path": image.relative_path}
                    ],
                }
                for image in images
            },
            "unknown_information": [],
            "claims_not_to_invent": [claim_guard],
        }
        return validate_canonical(
            canonical,
            image_paths=[image.relative_path for image in images],
            raw_line_count=len(raw_text.splitlines()),
        )

    def generate_post(
        self, canonical: Mapping[str, Any], style: str, prompt_text: str
    ) -> dict[str, Any]:
        del prompt_text
        self.generate_calls += 1
        topic = str(canonical["topic"])
        points = [str(item["text"]) for item in canonical["source_supported_points"]]
        images = list(canonical["image_interpretations"])
        is_chinese = bool(re.search(r"[\u3400-\u9fff]", topic))
        if style == "personal":
            title = topic
            body = "\n\n".join(points)
            tags = ["个人记录" if is_chinese else "personal record"]
        elif style == "knowledge":
            title = f"{topic}｜信息整理" if is_chinese else f"{topic} | organized notes"
            heading = "核心信息" if is_chinese else "Key information"
            body = heading + "\n" + "\n".join(f"• {point}" for point in points)
            tags = ["知识分享", "信息整理"] if is_chinese else ["knowledge", "notes"]
        elif style == "concise":
            title = f"{topic}｜简记" if is_chinese else f"{topic} | brief"
            body = " / ".join(points[:3])
            tags = ["简记" if is_chinese else "brief"]
        else:
            raise ProviderError(f"unsupported style: {style}")
        return {
            "schema_version": 1,
            "style": style,
            "title": title,
            "body": body,
            "tags": tags,
            "images": images,
        }

    def edit_post(
        self, post: Mapping[str, Any], findings: Sequence[str], prompt_text: str
    ) -> dict[str, Any]:
        del prompt_text
        self.edit_calls += 1
        replacements: list[dict[str, str]] = []
        for finding in findings:
            for phrase in (
                "值得一提的是",
                "首先",
                "其次",
                "最后",
                "总的来说",
                "综上所述",
                "希望对你有所帮助",
            ):
                if phrase in finding:
                    for field in ("title", "body"):
                        if str(post[field]).count(phrase) == 1:
                            replacements.append(
                                {"field": field, "find": phrase, "replace": ""}
                            )
        return {"replacements": replacements}
