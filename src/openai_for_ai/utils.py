from __future__ import annotations

import re
from typing import Any, Iterable

from markupsafe import Markup, escape


_PATH_SLUG_RE = re.compile(r"[^A-Za-z0-9\-_{}]+")
_SEGMENT_SLUG_RE = re.compile(r"[^A-Za-z0-9\-_]+")
_DASH_RE = re.compile(r"-{2,}")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


def normalize_path_to_slug(path: str) -> str:
    slug = path.lstrip("/")
    slug = slug.replace("/", "-")
    slug = _PATH_SLUG_RE.sub("-", slug)
    slug = _DASH_RE.sub("-", slug)
    return slug.strip("-")


def sanitize_path_segment(value: str, fallback: str) -> str:
    if not value:
        return fallback
    slug = _SEGMENT_SLUG_RE.sub("-", value.strip())
    slug = _DASH_RE.sub("-", slug)
    slug = slug.strip("-")
    return slug or fallback


def collect_parameters(
    *sources: Iterable[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Merge parameter definitions, preserving order and removing duplicates.

    Deduplication uses (name, in), with later entries overriding earlier ones.
    """
    seen: set[tuple[str, str]] = set()
    index_by_key: dict[tuple[str, str], int] = {}
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
                merged[index_by_key[key]] = param
                continue
            seen.add(key)
            index_by_key[key] = len(merged)
            merged.append(param)
    return merged


def extract_ref_name(
    ref: str | None,
    prefix: str = "#/components/schemas/",
) -> str | None:
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
            schema = (
                content_info.get("schema")
                if isinstance(content_info, dict)
                else None
            )
            if not schema:
                continue
            _collect_schema_refs(schema, models_in)

    if responses:
        for resp in responses.values():
            contents = (
                resp.get("content")
                if isinstance(resp, dict)
                else None
            )
            if not contents:
                continue
            for content_info in contents.values():
                schema = (
                    content_info.get("schema")
                    if isinstance(content_info, dict)
                    else None
                )
                if not schema:
                    continue
                _collect_schema_refs(schema, models_out)

    return sorted(models_in), sorted(models_out)


def _collect_schema_refs(
    schema: Any,
    refs: set[str],
    *,
    prefix: str = "#/components/schemas/",
    seen: set[int] | None = None,
) -> None:
    if schema is None:
        return
    if seen is None:
        seen = set()

    if isinstance(schema, dict):
        obj_id = id(schema)
        if obj_id in seen:
            return
        seen.add(obj_id)

        ref_value = schema.get("$ref")
        if isinstance(ref_value, str):
            if ref_name := extract_ref_name(ref_value, prefix=prefix):
                refs.add(ref_name)

        for value in schema.values():
            _collect_schema_refs(value, refs, prefix=prefix, seen=seen)
        return

    if isinstance(schema, list):
        obj_id = id(schema)
        if obj_id in seen:
            return
        seen.add(obj_id)
        for item in schema:
            _collect_schema_refs(item, refs, prefix=prefix, seen=seen)


def ensure_trailing_slash(path: str) -> str:
    return path if path.endswith("/") else f"{path}/"


def markdown_links_to_html(text: str | None) -> Markup:
    """Convert inline Markdown links while escaping the rest."""

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
