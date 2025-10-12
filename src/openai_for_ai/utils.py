from __future__ import annotations

import re
from typing import Any, Iterable

from markupsafe import Markup, escape


_PATH_SLUG_RE = re.compile(r"[^A-Za-z0-9\-_{}]+")
_DASH_RE = re.compile(r"-{2,}")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


def normalize_path_to_slug(path: str) -> str:
    slug = path.lstrip("/")
    slug = slug.replace("/", "-")
    slug = _PATH_SLUG_RE.sub("-", slug)
    slug = _DASH_RE.sub("-", slug)
    return slug.strip("-")


def collect_parameters(*sources: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Merge parameter definitions, preserving order and removing duplicates by (name, in)."""
    seen: set[tuple[str, str]] = set()
    merged: list[dict[str, Any]] = []
    for params in sources:
        if not params:
            continue
        for param in params:
            name = param.get("name")
            loc = param.get("in")
            if not name or not loc:
                continue
            key = (name, loc)
            if key in seen:
                continue
            seen.add(key)
            merged.append(param)
    return merged


def extract_ref_name(ref: str | None, prefix: str = "#/components/schemas/") -> str | None:
    if not ref:
        return None
    if ref.startswith(prefix):
        return ref.split("/")[-1]
    return None


def extract_models(
    request_body: dict[str, Any] | None,
    responses: dict[str, Any] | None,
) -> tuple[list[str], list[str]]:
    models_in: set[str] = set()
    models_out: set[str] = set()

    if request_body and "content" in request_body:
        for content_info in request_body["content"].values():
            schema = content_info.get("schema") if isinstance(content_info, dict) else None
            if not schema:
                continue
            if ref := extract_ref_name(schema.get("$ref")):
                models_in.add(ref)

    if responses:
        for resp in responses.values():
            contents = resp.get("content") if isinstance(resp, dict) else None
            if not contents:
                continue
            for content_info in contents.values():
                schema = content_info.get("schema") if isinstance(content_info, dict) else None
                if not schema:
                    continue
                if ref := extract_ref_name(schema.get("$ref")):
                    models_out.add(ref)

    return sorted(models_in), sorted(models_out)


def ensure_trailing_slash(path: str) -> str:
    return path if path.endswith("/") else f"{path}/"


def markdown_links_to_html(text: str | None) -> Markup:
    """Convert inline Markdown links to HTML anchor tags while escaping other content."""

    if not text:
        return Markup("")

    parts: list[Markup] = []
    last_index = 0

    for match in _MARKDOWN_LINK_RE.finditer(text):
        start, end = match.span()
        if start > last_index:
            parts.append(escape(text[last_index:start]))

        label = escape(match.group(1))
        url = escape(match.group(2))
        parts.append(Markup(f'<a href="{url}">{label}</a>'))
        last_index = end

    if last_index < len(text):
        parts.append(escape(text[last_index:]))

    return Markup("").join(parts)
