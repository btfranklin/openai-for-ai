from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import OperationBlock, SchemaBlock
from .utils import collect_parameters, extract_models, extract_ref_name, normalize_path_to_slug

VALID_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


@dataclass(slots=True)
class OperationParseResult:
    by_tag: dict[str, list[OperationBlock]]
    all_operations: list[OperationBlock]


def parse_operations(
    spec: dict[str, Any],
    *,
    sha: str,
    out_dir: Path,
) -> OperationParseResult:
    by_tag: dict[str, list[OperationBlock]] = {}
    all_ops: list[OperationBlock] = []

    paths = spec.get("paths", {}) or {}
    for path, path_item in sorted(paths.items()):
        if not isinstance(path_item, dict):
            continue
        path_params = path_item.get("parameters")
        for method, operation in path_item.items():
            method_upper = method.upper()
            if method_upper not in VALID_METHODS:
                continue
            if not isinstance(operation, dict):
                continue
            tags = operation.get("tags") or ["untagged"]
            tag = str(tags[0])
            op_id = operation.get("operationId")
            block_id = build_block_id(tag, op_id, method_upper, path)
            page_name = f"{method_upper}-{normalize_path_to_slug(path)}.html"
            tag_dir = out_dir / tag
            output_path = tag_dir / page_name

            parameters = collect_parameters(path_params, operation.get("parameters"))
            normalized_params = [normalize_parameter(p) for p in parameters]
            request_body = operation.get("requestBody")
            normalized_bodies = normalize_request_bodies(request_body)

            responses = operation.get("responses") or {}
            normalized_responses = normalize_responses(responses)

            models_in, models_out = extract_models(request_body, responses)

            examples = extract_examples(operation)

            block = OperationBlock(
                block_id=block_id,
                tag=tag,
                method=method_upper,
                path=path,
                operation_id=op_id,
                summary=operation.get("summary"),
                description=operation.get("description"),
                parameters=normalized_params,
                request_bodies=normalized_bodies,
                responses=normalized_responses,
                models_in=models_in,
                models_out=models_out,
                examples=examples,
                sha=sha,
                output_path=output_path,
            )
            by_tag.setdefault(tag, []).append(block)
            all_ops.append(block)

    for ops in by_tag.values():
        ops.sort(key=lambda b: (b.path, b.method))

    all_ops.sort(key=lambda b: (b.tag, b.path, b.method))
    return OperationParseResult(by_tag=by_tag, all_operations=all_ops)


def normalize_parameter(raw: dict[str, Any]) -> dict[str, Any]:
    schema = raw.get("schema") if isinstance(raw, dict) else None
    param_type = schema.get("type") if isinstance(schema, dict) else None
    param_format = schema.get("format") if isinstance(schema, dict) else None
    enum_values = schema.get("enum") if isinstance(schema, dict) else None

    return {
        "name": raw.get("name"),
        "in": raw.get("in"),
        "required": bool(raw.get("required", False)),
        "description": raw.get("description"),
        "schema": schema or {},
        "type": build_type_label(param_type, param_format),
        "enum": enum_values or [],
        "deprecated": bool(raw.get("deprecated", False)),
    }


