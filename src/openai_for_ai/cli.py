from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from .builder import BuildConfig, build
from .spec import DEFAULT_SPEC_URL, SpecLoadError


@click.group(
    help=(
        "Tools for compiling the OpenAI OpenAPI spec into LLM-friendly "
        "blocks."
    )
)
def cli() -> None:
    pass


@cli.command(
    "build",
    help="Fetch the OpenAI OpenAPI spec and render HTML blocks.",
)
@click.option(
    "--spec-url",
    type=str,
    default=DEFAULT_SPEC_URL,
    show_default=True,
    help="URL of the OpenAPI YAML document.",
)
@click.option(
    "--out",
    "out_dir",
    type=click.Path(path_type=Path),
    default=Path("site"),
    show_default=True,
    help="Output directory for generated files.",
)
@click.option(
    "--lang",
    "languages",
    multiple=True,
    default=("curl", "python"),
    show_default=True,
    help="Language examples to include (can be passed multiple times).",
)
@click.option(
    "--max-tokens",
    type=int,
    default=1500,
    show_default=True,
    help=(
        "Target maximum number of tokens per block (used for future "
        "truncation logic)."
    ),
)
def build_command(
    spec_url: str,
    out_dir: Path,
    languages: tuple[str, ...],
    max_tokens: int,
) -> None:
    config = BuildConfig(
        spec_url=spec_url,
        out_dir=out_dir,
        languages=list(languages) if languages else ["curl", "python"],
        max_tokens=max_tokens,
    )
    click.echo(f"Building blocks into {config.out_dir} ...")
    try:
        result = build(config)
    except SpecLoadError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(
        f"Generated {result['block_count']} blocks and "
        f"{result['schema_count']} schemas "
        f"(spec sha {result['spec_sha']})"
    )


def main(argv: Optional[list[str]] = None) -> None:
    cli.main(args=argv, prog_name="openai-for-ai")
