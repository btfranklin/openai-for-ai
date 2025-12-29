from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import hashlib
import httpx
import yaml

DEFAULT_SPEC_URL = (
    "https://app.stainless.com/api/spec/documented/openai/"
    "openapi.documented.yml"
)


class SpecLoadError(RuntimeError):
    """Raised when the OpenAPI specification cannot be loaded or parsed."""


def load_spec(
    spec_url: str | Path | None = None,
    *,
    cache_dir: Path | None = None,
    timeout: float = 30.0,
) -> tuple[dict[str, Any], str]:
    """Fetch the OpenAPI spec, optionally using an on-disk cache.

    Returns a tuple of (parsed_spec, sha).
    """
    spec_url = spec_url or DEFAULT_SPEC_URL
    if isinstance(spec_url, Path):
        return _load_local_spec(spec_url)

    parsed = urlparse(spec_url)
    if parsed.scheme in ("", "file"):
        local_path = Path(parsed.path if parsed.scheme else spec_url)
        return _load_local_spec(local_path)

    cache_dir = cache_dir or Path(".cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    spec_path = cache_dir / "openapi.yml"
    etag_path = cache_dir / "openapi.etag"

    headers: dict[str, str] = {}
    if etag_path.exists():
        etag_value = etag_path.read_text(encoding="utf-8").strip()
        if etag_value:
            headers["If-None-Match"] = etag_value

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(spec_url, headers=headers)

            if response.status_code == httpx.codes.NOT_MODIFIED:
                if spec_path.exists():
                    raw_text = spec_path.read_text(encoding="utf-8")
                else:
                    response = client.get(spec_url)
                    response.raise_for_status()
                    raw_text = response.text
                    spec_path.write_text(raw_text, encoding="utf-8")
                    if etag := response.headers.get("ETag"):
                        etag_path.write_text(etag, encoding="utf-8")
            else:
                response.raise_for_status()
                raw_text = response.text
                spec_path.write_text(raw_text, encoding="utf-8")
                if etag := response.headers.get("ETag"):
                    etag_path.write_text(etag, encoding="utf-8")
    except (httpx.HTTPError, OSError) as exc:
        raise SpecLoadError(
            f"Failed to fetch spec from {spec_url}"
        ) from exc

    try:
        parsed = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise SpecLoadError("Spec is not valid YAML") from exc

    if not isinstance(parsed, dict):
        raise SpecLoadError("Spec root document must be a mapping")

    version = str(parsed.get("openapi", ""))
    if not version.startswith("3.1"):
        raise SpecLoadError(
            f"Unsupported OpenAPI version '{version}'. Expected 3.1.x."
        )

    sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:12]

    return parsed, sha


def _load_local_spec(path: Path) -> tuple[dict[str, Any], str]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecLoadError(
            f"Failed to read local spec at {path}"
        ) from exc

    try:
        parsed = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise SpecLoadError(
            f"Spec at {path} is not valid YAML"
        ) from exc

    if not isinstance(parsed, dict):
        raise SpecLoadError(
            f"Spec at {path} root document must be a mapping"
        )

    version = str(parsed.get("openapi", ""))
    if not version.startswith("3.1"):
        raise SpecLoadError(
            f"Unsupported OpenAPI version '{version}'. Expected 3.1.x."
        )

    sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:12]
    return parsed, sha
