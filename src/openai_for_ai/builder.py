from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import SchemaBlock
from .parser import OperationParseResult, parse_operations, parse_schemas
from .renderers import render_index, render_operation, render_schema
from .spec import DEFAULT_SPEC_URL, load_spec


@dataclass(slots=True)
class BuildConfig:
    spec_url: str = DEFAULT_SPEC_URL
    out_dir: Path = Path("site")
    languages: list[str] = field(default_factory=lambda: ["curl", "python"])
    max_tokens: int = 1500

    def resolved_out_dir(self) -> Path:
        return self.out_dir.expanduser().resolve()


def build(config: BuildConfig) -> dict[str, Any]:
    out_dir = config.resolved_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    spec, sha = load_spec(config.spec_url)
    operations = parse_operations(spec, sha=sha, out_dir=out_dir)
    schemas = parse_schemas(spec, sha=sha, out_dir=out_dir)

    build_date = datetime.now(timezone.utc)

    schema_paths = {
        schema.name: schema.output_path
        for schema in schemas
        if schema.output_path is not None
    }

    _write_operations(
        out_dir,
        operations,
        schema_paths,
        sha,
        build_date,
        config.languages,
    )
    _write_schemas(out_dir, schemas, schema_paths, sha, build_date)
    _write_indexes(out_dir, operations, schema_paths, sha, build_date)

    return {
        "out_dir": out_dir,
        "spec_sha": sha,
        "build_date": build_date,
        "block_count": len(operations.all_operations),
        "schema_count": len(schemas),
    }


def _write_operations(
    out_dir: Path,
    operations: OperationParseResult,
    schema_paths: dict[str, Path],
    sha: str,
    build_date: datetime,
    languages: list[str],
) -> None:
    for tag, ops in operations.by_tag.items():
        tag_dir = out_dir / tag
        tag_dir.mkdir(parents=True, exist_ok=True)
        for block in ops:
            html = render_operation(
                block,
                schema_paths=schema_paths,
                siblings=operations.by_tag[tag],
                build_sha=sha,
                build_date=build_date,
                languages=languages,
            )
            block.output_path.write_text(html, encoding="utf-8")


def _write_schemas(
    out_dir: Path,
    schemas: list[SchemaBlock],
    schema_paths: dict[str, Path],
    sha: str,
    build_date: datetime,
) -> None:
    if not schemas:
        return
    for schema in schemas:
        if schema.output_path is None:
            continue
        schema.output_path.parent.mkdir(parents=True, exist_ok=True)
        html = render_schema(
            schema,
            schema_paths=schema_paths,
            build_sha=sha,
            build_date=build_date,
        )
        schema.output_path.write_text(html, encoding="utf-8")


def _write_indexes(
    out_dir: Path,
    operations: OperationParseResult,
    schema_paths: dict[str, Path],
    sha: str,
    build_date: datetime,
) -> None:
    index_html = render_index(operations.by_tag, out_dir=out_dir)
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")

    llms_txt = _render_llms_index(operations)
    (out_dir / "llms.txt").write_text(llms_txt, encoding="utf-8")

    manifest = _build_manifest(operations)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    blocks_dir = out_dir / "blocks"
    blocks_dir.mkdir(parents=True, exist_ok=True)
    blocks_json = _build_blocks_index(operations, sha, build_date)
    (blocks_dir / "index.json").write_text(
        json.dumps(blocks_json, indent=2),
        encoding="utf-8",
    )

    sitemap = _build_sitemap(operations, schema_paths)
    (out_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")


def _render_llms_index(operations: OperationParseResult) -> str:
    lines = [
        "# OpenAI API Endpoint Blocks",
        "",
        "> Deterministic HTML blocks extracted from the official OpenAI "
        "OpenAPI specification.",
        "",
        "This site publishes machine-friendly slices of the OpenAI API "
        "reference. Each block keeps token counts low, uses predictable "
        "markup, and links back to related operations and schemas for agent "
        "workflows.",
        "",
        "## Essential Entry Points",
        "",
        "- [Overview](/index.html): Tag-organised landing page",
        "- [Manifest](/manifest.json): Operation lookup map (operationId "
        "→ URL)",
        "- [Block Catalog](/blocks/index.json): JSON index of every operation "
        "block",
        "- [Sitemap](/sitemap.xml): URL manifest for crawlers",
        "",
        "## Tags",
        "",
    ]

    for tag in sorted(operations.by_tag.keys()):
        ops = operations.by_tag[tag]
        if not ops:
            continue
        primary = ops[0]
        summary = primary.summary or "First available operation"
        lines.append(
            f"- **{tag}** — {len(ops)} operations. Start with "
            f"[{primary.method} {primary.path}]"
            f"(/{primary.tag}/{primary.output_path.name}): {summary}"
        )

    lines.extend([
        "",
        "## OPTIONAL",
        "",
    ])

    for op in operations.all_operations:
        descriptor = (op.summary or op.description or "").strip()
        descriptor_text = f" — {descriptor}" if descriptor else ""
        lines.append(
            f"- [{op.block_id}](/{op.tag}/{op.output_path.name}): "
            f"{op.method} {op.path}{descriptor_text}"
        )

    return "\n".join(lines)


def _build_manifest(operations: OperationParseResult) -> dict[str, Any]:
    manifest: dict[str, Any] = {}
    for op in operations.all_operations:
        key = op.operation_id or op.block_id
        manifest[key] = {
            "url": f"/{op.tag}/{op.output_path.name}",
            "method": op.method,
            "path": op.path,
            "tag": op.tag,
            "returns": op.models_out,
        }
    return manifest


def _build_blocks_index(
    operations: OperationParseResult,
    sha: str,
    build_date: datetime,
) -> dict[str, Any]:
    blocks = []
    for op in operations.all_operations:
        blocks.append(
            {
                "block_id": op.block_id,
                "tag": op.tag,
                "method": op.method,
                "path": op.path,
                "operation_id": op.operation_id,
                "summary": op.summary,
                "description": op.description,
                "url": f"/{op.tag}/{op.output_path.name}",
                "models_in": op.models_in,
                "models_out": op.models_out,
                "parameters": op.parameters,
            }
        )
    return {
        "version": 1,
        "spec_sha": sha,
        "generated_at": build_date.isoformat(),
        "blocks": blocks,
    }


def _build_sitemap(
    operations: OperationParseResult,
    schema_paths: dict[str, Path],
) -> str:
    urls = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    urls.append("<url><loc>/index.html</loc></url>")
    urls.append("<url><loc>/llms.txt</loc></url>")
    for op in operations.all_operations:
        urls.append(
            f"<url><loc>/{op.tag}/{op.output_path.name}</loc></url>"
        )
    for name in sorted(schema_paths.keys()):
        urls.append(
            f"<url><loc>/components/schemas/{name}.html</loc></url>"
        )
    urls.append("</urlset>")
    return "\n".join(urls)
