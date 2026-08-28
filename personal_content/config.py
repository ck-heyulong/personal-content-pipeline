"""Environment-backed runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


DEFAULT_PROVIDER_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_PROVIDER_MODEL = "deepseek-v4-flash-vision-exp"
DEFAULT_SAU_HOME = r"%USERPROFILE%\tools\social-auto-upload"
DEFAULT_WINDOWS_STAGING_ROOT = r"C:\Users\Public\personal-content-staging"


@dataclass(frozen=True)
class Settings:
    provider: str
    provider_url: str
    provider_model: str
    provider_api_key: str | None
    provider_timeout: float
    sau_home: str
    sau_account: str
    windows_staging_root: str
    powershell: str

    @classmethod
    def from_environment(cls) -> "Settings":
        timeout_text = os.environ.get("CONTENT_PROVIDER_TIMEOUT", "60")
        try:
            timeout = float(timeout_text)
        except ValueError as exc:
            raise ValueError("CONTENT_PROVIDER_TIMEOUT must be a positive number") from exc
        if timeout <= 0:
            raise ValueError("CONTENT_PROVIDER_TIMEOUT must be a positive number")
        provider = os.environ.get("CONTENT_PROVIDER", "live")
        if provider not in {"live", "fake"}:
            raise ValueError("CONTENT_PROVIDER must be 'live' or 'fake'")
        return cls(
            provider=provider,
            provider_url=os.environ.get("CONTENT_PROVIDER_URL", DEFAULT_PROVIDER_URL),
            provider_model=os.environ.get("CONTENT_PROVIDER_MODEL", DEFAULT_PROVIDER_MODEL),
            provider_api_key=os.environ.get("CONTENT_PROVIDER_API_KEY") or None,
            provider_timeout=timeout,
            sau_home=os.environ.get("CONTENT_SAU_HOME", DEFAULT_SAU_HOME),
            sau_account=os.environ.get("CONTENT_SAU_ACCOUNT", "main"),
            windows_staging_root=os.environ.get(
                "CONTENT_WINDOWS_STAGING_ROOT", DEFAULT_WINDOWS_STAGING_ROOT
            ),
            powershell=os.environ.get("CONTENT_POWERSHELL", "powershell.exe"),
        )


def repository_root() -> Path:
    return Path(__file__).resolve().parent.parent
