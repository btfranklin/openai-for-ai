from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(slots=True, frozen=True)
class BlockRef:
    block_id: str
    url: str
    tag: str


@dataclass(slots=True)
class OperationBlock:
    block_id: str
    tag: str
    method: str
    path: str
    operation_id: str | None
    summary: str | None
    description: str | None
    parameters: list[dict[str, Any]]
    request_bodies: list[dict[str, Any]]
    responses: list[dict[str, Any]]
    examples: dict[str, str]
    models_in: list[str]
    models_out: list[str]
    sha: str
    output_path: Path

    def to_front_matter(self) -> str:
        models_in = ", ".join(self.models_in) if self.models_in else "(none)"
        models_out = ", ".join(self.models_out) if self.models_out else "(none)"
        return (
            "<!--\n"
            f"block_id: {self.block_id}\n"
            f"operationId: {self.operation_id or '(none)'}\n"
            f"method: {self.method}\n"
            f"path: {self.path}\n"
            f"tag: {self.tag}\n"
            f"models_in: {models_in}\n"
            f"models_out: {models_out}\n"
            "-->\n"
        )


@dataclass(slots=True)
class SchemaBlock:
    name: str
    description: str | None
    properties: list[dict[str, Any]]
    any_of: list[dict[str, Any]] = field(default_factory=list)
    one_of: list[dict[str, Any]] = field(default_factory=list)
    all_of: list[dict[str, Any]] = field(default_factory=list)
    examples: list[Any] = field(default_factory=list)
    sha: str = ""
    output_path: Path | None = None

    def to_metadata_comment(self) -> str:
        return f"<!-- block_type:schema name:{self.name} sha:{self.sha} -->\n"


def ensure_list(value: Iterable[Any] | None) -> list[Any]:
    if not value:
        return []
    if isinstance(value, list):
        return value
    return list(value)
