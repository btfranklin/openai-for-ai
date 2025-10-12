# Repository Guidelines

## Agent Operating Rules
- Never perform git write operations (commits, branches, tags, pushes, or pull requests); limit git usage to read-only commands such as `git status`, `git diff`, and `git log`.
- Before marking any task complete, update or add unit tests as needed and revise `README.md` whenever behavior or instructions change.

## Project Structure & Module Organization
- `src/openai_for_ai/` contains the CLI entry point (`cli.py`), spec ingestion (`spec.py`), parser/renderer modules, and Jinja `templates/` used for HTML output.
- `tests/` hosts unit suites (`test_parser.py`, `test_utils.py`) plus the end-to-end pipeline check (`test_builder_integration.py`) that reads fixtures from `tests/data/`.
- `site/` stores generated artifacts; regenerate rather than editing by hand, and use a throwaway directory when experimenting.
- Manage dependencies through `pdm`; avoid editing `pyproject.toml` or `pdm.lock` by hand.

## Build, Test & Development Commands
- `pdm install` provisions the Python 3.12 environment with runtime and test extras.
- `pdm run openai-for-ai build --spec-url https://app.stainless.com/api/spec/documented/openai/openapi.documented.yml --out site/` fetches the spec and regenerates blocks, indexes, and manifests; append `--help` to inspect options such as `--lang javascript`.
- `pdm run pytest` runs the suite; narrow scope while iterating with `pdm run pytest tests/test_parser.py -k Schema`.

## Coding Style & Naming Conventions
- Follow idiomatic Python 3.12: four-space indentation, type hints, dataclasses where structure matters (`builder.py`, `models.py` are references).
- Keep modules snake_case, exported callables as descriptive verbs (`render_index`, `parse_operations`), and constants upper snake case.
- Limit side effects to the CLI layer, and keep template folders aligned with the tag-based layout produced in `site/`.

## Testing Guidelines
- Tests run with `pytest`; name files and functions `test_*` for auto-discovery.
- Integration coverage lives in `tests/test_builder_integration.py`, which exercises the bundled spec at `tests/data/openai.documented.yml`; refresh fixtures when the upstream schema changes.
- New parsers or renderers should ship with unit coverage plus at least one builder invocation, storing any extra fixtures in `tests/data/`.

## Security & Configuration Tips
- The builder fetches remote specs over HTTPS; pin `--spec-url` to trusted sources and prefer the bundled fixture for deterministic CI runs.
- Never commit secrets or authorization headers—the tool operates on public endpoints only.
- For experiments, redirect output with `pdm run openai-for-ai build --out tmp/site-preview` to avoid clobbering `site/`.
