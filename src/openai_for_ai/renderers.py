from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import OperationBlock, SchemaBlock
from .utils import markdown_links_to_html

_ENV: Environment | None = None


def _environment() -> Environment:
    global _ENV
    if _ENV is None:
        template_dir = Path(__file__).resolve().parent / "templates"
        _ENV = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        _ENV.filters["jsonify"] = _jsonify
        _ENV.filters["markdown_links"] = markdown_links_to_html
    return _ENV


def _jsonify(value: Any) -> str:
    try:
        return json.dumps(value, indent=2, ensure_ascii=True)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=True)


def render_operation(
    block: OperationBlock,
    *,
    schema_paths: dict[str, Path],
    siblings: list[OperationBlock],
    build_sha: str,
    build_date: datetime,
    languages: list[str],
) -> str:
    env = _environment()
    template = env.get_template("operation.html.j2")

    parameter_groups = build_parameter_groups(block)
    request_bodies = annotate_schema_hrefs(
        block.request_bodies,
        block.output_path,
        schema_paths,
    )
    responses = annotate_responses(block, schema_paths)
    filtered_examples = {
        lang: code
        for lang, code in block.examples.items()
        if lang in languages
    }

    sibling_links = [
        {
            "label": f"{s.method} {s.path}",
            "summary": s.summary,
            "url": relative_url(block.output_path, s.output_path),
        }
        for s in siblings
        if s.block_id != block.block_id
    ]

    component_refs: set[tuple[str, str]] = set()
    for body in request_bodies:
        if body.get("schema_href") and body.get("schema_name"):
            component_refs.add((body["schema_name"], body["schema_href"]))
    for response in responses:
        for content in response["content"]:
            if content.get("schema_href") and content.get("schema_name"):
                component_refs.add(
                    (content["schema_name"], content["schema_href"])
                )

    sorted_components = sorted(
        component_refs,
        key=lambda item: item[0],
    )
    referenced_components = [
        {"label": name, "url": href}
        for name, href in sorted_components
    ]

    context = {
        "block": block,
        "front_matter": block.to_front_matter(),
        "title": f"{block.method} {block.path}",
        "parameter_groups": parameter_groups,
        "request_bodies": request_bodies,
        "responses": responses,
        "examples": filtered_examples,
        "siblings": sibling_links,
        "referenced_components": referenced_components,
        "build_sha": build_sha,
        "build_date": build_date.strftime("%Y-%m-%d"),
    }
    return template.render(**context)


def render_schema(
    schema: SchemaBlock,
    *,
    schema_paths: dict[str, Path],
    build_sha: str,
    build_date: datetime,
) -> str:
    env = _environment()
    template = env.get_template("schema.html.j2")

    properties = annotate_schema_properties(schema, schema_paths)
    any_of = annotate_schema_variants(
        schema.any_of,
        schema_paths,
        schema.output_path,
    )
    one_of = annotate_schema_variants(
        schema.one_of,
        schema_paths,
        schema.output_path,
    )
    all_of = annotate_schema_variants(
        schema.all_of,
        schema_paths,
        schema.output_path,
    )

    context = {
        "schema": schema,
        "properties": properties,
        "any_of": any_of,
        "one_of": one_of,
        "all_of": all_of,
        "front_matter": schema.to_metadata_comment(),
        "build_sha": build_sha,
        "build_date": build_date.strftime("%Y-%m-%d"),
    }
    return template.render(**context)


def render_index(
    operations_by_tag: dict[str, list[OperationBlock]],
    *,
    out_dir: Path,
    build_date: datetime,
) -> str:
    env = _environment()
    template = env.get_template("index.html.j2")
    tags = []
    for tag, ops in sorted(operations_by_tag.items()):
        tags.append(
            {
                "tag": tag,
                "operations": [
                    {
                        "label": f"{op.method} {op.path}",
                        "summary": op.summary,
                        "url": relative_url(
                            out_dir / "index.html",
                            op.output_path,
                        ),
                    }
                    for op in ops
                ],
            }
        )
    return template.render(tags=tags, build_time=build_date)


def relative_url(from_path: Path, to_path: Path) -> str:
    import os

    rel = os.path.relpath(to_path, start=from_path.parent)
    return rel.replace("\\", "/")


def annotate_schema_hrefs(
    bodies: list[dict[str, Any]],
    from_path: Path,
    schema_paths: dict[str, Path],
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for body in bodies:
        schema_href = None
        schema_name = body.get("schema_ref")
        if ref_name := body.get("schema_ref"):
            target = schema_paths.get(ref_name)
            if target:
                schema_href = relative_url(from_path, target)

        annotated.append(
            {
                **body,
                "schema_href": schema_href,
                "schema_name": schema_name,
            }
        )
    return annotated


def annotate_responses(
    block: OperationBlock,
    schema_paths: dict[str, Path],
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for response in block.responses:
        content_items = []
        for content in response.get("content", []):
            schema_href = None
            schema_name = content.get("schema_ref")
            if ref_name := content.get("schema_ref"):
                target = schema_paths.get(ref_name)
                if target:
                    schema_href = relative_url(block.output_path, target)
            content_items.append(
                {
                    **content,
                    "schema_href": schema_href,
                    "schema_name": schema_name,
                }
            )
        annotated.append({**response, "content": content_items})
    return annotated


def annotate_schema_properties(
    schema: SchemaBlock,
    schema_paths: dict[str, Path],
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for prop in schema.properties:
        schema_href = None
        if ref_name := prop.get("schema_ref"):
            target = schema_paths.get(ref_name)
            if target:
                # schema.output_path may be None during tests; guard for that
                if schema.output_path is not None:
                    schema_href = relative_url(schema.output_path, target)
                else:
                    schema_href = target.name
        annotated.append({**prop, "schema_href": schema_href})
    return annotated


def annotate_schema_variants(
    variants: list[dict[str, Any]],
    schema_paths: dict[str, Path],
    base_path: Path | None,
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for variant in variants:
        schema_href = None
        if ref_name := variant.get("schema_ref"):
            target = schema_paths.get(ref_name)
            if target:
                if base_path is not None:
                    schema_href = relative_url(base_path, target)
                else:
                    schema_href = target.name
        normalized = {**variant, "schema_href": schema_href}
        if variant.get("any_of"):
            normalized["any_of"] = annotate_schema_variants(
                variant["any_of"],
                schema_paths,
                base_path,
            )
        if variant.get("one_of"):
            normalized["one_of"] = annotate_schema_variants(
                variant["one_of"],
                schema_paths,
                base_path,
            )
        if variant.get("all_of"):
            normalized["all_of"] = annotate_schema_variants(
                variant["all_of"],
                schema_paths,
                base_path,
            )
        annotated.append(normalized)
    return annotated


def build_parameter_groups(block: OperationBlock) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    order = [
        ("path", "Path Parameters"),
        ("query", "Query Parameters"),
        ("header", "Header Parameters"),
        ("cookie", "Cookie Parameters"),
    ]
    for location, label in order:
        items = [p for p in block.parameters if p.get("in") == location]
        if not items:
            continue
        groups.append({"label": label, "entries": items})
    return groups