def normalize_request_bodies(request_body: dict[str, Any] | None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not request_body:
        return results

    content = request_body.get("content") or {}
    for content_type, info in content.items():
        schema = info.get("schema") if isinstance(info, dict) else None
        ref_name = extract_ref_name(schema.get("$ref")) if schema else None
        description = None
        if isinstance(info, dict):
            description = info.get("description")
        if not description and isinstance(schema, dict):
            description = schema.get("description")
        results.append(
            {
                "content_type": content_type,
                "schema": schema or {},
                "schema_ref": ref_name,
                "description": description,
                "examples": collect_examples(info),
            }
        )
    return results


def normalize_responses(responses: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for status, payload in sorted(responses.items(), key=lambda item: status_order_key(item[0])):
        if not isinstance(payload, dict):
            payload = {}
        description = payload.get("description")
        content = payload.get("content") or {}
        normalized_content: list[dict[str, Any]] = []
        for content_type, info in content.items():
            schema = info.get("schema") if isinstance(info, dict) else None
            ref_name = extract_ref_name(schema.get("$ref")) if schema else None
            normalized_content.append(
                {
                    "content_type": content_type,
                    "schema": schema or {},
                    "schema_ref": ref_name,
                    "examples": collect_examples(info),
                }
            )
        normalized.append(
            {
                "status": status,
                "description": description,
                "content": normalized_content,
            }
        )
    return normalized


def collect_examples(info: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not info:
        return []

    examples: list[dict[str, Any]] = []
    if example := info.get("example"):
        examples.append({"label": "default", "value": example})

    info_examples = info.get("examples")
    if isinstance(info_examples, dict):
        for label, example_info in info_examples.items():
            if isinstance(example_info, dict):
                value = example_info.get("value")
            else:
                value = example_info
            if value is not None:
                examples.append({"label": label, "value": value})
    return examples


def build_type_label(type_value: str | None, format_value: str | None) -> str | None:
    if not type_value:
        return None
    if format_value:
        return f"{type_value} ({format_value})"
    return type_value


def build_block_id(tag: str, operation_id: str | None, method: str, path: str) -> str:
    if operation_id:
        stem = operation_id.replace(" ", "_")
    else:
        normalized_path = path.strip("/").replace("/", "_") or "root"
        stem = f"{method.lower()}_{normalized_path}"
    return f"{tag.lower()}.{stem}"


def status_order_key(status: str) -> tuple[int, str]:
    if status == "default":
        return (999, status)
    try:
        code = int(status)
    except ValueError:
        return (998, status)
    return (code, status)


def parse_schemas(
    spec: dict[str, Any],
    *,
    sha: str,
    out_dir: Path,
) -> list[SchemaBlock]:
    schemas = spec.get("components", {}).get("schemas") or {}
    results: list[SchemaBlock] = []

    for name, schema in sorted(schemas.items()):
        if not isinstance(schema, dict):
            continue
        block = SchemaBlock(
            name=name,
            description=schema.get("description"),
            properties=normalize_properties(schema.get("properties"), schema.get("required")),
            any_of=normalize_variants(schema.get("anyOf")),
            one_of=normalize_variants(schema.get("oneOf")),
            all_of=normalize_variants(schema.get("allOf")),
            examples=extract_schema_examples(schema),
            sha=sha,
            output_path=out_dir / "components" / "schemas" / f"{name}.html",
        )
        results.append(block)

    return results


def normalize_properties(
    props: dict[str, Any] | None,
    required: Iterable[str] | None,
) -> list[dict[str, Any]]:
    if not props:
        return []
    required_set = set(required or [])
    normalized: list[dict[str, Any]] = []
    for name, schema in sorted(props.items()):
        ref_name = extract_ref_name(schema.get("$ref")) if isinstance(schema, dict) else None
        entry = {
            "name": name,
            "description": schema.get("description") if isinstance(schema, dict) else None,
            "type": build_type_label(schema.get("type"), schema.get("format")) if isinstance(schema, dict) else None,
            "required": name in required_set,
            "enum": schema.get("enum") if isinstance(schema, dict) else None,
            "schema_ref": ref_name,
            "schema": schema,
        }
        normalized.append(entry)
    return normalized


def extract_schema_examples(schema: dict[str, Any] | None) -> list[Any]:
    if not schema:
        return []
    examples = schema.get("examples")
    if isinstance(examples, list):
        return examples
    example = schema.get("example")
    if example is not None:
        return [example]
    return []


def extract_examples(operation: dict[str, Any]) -> dict[str, str]:
    examples: dict[str, str] = {}

    x_meta = operation.get("x-oaiMeta")
    if isinstance(x_meta, dict):
        x_examples = x_meta.get("examples")
        if isinstance(x_examples, dict):
            for lang, code in x_examples.items():
                if isinstance(code, str):
                    examples[lang] = code

    example_section = operation.get("x-examples")
    if isinstance(example_section, dict):
        for lang, code in example_section.items():
            if isinstance(code, str):
                examples.setdefault(lang, code)

    return dict(sorted(examples.items()))


def normalize_variants(variants: Any) -> list[dict[str, Any]]:
    if not variants:
        return []
    normalized: list[dict[str, Any]] = []
    for entry in variants:
        if not isinstance(entry, dict):
            normalized.append({"schema": entry})
            continue
        ref_name = extract_ref_name(entry.get("$ref"))
        if ref_name:
            normalized.append({"schema_ref": ref_name})
            continue
        normalized.append(
            {
                "schema": entry,
                "title": entry.get("title"),
                "description": entry.get("description"),
                "type": entry.get("type"),
                "any_of": normalize_variants(entry.get("anyOf")),
                "one_of": normalize_variants(entry.get("oneOf")),
                "all_of": normalize_variants(entry.get("allOf")),
            }
        )
    return normalized
